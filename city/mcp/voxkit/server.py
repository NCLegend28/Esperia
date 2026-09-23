"""Esperia voxkit — an MCP server that turns building specs into MagicaVoxel files, glTF and previews.

The grammar (city/kit/GRAMMAR.md) is the contract: an architecture agent writes a spec, this server builds it.
Nothing here talks to MagicaVoxel over a socket — it has no API. The server writes real .vox files that
MagicaVoxel opens, and glTF that the city renderer loads directly, so the pipeline works with or without the GUI.

Run:   uv run esperia-voxkit            (stdio transport, for Claude Desktop / Claude Code / any MCP client)
Env:   ESPERIA_KIT_DIR    where approved specs live            (default: ../../kit relative to this file)
       ESPERIA_BUILD_DIR  where .vox/.gltf/.png are written     (default: ../../build)
       MAGICAVOXEL_APP    app name/path for open_in_magicavoxel (default: "MagicaVoxel")
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .architects import Studio, evolutionary_proposer, features, llm_proposer, novelty
from .gltf import write_gltf
from .grammar import EMISSIVE_SLOTS, MAX_HEIGHT, PART_DOCS, SLOT_DEFAULTS, Division, Project, validate
from .preview import render_preview
from .raster import VOXELS_PER_UNIT, rasterize
from .vox import write_vox

JSON = dict[str, Any]
SpecInput = JSON | str

HERE = Path(__file__).resolve().parent
KIT_DIR = Path(os.environ.get("ESPERIA_KIT_DIR", HERE.parent.parent / "kit")).resolve()
BUILD_DIR = Path(os.environ.get("ESPERIA_BUILD_DIR", HERE.parent.parent / "build")).resolve()
AGENTS_DIR = Path(os.environ.get("ESPERIA_AGENTS_DIR", HERE.parent.parent / "agents")).resolve()
MODEL_URL = os.environ.get("ESPERIA_MODEL_URL")  # OpenAI-compatible, e.g. http://127.0.0.1:11434/v1 for Ollama
MODEL_NAME = os.environ.get("ESPERIA_MODEL", "qwen2.5:7b")
MANIFEST = BUILD_DIR / "manifest.json"

# Block 0 is 13×13 lots, rings from the centre (6,6). These mirror BUILDINGS in the city page.
GRID = 13
MID = 6
NAMED_LOTS: dict[str, list[int]] = {
    "u1": [6, 6],
    "u3": [6, 3],
    "u2": [11, 6],
    "t1": [3, 6],
    "t2": [9, 6],
    "t3": [6, 9],
    "t4": [9, 9],
}
UNPOPULATED: list[list[int]] = [[4, 8], [2, 4], [12, 1]]  # the silkscreened plots; fill these first


def _ring(lot: list[int]) -> str:
    r = max(abs(lot[0] - MID), abs(lot[1] - MID))
    return "centre" if r == 0 else ("residential" if r <= 2 else ("commerce" if r <= 4 else "industrial"))


mcp = FastMCP(
    "esperia-voxkit",
    instructions=(
        "Build Esperia city buildings from kit-of-parts specs. Call `grammar` first to learn the parts and palette "
        "slots, `validate_spec` before building, then `build_building` to get a .vox, a .gltf and a PNG preview. "
        "Specs are JSON: {name, code, palette:{slot:hex}, parts:[{type, ...}]}. Positions are offsets from the lot "
        "centre, y is height above the board, units are board units (a lot is 14 wide). Never emit geometry — emit specs."
    ),
)


def _safe_name(name: str) -> str:
    keep = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in name.strip())
    return keep.strip("-").lower() or "building"


def _read_json(path: Path) -> JSON:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not hold a JSON object")
    return data


def _load_spec(spec: SpecInput) -> tuple[JSON, str | None]:
    """Accept a JSON object, a JSON string, a kit id like "u1", or a path to a .json file.
    Returns (data, id) where id is the kit id or file stem when the spec came from disk."""
    if isinstance(spec, dict):
        return spec, None
    p = Path(spec)
    if p.suffix == ".json" and p.exists():
        return _read_json(p), p.stem
    kit = KIT_DIR / f"{_safe_name(spec)}.json"
    if kit.exists():
        return _read_json(kit), kit.stem
    data = json.loads(spec)
    if not isinstance(data, dict):
        raise ValueError("spec must be a JSON object")
    return data, None


def _name_for(data: JSON, name: str | None, spec_id: str | None) -> str:
    fallback = spec_id or data.get("code") or data.get("name") or "building"
    return _safe_name(name or str(fallback))


def _manifest() -> JSON:
    if MANIFEST.exists():
        try:
            return _read_json(MANIFEST)
        except (OSError, ValueError):
            pass
    return {"version": 1, "buildings": {}}


def _manifest_put(entry_id: str, **fields: Any) -> JSON:
    """Record a built model so the city page can load it. Paths are relative to the city folder."""
    m = _manifest()
    b: JSON = m.setdefault("buildings", {})
    cur: JSON = b.get(entry_id, {})
    cur.update({k: v for k, v in fields.items() if v is not None})
    b[entry_id] = cur
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=2))
    return cur


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(BUILD_DIR.parent))
    except ValueError:
        return str(p)


def _studio() -> Studio:
    return Studio(AGENTS_DIR, KIT_DIR)


@mcp.tool()
def grammar() -> JSON:
    """The building grammar: part types with their fields, palette slots with default colours, units and limits."""
    return {
        "version": "0.1",
        "units": "board units; a lot is 14x14; x,z are offsets from the lot centre; y is height above the board",
        "voxels_per_unit": VOXELS_PER_UNIT,
        "max_height": MAX_HEIGHT,
        "rule": "parts are laid down in order; the first non-plinth part is where the building becomes hideable in cutaway",
        "parts": PART_DOCS,
        "slots": SLOT_DEFAULTS,
        "emissive_slots": sorted(EMISSIVE_SLOTS),
        "example_ids": sorted(p.stem for p in KIT_DIR.glob("*.json")) if KIT_DIR.exists() else [],
        "provenance": "specs may carry architect, lineage (kit ids) and statement; adopt_proposal sets them",
    }


@mcp.tool()
def list_kit() -> list[JSON]:
    """List the approved specs in the kit directory (the versioned city assets)."""
    out: list[JSON] = []
    for p in sorted(KIT_DIR.glob("*.json")):
        try:
            d = _read_json(p)
            out.append(
                {"id": p.stem, "name": d.get("name"), "code": d.get("code"), "parts": len(d.get("parts", [])), "path": str(p)}
            )
        except (OSError, ValueError) as e:
            out.append({"id": p.stem, "error": str(e), "path": str(p)})
    return out


@mcp.tool()
def get_spec(spec_id: str) -> JSON:
    """Read one approved spec from the kit by id (e.g. "u1"). Use it as a starting point for a new design."""
    p = KIT_DIR / f"{_safe_name(spec_id)}.json"
    if not p.exists():
        raise FileNotFoundError(f"no spec '{spec_id}' in {KIT_DIR}")
    return _read_json(p)


@mcp.tool()
def validate_spec(spec: SpecInput) -> JSON:
    """Validate a spec against the grammar. Returns {ok, errors, warnings, summary}. Fix errors before building; warnings are taste."""
    data, _sid = _load_spec(spec)
    s, errors, warnings = validate(data)
    summary: JSON | None = None
    if s:
        summary = {
            "parts": len(s.parts),
            "types": sorted({p.type for p in s.parts}),
            "height": round(s.height(), 1),
            "slots_used": sorted(s.palette),
        }
    return {"ok": not errors, "errors": errors, "warnings": warnings, "summary": summary}


@mcp.tool()
def build_building(
    spec: SpecInput, name: str | None = None, voxels_per_unit: int = VOXELS_PER_UNIT, preview: bool = True
) -> JSON:
    """Build a spec: writes <name>.vox (MagicaVoxel), <name>.gltf (city renderer) and <name>.png (isometric preview)
    under the build dir. Returns the paths, voxel count and model size. `spec` may be a JSON object, a JSON string,
    a kit id like "u1", or a path to a .json file."""
    data, sid = _load_spec(spec)
    s, errors, warnings = validate(data)
    if not s:
        return {"ok": False, "errors": errors, "warnings": warnings}
    nm = _name_for(data, name, sid)
    out = BUILD_DIR / nm
    out.mkdir(parents=True, exist_ok=True)
    r = rasterize(s, voxels_per_unit)
    vox = write_vox(r, out / f"{nm}.vox")
    gltf = write_gltf(r, out / f"{nm}.gltf", name=s.name or nm)
    spec_path = out / f"{nm}.spec.json"
    spec_path.write_text(json.dumps(data, indent=2))
    (out / f"{nm}.{time.strftime('%Y%m%d-%H%M%S')}.spec.json").write_text(json.dumps(data, indent=2))
    result: JSON = {
        "ok": True,
        "name": nm,
        "warnings": warnings,
        "vox": str(vox),
        "gltf": str(gltf),
        "spec": str(spec_path),
        "voxels": r.count(),
        "size": list(r.size),
        "voxels_per_unit": voxels_per_unit,
        "slots": {str(i): {"slot": n, "color": c, "emissive": e} for i, (n, c, e) in r.slots.items()},
    }
    if preview:
        result["png"] = str(render_preview(r, out / f"{nm}.png"))
    _manifest_put(
        nm,
        gltf=_rel(gltf),
        name=data.get("name"),
        code=data.get("code"),
        architect=data.get("architect"),
        lineage=data.get("lineage"),
        divisions=data.get("divisions") or None,
        project=data.get("project"),
        height=round(s.height(), 1),
        built=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )
    result["manifest"] = str(MANIFEST)
    return result


@mcp.tool()
def preview_building(spec: SpecInput, name: str | None = None, cell: int = 6) -> JSON:
    """Render only the isometric PNG preview of a spec (fast; no .vox/.gltf). Returns the path."""
    data, sid = _load_spec(spec)
    s, errors, warnings = validate(data)
    if not s:
        return {"ok": False, "errors": errors, "warnings": warnings}
    nm = _name_for(data, name, sid)
    r = rasterize(s)
    p = render_preview(r, BUILD_DIR / nm / f"{nm}.preview.png", cell=cell)
    return {"ok": True, "png": str(p), "voxels": r.count(), "size": list(r.size), "warnings": warnings}


@mcp.tool()
def approve_spec(spec: SpecInput, spec_id: str, lot: list[int] | None = None, overwrite: bool = False) -> JSON:
    """Save a spec into the kit as an approved city asset — the owner's decision; call this only when told to.
    Also builds it and, if `lot` = [column, row] (0..12 on block 0), places the model on that lot in the city page.
    Refuses to overwrite an existing id unless overwrite=true."""
    data, _sid = _load_spec(spec)
    s, errors, _ = validate(data)
    if not s:
        return {"ok": False, "errors": errors}
    sid = _safe_name(spec_id)
    p = KIT_DIR / f"{sid}.json"
    if p.exists() and not overwrite:
        return {"ok": False, "errors": [f"{p.name} exists; pass overwrite=true to replace it"]}
    KIT_DIR.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2))
    built = build_building(data, name=sid, preview=True)
    placed = place_building(sid, lot) if lot is not None else None
    return {"ok": True, "path": str(p), "built": built, "placed": placed}


def _lot_taken_by(m: JSON, lot: list[int]) -> str | None:
    for nid, nl in NAMED_LOTS.items():
        if nl == lot:
            return nid
    for bid, e in m.get("buildings", {}).items():
        if e.get("lot") == lot:
            return str(bid)
    return None


@mcp.tool()
def place_building(entry_id: str, lot: list[int] | None, force: bool = False) -> JSON:
    """Put a built model on a lot ([column, row], 0..12) in the city page, or take it off the map with lot=null.
    A named building's own lot is fine for its own model; anyone else's lot is refused unless force=true."""
    m = _manifest()
    if entry_id not in m.get("buildings", {}):
        return {"ok": False, "error": f"{entry_id} has not been built; call build_building or approve_spec first"}
    cur = m["buildings"][entry_id]
    if lot is None:
        cur.pop("lot", None)
    else:
        L = [int(lot[0]), int(lot[1])]
        if not (0 <= L[0] < GRID and 0 <= L[1] < GRID):
            return {"ok": False, "error": f"lot {L} is off block 0 (0..{GRID - 1})"}
        owner = _lot_taken_by(m, L)
        if owner and owner != entry_id and not force:
            return {"ok": False, "error": f"lot {L} belongs to {owner}; pick another (see free_lots) or pass force=true"}
        cur["lot"] = L
        cur["ring"] = _ring(L)
    MANIFEST.write_text(json.dumps(m, indent=2))
    return {"ok": True, "entry": cur}


@mcp.tool()
def assign_divisions(entry_id: str, divisions: list[Division], project: Project | None = None) -> JSON:
    """Give a built model its divisions — the owner's call — so the city page builds floors, desks and a roster for it
    and hires agents from the reserve pool (24 at a time; each division takes `offices` of them). One division per floor,
    top to bottom in the order given. Replaces any previous divisions on the entry; the kit spec is updated too if one
    exists under the same id. `project` fills the building's panel (title, stage, backend, budget)."""
    m = _manifest()
    if entry_id not in m.get("buildings", {}):
        return {"ok": False, "error": f"{entry_id} has not been built; call build_building or approve_spec first"}
    if not divisions:
        return {"ok": False, "error": "give at least one division"}
    divs = [d.model_dump() for d in divisions]
    seats = sum(int(d["offices"]) for d in divs)
    fields: dict[str, Any] = {"divisions": divs}
    if project is not None:
        fields["project"] = project.model_dump()
    cur = _manifest_put(entry_id, **fields)
    kit = KIT_DIR / f"{entry_id}.json"
    if kit.exists():
        data = _read_json(kit)
        data.update(fields)
        kit.write_text(json.dumps(data, indent=2))
    warn = [] if seats <= 24 else [f"{seats} offices asked for; the page hires at most 24 across all emergent buildings"]
    return {"ok": True, "entry": cur, "seats": seats, "warnings": warn}


