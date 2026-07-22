"""Hypothesis verification helpers."""

from stockresearch.services.hypothesis_verify import HYPOTHESIS_PRESETS, _match, _momentum_at


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


def test_presets_cover_core_rules() -> None:
    assert "momentum_positive" in HYPOTHESIS_PRESETS
    assert "momentum_strong_down" in HYPOTHESIS_PRESETS
