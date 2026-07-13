"""Risk metrics helpers: concentration, stress shocks."""

from stockresearch.agents.risk.metrics import (
    HoldingQuote,
    apply_price_shocks,
    calculate_portfolio_metrics,
    closes_to_daily_returns,
    run_stress_presets,
)


def test_closes_to_daily_returns() -> None:
    assert closes_to_daily_returns([100.0, 110.0, 99.0]) == [0.1, -0.1]


def test_sector_weights_and_top_holding() -> None:
    holdings = [
        HoldingQuote("600519", "茅台", 100, 100, 10, "白酒"),
        HoldingQuote("300750", "宁德", 200, 200, 5, "新能源"),
        HoldingQuote("000858", "五粮液", 100, 100, 2, "白酒"),
    ]
    # values: 1000, 1000, 200 → total 2200; 白酒 1200/2200 ≈ 0.545
    pm = calculate_portfolio_metrics(holdings)
    assert pm.concentration_sector == "白酒"
    assert abs(pm.concentration_ratio - 1200 / 2200) < 1e-6
    assert len(pm.sector_weights) == 2
    assert pm.sector_weights[0]["sector"] == "白酒"
    assert pm.top_holding_weight == 1000 / 2200


def test_apply_price_shocks_all_book() -> None:
    holdings = [
        HoldingQuote("600519", "茅台", 100, 100, 10, "白酒"),
        HoldingQuote("300750", "宁德", 200, 200, 5, "新能源"),
    ]
    # total 2000; -10% → 1800
    out = apply_price_shocks(holdings, {"*": -0.10}, by="symbol")
    assert out["portfolio_value"] == 2000
    assert abs(out["shocked_value"] - 1800) < 1e-6
    assert abs(out["pnl_pct"] - (-0.10)) < 1e-9


def test_run_stress_presets_returns_rows() -> None:
    holdings = [
        HoldingQuote("600519", "茅台", 100, 100, 20, "白酒"),
        HoldingQuote("300750", "宁德", 200, 200, 1, "新能源"),
    ]
    rows = run_stress_presets(holdings)
    assert len(rows) >= 2
    assert all("pnl" in r and "name" in r for r in rows)
    crash = next(r for r in rows if r["id"] == "crash_2015_style")
    assert crash["pnl"] < 0
