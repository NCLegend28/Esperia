"""Architecture agents: a small population that designs buildings and drifts.

Emergence here is not a prompt that says "be creative". It is three mechanisms that compound:

1. **Taste.** Each architect carries a weight vector over measurable features (height, mass, glow, rhythm,
   asymmetry, novelty). It scores candidates with its own taste, so different architects prefer different things.
2. **Variation.** Candidates come from mutation and crossover over the grammar — numeric drift, slot swaps,
   transplanting a part from a neighbour, adding or removing parts — or from a language model when one is
   configured. Every candidate still has to validate; the grammar is the physics.
3. **Selection with imitation.** A round has a brief and several architects. Each submits its best candidate.
   The critic (code, not vibes) ranks by coherence × taste-fit + novelty against the whole kit. When the owner
   adopts a winner, the winner's taste sharpens toward what won and the losers drift a little toward the winner,
   plus a small random walk. Lineage is recorded on the spec. Over rounds, styles form, split and die.

Nothing is adopted without the owner. Rounds are written to disk so a session can be replayed.
"""

from __future__ import annotations

import copy
import json
import math
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .grammar import LOT, SLOT_DEFAULTS, Spec, validate

JSON = dict[str, Any]

FEATURES = ("height", "mass", "glow", "rhythm", "asymmetry", "palette")
PART_TYPES = (
    "plinth",
    "volume",
    "fins",
    "slabs",
    "pylons",
    "strip",
    "mast",
    "facade_lights",
    "cylinder",
    "setback",
    "sign",
    "bridge",
    "antenna_array",
)
BODY_TYPES = ("volume", "fins", "slabs", "cylinder", "setback")
SIGN_WORDS = ("ESPERIA", "NODE", "HALO", "DELTA", "VECTOR", "ORBIT", "PULSE", "KIT", "ZERO", "FLUX", "BLOCK 0", "SIGNAL")
NEON_SLOTS = ("neonA", "neonB", "white", "gold", "glass")

# ---------------------------------------------------------------------------------------------- features


def features(spec: Spec) -> dict[str, float]:
    """Measurable character of a building, each roughly 0..1. What taste is a taste *for*."""
    parts = spec.parts
    n = len(parts)
    height = min(1.0, spec.height() / 50.0)
    footprint = 0.0
    for p in parts:
        fp = p.footprint()
        if fp:
            footprint = max(footprint, (fp[0] * fp[1]) / (LOT * LOT))
    mass = min(1.0, footprint * (0.4 + 0.6 * height))
    glow_parts = sum(1 for p in parts if any(s in NEON_SLOTS for s in p.slot_refs()))
    glow = glow_parts / n
    rhythm = min(1.0, sum(getattr(p, "count", 0) or 0 for p in parts) / 16.0)
    off_centre = [math.hypot(p.x, p.z) for p in parts if p.type != "plinth"]
    asymmetry = min(1.0, (sum(off_centre) / len(off_centre)) / 4.0) if off_centre else 0.0
    palette = min(1.0, sum(1 for k, v in spec.palette.items() if SLOT_DEFAULTS.get(k) != v) / 5.0)
    return {"height": height, "mass": mass, "glow": glow, "rhythm": rhythm, "asymmetry": asymmetry, "palette": palette}


def part_histogram(spec: Spec) -> list[float]:
    n = len(spec.parts)
    return [sum(1 for p in spec.parts if p.type == t) / n for t in PART_TYPES]


def distance(a: Spec, b: Spec) -> float:
    fa, fb = features(a), features(b)
    ha, hb = part_histogram(a), part_histogram(b)
    d_feat = math.sqrt(sum((fa[k] - fb[k]) ** 2 for k in FEATURES) / len(FEATURES))
    d_hist = math.sqrt(sum((x - y) ** 2 for x, y in zip(ha, hb)) / len(PART_TYPES))
    return 0.6 * d_feat + 0.4 * d_hist


def novelty(spec: Spec, kit: list[Spec]) -> float:
    """Distance to the nearest building already in the city. 0 = a copy; ~0.5 = unlike anything."""
    if not kit:
        return 1.0
    return min(distance(spec, k) for k in kit)


