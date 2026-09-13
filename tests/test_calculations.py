"""Check scenario units and invalid financial assumptions."""

from decimal import Decimal

import pytest

from esperia.calculations import portfolio_impact, runway_months


def test_portfolio_impact_uses_percentage_points() -> None:
    assert portfolio_impact(Decimal("15"), Decimal("-60")) == Decimal("-9")
    assert portfolio_impact(Decimal("4.6"), Decimal("-60")) == Decimal("-2.76")


def test_runway_uses_quarterly_burn() -> None:
    assert runway_months(Decimal("100"), Decimal("25")) == Decimal("12")
    with pytest.raises(ValueError):
        runway_months(Decimal("100"), Decimal("0"))


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_inputs_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        portfolio_impact(Decimal(value), Decimal("0"))
