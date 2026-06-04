"""Holding P&L and annualized return calculations."""

from datetime import date, timedelta

from stockresearch.services.holding_metrics import (
    annualized_return_pct,
    profit_amount,
    profit_pct,
)


def test_profit_amount_and_pct() -> None:
    assert profit_amount(100.0, 100, 110.0) == 1000.0
    assert profit_pct(100.0, 110.0) == 10.0
    assert profit_pct(100.0, 90.0) == -10.0


def test_annualized_requires_buy_date() -> None:
    assert annualized_return_pct(100.0, 110.0, None) is None


def test_annualized_positive_return() -> None:
    buy = date.today() - timedelta(days=365)
    result = annualized_return_pct(100.0, 110.0, buy)
    assert result is not None
    assert 9.0 < result < 11.0