def coherence(spec: Spec, warnings: list[str]) -> float:
    """Does it read as one of *this* city's buildings? Penalise off-lot parts, slot sprawl, silly proportions."""
    score = 1.0
    score -= 0.15 * sum(1 for w in warnings if "extends past the lot" in w)
    score -= 0.10 * sum(1 for w in warnings if "not in the palette" in w)
    if len(spec.palette) > 6:
        score -= 0.1
    if spec.height() < 3:
        score -= 0.3
    if not any(p.type in BODY_TYPES for p in spec.parts):
        score -= 0.45  # a mast on a plinth is a lamp, not a building
    if len(spec.parts) > 14:
        score -= 0.1 * (len(spec.parts) - 14)
    return max(0.0, score)


# ---------------------------------------------------------------------------------------------- architects


@dataclass
class Architect:
    id: str
    name: str
    manifesto: str
    taste: dict[str, float]
    wins: int = 0
    rounds: int = 0
    history: list[str] = field(default_factory=list)
    signature: str = ""  # the one trait imitation may not erode — an architect's identity

    def __post_init__(self) -> None:
        if not self.signature:
            self.signature = max(FEATURES, key=lambda k: abs(self.taste[k]))

    def fit(self, f: dict[str, float]) -> float:
        """How much this architect likes a building, by its own taste. Taste weights are signed (-1..1)."""
        return sum(self.taste[k] * (f[k] - 0.5) for k in FEATURES) / len(FEATURES) + 0.5

    def voice(self) -> str:
        top = sorted(FEATURES, key=lambda k: -abs(self.taste[k]))[:2]
        words = {
            "height": ("reaches", "stays low"),
            "mass": ("is heavy", "is thin"),
            "glow": ("burns", "keeps dark"),
            "rhythm": ("repeats", "is one gesture"),
            "asymmetry": ("leans", "sits square"),
            "palette": ("wears its own colours", "wears the city's"),
        }
        return " and ".join(words[k][0] if self.taste[k] >= 0 else words[k][1] for k in top)


FOUNDERS: list[Architect] = [
    Architect(
        "arch-vela",
        "Vela",
        "Height is honesty. A building should be seen from every ring.",
        {"height": 0.9, "mass": 0.2, "glow": 0.4, "rhythm": 0.1, "asymmetry": -0.2, "palette": 0.0},
    ),
    Architect(
        "arch-tamsin",
        "Tamsin",
        "Repetition is how a city breathes. Fins, slabs, arrays.",
        {"height": 0.1, "mass": 0.3, "glow": 0.2, "rhythm": 0.9, "asymmetry": -0.4, "palette": -0.2},
    ),
    Architect(
        "arch-okoro",
        "Okoro",
        "Light is structure. Build the neon first, then hang the walls on it.",
        {"height": 0.2, "mass": -0.3, "glow": 0.9, "rhythm": 0.3, "asymmetry": 0.2, "palette": 0.5},
    ),
    Architect(
        "arch-brise",
        "Brise",
        "Nothing is centred. A building should lean toward its neighbours.",
        {"height": 0.0, "mass": 0.4, "glow": 0.0, "rhythm": -0.2, "asymmetry": 0.9, "palette": 0.1},
    ),
    Architect(
        "arch-nomen",
        "Nomen",
        "Mass. Plinth. Silence. One material and a single light on top.",
        {"height": 0.3, "mass": 0.9, "glow": -0.6, "rhythm": -0.5, "asymmetry": -0.3, "palette": -0.4},
    ),
]


# ---------------------------------------------------------------------------------------------- variation


def _num(rng: random.Random, v: float, lo: float, hi: float, spread: float = 0.25) -> float:
    return round(min(hi, max(lo, v * (1 + rng.uniform(-spread, spread)))), 2)


def _slot(rng: random.Random, current: str | None, palette: dict[str, str]) -> str:
    pool = list(dict.fromkeys(list(SLOT_DEFAULTS) + list(palette)))
    return rng.choice([s for s in pool if s != current] or pool)


