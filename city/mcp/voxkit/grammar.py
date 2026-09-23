"""The building grammar, v0.1 — mirrors city/kit/GRAMMAR.md and genSpec in the renderer.

A building is a kit of parts. A spec is a palette of named slots plus an ordered list of parts.
Positions are offsets from the lot centre (x, z); y is height above the board. Units are board units; a lot is 14 wide.
Each part type is its own model, so a spec that validates has every field its rasteriser needs.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

LOT = 14.0
MAX_HEIGHT = 52.0

SLOT_DEFAULTS: dict[str, str] = {
    "plinth": "#1a1d28",
    "structure": "#2c3250",
    "trim": "#353b58",
    "metal": "#8f97a6",
    "glass": "#eef2ff",
    "neonA": "#3fd8f0",
    "neonB": "#ff5fd2",
    "gold": "#d8ad55",
    "white": "#eef2ff",
}
EMISSIVE_SLOTS: frozenset[str] = frozenset({"glass", "neonA", "neonB", "white"})


class Glass(BaseModel):
    """A window grid painted on a part's faces."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    slot: str = "glass"
    density: float = Field(0.65, ge=0, le=1)
    cw: float = 1.9
    ch: float = 2.6
    from_: float = Field(1.2, alias="from")


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = 0
    z: float = 0
    y: float = 0

    def slot_refs(self) -> list[str]:
        """Every slot name this part references (for validation)."""
        return []

    def top(self) -> float:
        return self.y

    def footprint(self) -> tuple[float, float] | None:
        """(width, depth) centred on (x, z), or None if the part has no meaningful footprint."""
        return None


class PlinthPart(_Base):
    type: Literal["plinth"]
    w: float
    d: float
    h: float
    slot: str = "plinth"

    def slot_refs(self) -> list[str]:
        return [self.slot]

    def top(self) -> float:
        return self.h

    def footprint(self) -> tuple[float, float] | None:
        return (self.w, self.d)


class VolumePart(_Base):
    type: Literal["volume"]
    w: float
    d: float
    h: float
    slot: str
    glass: Glass | None = None
    edges: str | None = None
    corner: str | None = None

    def slot_refs(self) -> list[str]:
        refs = [self.slot]
        if self.glass:
            refs.append(self.glass.slot)
        if self.edges:
            refs.append(self.edges)
        if self.corner:
            refs.append(self.corner)
        return refs

    def top(self) -> float:
        return self.y + self.h

    def footprint(self) -> tuple[float, float] | None:
        return (self.w, self.d)


class FinsPart(_Base):
    type: Literal["fins"]
    axis: Literal["x", "z"]
    count: int = Field(ge=1, le=64)
    pitch: float
    t: float
    d: float
    h: float
    slot: str
    alt: str | None = None
    wave: float = 0
    glassOn: Literal["last", "all"] | None = None
    glass: Glass | None = None

    def slot_refs(self) -> list[str]:
        refs = [self.slot]
        if self.alt:
            refs.append(self.alt)
        if self.glass:
            refs.append(self.glass.slot)
        return refs

    def top(self) -> float:
        return self.y + self.h + abs(self.wave)

    def footprint(self) -> tuple[float, float] | None:
        span = (self.count - 1) * self.pitch + self.t
        return (span, self.d) if self.axis == "x" else (self.d, span)


class SlabsPart(_Base):
    type: Literal["slabs"]
    count: int = Field(ge=1, le=64)
    pitch: float
    w: float
    h: float
    t: float
    slot: str
    foot: str | None = None
    glass: Glass | None = None

    def slot_refs(self) -> list[str]:
        refs = [self.slot]
        if self.foot:
            refs.append(self.foot)
        if self.glass:
            refs.append(self.glass.slot)
        return refs

    def top(self) -> float:
        return self.y + self.h

    def footprint(self) -> tuple[float, float] | None:
        return (self.w, (self.count - 1) * self.pitch + self.t)


