"""Tests for local daily bar warehouse and numeric factors."""

from datetime import date

import pytest

from stockresearch.db.models import DailyBar
from stockresearch.services.daily_bars import load_bars, upsert_bars
from stockresearch.services.factors import compute_numeric_factors
from stockresearch.services.signal_backtest import _factor_tilt


def test_upsert_and_load_daily_bars(db_session) -> None:
    bars = [
        {
            "date": "2024-01-02",
            "open": 10.0,
            "high": 11.0,
            "low": 9.5,
            "close": 10.5,
            "volume": 1000,
        },
        {
            "date": "2024-01-03",
            "open": 10.5,
            "high": 11.2,
            "low": 10.0,
            "close": 11.0,
            "volume": 1200,
        },
    ]
    touched = upsert_bars(db_session, "600519", bars)
    assert touched == 2
    loaded = load_bars(db_session, "600519", days=10)
    assert len(loaded) == 2
    assert loaded[-1]["close"] == 11.0
    row = db_session.query(DailyBar).filter_by(symbol="600519", trade_date=date(2024, 1, 3)).one()
    assert row.adj == "qfq"


@pytest.mark.asyncio
async def test_compute_numeric_factors_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_bars(symbol: str, days: int = 90):
        return [
            {
                "date": f"2024-01-{i + 1:02d}",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10 + i * 0.1,
                "volume": 1000,
            }
            for i in range(40)
        ]

    monkeypatch.setattr(
        "stockresearch.services.factors.get_bars_for_symbol",
        _fake_bars,
    )
    factors = await compute_numeric_factors("600519")
    keys = {f.key for f in factors}
    assert {"momentum_20d", "volatility_20d", "pe_percentile"} <= keys
    assert len(factors) >= 3
    pe = next(f for f in factors if f.key == "pe_percentile")
    assert pe.percentile is not None
    assert pe.partial is False


def test_factor_tilt_from_payload() -> None:
    assert _factor_tilt({"factors": [{"key": "momentum_20d", "value": 8.0}]}) == "bullish"
    assert _factor_tilt({"factors": [{"key": "momentum_20d", "value": -8.0}]}) == "bearish"
    assert _factor_tilt({"factors": [{"key": "pe_percentile", "percentile": 0.2}]}) == "bullish"
