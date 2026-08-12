"""Phase 12f Market Regime — 纯规则判定单元测试。"""

from stockresearch.services.market_regime import (
    _daily_returns,
    compute_regime,
    regime_label,
)


def test_compute_regime_trend_up() -> None:
    # 25 根单调上行，20d 动量 >> 4%
    closes = [100.0 + i * 1.0 for i in range(30)]
    assert compute_regime(closes) == "trend_up"


def test_compute_regime_trend_down() -> None:
    closes = [100.0 - i * 1.0 for i in range(30)]
    assert compute_regime(closes) == "trend_down"


def test_compute_regime_choppy() -> None:
    # 20d 动量接近 0，震荡
    closes = [100.0 + (1.5 if i % 2 else -1.5) for i in range(30)]
    assert compute_regime(closes) == "choppy"


def test_compute_regime_insufficient_data() -> None:
    assert compute_regime([100.0, 101.0]) == "unknown"
    assert compute_regime([]) == "unknown"


def test_compute_regime_zero_start() -> None:
    # 倒数第 21 根（动量窗口起点）为 0 → 无法算动量，unknown
    closes = [0.0] * 21 + [100.0] * 9
    assert compute_regime(closes) == "unknown"


def test_regime_label_all() -> None:
    assert regime_label("trend_up") == "趋势上行"
    assert regime_label("trend_down") == "趋势下行"
    assert regime_label("choppy") == "震荡"
    assert regime_label("unknown") == "未知"


def test_daily_returns_skips_zero_prev() -> None:
    # prev=0 的跳空日不参与收益率（避免除零）
    returns = _daily_returns([100.0, 101.0, 0.0, 99.0])
    assert returns == [1.0, -100.0]