class PylonsPart(_Base):
    type: Literal["pylons"]
    spread: float
    size: float
    h: float
    slot: str
    cap: str | None = None

    def slot_refs(self) -> list[str]:
        return [self.slot] + ([self.cap] if self.cap else [])

    def top(self) -> float:
        return self.y + self.h + (0.4 if self.cap else 0)

    def footprint(self) -> tuple[float, float] | None:
        return (self.spread + self.size, self.spread + self.size)


class StripPart(_Base):
    type: Literal["strip"]
    axis: Literal["x", "z"]
    len: float
    slot: str
    t: float = 0.25

    def slot_refs(self) -> list[str]:
        return [self.slot]

    def top(self) -> float:
        return self.y + self.t

    def footprint(self) -> tuple[float, float] | None:
        return (self.len, self.t) if self.axis == "x" else (self.t, self.len)


class MastPart(_Base):
    type: Literal["mast"]
    h: float
    slot: str = "metal"
    beacon: str | None = None
    beaconSize: float = 0.9

    def slot_refs(self) -> list[str]:
        return [self.slot] + ([self.beacon] if self.beacon else [])

    def top(self) -> float:
        return self.y + self.h + (self.beaconSize + 0.1 if self.beacon else 0)


class FacadeLightsPart(_Base):
    type: Literal["facade_lights"]
    side: Literal["n", "s", "e", "w"]
    h: float
    count: int = Field(ge=1, le=64)
    pitch: float
    slots: list[str] = Field(min_length=1)

    def slot_refs(self) -> list[str]:
        return list(self.slots)

    def top(self) -> float:
        return self.y + self.h


class CylinderPart(_Base):
    type: Literal["cylinder"]
    r: float
    h: float
    slot: str
    cap: str | None = None

    def slot_refs(self) -> list[str]:
        return [self.slot] + ([self.cap] if self.cap else [])

    def top(self) -> float:
        return self.y + self.h + (0.7 if self.cap else 0)

    def footprint(self) -> tuple[float, float] | None:
        return (2 * self.r, 2 * self.r)


class SetbackPart(_Base):
    """A volume that sits on top of whatever came before it. `y` is ignored; the rasteriser stacks it."""

    type: Literal["setback"]
    w: float
    d: float
    h: float
    slot: str
    glass: Glass | None = None
    edges: str | None = None
    corner: str | None = None

    def slot_refs(self) -> list[str]:
        refs = [self.slot]
        if self.glass:
            refs.append(self.glass.slot)
        if self.edges:
            refs.append(self.edges)
        if self.corner:
            refs.append(self.corner)
        return refs

    def top(self) -> float:
        return self.h  # relative; Spec.height() adds the stack below

    def footprint(self) -> tuple[float, float] | None:
        return (self.w, self.d)


class SignPart(_Base):
    """An emissive panel with text, hung on one façade at the lot edge (or at x/z if given). 3×5 pixel glyphs."""

    type: Literal["sign"]
    side: Literal["n", "s", "e", "w"]
    text: str = Field(min_length=1, max_length=12)
    h: float = 2.4
    slot: str = "neonA"
    panel: str = "plinth"
    w: float | None = None  # default: fits the text

    def slot_refs(self) -> list[str]:
        return [self.slot, self.panel]

    def top(self) -> float:
        return self.y + self.h

    def width(self) -> float:
        return self.w if self.w is not None else max(2.0, len(self.text) * self.h * 0.7)


class BridgePart(_Base):
    """An axis-aligned bar from (x, z) to (x2, z2) at height y; a walkway, a duct, a beam. Optional lit strip on top."""

    type: Literal["bridge"]
    x2: float
    z2: float
    t: float = 1.0
    slot: str = "metal"
    strip: str | None = None

    def slot_refs(self) -> list[str]:
        return [self.slot] + ([self.strip] if self.strip else [])

    def top(self) -> float:
        return self.y + self.t + (0.25 if self.strip else 0)

    def footprint(self) -> tuple[float, float] | None:
        return None


