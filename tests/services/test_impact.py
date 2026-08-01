"""Phase 10 L1 Impact — pure helper unit tests (no network)."""

from __future__ import annotations

from stockresearch.services.impact import _decompose_window, _ols_beta


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


def test_decompose_window_rounds_to_four_decimals() -> None:
    stock = [0.012345, 0.001]
    mkt = [0.005, 0.002]
    out = _decompose_window(stock, mkt, None, beta=1.0)
    for v in out.values():
        # rounded to 4 decimals → at most 4 decimal places
        assert round(v, 4) == v
