"""Unit tests for research-signal verification helpers."""

from stockresearch.services.signal_backtest import (
    _build_sample_bias_note,
    _factor_tilt,
    _forward_return_pct,
)


def test_forward_return_pct() -> None:
    bars = [
        {"date": "2024-01-01", "close": 100.0},
        {"date": "2024-01-02", "close": 101.0},
        {"date": "2024-01-03", "close": 110.0},
    ]
    assert _forward_return_pct(bars, 0, 2) == 10.0
    assert _forward_return_pct(bars, 0, 5) is None


def test_factor_tilt_momentum() -> None:
    assert _factor_tilt({"factors": [{"key": "momentum_20d", "value": 6.0}]}) == "bullish"
    assert _factor_tilt({"factors": [{"key": "momentum_20d", "value": -6.0}]}) == "bearish"
    assert _factor_tilt({"factors": [{"key": "pe_percentile", "percentile": 0.2}]}) == "bullish"
    assert _factor_tilt({"bias": "neutral"}) is None


def test_sample_bias_note_flags_small_sample() -> None:
    note = _build_sample_bias_note(
        unique_symbols=2,
        total_samples=3,
        bias_count=2,
        tilt_count=1,
        skipped_non_qfq=1,
    )
    assert "选择偏差" in note
    assert "样本量 < 8" in note
    assert "研报偏向 2" in note
    assert "前复权" in note