class AntennaArrayPart(_Base):
    """A row of thin masts with lit tips — the roof of every cyberpunk tower."""

    type: Literal["antenna_array"]
    count: int = Field(3, ge=1, le=16)
    pitch: float = 1.5
    h: float = 4.0
    axis: Literal["x", "z"] = "x"
    slot: str = "metal"
    tip: str = "neonB"

    def slot_refs(self) -> list[str]:
        return [self.slot, self.tip]

    def top(self) -> float:
        return self.y + self.h + 0.4

    def footprint(self) -> tuple[float, float] | None:
        span = (self.count - 1) * self.pitch + 0.4
        return (span, 0.4) if self.axis == "x" else (0.4, span)


Part = Annotated[
    PlinthPart
    | VolumePart
    | FinsPart
    | SlabsPart
    | PylonsPart
    | StripPart
    | MastPart
    | FacadeLightsPart
    | CylinderPart
    | SetbackPart
    | SignPart
    | BridgePart
    | AntennaArrayPart,
    Field(discriminator="type"),
]


class Division(BaseModel):
    """A unit of work inside a building: one floor (or one room in City Hall), `offices` desks, one role."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=40)
    role: str = Field(min_length=1, max_length=40)
    offices: int = Field(2, ge=1, le=6)


class Project(BaseModel):
    """The building's current job as the city panel shows it."""

    model_config = ConfigDict(extra="forbid")
    job: str = "—"
    title: str
    stage: str = "Queued"
    backend: str = "—"
    budget: str = "—"
    since: str = "—"


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    code: str | None = None
    palette: dict[str, str] = Field(default_factory=dict)
    emissive: list[str] | None = None  # override which slots glow; default EMISSIVE_SLOTS
    parts: list[Part] = Field(min_length=1)
    # provenance — who designed it and what it descends from (kit ids). Set by the architects, kept forever.
    architect: str | None = None
    lineage: list[str] = Field(default_factory=list)
    statement: str | None = None  # the architect's one-line intent, in their words
    divisions: list[Division] = Field(default_factory=list)  # who works here; the page builds floors and rooms from these
    project: Project | None = None  # what the building is working on, shown in its panel

    def color(self, slot: str | None) -> str:
        if slot and slot in self.palette:
            return self.palette[slot]
        if slot and slot in SLOT_DEFAULTS:
            return SLOT_DEFAULTS[slot]
        return self.palette.get("structure", SLOT_DEFAULTS["structure"])

    def is_emissive(self, slot: str | None) -> bool:
        wanted = frozenset(self.emissive) if self.emissive is not None else EMISSIVE_SLOTS
        return bool(slot) and slot in wanted

    def height(self) -> float:
        top = 0.0
        stack = 0.0  # where the next setback lands
        for p in self.parts:
            if isinstance(p, SetbackPart):
                stack = stack + p.h
                top = max(top, stack)
            else:
                t = p.top()
                top = max(top, t)
                if isinstance(p, PlinthPart | VolumePart | FinsPart | SlabsPart | CylinderPart):
                    stack = max(stack, t)
        return top

    def stacked_y(self, index: int) -> float:
        """Height at which parts[index] sits if it is a setback: the top of the stackable parts before it."""
        stack = 0.0
        for p in self.parts[:index]:
            if isinstance(p, SetbackPart):
                stack = stack + p.h
            elif isinstance(p, PlinthPart | VolumePart | FinsPart | SlabsPart | CylinderPart):
                stack = max(stack, p.top())
        return stack


PART_DOCS: dict[str, str] = {
    "plinth": "The pad. Always first. w d h [slot]. Not hidden in cutaway.",
    "volume": "A box. x z y w d h slot [glass{slot,density,cw,ch,from}] [edges=neon slot around top] [corner=neon slot down +x+z corner].",
    "fins": "Row of thin slabs (heatsink). x z y axis count pitch t d h [wave] slot [alt] [glassOn=last|all, glass].",
    "slabs": "Parallel upright plates (memory bank). x z y count pitch w h t slot [foot=slot] [glass].",
    "pylons": "Four corner posts at ±spread/2. x z y spread size h slot [cap=slot].",
    "strip": "One neon bar. x z y axis len [t] slot.",
    "mast": "Thin pole with a light. x z y h [slot] [beacon=slot beaconSize].",
    "facade_lights": "Vertical neon fins along one façade. side(n|s|e|w) y h count pitch slots[].",
    "cylinder": "Tank/silo. x z y r h slot [cap=slot].",
    "setback": "A volume stacked on top of whatever came before (y is computed). x z w d h slot [glass] [edges] [corner].",
    "sign": "Emissive text panel on one façade, 3×5 pixel glyphs A–Z 0–9. side text [h=2.4] [slot=neonA] [panel=plinth] [w] [y].",
    "bridge": "Axis-aligned bar from (x,z) to (x2,z2) at height y. x z x2 z2 y [t=1] [slot=metal] [strip=neon slot on top].",
    "antenna_array": "Row of thin masts with lit tips. x z y [count=3] [pitch=1.5] [h=4] [axis=x] [slot=metal] [tip=neonB].",
}


