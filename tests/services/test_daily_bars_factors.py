"""Tests for local daily bar warehouse and numeric factors."""

from datetime import date

import pytest

from stockresearch.db.models import DailyBar
from stockresearch.services.daily_bars import load_bars, upsert_bars
from stockresearch.services.factors import compute_numeric_factors
from stockresearch.services.signal_backtest import _build_sample_bias_note, _factor_tilt


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
    loaded, adj = load_bars(db_session, "600519", days=10)
    assert adj == "qfq"
    assert len(loaded) == 2
    assert loaded[-1]["close"] == 11.0
    row = db_session.query(DailyBar).filter_by(symbol="600519", trade_date=date(2024, 1, 3)).one()
    assert row.adj == "qfq"


@pytest.mark.asyncio
async def test_compute_numeric_factors_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    from stockresearch.services.daily_bars import BarsMeta

    async def _fake_meta(symbol: str, days: int = 90):
        return BarsMeta(
            bars=[
                {
                    "date": f"2024-01-{i + 1:02d}",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10 + i * 0.1,
                    "volume": 1000,
                }
                for i in range(40)
            ],
            source="warehouse",
            adjust="qfq",
            as_of="2024-01-40",
        )

    monkeypatch.setattr(
        "stockresearch.services.factors.get_bars_meta_for_symbol",
        _fake_meta,
    )
    factors, provenance = await compute_numeric_factors("600519")
    keys = {f.key for f in factors}
    assert {"momentum_20d", "volatility_20d", "pe_percentile"} <= keys
    assert len(factors) >= 3
    assert provenance.adjust == "qfq"
    pe = next(f for f in factors if f.key == "pe_percentile")
    assert pe.percentile is not None
    assert pe.partial is False


@pytest.mark.asyncio
async def test_compute_numeric_factors_on_unadjusted_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    from stockresearch.services.daily_bars import BarsMeta

    async def _fake_meta(symbol: str, days: int = 90):
        return BarsMeta(
            bars=[
                {
                    "date": f"2024-01-{i + 1:02d}",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10 + i * 0.1,
                    "volume": 1000,
                }
                for i in range(40)
            ],
            source="sina",
            adjust="none",
            as_of="2024-02-09",
            partial=True,
            note="前复权(qfq)不可用，动量/波动暂用未复权日线（分红/送转窗口会偏）",
        )

    monkeypatch.setattr(
        "stockresearch.services.factors.get_bars_meta_for_symbol",
        _fake_meta,
    )
    factors, provenance = await compute_numeric_factors("600519")
    mom = next(f for f in factors if f.key == "momentum_20d")
    vol = next(f for f in factors if f.key == "volatility_20d")
    assert mom.value is not None
    assert vol.value is not None
    assert mom.partial is True
    assert vol.partial is True
    assert provenance.adjust == "none"
    assert provenance.partial is True


def test_upsert_rejects_adj_mix_by_replacing(db_session) -> None:
    upsert_bars(
        db_session,
        "600519",
        [{"date": "2024-01-02", "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 1}],
        adj="none",
    )
    upsert_bars(
        db_session,
        "600519",
        [{"date": "2024-01-03", "open": 10, "high": 11, "low": 9, "close": 11.0, "volume": 1}],
        adj="qfq",
    )
    loaded, adj = load_bars(db_session, "600519", days=10, require_adj="qfq")
    assert adj == "qfq"
    assert len(loaded) == 1
    assert loaded[0]["close"] == 11.0


def test_factor_tilt_from_payload() -> None:
    assert _factor_tilt({"factors": [{"key": "momentum_20d", "value": 8.0}]}) == "bullish"
    assert _factor_tilt({"factors": [{"key": "momentum_20d", "value": -8.0}]}) == "bearish"
    assert _factor_tilt({"factors": [{"key": "pe_percentile", "percentile": 0.2}]}) == "bullish"