def _template_part(rng: random.Random, top: float, palette: dict[str, str]) -> JSON:
    """A fresh part to add. Placed on top of the building or beside it."""
    kind = rng.choice(
        [
            "volume",
            "strip",
            "mast",
            "fins",
            "pylons",
            "facade_lights",
            "cylinder",
            "slabs",
            "setback",
            "sign",
            "bridge",
            "antenna_array",
        ]
    )
    neon = rng.choice(["neonA", "neonB", "white"])
    if kind == "volume":
        w = rng.uniform(3, 9)
        return {
            "type": "volume",
            "y": round(top, 2),
            "x": round(rng.uniform(-2, 2), 2),
            "z": round(rng.uniform(-2, 2), 2),
            "w": round(w, 2),
            "d": round(rng.uniform(3, 9), 2),
            "h": round(rng.uniform(3, 12), 2),
            "slot": rng.choice(["structure", "trim"]),
            "glass": {"slot": "glass", "density": round(rng.uniform(0.3, 0.9), 2)},
            "edges": neon if rng.random() < 0.6 else None,
        }
    if kind == "strip":
        return {
            "type": "strip",
            "y": round(top + 0.1, 2),
            "axis": rng.choice(["x", "z"]),
            "len": round(rng.uniform(3, 12), 2),
            "slot": neon,
        }
    if kind == "mast":
        return {
            "type": "mast",
            "y": round(top, 2),
            "h": round(rng.uniform(3, 9), 2),
            "beacon": neon,
            "x": round(rng.uniform(-4, 4), 2),
            "z": round(rng.uniform(-4, 4), 2),
        }
    if kind == "fins":
        return {
            "type": "fins",
            "y": round(top, 2),
            "axis": rng.choice(["x", "z"]),
            "count": rng.randint(3, 8),
            "pitch": round(rng.uniform(1.2, 2.2), 2),
            "t": round(rng.uniform(0.6, 1.4), 2),
            "d": round(rng.uniform(5, 11), 2),
            "h": round(rng.uniform(4, 14), 2),
            "wave": round(rng.uniform(0, 3), 2),
            "slot": "structure",
            "alt": "trim",
        }
    if kind == "pylons":
        return {
            "type": "pylons",
            "y": round(top, 2),
            "spread": round(rng.uniform(6, 12), 2),
            "size": round(rng.uniform(0.6, 1.4), 2),
            "h": round(rng.uniform(3, 10), 2),
            "slot": "metal",
            "cap": neon,
        }
    if kind == "facade_lights":
        return {
            "type": "facade_lights",
            "y": 1.5,
            "side": rng.choice(["n", "s", "e", "w"]),
            "h": round(rng.uniform(3, 12), 2),
            "count": rng.randint(2, 6),
            "pitch": round(rng.uniform(1.5, 3), 2),
            "slots": [neon, rng.choice(["neonA", "neonB"])],
        }
    if kind == "cylinder":
        return {
            "type": "cylinder",
            "y": round(top, 2),
            "x": round(rng.uniform(-4, 4), 2),
            "z": round(rng.uniform(-4, 4), 2),
            "r": round(rng.uniform(1, 3), 2),
            "h": round(rng.uniform(3, 10), 2),
            "slot": "trim",
            "cap": "metal",
        }
    if kind == "setback":
        return {
            "type": "setback",
            "x": round(rng.uniform(-1.5, 1.5), 2),
            "z": round(rng.uniform(-1.5, 1.5), 2),
            "w": round(rng.uniform(3, 8), 2),
            "d": round(rng.uniform(3, 8), 2),
            "h": round(rng.uniform(2, 8), 2),
            "slot": rng.choice(["structure", "trim"]),
            "glass": {"slot": "glass", "density": round(rng.uniform(0.3, 0.9), 2)},
            "edges": neon if rng.random() < 0.7 else None,
        }
    if kind == "sign":
        return {
            "type": "sign",
            "side": rng.choice(["n", "s", "e", "w"]),
            "text": rng.choice(SIGN_WORDS),
            "y": round(rng.uniform(1.5, max(2.0, top - 3)), 2),
            "h": round(rng.uniform(1.6, 3.2), 2),
            "slot": neon,
        }
    if kind == "bridge":
        axis = rng.choice(["x", "z"])
        a, b = round(rng.uniform(-6, -1), 2), round(rng.uniform(1, 6), 2)
        k = round(rng.uniform(-4, 4), 2)
        return {
            "type": "bridge",
            "x": a if axis == "x" else k,
            "z": k if axis == "x" else a,
            "x2": b if axis == "x" else k,
            "z2": k if axis == "x" else b,
            "y": round(rng.uniform(2, max(3.0, top - 1)), 2),
            "t": round(rng.uniform(0.6, 1.4), 2),
            "slot": "metal",
            "strip": neon if rng.random() < 0.6 else None,
        }
    if kind == "antenna_array":
        return {
            "type": "antenna_array",
            "y": round(top, 2),
            "x": round(rng.uniform(-3, 3), 2),
            "z": round(rng.uniform(-3, 3), 2),
            "count": rng.randint(2, 7),
            "pitch": round(rng.uniform(1, 2.2), 2),
            "h": round(rng.uniform(2, 7), 2),
            "axis": rng.choice(["x", "z"]),
            "tip": neon,
        }
    return {
        "type": "slabs",
        "y": round(top, 2),
        "count": rng.randint(2, 5),
        "pitch": round(rng.uniform(1.8, 3.2), 2),
        "w": round(rng.uniform(6, 12), 2),
        "h": round(rng.uniform(5, 14), 2),
        "t": round(rng.uniform(0.8, 1.6), 2),
        "slot": "structure",
        "foot": "gold",
    }