def validate(data: dict[str, Any]) -> tuple[Spec | None, list[str], list[str]]:
    """Return (spec or None, errors, warnings). Errors must be fixed; warnings are taste."""
    errors: list[str] = []
    warnings: list[str] = []
    try:
        spec = Spec.model_validate(data)
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(p) for p in err["loc"])
            errors.append(f"{loc}: {err['msg']}")
        return None, errors, warnings

    if spec.parts[0].type != "plinth":
        warnings.append("parts[0] is not a plinth; the building will sit directly on the board")

    known = set(SLOT_DEFAULTS) | set(spec.palette)
    for i, p in enumerate(spec.parts):
        for ref in p.slot_refs():
            if ref not in known:
                warnings.append(f"parts[{i}] ({p.type}): slot '{ref}' is not in the palette; falls back to 'structure'")
        fp = p.footprint()
        if fp:
            w, d = fp
            if abs(p.x) + w / 2 > LOT / 2 + 0.01:
                warnings.append(f"parts[{i}] ({p.type}): extends past the lot in x")
            if abs(p.z) + d / 2 > LOT / 2 + 0.01:
                warnings.append(f"parts[{i}] ({p.type}): extends past the lot in z")
    for i, p in enumerate(spec.parts):
        if isinstance(p, BridgePart) and p.x != p.x2 and p.z != p.z2:
            errors.append(f"parts[{i}] (bridge): must be axis-aligned — share x or z between the two ends")
        if isinstance(p, SignPart):
            bad = sorted({ch for ch in p.text.upper() if ch not in GLYPHS and ch != " "})
            if bad:
                errors.append(f"parts[{i}] (sign): no glyph for {''.join(bad)!r}; use A–Z, 0–9, space, - or ·")
    top = spec.height()
    if top > MAX_HEIGHT:
        errors.append(f"building is {top:.1f} tall; keep it under {MAX_HEIGHT}")
    return spec, errors, warnings


# 3×5 pixel font for signs: rows top→bottom, 1 = lit. Shared by the rasteriser and the city page.
GLYPHS: dict[str, tuple[str, str, str, str, str]] = {
    "A": ("010", "101", "111", "101", "101"),
    "B": ("110", "101", "110", "101", "110"),
    "C": ("011", "100", "100", "100", "011"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "G": ("011", "100", "101", "101", "011"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"),
    "J": ("001", "001", "001", "101", "010"),
    "K": ("101", "110", "100", "110", "101"),
    "L": ("100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("010", "101", "101", "101", "010"),
    "P": ("110", "101", "110", "100", "100"),
    "Q": ("010", "101", "101", "110", "011"),
    "R": ("110", "101", "110", "101", "101"),
    "S": ("011", "100", "010", "001", "110"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "011"),
    "V": ("101", "101", "101", "101", "010"),
    "W": ("101", "101", "111", "111", "101"),
    "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"),
    "Z": ("111", "001", "010", "100", "111"),
    "0": ("010", "101", "101", "101", "010"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("110", "001", "010", "100", "111"),
    "3": ("110", "001", "010", "001", "110"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "110", "001", "110"),
    "6": ("011", "100", "110", "101", "010"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("010", "101", "010", "101", "010"),
    "9": ("010", "101", "011", "001", "110"),
    "-": ("000", "000", "111", "000", "000"),
    "·": ("000", "000", "010", "000", "000"),
}
