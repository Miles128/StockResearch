"""Tests for the Phase 10 L2 pricing bridge service.

Pure helpers (`_price_change_pct`, `_earnings_growth`, `_contribs`) are
network-free and tested directly; `compute_pricing_bridge` is exercised with
monkey-patched bars + valuation providers.
"""

from __future__ import annotations

import pytest

from stockresearch.core.schemas import NumericFactorOut
from stockresearch.services.pricing_bridge import (
    _contribs,
    _earnings_growth,
    _price_change_pct,
    compute_pricing_bridge,
)


def _factor(key: str, value: float | None, *, partial: bool = False) -> NumericFactorOut:
    return NumericFactorOut(
        key=key,
        label=key,
        value=value,
        as_of="2024-01-30",
        unit="%",
        partial=partial,
    )


def test_price_change_pct_60d_qfq() -> None:
    closes = [100.0 + i for i in range(61)]  # 100..160
    pct, label, gap = _price_change_pct(closes, window=60)
    assert pct == round((160.0 / 100.0 - 1.0) * 100.0, 2)
    assert label == "60d qfq"
    assert gap is None


def test_price_change_pct_falls_back_to_20d_when_short() -> None:
    closes = [100.0 + i * 0.5 for i in range(25)]  # 25 bars only
    pct, label, gap = _price_change_pct(closes, window=60)
    assert pct is not None
    assert "20d" in label
    assert gap and "60" in gap


def test_price_change_pct_too_short_returns_none() -> None:
    closes = [10.0, 11.0, 12.0]
    pct, label, gap = _price_change_pct(closes, window=60)
    assert pct is None
    assert gap is not None


def test_earnings_growth_prefers_np_yoy() -> None:
    factors = [
        _factor("np_yoy", 18.5),
        _factor("revenue_yoy", 12.0),
    ]
    g, src, gap = _earnings_growth(factors)
    assert g == 18.5
    assert src == "np_yoy"
    assert gap is None


def test_earnings_growth_falls_back_to_revenue_yoy() -> None:
    factors = [
        _factor("np_yoy", None, partial=True),
        _factor("revenue_yoy", 9.0),
    ]
    g, src, gap = _earnings_growth(factors)
    assert g == 9.0
    assert src == "revenue_yoy"
    assert gap and "revenue_yoy" in gap


def test_earnings_growth_missing() -> None:
    g, src, gap = _earnings_growth([])
    assert g is None
    assert src is None
    assert gap is not None


def test_contribs_full_decomposition() -> None:
    # pe_start=20, pe_end=25 -> multiple_contrib = 25%; g=10 -> earnings=10
    multiple, earnings, partial, gaps = _contribs(
        pe_start=20.0, pe_end=25.0, g=10.0, price_change_pct=34.0
    )
    assert multiple == 25.0
    assert earnings == 10.0
    # |34 - (25+10)| = 1 <= 15 -> not partial
    assert partial is False
    assert gaps == []


def test_contribs_identity_residual_marks_partial() -> None:
    # price 50, m+e = 35 -> residual 15 (boundary, not partial); 16 -> partial
    multiple, earnings, partial, gaps = _contribs(
        pe_start=20.0, pe_end=25.0, g=10.0, price_change_pct=51.0
    )
    assert partial is True
    assert any("残差" in gp for gp in gaps)


def test_contribs_missing_pe_start() -> None:
    multiple, earnings, partial, gaps = _contribs(
        pe_start=None, pe_end=25.0, g=10.0, price_change_pct=12.0
    )
    assert multiple is None
    assert earnings == 10.0
    assert partial is True
    assert any("pe_start" in gp or "PE 起点" in gp for gp in gaps)


def test_contribs_missing_all() -> None:
    multiple, earnings, partial, gaps = _contribs(
        pe_start=None, pe_end=None, g=None, price_change_pct=None
    )
    assert multiple is None
    assert earnings is None
    assert partial is True
    assert gaps  # non-empty


