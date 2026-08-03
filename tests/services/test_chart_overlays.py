"""Chart overlay algorithm tests (Python port of chartTrendlines.ts)."""

from stockresearch.services.chart_overlays import (
    Bar,
    TrendLineOptions,
    build_overlay_set,
    detect_trend_lines,
    find_pivots,
)


def _zigzag_uptrend(n: int = 80) -> list[Bar]:
    """Straight uptrend with ±2.5 zigzag so pivots sit on two clean lines."""
    bars: list[Bar] = []
    for i in range(n):
        mid = 100.0 + 0.5 * i
        wave = 2.0 if (i % 10) < 5 else -2.0
        bars.append(
            Bar(
                date=f"2026-{(i // 22) + 4:02d}-{(i % 22) + 1:02d}",
                high=mid + wave + 0.5,
                low=mid + wave - 0.5,
                close=mid,
            )
        )
    return bars


def test_find_pivots_detects_zigzag_extremes() -> None:
    bars = _zigzag_uptrend()
    highs, lows = find_pivots(bars, 3)
    assert highs, "expected fractal highs"
    assert lows, "expected fractal lows"
    # trough pivots land at phase-5 bars (i=5,15,25,...)
    assert any(p.index == 5 for p in lows)
    assert any(p.index == 15 for p in lows)


def test_detect_trend_lines_finds_support_and_resistance() -> None:
    bars = _zigzag_uptrend()
    lines = detect_trend_lines(bars)
    assert lines, "expected trendlines on clean zigzag"
    kinds = {line.kind for line in lines}
    assert "support" in kinds
    support = next(line for line in lines if line.kind == "support")
    assert support.touches >= 3
    assert len(lines) <= TrendLineOptions().max_lines


def test_detect_trend_lines_empty_when_bars_too_few() -> None:
    assert detect_trend_lines(_zigzag_uptrend(8)) == []


def test_detect_trend_lines_respects_relevance_filter() -> None:
    bars = _zigzag_uptrend()
    # Very strict relevance window drops everything far from last close.
    lines = detect_trend_lines(bars, TrendLineOptions(relevance_pct=0.0001))
    assert lines == []


def test_build_overlay_set_shapes_and_language() -> None:
    bars = _zigzag_uptrend()
    overlay_set = build_overlay_set("600519", bars)
    assert overlay_set.symbol == "600519"
    assert overlay_set.generatedAt
    assert overlay_set.overlays
    for overlay in overlay_set.overlays:
        assert overlay.kind == "trend"
        assert overlay.source == "ai"
        assert overlay.side in ("support", "resistance")
        assert 0.0 <= overlay.strength <= 1.0
        assert overlay.a and overlay.b
        assert overlay.rationale and "不构成交易建议" in overlay.rationale


def test_build_overlay_set_empty_bars() -> None:
    overlay_set = build_overlay_set("600519", [])
    assert overlay_set.overlays == []
