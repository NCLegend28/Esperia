"""Spec → voxel grid. One branch per part type; the same semantics as genSpec in the renderer.

Grid axes: grid[x, y, z] with y up, uint8 palette index (0 = empty). Slots are assigned indices 1..n in
first-seen order; `Raster.slots` maps index → (slot name, hex colour, emissive).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from .grammar import (
    GLYPHS,
    LOT,
    SLOT_DEFAULTS,
    AntennaArrayPart,
    BridgePart,
    CylinderPart,
    FacadeLightsPart,
    FinsPart,
    Glass,
    MastPart,
    PlinthPart,
    PylonsPart,
    SetbackPart,
    SignPart,
    SlabsPart,
    Spec,
    StripPart,
    VolumePart,
)

VOXELS_PER_UNIT = 4  # 1 board unit = 4 voxels; a 14-unit lot = 56 voxels
NEON_T = 0.25  # neon bar thickness in units (one voxel)

Grid = npt.NDArray[np.uint8]
SlotInfo = tuple[str, str, bool]


@dataclass
class Raster:
    grid: Grid  # [X, Y, Z]
    slots: dict[int, SlotInfo] = field(default_factory=dict)

    @property
    def size(self) -> tuple[int, int, int]:
        x, y, z = self.grid.shape
        return int(x), int(y), int(z)

    def count(self) -> int:
        return int((self.grid > 0).sum())


class _Ctx:
    def __init__(self, spec: Spec, s: int):
        self.spec = spec
        self.s = s
        self.index: dict[str, int] = {}
        top = spec.height() + 2.0
        self.X = int(round(LOT * s)) + 2
        self.Y = int(math.ceil(top * s)) + 4
        self.Z = self.X
        self.grid: Grid = np.zeros((self.X, self.Y, self.Z), dtype=np.uint8)
        self.half = LOT / 2

    def idx(self, slot: str | None) -> int:
        name = slot if (slot and (slot in self.spec.palette or slot in SLOT_DEFAULTS)) else "structure"
        if name not in self.index:
            self.index[name] = len(self.index) + 1
        return self.index[name]

    # unit → voxel coordinate helpers
    def vx(self, x: float) -> int:
        return int(round((x + self.half) * self.s)) + 1

    def vy(self, y: float) -> int:
        return int(round(y * self.s))

    def vz(self, z: float) -> int:
        return int(round((z + self.half) * self.s)) + 1

    def box(self, cx: float, y0: float, cz: float, w: float, h: float, d: float, slot: str | None) -> None:
        x0, x1 = self.vx(cx - w / 2), max(self.vx(cx - w / 2) + 1, self.vx(cx + w / 2))
        z0, z1 = self.vz(cz - d / 2), max(self.vz(cz - d / 2) + 1, self.vz(cz + d / 2))
        y0v, y1v = self.vy(y0), max(self.vy(y0) + 1, self.vy(y0 + h))
        x0, z0, y0v = max(x0, 0), max(z0, 0), max(y0v, 0)
        x1, z1, y1v = min(x1, self.X), min(z1, self.Z), min(y1v, self.Y)
        if x1 <= x0 or z1 <= z0 or y1v <= y0v:
            return
        self.grid[x0:x1, y0v:y1v, z0:z1] = self.idx(slot)

    def cylinder(self, cx: float, y0: float, cz: float, r: float, h: float, slot: str | None) -> None:
        i = self.idx(slot)
        y0v, y1v = self.vy(y0), max(self.vy(y0) + 1, self.vy(y0 + h))
        cxv, czv, rv = (cx + self.half) * self.s + 1, (cz + self.half) * self.s + 1, r * self.s
        x0, x1 = max(int(cxv - rv) - 1, 0), min(int(cxv + rv) + 2, self.X)
        z0, z1 = max(int(czv - rv) - 1, 0), min(int(czv + rv) + 2, self.Z)
        xs = np.arange(x0, x1)[:, None] + 0.5 - cxv
        zs = np.arange(z0, z1)[None, :] + 0.5 - czv
        disk = (xs * xs + zs * zs) <= rv * rv
        for y in range(max(y0v, 0), min(y1v, self.Y)):
            sl = self.grid[x0:x1, y, z0:z1]
            sl[disk] = i

    def paint(self, xa: int, xb: int, ya: int, yb: int, za: int, zb: int, i: int) -> None:
        xa, xb = max(xa, 0), min(xb, self.X)
        za, zb = max(za, 0), min(zb, self.Z)
        ya, yb = max(ya, 0), min(yb, self.Y)
        if xb > xa and zb > za and yb > ya:
            self.grid[xa:xb, ya:yb, za:zb] = i

    def windows(self, cx: float, y0: float, cz: float, w: float, h: float, d: float, g: Glass, seed: int) -> None:
        """Paint a window grid on all four faces, one voxel deep, in the glass slot."""
        rng = np.random.default_rng(seed)
        rows = max(1, int((h - g.from_) / g.ch))
        rh = (h - g.from_) / rows
        i = self.idx(g.slot)
        cols_x = max(1, int(w / g.cw))
        cols_z = max(1, int(d / g.cw))
        for r in range(rows):
            y = y0 + g.from_ + (r + 0.5) * rh
            ya, yb = self.vy(y - g.ch * 0.22), self.vy(y + g.ch * 0.22) + 1
            for q in range(cols_x):  # north and south faces, windows spread along x
                if rng.random() > g.density:
                    continue
                u = cx - w / 2 + (q + 0.5) * w / cols_x
                ua, ub = self.vx(u - g.cw * 0.25), self.vx(u + g.cw * 0.25) + 1
                zn, zs_ = self.vz(cz - d / 2), self.vz(cz + d / 2) - 1
                self.paint(ua, ub, ya, yb, zn, zn + 1, i)
                self.paint(ua, ub, ya, yb, zs_, zs_ + 1, i)
            for q in range(cols_z):  # west and east faces, windows spread along z
                if rng.random() > g.density:
                    continue
                u = cz - d / 2 + (q + 0.5) * d / cols_z
                ua, ub = self.vz(u - g.cw * 0.25), self.vz(u + g.cw * 0.25) + 1
                xw, xe = self.vx(cx - w / 2), self.vx(cx + w / 2) - 1
                self.paint(xw, xw + 1, ya, yb, ua, ub, i)
                self.paint(xe, xe + 1, ya, yb, ua, ub, i)


def _edges(c: _Ctx, x: float, t: float, z: float, w: float, d: float, slot: str) -> None:
    c.box(x, t, z + d / 2 - NEON_T / 2, w, NEON_T, NEON_T, slot)
    c.box(x, t, z - d / 2 + NEON_T / 2, w, NEON_T, NEON_T, slot)
    c.box(x + w / 2 - NEON_T / 2, t, z, NEON_T, NEON_T, d, slot)
    c.box(x - w / 2 + NEON_T / 2, t, z, NEON_T, NEON_T, d, slot)


def _sign(c: _Ctx, p: SignPart) -> None:
    """A dark panel just outside the lot edge on one side, with 3×5 glyphs lit in the sign slot."""
    text = p.text.upper()
    w = p.width()
    half = LOT / 2 - 0.3
    px = 0.0 if p.side in ("n", "s") else (-half if p.side == "w" else half)
    pz = 0.0 if p.side in ("e", "w") else (-half if p.side == "n" else half)
    along = "x" if p.side in ("n", "s") else "z"
    if along == "x":
        c.box(px + p.x, p.y, pz, w, p.h, NEON_T, p.panel)
    else:
        c.box(px, p.y, pz + p.z, NEON_T, p.h, w, p.panel)
    # glyph cell: 3 wide + 1 gap, 5 tall; scale so the text fits the panel height with a margin
    cell = p.h / 7.0
    total = len(text) * 4 * cell - cell
    start = -total / 2
    # reads left→right for someone standing outside facing the wall: +x on the south face, +z on the west face
    flip = p.side in ("n", "e")
    for gi, ch in enumerate(text):
        rows = GLYPHS.get(ch)
        if rows is None:
            continue
        g0 = start + gi * 4 * cell
        for ry, row in enumerate(rows):
            for rx, bit in enumerate(row):
                if bit != "1":
                    continue
                u = g0 + (rx + 0.5) * cell
                if flip:
                    u = -u
                v = p.y + p.h - cell - (ry + 0.5) * cell
                if along == "x":
                    c.box(px + p.x + u, v - cell / 2, pz + (NEON_T if p.side == "s" else -NEON_T), cell, cell, NEON_T, p.slot)
                else:
                    c.box(px + (NEON_T if p.side == "e" else -NEON_T), v - cell / 2, pz + p.z + u, NEON_T, cell, cell, p.slot)


def rasterize(spec: Spec, voxels_per_unit: int = VOXELS_PER_UNIT) -> Raster:
    c = _Ctx(spec, voxels_per_unit)
    seed = 7
    for i, p in enumerate(spec.parts):
        seed += 1
        x, z, y = p.x, p.z, p.y
        if isinstance(p, PlinthPart):
            c.box(0, 0, 0, p.w, p.h, p.d, p.slot)
        elif isinstance(p, VolumePart):
            c.box(x, y, z, p.w, p.h, p.d, p.slot)
            if p.glass:
                c.windows(x, y, z, p.w, p.h, p.d, p.glass, seed)
            if p.edges:
                _edges(c, x, y + p.h, z, p.w, p.d, p.edges)
            if p.corner:
                c.box(x + p.w / 2 + NEON_T / 2, y + p.h * 0.05, z + p.d / 2 + NEON_T / 2, NEON_T, p.h * 0.9, NEON_T, p.corner)
        elif isinstance(p, FinsPart):
            for k in range(p.count):
                off = (k - (p.count - 1) / 2) * p.pitch
                fh = p.h + math.sin(k * 1.3) * p.wave
                slot = p.alt if (k % 2 and p.alt) else p.slot
                glazed = p.glass is not None and (p.glassOn == "all" or (p.glassOn == "last" and k == p.count - 1))
                if p.axis == "x":
                    c.box(x + off, y, z, p.t, fh, p.d, slot)
                    if glazed and p.glass:
                        c.windows(x + off, y, z, p.t, fh, p.d, p.glass, seed + k)
                else:
                    c.box(x, y, z + off, p.d, fh, p.t, slot)
                    if glazed and p.glass:
                        c.windows(x, y, z + off, p.d, fh, p.t, p.glass, seed + k)
        elif isinstance(p, SlabsPart):
            for k in range(p.count):
                zz = z + (k - (p.count - 1) / 2) * p.pitch
                c.box(x, y, zz, p.w, p.h, p.t, p.slot)
                if p.foot:
                    c.box(x, y, zz, p.w - 2, 0.5, p.t + 0.1, p.foot)
                if p.glass and k == p.count - 1:
                    c.windows(x, y, zz, p.w, p.h, p.t, p.glass, seed + k)
        elif isinstance(p, PylonsPart):
            for k in range(4):
                px = x + (p.spread / 2 if k % 2 else -p.spread / 2)
                pz = z + (-p.spread / 2 if k < 2 else p.spread / 2)
                c.box(px, y, pz, p.size, p.h, p.size, p.slot)
                if p.cap:
                    c.box(px, y + p.h, pz, 0.5, 0.3, 0.5, p.cap)
        elif isinstance(p, StripPart):
            c.box(x, y, z, p.len if p.axis == "x" else p.t, p.t, p.len if p.axis == "z" else p.t, p.slot)
        elif isinstance(p, MastPart):
            c.box(x, y, z, 0.5, p.h, 0.5, p.slot)
            if p.beacon:
                c.box(x, y + p.h + 0.1, z, p.beaconSize, p.beaconSize, p.beaconSize, p.beacon)
        elif isinstance(p, FacadeLightsPart):
            half = LOT / 2 - 0.55  # the façade sits just inside the lot edge, like the renderer
            for k in range(p.count):
                a = (k - (p.count - 1) / 2) * p.pitch
                slot = p.slots[k % len(p.slots)]
                if p.side == "w":
                    c.box(-half, y, a, NEON_T, p.h, 0.36, slot)
                elif p.side == "e":
                    c.box(half, y, a, NEON_T, p.h, 0.36, slot)
                elif p.side == "n":
                    c.box(a, y, -half, 0.36, p.h, NEON_T, slot)
                else:
                    c.box(a, y, half, 0.36, p.h, NEON_T, slot)
        elif isinstance(p, CylinderPart):
            c.cylinder(x, y, z, p.r, p.h, p.slot)
            if p.cap:
                c.cylinder(x, y + p.h, z, p.r * 1.05, 0.7, p.cap)
        elif isinstance(p, SetbackPart):
            y = spec.stacked_y(i)
            c.box(x, y, z, p.w, p.h, p.d, p.slot)
            if p.glass:
                c.windows(x, y, z, p.w, p.h, p.d, p.glass, seed)
            if p.edges:
                _edges(c, x, y + p.h, z, p.w, p.d, p.edges)
            if p.corner:
                c.box(x + p.w / 2 + NEON_T / 2, y + p.h * 0.05, z + p.d / 2 + NEON_T / 2, NEON_T, p.h * 0.9, NEON_T, p.corner)
        elif isinstance(p, SignPart):
            _sign(c, p)
        elif isinstance(p, BridgePart):
            cx, cz = (x + p.x2) / 2, (z + p.z2) / 2
            w = abs(p.x2 - x) + p.t if p.x != p.x2 else p.t
            d = abs(p.z2 - z) + p.t if p.z != p.z2 else p.t
            c.box(cx, y, cz, w, p.t, d, p.slot)
            if p.strip:
                c.box(cx, y + p.t, cz, max(NEON_T, w - 0.5), NEON_T, max(NEON_T, d - 0.5), p.strip)
        elif isinstance(p, AntennaArrayPart):
            for k in range(p.count):
                off = (k - (p.count - 1) / 2) * p.pitch
                ax, az = (x + off, z) if p.axis == "x" else (x, z + off)
                hk = p.h * (1.0 - 0.12 * (k % 3))  # a little unevenness, like real roof clutter
                c.box(ax, y, az, NEON_T, hk, NEON_T, p.slot)
                c.box(ax, y + hk, az, 0.4, 0.4, 0.4, p.tip)

    slots: dict[int, SlotInfo] = {i: (name, spec.color(name), spec.is_emissive(name)) for name, i in c.index.items()}
    return Raster(grid=c.grid, slots=slots)