@pytest.mark.asyncio
async def test_compute_pricing_bridge_honest_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    from stockresearch.services.daily_bars import BarsMeta

    async def _fake_meta(symbol: str, days: int = 90):
        return BarsMeta(
            bars=[
                {
                    "date": f"2024-01-{i + 1:02d}",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 100.0 + i,
                    "volume": 1000,
                }
                for i in range(61)
            ],
            source="warehouse",
            adjust="qfq",
            as_of="2024-03-01",
        )

    monkeypatch.setattr(
        "stockresearch.services.pricing_bridge.get_bars_meta_for_symbol",
        _fake_meta,
    )

    class _FakeProvider:
        async def get_valuation(self, symbol: str):
            return {
                "pe_ttm": 28.0,
                "pe_percentile": 0.42,
                "source": "mock",
                "partial": False,
                "gaps": [],
            }

    monkeypatch.setattr(
        "stockresearch.services.pricing_bridge.FinancialDataProvider",
        _FakeProvider,
    )

    factors = [
        _factor("pe_percentile", 42.0),
        _factor("np_yoy", 15.0),
        _factor("revenue_yoy", 10.0),
    ]
    out = await compute_pricing_bridge("600519", factors)
    assert out.window_label.startswith("60d")
    assert out.price_change_pct == round((160.0 / 100.0 - 1.0) * 100.0, 2)
    assert out.pe_end == 28.0
    # pe_start not historically exposed -> None, gap, partial
    assert out.pe_start is None
    assert out.multiple_contrib_pct is None
    assert out.earnings_contrib_pct == 15.0
    assert out.partial is True
    assert out.gaps  # non-empty
    # implied growth skipped per honest-partial policy
    assert out.implied_growth_pct is None
    assert any("implied" in g or "growth" in g for g in out.gaps)
    assert "np_yoy" in out.factor_keys_used
    assert "pe_percentile" in out.factor_keys_used
    assert out.point_in_time is True


@pytest.mark.asyncio
async def test_compute_pricing_bridge_requests_61_bars_for_60d(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from stockresearch.services.daily_bars import BarsMeta

    requested_days: list[int] = []

    async def _fake_meta(symbol: str, days: int = 90):
        requested_days.append(days)
        return BarsMeta(
            bars=[
                {
                    "date": f"2024-01-{i + 1:02d}",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 100.0 + i,
                    "volume": 1000,
                }
                for i in range(61)
            ],
            source="warehouse",
            adjust="qfq",
            as_of="2024-03-01",
        )

    monkeypatch.setattr(
        "stockresearch.services.pricing_bridge.get_bars_meta_for_symbol",
        _fake_meta,
    )

    class _FakeProvider:
        async def get_valuation(self, symbol: str):
            return {"pe_ttm": 20.0, "source": "mock", "partial": False, "gaps": []}

    monkeypatch.setattr(
        "stockresearch.services.pricing_bridge.FinancialDataProvider",
        _FakeProvider,
    )

    out = await compute_pricing_bridge("600519", [_factor("np_yoy", 5.0)])
    assert requested_days == [61]
    assert out.window_label.startswith("60d")
    assert "20d" not in out.window_label
    assert out.price_change_pct == round((160.0 / 100.0 - 1.0) * 100.0, 2)


@pytest.mark.asyncio
async def test_compute_pricing_bridge_60_closes_falls_back_to_20d(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from stockresearch.services.daily_bars import BarsMeta

    async def _fake_meta(symbol: str, days: int = 90):
        return BarsMeta(
            bars=[
                {
                    "date": f"2024-01-{i + 1:02d}",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 100.0 + i * 0.5,
                    "volume": 1000,
                }
                for i in range(60)
            ],
            source="warehouse",
            adjust="qfq",
            as_of="2024-03-01",
        )

    monkeypatch.setattr(
        "stockresearch.services.pricing_bridge.get_bars_meta_for_symbol",
        _fake_meta,
    )

    class _FakeProvider:
        async def get_valuation(self, symbol: str):
            return {"pe_ttm": 20.0, "source": "mock", "partial": False, "gaps": []}

    monkeypatch.setattr(
        "stockresearch.services.pricing_bridge.FinancialDataProvider",
        _FakeProvider,
    )

    out = await compute_pricing_bridge("600519", [_factor("np_yoy", 5.0)])
    assert "20d" in out.window_label
    assert out.price_change_pct is not None
    assert any("60" in g for g in out.gaps)


@pytest.mark.asyncio
async def test_compute_pricing_bridge_no_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    from stockresearch.services.daily_bars import BarsMeta

    async def _fake_meta(symbol: str, days: int = 90):
        return BarsMeta(bars=[], source="unavailable", adjust="none", as_of=None, partial=True)

    monkeypatch.setattr(
        "stockresearch.services.pricing_bridge.get_bars_meta_for_symbol",
        _fake_meta,
    )

    class _FakeProvider:
        async def get_valuation(self, symbol: str):
            return {"pe_ttm": None, "source": "none", "partial": True, "gaps": ["估值不可用"]}

    monkeypatch.setattr(
        "stockresearch.services.pricing_bridge.FinancialDataProvider",
        _FakeProvider,
    )

    out = await compute_pricing_bridge("000001", [])
    assert out.price_change_pct is None
    assert out.pe_end is None
    assert out.earnings_contrib_pct is None
    assert out.partial is True
    assert out.gaps
