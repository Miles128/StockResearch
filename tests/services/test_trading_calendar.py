"""Trading calendar validation."""

from datetime import date

import pytest

from stockresearch.core.exceptions import ValidationError
from stockresearch.services import trading_calendar as cal_mod
from stockresearch.services.trading_calendar import validate_buy_date


def test_validate_buy_date_rejects_weekend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cal_mod,
        "_load_trading_days",
        lambda: frozenset({date(2026, 5, 25)}),
    )
    with pytest.raises(ValidationError, match="不是 A 股交易日"):
        validate_buy_date(date(2026, 5, 24))


def test_validate_buy_date_accepts_trading_day(monkeypatch: pytest.MonkeyPatch) -> None:
    d = date(2026, 5, 25)
    monkeypatch.setattr(cal_mod, "_load_trading_days", lambda: frozenset({d}))
    validate_buy_date(d)


def test_validate_buy_date_allows_none() -> None:
    validate_buy_date(None)
