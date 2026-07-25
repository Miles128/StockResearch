"""Hypothesis verification helpers."""

from stockresearch.services.hypothesis_verify import (
    HYPOTHESIS_PRESETS,
    _match,
    _momentum_at,
    _vol_ann_pct_at,
)


def test_momentum_at() -> None:
    closes = [100.0] + [100.0] * 19 + [110.0]
    # idx 20 → compare to idx 0
    mom = _momentum_at(closes, 20, 20)
    assert mom is not None
    assert abs(mom - 10.0) < 1e-6


def test_match_rules() -> None:
    assert _match("momentum_positive", 1.0) is True
    assert _match("momentum_negative", -1.0) is True
    assert _match("momentum_strong_up", 5.0) is True
    assert _match("momentum_strong_down", -5.0) is True
    assert _match("momentum_strong_up", 4.0) is False
    assert _match("drawdown_rebound", -10.0) is True
    assert _match("rally_continuation", 10.0) is True
    assert _match("calm_momentum_up", 4.0, vol=25.0) is True
    assert _match("calm_momentum_up", 4.0, vol=35.0) is False
    assert _match("high_vol_momentum_up", 6.0, vol=45.0) is True


def test_vol_ann_pct_at_positive() -> None:
    # Alternating moves → non-zero vol
    closes = [100.0]
    for i in range(25):
        closes.append(closes[-1] * (1.02 if i % 2 == 0 else 0.98))
    vol = _vol_ann_pct_at(closes, len(closes) - 1, 20)
    assert vol is not None
    assert vol > 0


def test_presets_cover_phase7_rules() -> None:
    assert len(HYPOTHESIS_PRESETS) >= 8
    assert "drawdown_rebound" in HYPOTHESIS_PRESETS
    assert "calm_momentum_up" in HYPOTHESIS_PRESETS
