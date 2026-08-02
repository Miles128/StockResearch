"""Phase 10 L1 Impact — pure helper unit tests (no network)."""

from __future__ import annotations

from stockresearch.core.schemas import ImpactPeakDayOut
from stockresearch.services.impact import _attach_peaks_from_events, _decompose_window, _ols_beta


def test_ols_beta_perfect_line() -> None:
    x = [0.01, 0.02, -0.01, 0.0, 0.03]
    y = [2 * v for v in x]
    beta, r2 = _ols_beta(y, x)
    assert abs(beta - 2.0) < 1e-9
    assert r2 > 0.99


def test_ols_beta_constant_x_returns_unit_beta() -> None:
    # var_x ~ 0 → helper returns (1.0, 0.0) instead of dividing by zero.
    beta, r2 = _ols_beta([0.01, 0.02, 0.03], [0.005, 0.005, 0.005])
    assert beta == 1.0
    assert r2 == 0.0


def test_ols_beta_too_few_points_returns_unit() -> None:
    beta, r2 = _ols_beta([0.01], [0.01])
    assert beta == 1.0
    assert r2 == 0.0


def test_decompose_window_sums() -> None:
    # stock 0.02+0.01-0.01 = 0.02 → 2.0%
    # market 0.01+0.01+0.0 = 0.02 → 2.0%; contrib = beta(1.0)*2.0 = 2.0
    # industry 0.005+0.0+0.0 = 0.005 → 0.5%
    # idio = 2.0 - 2.0 - 0.5 = -0.5
    stock = [0.02, 0.01, -0.01]
    mkt = [0.01, 0.01, 0.0]
    ind = [0.005, 0.0, 0.0]
    out = _decompose_window(stock, mkt, ind, beta=1.0)
    assert out["stock_return_pct"] == 2.0
    assert out["market_contrib_pct"] == 2.0
    assert out["industry_contrib_pct"] == 0.5
    assert out["idio_return_pct"] == -0.5


def test_decompose_window_without_industry() -> None:
    # No industry proxy → industry_contrib = 0, idio = stock - market only.
    stock = [0.03, -0.01]
    mkt = [0.01, 0.01]
    out = _decompose_window(stock, mkt, None, beta=2.0)
    # stock_sum = 0.02 * 100 = 2.0; mkt_sum = 0.02 * 100 = 2.0; contrib = 2.0*2.0 = 4.0
    # idio = 2.0 - 4.0 - 0.0 = -2.0
    assert out["stock_return_pct"] == 2.0
    assert out["market_contrib_pct"] == 4.0
    assert out["industry_contrib_pct"] == 0.0
    assert out["idio_return_pct"] == -2.0
    assert out["idio_return_pct"] == out["stock_return_pct"] - out["market_contrib_pct"]


def test_idio_preserved_when_industry_proxy_missing() -> None:
    """Call-site rule: null industry_contrib only; idio always from decomp."""
    decomp = _decompose_window([0.03, -0.01], [0.01, 0.01], None, beta=2.0)
    ind_win = None
    industry_contrib_pct = decomp["industry_contrib_pct"] if ind_win is not None else None
    idio_return_pct = decomp["idio_return_pct"]
    assert industry_contrib_pct is None
    assert idio_return_pct == -2.0
    assert idio_return_pct == decomp["stock_return_pct"] - decomp["market_contrib_pct"]


def test_ols_beta_pre_window_sample() -> None:
    """β estimated on pre-window returns does not include attribution window."""
    # 20 estimation days + 5 attribution days; y = 1.5 * x on estimation slice.
    est_x = [0.01 * (i % 3 - 1) for i in range(20)]
    est_y = [1.5 * v for v in est_x]
    attr_x = [0.02, -0.01, 0.03, 0.0, -0.02]
    attr_y = [0.99 * v for v in attr_x]  # deliberately off-beta in window
    x = est_x + attr_x
    y = est_y + attr_y
    win = 5
    beta, _ = _ols_beta(y[:-win], x[:-win])
    assert abs(beta - 1.5) < 1e-9
    decomp = _decompose_window(y[-win:], x[-win:], None, beta=beta)
    assert decomp["idio_return_pct"] == round(
        decomp["stock_return_pct"] - decomp["market_contrib_pct"], 4
    )


def test_attach_peaks_marks_unexplained_without_event() -> None:
    peaks = [ImpactPeakDayOut(date="2026-06-01", idio_return_pct=3.0)]
    out = _attach_peaks_from_events(peaks, events=[])
    assert out[0].unexplained is True
    assert out[0].event_title is None


def test_attach_peaks_links_same_day_event() -> None:
    peaks = [ImpactPeakDayOut(date="2026-06-01", idio_return_pct=3.0)]
    events = [{"date": "2026-06-01", "title": "业绩预告", "kind": "earnings", "fwd_5d": 1.2}]
    out = _attach_peaks_from_events(peaks, events)
    assert out[0].unexplained is False
    assert out[0].event_title == "业绩预告"


def test_decompose_window_rounds_to_four_decimals() -> None:
    stock = [0.012345, 0.001]
    mkt = [0.005, 0.002]
    out = _decompose_window(stock, mkt, None, beta=1.0)
    for v in out.values():
        # rounded to 4 decimals → at most 4 decimal places
        assert round(v, 4) == v
