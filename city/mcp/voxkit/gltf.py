"""Write a self-contained glTF 2.0 (.gltf, base64 buffer) from a Raster, in board units, Y-up, lot-centred.

Two meshes: "structure" (lit, vertex colours) and "emissive" (KHR_materials_unlit, vertex colours) — the city
renderer flags any mesh named "emissive" for the bloom pass. Exposed faces are greedily merged into rectangles.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from .grammar import LOT
from .raster import VOXELS_PER_UNIT, Raster

Vec3 = tuple[float, float, float]
F32 = npt.NDArray[np.float32]
U32 = npt.NDArray[np.uint32]

ARRAY_BUFFER = 34962
ELEMENT_ARRAY_BUFFER = 34963
FLOAT = 5126
UNSIGNED_INT = 5125


def _hex(c: str) -> Vec3:
    c = c.lstrip("#")
    return int(c[0:2], 16) / 255.0, int(c[2:4], 16) / 255.0, int(c[4:6], 16) / 255.0


def _greedy_quads(mask: npt.NDArray[np.uint8]) -> list[tuple[int, int, int, int, int]]:
    """Greedy rectangles over a 2D palette-index mask. Returns (u, v, w, h, index) with index > 0."""
    m = mask.copy()
    U, V = m.shape
    out: list[tuple[int, int, int, int, int]] = []
    for v in range(V):
        u = 0
        while u < U:
            i = int(m[u, v])
            if i == 0:
                u += 1
                continue
            w = 1
            while u + w < U and m[u + w, v] == i:
                w += 1
            h = 1
            while v + h < V and bool(np.all(m[u : u + w, v + h] == i)):
                h += 1
            out.append((u, v, w, h, i))
            m[u : u + w, v : v + h] = 0
            u += w
    return out


def _mesh_arrays(r: Raster, want_emissive: bool, scale: float) -> tuple[F32, F32, F32, U32]:
    """Exposed faces, greedily merged into rectangles per slice, as quads with flat normals and vertex colours."""
    g = r.grid
    dims = g.shape
    colors = {i: _hex(c) for i, (_n, c, _e) in r.slots.items()}
    emissive = {i for i, (_n, _c, e) in r.slots.items() if e}
    keep = np.zeros(256, dtype=bool)
    for i in colors:
        keep[i] = (i in emissive) == want_emissive
    sel = keep[g]  # voxels of the wanted kind
    pos: list[Vec3] = []
    nrm: list[Vec3] = []
    col: list[Vec3] = []
    idx: list[int] = []
    half = LOT / 2

    def emit(quad: list[Vec3], n: Vec3, c: Vec3) -> None:
        base = len(pos)
        pos.extend(quad)
        nrm.extend([n] * 4)
        col.extend([c] * 4)
        idx.extend([base, base + 1, base + 2, base, base + 2, base + 3])

    def world(x: float, y: float, z: float) -> Vec3:
        return ((x - 1) / scale - half, y / scale, (z - 1) / scale - half)

    # axis a is the face normal axis; (b, c) span the slice
    for a in range(3):
        b, c = (a + 1) % 3, (a + 2) % 3
        for direction in (1, -1):
            for k in range(dims[a]):
                # neighbour slice along the normal
                kn = k + direction
                sl = np.take(g, k, axis=a)
                own = np.take(sel, k, axis=a)
                if 0 <= kn < dims[a]:
                    blocked = np.take(g, kn, axis=a) > 0
                else:
                    blocked = np.zeros_like(own)
                mask = np.where(own & ~blocked, sl, 0).astype(np.uint8)
                if not mask.any():
                    continue
                for u, v, w, h, i in _greedy_quads(mask):
                    coord = k + (1 if direction == 1 else 0)
                    p0 = [0.0, 0.0, 0.0]

                    def pt(du: float, dv: float) -> Vec3:
                        q = list(p0)
                        q[a] = float(coord)
                        q[b] = float(u + du)
                        q[c] = float(v + dv)
                        return world(q[0], q[1], q[2])

                    corners = [pt(0, 0), pt(w, 0), pt(w, h), pt(0, h)]
                    # winding: normal must point along `direction` on axis a
                    n = [0.0, 0.0, 0.0]
                    n[a] = float(direction)
                    if (direction == 1) == (a == 1):  # y is special: (b,c) = (z,x) flips handedness
                        corners = [corners[0], corners[3], corners[2], corners[1]]
                    emit(corners, (n[0], n[1], n[2]), colors[i])
    return (
        np.array(pos, dtype=np.float32).reshape(-1, 3),
        np.array(nrm, dtype=np.float32).reshape(-1, 3),
        np.array(col, dtype=np.float32).reshape(-1, 3),
        np.array(idx, dtype=np.uint32),
    )


def gltf_dict(r: Raster, scale: float = VOXELS_PER_UNIT, name: str = "building") -> dict[str, Any]:
    buf = bytearray()
    views: list[dict[str, Any]] = []
    accessors: list[dict[str, Any]] = []
    meshes: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []

    def add_view(arr: npt.NDArray[Any], target: int) -> int:
        while len(buf) % 4:
            buf.append(0)
        off = len(buf)
        buf.extend(arr.tobytes())
        views.append({"buffer": 0, "byteOffset": off, "byteLength": arr.nbytes, "target": target})
        return len(views) - 1

    def add_accessor(arr: npt.NDArray[Any], target: int, ctype: int, atype: str, minmax: bool = False) -> int:
        v = add_view(arr, target)
        acc: dict[str, Any] = {"bufferView": v, "componentType": ctype, "count": int(arr.shape[0]), "type": atype}
        if minmax:
            acc["min"] = arr.min(axis=0).tolist()
            acc["max"] = arr.max(axis=0).tolist()
        accessors.append(acc)
        return len(accessors) - 1

    materials: list[dict[str, Any]] = [
        {
            "name": "structure",
            "pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1], "metallicFactor": 0.0, "roughnessFactor": 0.9},
        },
        {
            "name": "emissive",
            "pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1], "metallicFactor": 0.0, "roughnessFactor": 1.0},
            "extensions": {"KHR_materials_unlit": {}},
        },
    ]
    for mi, (mesh_name, want_e) in enumerate((("structure", False), ("emissive", True))):
        pos, nrm, col, idx = _mesh_arrays(r, want_e, scale)
        if len(idx) == 0:
            continue
        p = add_accessor(pos, ARRAY_BUFFER, FLOAT, "VEC3", True)
        n = add_accessor(nrm, ARRAY_BUFFER, FLOAT, "VEC3")
        c = add_accessor(col, ARRAY_BUFFER, FLOAT, "VEC3")
        i = add_accessor(idx, ELEMENT_ARRAY_BUFFER, UNSIGNED_INT, "SCALAR")
        meshes.append(
            {
                "name": mesh_name,
                "primitives": [{"attributes": {"POSITION": p, "NORMAL": n, "COLOR_0": c}, "indices": i, "material": mi}],
            }
        )
        nodes.append({"name": mesh_name, "mesh": len(meshes) - 1})

    return {
        "asset": {"version": "2.0", "generator": "esperia-voxkit"},
        "extensionsUsed": ["KHR_materials_unlit"],
        "scene": 0,
        "scenes": [{"name": name, "nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [
            {"byteLength": len(buf), "uri": "data:application/octet-stream;base64," + base64.b64encode(bytes(buf)).decode()}
        ],
    }


def write_gltf(r: Raster, path: str | Path, name: str = "building") -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(gltf_dict(r, name=name)))
    return out
