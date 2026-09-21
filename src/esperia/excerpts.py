"""Deterministic source excerpts for local-model citation selection.

Example: catalog = excerpt_catalog(sources)
Models select IDs; source IDs and verbatim quotes come from archived text, not generation.
This verifies provenance only, never whether a statement follows from a quote.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from esperia.evidence import Source
from esperia.settings import Settings


@dataclass(frozen=True)
class Excerpt:
    """An exact, bounded slice of one archived source."""

    id: str
    source_id: str
    start: int
    end: int
    quote: str


def excerpt_catalog(
    sources: Sequence[Source], settings: Settings | None = None
) -> dict[str, Excerpt]:
    """Index configured overlapping slices while preserving exact source text."""
    settings = settings or Settings()
    result: dict[str, Excerpt] = {}
    for source in sources:
        offset = 0
        number = 0
        for part in source.text.split("\n[EXCERPT BREAK]\n"):
            for local_start in range(0, len(part), settings.excerpt_stride):
                end = min(local_start + settings.excerpt_chars, len(part))
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
