"""Hypothesis verification helpers."""

import pytest

from stockresearch.services.hypothesis_verify import (
    HYPOTHESIS_PRESETS,
    _match,
    _momentum_at,
    _vol_ann_pct_at,
)


def _factors(pe_percentile: float | None = None, pe_partial: bool = True,
             roe_ttm: float | None = None, roe_partial: bool = True):
    return {
        "pe_percentile": pe_percentile,
        "pe_percentile_partial": pe_partial,
        "roe_ttm": roe_ttm,
        "roe_ttm_partial": roe_partial,
    }


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


def test_presets_include_current_condition_rules() -> None:
    assert "valuation_momentum_now" in HYPOTHESIS_PRESETS
    assert "quality_hold_now" in HYPOTHESIS_PRESETS
    assert "valuation_momentum_now" in HYPOTHESIS_PRESETS
    # labels should mention current-condition semantics
    assert "当前" in HYPOTHESIS_PRESETS["valuation_momentum_now"]


def test_match_valuation_momentum_now_satisfied() -> None:
    fac = _factors(pe_percentile=40.0, pe_partial=False)
    assert _match("valuation_momentum_now", 1.5, factors=fac) is True


def test_match_valuation_momentum_now_pe_too_high() -> None:
    fac = _factors(pe_percentile=70.0, pe_partial=False)
    assert _match("valuation_momentum_now", 1.5, factors=fac) is False


def test_match_valuation_momentum_now_momentum_negative() -> None:
    fac = _factors(pe_percentile=40.0, pe_partial=False)
    assert _match("valuation_momentum_now", -1.0, factors=fac) is False


def test_match_valuation_momentum_now_pe_partial_skips() -> None:
    fac = _factors(pe_percentile=40.0, pe_partial=True)
    assert _match("valuation_momentum_now", 1.5, factors=fac) is False
    fac_none = _factors(pe_percentile=None, pe_partial=True)
    assert _match("valuation_momentum_now", 1.5, factors=fac_none) is False


def test_match_valuation_momentum_now_no_factors() -> None:
    assert _match("valuation_momentum_now", 1.5) is False
    assert _match("valuation_momentum_now", 1.5, factors=None) is False


def test_match_quality_hold_now_satisfied() -> None:
    fac = _factors(roe_ttm=12.0, roe_partial=False)
    assert _match("quality_hold_now", -1.0, factors=fac) is True


def test_match_quality_hold_now_roe_low() -> None:
    fac = _factors(roe_ttm=8.0, roe_partial=False)
    assert _match("quality_hold_now", -1.0, factors=fac) is False


def test_match_quality_hold_now_momentum_too_negative() -> None:
    fac = _factors(roe_ttm=12.0, roe_partial=False)
    assert _match("quality_hold_now", -6.0, factors=fac) is False


def test_match_quality_hold_now_roe_partial_skips() -> None:
    fac = _factors(roe_ttm=12.0, roe_partial=True)
    assert _match("quality_hold_now", -1.0, factors=fac) is False


@pytest.mark.asyncio
async def test_verify_valuation_momentum_now_partial_when_pe_unavailable(monkeypatch):
    """When PE factor is unavailable, verify returns partial with honest note."""
    from stockresearch.services import hypothesis_verify as hv

    async def fake_factors(symbol, *, factor_keys=None):
        # Return a pe_percentile factor marked partial with None value.
        from stockresearch.core.schemas import NumericFactorOut, BarsProvenanceOut
        pe = NumericFactorOut(
            key="pe_percentile", label="PE历史分位", value=None,
            as_of="2026-08-01", unit="%", partial=True,
            note="PE不可用", bars_source="test", bars_adjust="qfq",
        )
        mom = NumericFactorOut(
            key="momentum_20d", label="20日动量", value=2.0,
            as_of="2026-08-01", unit="%", partial=False,
            note=None, bars_source="test", bars_adjust="qfq",
        )
        return [pe, mom], BarsProvenanceOut(
            source="test", adjust="qfq", as_of="2026-08-01",
            partial=False, note=None,
        )

    monkeypatch.setattr(hv, "compute_numeric_factors", fake_factors)
    out = await hv.verify_hypothesis("600519", rule="valuation_momentum_now")
    assert out.rule == "valuation_momentum_now"
    assert out.partial is True
    assert out.sample_count == 0
    assert any("PE" in n or "估值" in n for n in out.notes)


@pytest.mark.asyncio
async def test_verify_valuation_momentum_now_signal_fires_at_last_bar(monkeypatch):
    """When PE<60 and momentum>0, signal fires once at last bar; forward returns pending."""
    from stockresearch.services import hypothesis_verify as hv
    from stockresearch.core.schemas import NumericFactorOut, BarsProvenanceOut

    async def fake_factors(symbol, *, factor_keys=None):
        pe = NumericFactorOut(
            key="pe_percentile", label="PE历史分位", value=40.0, percentile=0.4,
            as_of="2026-08-01", unit="%", partial=False,
            note=None, bars_source="test", bars_adjust="qfq",
        )
        mom = NumericFactorOut(
            key="momentum_20d", label="20日动量", value=3.0,
            as_of="2026-08-01", unit="%", partial=False,
            note=None, bars_source="test", bars_adjust="qfq",
        )
        return [pe, mom], BarsProvenanceOut(
            source="test", adjust="qfq", as_of="2026-08-01",
            partial=False, note=None,
        )

    monkeypatch.setattr(hv, "compute_numeric_factors", fake_factors)
    out = await hv.verify_hypothesis("600519", rule="valuation_momentum_now")
    assert out.sample_count == 1
    # forward returns from last bar are not yet available
    assert all(w.sample_count == 0 for w in out.windows)
    assert out.partial is True


@pytest.mark.asyncio
async def test_verify_valuation_momentum_now_condition_not_met(monkeypatch):
    """When PE>=60, condition not met; sample_count=0, not partial."""
    from stockresearch.services import hypothesis_verify as hv
    from stockresearch.core.schemas import NumericFactorOut, BarsProvenanceOut

    async def fake_factors(symbol, *, factor_keys=None):
        pe = NumericFactorOut(
            key="pe_percentile", label="PE历史分位", value=70.0, percentile=0.7,
            as_of="2026-08-01", unit="%", partial=False,
            note=None, bars_source="test", bars_adjust="qfq",
        )
        mom = NumericFactorOut(
            key="momentum_20d", label="20日动量", value=3.0,
            as_of="2026-08-01", unit="%", partial=False,
            note=None, bars_source="test", bars_adjust="qfq",
        )
        return [pe, mom], BarsProvenanceOut(
            source="test", adjust="qfq", as_of="2026-08-01",
            partial=False, note=None,
        )

    monkeypatch.setattr(hv, "compute_numeric_factors", fake_factors)
    out = await hv.verify_hypothesis("600519", rule="valuation_momentum_now")
    assert out.sample_count == 0
    assert out.partial is False
