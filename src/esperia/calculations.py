"""Reproducible scenario arithmetic; these functions make no recommendations.

Example: portfolio_impact(Decimal("15"), Decimal("-60")) == Decimal("-9")
"""

from decimal import Decimal


def portfolio_impact(weight_percent: Decimal, asset_return_percent: Decimal) -> Decimal:
    """Return portfolio percentage-point impact, holding all other assets flat."""
    if not weight_percent.is_finite() or not asset_return_percent.is_finite():
        raise ValueError("Inputs must be finite")
    if not 0 <= weight_percent <= 100 or asset_return_percent < -100:
        raise ValueError("Invalid long-only, unlevered scenario")
    return weight_percent * asset_return_percent / 100


def runway_months(cash: Decimal, quarterly_cash_burn: Decimal) -> Decimal:
    """Estimate runway assuming constant positive cash burn; amounts must share units.

    Example: runway_months(Decimal("100"), Decimal("25")) == Decimal("12")
    Excludes financing, debt maturities and changing burn; not a solvency forecast.
    """
    if not cash.is_finite() or not quarterly_cash_burn.is_finite():
        raise ValueError("Inputs must be finite")
    if cash < 0 or quarterly_cash_burn <= 0:
        raise ValueError("Cash must be nonnegative and burn strictly positive")
    return cash / quarterly_cash_burn * 3