@mcp.tool()
def free_lots(ring: str | None = None) -> JSON:
    """Lots a new building can take: the three unpopulated plots first, then everything not named or placed.
    `ring` filters to residential | commerce | industrial. Returns [column, row] pairs; the city centre is [6, 6]."""
    m = _manifest()
    taken = {tuple(v) for v in NAMED_LOTS.values()} | {tuple(e["lot"]) for e in m.get("buildings", {}).values() if e.get("lot")}
    plots = [p for p in UNPOPULATED if tuple(p) not in taken and (ring is None or _ring(p) == ring)]
    rest: list[list[int]] = []
    for i in range(GRID):
        for j in range(GRID):
            L = [i, j]
            if tuple(L) in taken or L in UNPOPULATED or _ring(L) == "centre":
                continue
            if ring is None or _ring(L) == ring:
                rest.append(L)
    return {"unpopulated_plots": plots, "other": rest[:60], "named": NAMED_LOTS}


@mcp.tool()
def city_manifest() -> JSON:
    """What the city page will load: every built model, its glTF path, and its lot if placed."""
    return _manifest()


# ---------------- the architects ----------------


@mcp.tool()
def architects() -> list[JSON]:
    """The architect population: id, name, manifesto, taste weights, wins, what they've designed and seen."""
    st = _studio()
    return [
        {
            "id": a.id,
            "name": a.name,
            "manifesto": a.manifesto,
            "taste": a.taste,
            "wins": a.wins,
            "rounds": a.rounds,
            "history": a.history[-8:],
            "voice": a.voice(),
        }
        for a in st.architects
    ]


