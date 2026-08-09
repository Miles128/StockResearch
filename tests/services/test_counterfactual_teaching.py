"""Phase 13b Counterfactual teaching — 历史情景教学服务测试（回撤/波动/估值）。"""

from datetime import date, timedelta

import pytest

from stockresearch.services.counterfactual_teaching import (
    _annualized_vol_pct,
    _bars_closes,
    _max_drawdown,
    _worst_day_pct,
    compute_counterfactual_teaching,
)


def _synthetic_bars(n: int = 250, *, start: date | None = None, end: float = 100.0) -> list[dict]:
    """自造日线：整体微涨，中间含一次明显回撤（峰值 120→谷值 70）。"""
    start = start or (date.today() - timedelta(days=n + 20))
    bars: list[dict] = []
    base = end / 120.0 * 100.0
    for i in range(n):
        day = start + timedelta(days=i + 1)
        if i < 120:
            close = base * (1.0 + i * 0.001) * (1.2 if i >= 118 else 1.0)
        elif i < 160:
            close = base * (1.2 - (i - 118) * 0.03)
        else:
            close = base * (0.7 + (i - 158) * 0.004)
        bars.append(
            {
                "date": day.isoformat(),
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": round(close, 2),
                "volume": 1000,
            }
        )
    return bars


def test_bars_closes_filters_nonpositive() -> None:
    bars = [
        {"date": "2024-01-01", "close": 10.0},
        {"date": "2024-01-02", "close": 0.0},
        {"date": "2024-01-03", "close": 11.0},
    ]
    assert _bars_closes(bars) == [("2024-01-01", 10.0), ("2024-01-03", 11.0)]


def test_max_drawdown_finds_peak_to_trough() -> None:
    series = [("d1", 100.0), ("d2", 120.0), ("d3", 90.0), ("d4", 70.0), ("d5", 75.0)]
    dd, peak, trough = _max_drawdown(series)
    assert dd is not None
    assert abs(dd - (-41.67)) < 0.1
    assert peak == "d2"
    assert trough == "d4"


def test_max_drawdown_none_when_uptrend_only() -> None:
    series = [("d1", 100.0), ("d2", 105.0), ("d3", 110.0)]
    assert _max_drawdown(series)[0] is None


def test_worst_day_pct() -> None:
    series = [("d1", 100.0), ("d2", 92.0), ("d3", 93.0)]
    worst, day = _worst_day_pct(series)
    assert day == "d2"
    assert worst is not None
    assert abs(worst - (-8.0)) < 0.01


def test_worst_day_floor() -> None:
    series = [("d1", 100.0), ("d2", 1.0), ("d3", 1.1)]
    worst, _ = _worst_day_pct(series)
    assert worst is not None
    assert worst >= -50.0


def test_annualized_vol_positive() -> None:
    bars = _synthetic_bars(60)
    series = _bars_closes(bars)
    vol = _annualized_vol_pct(series)
    assert vol is not None
    assert vol > 0


@pytest.mark.asyncio
async def test_compute_teaching_full(monkeypatch: pytest.MonkeyPatch) -> None:
    from stockresearch.services.daily_bars import BarsMeta

    async def _fake_meta(symbol: str, days: int = 250):
        return BarsMeta(
            bars=_synthetic_bars(days),
            source="warehouse",
            adjust="qfq",
            as_of="2025-01-01",
        )

    monkeypatch.setattr(
        "stockresearch.services.counterfactual_teaching.get_bars_meta_for_symbol",
        _fake_meta,
    )

    class _FakeValuation:
        async def get_valuation(self, symbol: str) -> dict[str, object]:
            return {
                "pe_ttm": 40.0,
                "pe_percentile": 0.75,
                "pe_history_count": 250,
                "pe_min": 16.0,
                "pe_max": 46.0,
                "source": "mock",
                "partial": False,
                "gaps": [],
            }

    monkeypatch.setattr(
        "stockresearch.services.counterfactual_teaching.FinancialDataProvider",
        _FakeValuation,
    )

    teaching = await compute_counterfactual_teaching("600519", position_value=300000.0)
    assert teaching.symbol == "600519"
    assert teaching.position_value == 300000.0
    concepts = {seg.concept: seg for seg in teaching.segments}
    assert set(concepts) == {"drawdown", "volatility", "valuation"}

    dd = concepts["drawdown"]
    assert not dd.partial
    assert "300000" not in dd.story or "30.0 万元" in dd.story
    assert "回撤" in dd.title
    assert "浮亏" in dd.story

    vol = concepts["volatility"]
    assert "波动率" in vol.story
    assert "持仓" in vol.story

    val = concepts["valuation"]
    assert not val.partial
    assert "PE" in val.story
    assert "分位" in val.story
    assert "缩水" in val.story  # 75% 分位 → 回中位收缩