def _clean(part: JSON) -> JSON:
    return {k: v for k, v in part.items() if v is not None}


def mutate(data: JSON, rng: random.Random, donors: list[JSON], strength: int = 3) -> JSON:
    """Apply `strength` random edits to a copy of a spec. Always keeps the plinth first."""
    d = copy.deepcopy(data)
    parts: list[JSON] = d["parts"]
    palette: dict[str, str] = d.setdefault("palette", {})
    for _ in range(strength):
        op = rng.choice(["num", "num", "num", "slot", "add", "remove", "transplant", "palette", "shift"])
        body = [p for p in parts if p.get("type") != "plinth"]
        if op == "num" and body:
            p = rng.choice(body)
            keys: list[str] = [k for k in ("w", "d", "h", "pitch", "count", "len", "spread", "r", "wave") if k in p]
            if keys:
                k = rng.choice(keys)
                if k == "count":
                    p[k] = max(1, min(12, int(p[k]) + rng.choice([-2, -1, 1, 2])))
                else:
                    p[k] = _num(rng, float(p[k]), 0.3, 48.0)
        elif op == "slot" and body:
            p = rng.choice(body)
            keys = [
                k for k in ("slot", "edges", "corner", "cap", "beacon", "alt", "foot", "tip", "strip", "panel") if k in p and p[k]
            ]
            if keys:
                k = rng.choice(keys)
                p[k] = _slot(rng, p[k], palette)
        elif op == "add":
            top = max((float(p.get("y", 0)) + float(p.get("h", 0)) for p in parts), default=1.2)
            if len(parts) < 14:
                parts.append(_clean(_template_part(rng, top, palette)))
        elif op == "remove" and len(body) > 1:
            parts.remove(rng.choice(body))
        elif op == "transplant" and donors:
            donor = rng.choice(donors)
            candidates = [p for p in donor.get("parts", []) if p.get("type") != "plinth"]
            if candidates and len(parts) < 14:
                part = copy.deepcopy(rng.choice(candidates))
                top = max((float(p.get("y", 0)) + float(p.get("h", 0)) for p in parts), default=1.2)
                if part.get("type") in BODY_TYPES + ("mast", "pylons"):
                    part["y"] = round(min(top, 40.0), 2)
                parts.append(part)
        elif op == "palette":
            slot = rng.choice(["structure", "trim", "neonA", "neonB", "glass"])
            h = rng.random()
            palette[slot] = _hsl_hex(h, 0.75 if slot.startswith("neon") else 0.25, 0.55 if slot.startswith("neon") else 0.22)
        elif op == "shift" and body:
            p = rng.choice(body)
            dx, dz = rng.uniform(-3.5, 3.5), rng.uniform(-3.5, 3.5)
            p["x"] = round(max(-4.0, min(4.0, float(p.get("x", 0)) + dx)), 2)
            p["z"] = round(max(-4.0, min(4.0, float(p.get("z", 0)) + dz)), 2)
            if p.get("type") == "bridge":  # both ends move together so it stays axis-aligned
                p["x2"] = round(max(-6.0, min(6.0, float(p.get("x2", 0)) + dx)), 2)
                p["z2"] = round(max(-6.0, min(6.0, float(p.get("z2", 0)) + dz)), 2)
        elif op == "num":
            signs = [q for q in parts if q.get("type") == "sign"]
            if signs:
                rng.choice(signs)["text"] = rng.choice(SIGN_WORDS)
    d["parts"] = parts
    return d