@mcp.tool()
def propose_round(
    brief: str,
    name: str | None = None,
    code: str | None = None,
    neighbours: list[str] | None = None,
    use_model: bool = False,
    novelty_weight: float = 0.6,
) -> JSON:
    """Run one design round: every architect proposes for the brief, the critic ranks by coherence × taste-fit + novelty.
    Returns ranked candidates with previews. Nothing enters the city until `adopt_proposal`. With use_model=true and
    ESPERIA_MODEL_URL set, architects design with a language model; otherwise they evolve the kit (mutation + crossover)."""
    st = _studio()
    b: JSON = {"text": brief, "name": name, "code": code, "neighbours": neighbours or []}
    proposer = None
    if use_model:
        if not MODEL_URL:
            return {"ok": False, "error": "use_model=true but ESPERIA_MODEL_URL is not set (e.g. http://127.0.0.1:11434/v1)"}
        proposer = llm_proposer(MODEL_URL, MODEL_NAME, fallback=evolutionary_proposer)
    rec = st.run_round(b, proposer=proposer, novelty_weight=novelty_weight)
    out_dir = BUILD_DIR / "rounds" / rec["id"]
    for c in rec["candidates"]:
        s, _e, _w = validate(c["spec"])
        if s:
            png = render_preview(rasterize(s), out_dir / f"{c['id']}.png", cell=4)
            c["png"] = str(png)
            c["features"] = {k: round(v, 2) for k, v in features(s).items()}
    return {
        "round": rec["id"],
        "brief": b,
        "model": bool(proposer),
        "candidates": rec["candidates"],
        "architects": rec["architects"],
    }


