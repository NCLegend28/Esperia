"""Write a MagicaVoxel .vox (format 150) from a Raster.

MagicaVoxel is Z-up; our grid is Y-up, so (x, y, z) → (x, z, y). Palette index i lives at RGBA[i-1].
Emissive slots get a MATL chunk of type _emit so the voxels glow inside MagicaVoxel and on export.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

from .raster import Raster

MAX_DIM = 256


def _chunk(tag: bytes, content: bytes, children: bytes = b"") -> bytes:
    return tag + struct.pack("<ii", len(content), len(children)) + content + children


def _dict(pairs: dict[str, str]) -> bytes:
    out = struct.pack("<i", len(pairs))
    for k, v in pairs.items():
        kb, vb = k.encode(), v.encode()
        out += struct.pack("<i", len(kb)) + kb + struct.pack("<i", len(vb)) + vb
    return out


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def vox_bytes(r: Raster) -> bytes:
    x_dim, y_dim, z_dim = r.size
    if max(x_dim, y_dim, z_dim) > MAX_DIM:
        raise ValueError(f"model {x_dim}x{y_dim}x{z_dim} exceeds MagicaVoxel's {MAX_DIM} per axis; lower voxels_per_unit")
    xs, ys, zs = np.nonzero(r.grid)
    idx = r.grid[xs, ys, zs]
    # Y-up → Z-up: MagicaVoxel (x, y, z) = ours (x, z, y)
    xyzi = np.stack([xs, zs, ys, idx], axis=1).astype(np.uint8).tobytes()
    size = struct.pack("<iii", x_dim, z_dim, y_dim)

    palette = bytearray()
    for i in range(1, 256):
        if i in r.slots:
            palette += bytes([*_hex(r.slots[i][1]), 255])
        else:
            palette += bytes([0, 0, 0, 255])
    palette += bytes([0, 0, 0, 0])

    children = _chunk(b"SIZE", size)
    children += _chunk(b"XYZI", struct.pack("<i", len(xs)) + xyzi)
    children += _chunk(b"RGBA", bytes(palette))
    for i, (_name, _color, emissive) in r.slots.items():
        if emissive:
            children += _chunk(b"MATL", struct.pack("<i", i) + _dict({"_type": "_emit", "_emit": "1", "_flux": "2"}))
    return b"VOX " + struct.pack("<i", 150) + _chunk(b"MAIN", b"", children)


def write_vox(r: Raster, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(vox_bytes(r))
    return out