@pytest.mark.asyncio
async def test_compute_teaching_holds_user_position_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from stockresearch.services.daily_bars import BarsMeta

    async def _fake_meta(symbol: str, days: int = 250):
        return BarsMeta(
            bars=_synthetic_bars(250),
            source="warehouse",
            adjust="qfq",
            as_of="2025-01-01",
        )

    monkeypatch.setattr(
        "stockresearch.services.counterfactual_teaching.get_bars_meta_for_symbol",
        _fake_meta,
    )

    class _FakeValuation:
        async def get_valuation(self, symbol: str) -> dict[str, object]:
            return {
                "pe_ttm": 28.0,
                "pe_percentile": 0.75,
                "pe_history_count": 250,
                "pe_min": 16.0,
                "pe_max": 46.0,
                "source": "mock",
                "partial": False,
                "gaps": [],
            }

    monkeypatch.setattr(
        "stockresearch.services.counterfactual_teaching.FinancialDataProvider",
        _FakeValuation,
    )

    teaching = await compute_counterfactual_teaching("000858", position_value=8888.0)
    assert teaching.position_value == 8888.0
    assert any("8888 元" in seg.story for seg in teaching.segments)


@pytest.mark.asyncio
async def test_compute_teaching_partial_without_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    from stockresearch.services.daily_bars import BarsMeta

    async def _fake_meta(symbol: str, days: int = 250):
        return BarsMeta(
            bars=[],
            source="unavailable",
            adjust="none",
            as_of=None,
            partial=True,
            note="日线不可用",
        )

    monkeypatch.setattr(
        "stockresearch.services.counterfactual_teaching.get_bars_meta_for_symbol",
        _fake_meta,
    )

    class _FakeValuation:
        async def get_valuation(self, symbol: str) -> dict[str, object]:
            return {
                "pe_ttm": None,
                "pe_percentile": None,
                "pe_min": None,
                "pe_max": None,
                "source": "mock",
                "partial": True,
                "gaps": ["PE 不可用"],
            }

    monkeypatch.setattr(
        "stockresearch.services.counterfactual_teaching.FinancialDataProvider",
        _FakeValuation,
    )

    teaching = await compute_counterfactual_teaching("600000", position_value=10000.0)
    assert all(seg.partial for seg in teaching.segments)
    assert teaching.bars_adjust == "none"


@pytest.mark.asyncio
async def test_compute_teaching_valuation_source_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from stockresearch.services.daily_bars import BarsMeta

    async def _fake_meta(symbol: str, days: int = 250):
        return BarsMeta(
            bars=_synthetic_bars(250),
            source="warehouse",
            adjust="qfq",
            as_of="2025-01-01",
        )

    monkeypatch.setattr(
        "stockresearch.services.counterfactual_teaching.get_bars_meta_for_symbol",
        _fake_meta,
    )

    class _FailingValuation:
        async def get_valuation(self, symbol: str) -> dict[str, object]:
            raise RuntimeError("source down")

    monkeypatch.setattr(
        "stockresearch.services.counterfactual_teaching.FinancialDataProvider",
        _FailingValuation,
    )

    teaching = await compute_counterfactual_teaching("600519", position_value=10000.0)
    concepts = {seg.concept: seg for seg in teaching.segments}
    assert concepts["valuation"].partial
    assert "稍后再看" in concepts["valuation"].story
    # 回撤/波动不受估值失败影响
    assert not concepts["drawdown"].partial
    assert not concepts["volatility"].partial