@mcp.tool()
def adopt_proposal(round_id: str, candidate_id: str, lot: list[int] | None = None, kit_id: str | None = None) -> JSON:
    """The owner picks a winner. Saves it to the kit (auto id a1, a2, …), builds it, places it if `lot` is given,
    and lets the architects drift: the winner sharpens, the others imitate a little. Returns the new kit entry."""
    st = _studio()
    res = st.adopt(round_id, candidate_id, kit_id=kit_id)
    data = _read_json(Path(res["path"]))
    built = build_building(data, name=res["kit_id"], preview=True)
    res["built"] = built
    res["placed"] = place_building(res["kit_id"], lot) if lot is not None else None
    return res


@mcp.tool()
def novelty_of(spec: SpecInput) -> JSON:
    """How unlike the current kit a spec is (0 = a copy, ~0.5 = unlike anything), plus its measured features."""
    data, _sid = _load_spec(spec)
    s, errors, _w = validate(data)
    if not s:
        return {"ok": False, "errors": errors}
    kit_specs = [k for k in (validate(v)[0] for v in _studio().kit().values()) if k is not None]
    return {"ok": True, "novelty": round(novelty(s, kit_specs), 3), "features": {k: round(v, 2) for k, v in features(s).items()}}


@mcp.tool()
def open_in_magicavoxel(path: str) -> JSON:
    """Open a built .vox in MagicaVoxel on this machine (macOS: `open -a`; elsewhere MAGICAVOXEL_APP must be an executable path)."""
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": f"{p} does not exist"}
    app = os.environ.get("MAGICAVOXEL_APP", "MagicaVoxel")
    try:
        args = ["open", "-a", app, str(p)] if platform.system() == "Darwin" else [app, str(p)]
        subprocess.Popen(args)  # noqa: S603 — owner-local tool, paths come from this server's own build dir
    except OSError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "opened": str(p), "app": app}


@mcp.resource("esperia://grammar")
def grammar_resource() -> str:
    """The grammar reference (GRAMMAR.md) when it sits next to the kit; otherwise the tool's JSON summary."""
    p = KIT_DIR / "GRAMMAR.md"
    return p.read_text() if p.exists() else json.dumps(grammar(), indent=2)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
