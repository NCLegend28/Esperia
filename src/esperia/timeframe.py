"""Anchor relative research horizons to a saved date, without topic-specific years.

Example: research_timeframe('next 5 years', date(2026, 9, 21)).
Explicit dates take precedence; unrecognized phrasing remains for the worker to interpret.
"""

import calendar
import re
from datetime import date
from typing import Any

# Language equivalents, not configurable research choices.
YEAR_WORDS = dict(
    zip(
        ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"),
        range(1, 11),
    )
)


def research_timeframe(question: str, as_of: date) -> dict[str, Any]:
    """Resolve unambiguous 'next/coming N years'; preserve explicit historical dates."""
    context: dict[str, Any] = {
        "as_of_date": as_of.isoformat(),
        "date_basis": "UTC job start",
        "rule": "Resolve relative dates from as_of_date, never from a source's publication date or model memory. Explicit dates in the user's question take precedence. A recent retrieval does not make an old publication current. Use older forecasts as historical context, not as evidence of the requested future outlook without current corroboration.",
    }
    matches = list(
        re.finditer(
            r"\b(?:next|coming)\s+(\d{1,4}|" + "|".join(YEAR_WORDS) + r")\s+years?\b",
            question,
            re.IGNORECASE,
        )
    )
    if not matches:
        return context
    if len(matches) != 1:
        context["interpretation"] = (
            "Multiple relative horizons present; preserve each requested timeframe."
        )
        return context
    match = matches[0]
    rest = question[: match.start()] + question[match.end() :]
    if re.search(r"\b\d{4}\b", rest):
        context["interpretation"] = (
            "Explicit dates present; preserve the user-defined timeframe."
        )
        return context
    token = match.group(1).lower()
    years = int(token) if token.isdigit() else YEAR_WORDS[token]
    if not 0 < years <= date.max.year - as_of.year:
        context["interpretation"] = (
            "Requested horizon is outside the supported calendar range; disclose ambiguity."
        )
        return context
    end_year = as_of.year + years
    end = as_of.replace(
        year=end_year, day=min(as_of.day, calendar.monthrange(end_year, as_of.month)[1])
    )
    context["requested_horizon"] = {
        "start_date": as_of.isoformat(),
        "end_date": end.isoformat(),
        "years": years,
    }
    return context
