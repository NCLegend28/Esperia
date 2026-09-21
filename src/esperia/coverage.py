"""Shared collection coverage gates. Example: coverage_tasks(load_coverage(output))."""

import json
from pathlib import Path
from typing import Any

from esperia.followups import Followup


def load_coverage(output: Path) -> dict[str, Any] | None:
    """Read the discovery record, or return None for explicit-manifest collection."""
    path = output / "evidence/discovery.json"
    return json.loads(path.read_text()) if path.exists() else None


def coverage_tasks(coverage: dict[str, Any] | None) -> list[Followup]:
    """Require positive coverage for every requested seed, including omitted counts."""
    if coverage is None:
        return []
    counts = coverage.get("seed_coverage", {})
    seeds = coverage.get("seeds", list(counts))
    if not seeds:
        return [
            Followup(
                "collector",
                "missing_evidence",
                "Discovery seed coverage is unavailable; recollect evidence",
            )
        ]
    return [
        Followup(
            "collector",
            "missing_evidence",
            f"No readable document collected for seed: {seed}",
        )
        for seed in seeds
        if counts.get(seed, 0) <= 0
    ]