def crossover(a: JSON, b: JSON, rng: random.Random) -> JSON:
    """Plinth and lower half from a, upper parts from b, palette merged."""
    d = copy.deepcopy(a)
    pa = [p for p in a["parts"] if p.get("type") != "plinth"]
    pb = [p for p in b["parts"] if p.get("type") != "plinth"]
    cut_a = max(1, len(pa) // 2)
    keep = [p for p in a["parts"] if p.get("type") == "plinth"] + pa[:cut_a]
    top = max((float(p.get("y", 0)) + float(p.get("h", 0)) for p in keep), default=1.2)
    for p in pb[len(pb) // 2 :]:
        q = copy.deepcopy(p)
        if q.get("type") in BODY_TYPES + ("mast", "pylons"):
            q["y"] = round(min(top, 40.0), 2)
        keep.append(q)
    d["parts"] = keep[:14]
    pal = dict(b.get("palette", {}))
    pal.update(a.get("palette", {}))
    d["palette"] = {k: v for k, v in pal.items() if rng.random() < 0.8}
    return d


def _hsl_hex(h: float, s: float, l_: float) -> str:
    def f(n: float) -> int:
        k = (n + h * 12) % 12
        a = s * min(l_, 1 - l_)
        return int(round(255 * (l_ - a * max(-1.0, min(k - 3, 9 - k, 1.0)))))

    return f"#{f(0):02x}{f(8):02x}{f(4):02x}"


# ---------------------------------------------------------------------------------------------- proposers


class Proposer(Protocol):
    def __call__(self, architect: Architect, brief: JSON, kit: dict[str, JSON], rng: random.Random) -> list[JSON]: ...


def evolutionary_proposer(architect: Architect, brief: JSON, kit: dict[str, JSON], rng: random.Random, n: int = 6) -> list[JSON]:
    """Mutation + crossover over the kit, biased by the architect's taste when picking parents."""
    if not kit:
        return []
    specs = {k: validate(v)[0] for k, v in kit.items()}
    parents = [k for k, s in specs.items() if s is not None]
    weights = [max(0.05, architect.fit(features(specs[k]))) for k in parents]  # type: ignore[arg-type]
    neighbours = [kit[k] for k in brief.get("neighbours", []) if k in kit]
    out: list[JSON] = []
    for _ in range(n):
        a = rng.choices(parents, weights)[0]
        base = kit[a]
        lineage = [a]
        if rng.random() < 0.4:
            b = rng.choices(parents, weights)[0]
            base = crossover(kit[a], kit[b], rng)
            lineage.append(b)
        strength = rng.randint(2, 5)
        cand = mutate(base, rng, neighbours or list(kit.values()), strength)
        cand["architect"] = architect.id
        cand["lineage"] = list(dict.fromkeys(lineage))
        cand["name"] = (
            brief.get("name") or f"{architect.name}'s {rng.choice(['tower', 'hall', 'stack', 'array', 'spire', 'block'])}"
        )
        cand["code"] = brief.get("code") or f"A{rng.randint(10, 99)}"
        cand["statement"] = f"{architect.name}: it {architect.voice()}."
        out.append(cand)
    return out


def _json_from_text(text: str) -> JSON | None:
    """Parse a model reply that may be fenced, prefixed with prose, or already clean JSON."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    try:
        obj = json.loads(t)
    except json.JSONDecodeError:
        a, b = t.find("{"), t.rfind("}")
        if a < 0 or b <= a:
            return None
        try:
            obj = json.loads(t[a : b + 1])
        except json.JSONDecodeError:
            return None
    return obj if isinstance(obj, dict) else None


def llm_proposer(url: str, model: str, timeout: float = 120.0, fallback: Proposer | None = None, n: int = 2) -> Proposer:
    """An OpenAI-compatible chat endpoint (Ollama's /v1 works) asked for a spec in JSON. Local by default.
    Asks `n` times per architect at temperature 0.9. If the endpoint fails or answers nonsense and `fallback` is given,
    that architect proposes with the fallback instead (so a dead Ollama never empties a round)."""
    import urllib.error
    import urllib.request

    from .grammar import PART_DOCS

    def ask(system: str, user: str) -> JSON | None:
        body = json.dumps(
            {
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": 0.9,
                "response_format": {"type": "json_object"},
            }
        ).encode()
        req = urllib.request.Request(
            url.rstrip("/") + "/chat/completions", data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — owner-configured local endpoint
                payload = json.loads(resp.read().decode())
            text = payload["choices"][0]["message"]["content"]
        except (urllib.error.URLError, OSError, KeyError, IndexError, TypeError, ValueError):
            return None
        return _json_from_text(str(text))

    def propose(architect: Architect, brief: JSON, kit: dict[str, JSON], rng: random.Random) -> list[JSON]:
        neighbours = {k: kit[k] for k in brief.get("neighbours", []) if k in kit}
        system = (
            "You are an architect in Esperia, a neon city on a circuit board. You design buildings as JSON specs: "
            "{name, code, palette:{slot:hex}, parts:[...]}. Units are board units; a lot is 14x14; x,z offset from lot centre; "
            "y is height. Parts (first must be a plinth): "
            + json.dumps(PART_DOCS)
            + ". Slots: "
            + json.dumps(SLOT_DEFAULTS)
            + ". Reply with ONLY a JSON object with keys 'spec' and 'statement'."
        )
        user = (
            f"You are {architect.name}. Manifesto: {architect.manifesto}\nYour taste: {json.dumps(architect.taste)}\n"
            f"Brief: {json.dumps(brief)}\nNeighbouring buildings you must respond to: {json.dumps(neighbours)}\n"
            "Design something the city has not seen, in your voice. Keep it under 50 tall and inside the lot."
        )
        out: list[JSON] = []
        for _ in range(n):
            obj = ask(system, user)
            if obj is None:
                continue
            spec = obj.get("spec") if "spec" in obj else (obj if "parts" in obj else None)
            if not isinstance(spec, dict) or not isinstance(spec.get("parts"), list):
                continue
            spec["architect"] = architect.id
            spec["lineage"] = list(neighbours)
            spec["statement"] = str(obj.get("statement", ""))[:200]
            spec.setdefault("name", brief.get("name") or f"{architect.name}'s building")
            spec.setdefault("code", brief.get("code") or f"A{rng.randint(10, 99)}")
            spec.setdefault("palette", {})
            out.append(spec)
        if not out and fallback is not None:
            return fallback(architect, brief, kit, rng)
        return out

    return propose


# ---------------------------------------------------------------------------------------------- rounds


@dataclass
class Candidate:
    id: str
    architect: str
    spec: JSON
    coherence: float
    novelty: float
    taste_fit: float
    score: float
    warnings: list[str]


class Studio:
    """The population plus its files: architects.json, rounds/<id>.json."""

    def __init__(self, state_dir: Path, kit_dir: Path, seed: int | None = None):
        self.state_dir = state_dir
        self.kit_dir = kit_dir
        self.rounds_dir = state_dir / "rounds"
        self.rng = random.Random(seed)
        self.architects: list[Architect] = self._load_architects()

    # ---- persistence
    def _load_architects(self) -> list[Architect]:
        p = self.state_dir / "architects.json"
        if not p.exists():
            return [copy.deepcopy(a) for a in FOUNDERS]
        raw = json.loads(p.read_text())
        return [Architect(**a) for a in raw]

    def save(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "architects.json").write_text(json.dumps([asdict(a) for a in self.architects], indent=2))

    def kit(self) -> dict[str, JSON]:
        out: dict[str, JSON] = {}
        for p in sorted(self.kit_dir.glob("*.json")):
            try:
                d = json.loads(p.read_text())
                if isinstance(d, dict):
                    out[p.stem] = d
            except (OSError, ValueError):
                continue
        return out

    def next_kit_id(self) -> str:
        n = 1
        while (self.kit_dir / f"a{n}.json").exists():
            n += 1
        return f"a{n}"

    # ---- a round
    def recent_winners(self, n: int = 3) -> list[Spec]:
        ids = [h for a in self.architects for h in a.history if not h.startswith("saw:")]
        out: list[Spec] = []
        for kid in ids[-n:]:
            p = self.kit_dir / f"{kid}.json"
            if p.exists():
                sp = validate(json.loads(p.read_text()))[0]
                if sp is not None:
                    out.append(sp)
        return out

    def run_round(
        self, brief: JSON, proposer: Proposer | None = None, per_architect: int = 6, novelty_weight: float = 0.6
    ) -> JSON:
        kit = self.kit()
        kit_specs = [s for s in (validate(v)[0] for v in kit.values()) if s is not None]
        recent = self.recent_winners()
        propose = proposer or (lambda a, b, k, r: evolutionary_proposer(a, b, k, r, per_architect))
        candidates: list[Candidate] = []
        for arch in self.architects:
            arch.rounds += 1
            best: Candidate | None = None
            for i, cand in enumerate(propose(arch, brief, kit, self.rng)):
                spec, errors, warnings = validate(cand)
                if spec is None or errors:
                    continue
                f = features(spec)
                c = coherence(spec, warnings)
                nv = novelty(spec, kit_specs)
                fresh = novelty(spec, recent) if recent else nv  # one school must not win every round
                tf = arch.fit(f)
                score = c * (0.5 + 0.5 * tf) + novelty_weight * (0.7 * nv + 0.3 * fresh)
                cc = Candidate(
                    f"{arch.id}-{i}", arch.id, cand, round(c, 3), round(nv, 3), round(tf, 3), round(score, 3), warnings
                )
                if best is None or cc.score > best.score:
                    best = cc
            if best:
                candidates.append(best)
        candidates.sort(key=lambda c: -c.score)
        round_id = time.strftime("%Y%m%d-%H%M%S")
        record: JSON = {
            "id": round_id,
            "brief": brief,
            "candidates": [asdict(c) for c in candidates],
            "architects": {a.id: {"name": a.name, "taste": a.taste, "wins": a.wins} for a in self.architects},
        }
        self.rounds_dir.mkdir(parents=True, exist_ok=True)
        (self.rounds_dir / f"{round_id}.json").write_text(json.dumps(record, indent=2))
        self.save()
        return record

    def load_round(self, round_id: str) -> JSON:
        p = self.rounds_dir / f"{round_id}.json"
        data = json.loads(p.read_text())
        if not isinstance(data, dict):
            raise ValueError(f"{p} is not a round record")
        return data

    # ---- adoption: the owner's decision, and where drift happens
    def adopt(self, round_id: str, candidate_id: str, kit_id: str | None = None, learn: float = 0.25) -> JSON:
        record = self.load_round(round_id)
        cands = {c["id"]: c for c in record["candidates"]}
        if candidate_id not in cands:
            raise KeyError(f"no candidate {candidate_id} in round {round_id}")
        winner = cands[candidate_id]
        spec, errors, _ = validate(winner["spec"])
        if spec is None or errors:
            raise ValueError(f"winner no longer validates: {errors}")
        f = features(spec)
        kid = kit_id or self.next_kit_id()
        data = dict(winner["spec"])
        data["code"] = data.get("code") or kid.upper()
        self.kit_dir.mkdir(parents=True, exist_ok=True)
        (self.kit_dir / f"{kid}.json").write_text(json.dumps(data, indent=2))
        # drift
        by_id = {a.id: a for a in self.architects}
        w = by_id[winner["architect"]]
        w.wins += 1
        w.history.append(kid)
        for a in self.architects:
            for k in FEATURES:
                target = (f[k] - 0.5) * 2.0  # what won, as a signed preference
                rate = learn if a is w else learn * 0.4  # winner sharpens, others imitate more weakly
                if k == a.signature and a is not w:
                    continue  # identity: nobody imitates their way out of who they are
                moved = a.taste[k] * (1 - rate) + target * rate + self.rng.gauss(0, 0.04)
                if k == a.signature:  # a winner may sharpen its signature, never flip it
                    sign = 1.0 if a.taste[k] >= 0 else -1.0
                    moved = sign * max(0.5, abs(moved))
                a.taste[k] = max(-1.0, min(1.0, moved))
            if a is not w:
                a.history.append(f"saw:{kid}")
        w.manifesto = self._revise_manifesto(w, spec)
        self.save()
        record.setdefault("adopted", []).append({"candidate": candidate_id, "kit_id": kid})
        (self.rounds_dir / f"{round_id}.json").write_text(json.dumps(record, indent=2))
        return {
            "kit_id": kid,
            "path": str(self.kit_dir / f"{kid}.json"),
            "architect": w.name,
            "taste": w.taste,
            "manifesto": w.manifesto,
        }

    def _revise_manifesto(self, a: Architect, spec: Spec) -> str:
        types = sorted({p.type for p in spec.parts if p.type != "plinth"})
        line = f"Won with {', '.join(types)}; now it {a.voice()}."
        lines = [ln for ln in a.manifesto.split("\n") if ln.strip()][-3:]
        return "\n".join(lines + [line])
