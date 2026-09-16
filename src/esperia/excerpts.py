"""Deterministic source excerpts for local-model citation selection.

Example: catalog = excerpt_catalog(sources)
Models select IDs; source IDs and verbatim quotes come from archived text, not generation.
This verifies provenance only, never whether a statement follows from a quote.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from esperia.evidence import Source


@dataclass(frozen=True)
class Excerpt:
    """An exact, bounded slice of one archived source."""

    id: str
    source_id: str
    start: int
    end: int
    quote: str


def excerpt_catalog(sources: Sequence[Source]) -> dict[str, Excerpt]:
    """Index overlapping 500-character slices without dropping source text."""
    result: dict[str, Excerpt] = {}
    for source in sources:
        offset = 0
        number = 0
        for part in source.text.split("\n[EXCERPT BREAK]\n"):
            for local_start in range(0, len(part), 400):
                end = min(local_start + 500, len(part))
                if end - local_start < 20:
                    continue
                number += 1
                start = offset + local_start
                identifier = f"{source.id}:E{number}"
                result[identifier] = Excerpt(
                    identifier,
                    source.id,
                    start,
                    offset + end,
                    source.text[start : offset + end],
                )
            offset += len(part) + len("\n[EXCERPT BREAK]\n")
    return result
