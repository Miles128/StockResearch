"""Portfolio window-return attribution tests (simplified: return × avg weight)."""

from datetime import date

from stockresearch.services.portfolio_performance import _build_attribution


class _Holding:
    def __init__(self, symbol: str, name: str) -> None:
        self.symbol = symbol
        self.name = name
        self.quantity = 100
        self.cost_price = 100.0


def test_attribution_simple_two_symbols() -> None:
    holdings = [_Holding("600519", "贵州茅台"), _Holding("000001", "平安银行")]
    common = [date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 4)]
    # A: 100→110 (+10%); B: 100→95 (-5%); both qty 100 → A weight 50%, B weight 50%
    closes = {
        "600519": {common[0]: 100.0, common[1]: 105.0, common[2]: 110.0},
        "000001": {common[0]: 100.0, common[1]: 97.5, common[2]: 95.0},
    }
    qty_series = {h.symbol: {d: 100 for d in common} for h in holdings}

    items = _build_attribution(holdings, qty_series=qty_series, closes=closes, common=common)
    by_symbol = {it.symbol: it for it in items}
    assert by_symbol["600519"].return_pct == 10.0
    assert by_symbol["000001"].return_pct == -5.0
    # 逐日平均权重：d1 50/50 → d2 51.85% → d3 53.66%，A 均 51.84%
    assert by_symbol["600519"].avg_weight_pct == 51.84
    assert by_symbol["000001"].avg_weight_pct == 48.16
    # 简化归因：return × avg_weight
    assert by_symbol["600519"].contribution_pct == 5.18
    assert by_symbol["000001"].contribution_pct == -2.41
    # 贡献降序：正贡献排前
    assert items[0].symbol == "600519"
    assert not any(it.partial for it in items)


def test_attribution_missing_bars_partial() -> None:
    holdings = [_Holding("600519", "贵州茅台"), _Holding("000858", "五粮液")]
    common = [date(2026, 1, 2), date(2026, 1, 3)]
    closes = {"600519": {common[0]: 100.0, common[1]: 110.0}}
    qty_series = {"600519": {d: 100 for d in common}, "000858": {d: 100 for d in common}}

    items = _build_attribution(holdings, qty_series=qty_series, closes=closes, common=common)
    missing = next(it for it in items if it.symbol == "000858")
    assert missing.partial is True
    assert missing.return_pct is None
    assert missing.contribution_pct is None


def test_attribution_empty_or_short_window() -> None:
    holdings = [_Holding("600519", "贵州茅台")]
    assert (
        _build_attribution(
            holdings,
            qty_series={},
            closes={},
            common=[],
        )
        == []
    )
    common = [date(2026, 1, 2)]
    assert (
        _build_attribution(
            holdings,
            qty_series={"600519": {common[0]: 100}},
            closes={"600519": {common[0]: 100.0}},
            common=common,
        )
        == []
    )
