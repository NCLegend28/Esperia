"""A quick isometric PNG of a Raster so an agent can look at what it built without opening MagicaVoxel.

Painter's algorithm over exposed voxels; three shaded faces per voxel; emissive slots drawn at full brightness.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .raster import Raster

RGB = tuple[int, int, int]


def _hex(c: str) -> RGB:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _shade(rgb: RGB, k: float) -> RGB:
    r, g, b = rgb
    return (max(0, min(255, int(r * k))), max(0, min(255, int(g * k))), max(0, min(255, int(b * k))))


def render_preview(r: Raster, path: str | Path, cell: int = 6, background: RGB = (13, 15, 23)) -> Path:
    g = r.grid
    x_dim, y_dim, z_dim = g.shape
    padded = np.zeros((x_dim + 2, y_dim + 2, z_dim + 2), dtype=np.uint8)
    padded[1:-1, 1:-1, 1:-1] = g
    core = padded[1:-1, 1:-1, 1:-1]
    exposed = (core > 0) & ((padded[2:, 1:-1, 1:-1] == 0) | (padded[1:-1, 2:, 1:-1] == 0) | (padded[1:-1, 1:-1, 2:] == 0))
    xs, ys, zs = np.nonzero(exposed)
    colors = {i: _hex(c) for i, (_n, c, _e) in r.slots.items()}
    emissive = {i for i, (_n, _c, e) in r.slots.items() if e}

    # isometric: screen u = (x - z), v = (x + z)/2 - y
    hw, hh = cell, cell // 2
    width = int((x_dim + z_dim) * hw) + 4 * cell
    height = int((x_dim + z_dim) * hh + y_dim * cell) + 4 * cell
    img = Image.new("RGB", (width, height), background)
    d = ImageDraw.Draw(img)
    ox, oy = width // 2, 2 * cell + int(y_dim * cell)

    order = np.argsort(xs + zs + ys * 0.001)  # far to near
    for k in order.tolist():
        x, y, z = int(xs[k]), int(ys[k]), int(zs[k])
        i = int(core[x, y, z])
        rgb = colors[i]
        u = ox + (x - z) * hw
        v = oy + (x + z) * hh - y * cell
        if i in emissive:
            top, left, right = _shade(rgb, 1.25), _shade(rgb, 1.1), _shade(rgb, 1.0)
        else:
            top, left, right = _shade(rgb, 1.15), _shade(rgb, 0.78), _shade(rgb, 0.58)
        if padded[x + 1, y + 2, z + 1] == 0:  # top face
            d.polygon([(u, v - cell), (u + hw, v - cell + hh), (u, v - cell + 2 * hh), (u - hw, v - cell + hh)], fill=top)
        if padded[x + 1, y + 1, z + 2] == 0:  # +z face, drawn on the left
            d.polygon([(u - hw, v - cell + hh), (u, v - cell + 2 * hh), (u, v + hh), (u - hw, v)], fill=left)
        if padded[x + 2, y + 1, z + 1] == 0:  # +x face, drawn on the right
            d.polygon([(u, v - cell + 2 * hh), (u + hw, v - cell + hh), (u + hw, v), (u, v + hh)], fill=right)

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out
