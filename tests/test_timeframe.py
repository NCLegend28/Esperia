"""Date anchoring is derived from the run, never a fixed topic or model's memory."""

from datetime import date

import pytest

from esperia.timeframe import research_timeframe


@pytest.mark.parametrize("word", ["5", "five", "FIVE"])
def test_next_five_years_are_resolved_from_saved_date(word: str) -> None:
    result = research_timeframe(
        f"Compare energy companies over the next {word} years.", date(2026, 9, 21)
    )
    assert result["requested_horizon"] == {
        "start_date": "2026-09-21",
        "end_date": "2031-09-21",
        "years": 5,
    }
    assert result["as_of_date"] == "2026-09-21"


def test_other_topic_and_future_year_are_not_hardcoded() -> None:
    assert (
        research_timeframe("Coral restoration in the coming 2 years", date(2032, 3, 1))[
            "requested_horizon"
        ]["end_date"]
        == "2034-03-01"
    )


@pytest.mark.parametrize(
    "question",
    [
        "Compare growth during 2010-2015",
        "As of 2020 compare the next 5 years",
        "Compare the next 5 years against 2023",
    ],
)
def test_explicit_dates_are_preserved(question: str) -> None:
    assert "requested_horizon" not in research_timeframe(question, date(2026, 9, 21))


def test_calendar_arithmetic_handles_leap_day() -> None:
    assert (
        research_timeframe("next one year", date(2028, 2, 29))["requested_horizon"][
            "end_date"
        ]
        == "2029-02-28"
    )


def test_multiple_horizons_are_not_silently_reduced_to_the_first() -> None:
    value = research_timeframe(
        "Compare next 5 years and next 10 years", date(2026, 9, 21)
    )
    assert "requested_horizon" not in value
    assert "Multiple" in value["interpretation"]
