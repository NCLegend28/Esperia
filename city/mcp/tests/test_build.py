"""Builds the kit specs end to end: validate → rasterise → .vox / .gltf / .png."""

import json
import struct
from pathlib import Path

import pytest

from voxkit import rasterize, render_preview, validate, write_gltf, write_vox

KIT = Path(__file__).resolve().parents[2] / "kit"


@pytest.mark.parametrize("sid", ["u1", "u3", "u2", "t1"])
def test_kit_specs_build(tmp_path: Path, sid: str) -> None:
    data = json.loads((KIT / f"{sid}.json").read_text())
    spec, errors, _warnings = validate(data)
    assert spec is not None, errors
    assert not errors
    r = rasterize(spec)
    assert r.count() > 500
    assert max(r.size) <= 256
    vox = write_vox(r, tmp_path / f"{sid}.vox")
    b = vox.read_bytes()
    assert b[:4] == b"VOX " and struct.unpack("<i", b[4:8])[0] == 150
    assert b"XYZI" in b and b"RGBA" in b and b"MATL" in b
    g = json.loads(write_gltf(r, tmp_path / f"{sid}.gltf").read_text())
    assert g["asset"]["version"] == "2.0"
    names = {m["name"] for m in g["meshes"]}
    assert {"structure", "emissive"} <= names
    png = render_preview(r, tmp_path / f"{sid}.png")
    assert png.stat().st_size > 1000


def test_validation_rejects_bad_parts() -> None:
    spec, errors, _ = validate({"parts": [{"type": "volume", "w": 4}]})
    assert spec is None and errors and any("required" in e.lower() or "missing" in e.lower() for e in errors)
    spec, errors, _ = validate({"parts": [{"type": "spire"}]})
    assert spec is None and errors


def test_validation_warns_off_lot() -> None:
    spec, errors, warnings = validate(
        {
            "parts": [
                {"type": "plinth", "w": 13, "d": 13, "h": 1},
                {"type": "volume", "x": 6, "w": 8, "d": 4, "h": 5, "slot": "structure"},
            ]
        }
    )
    assert spec is not None and not errors
    assert any("extends past the lot in x" in w for w in warnings)
