"""Portfolio performance — 纯函数单元测试（重建净值/数量序列/归因）。"""

from datetime import date, datetime

from stockresearch.db.models import Trade
from stockresearch.services.portfolio_performance import (
    _build_attribution,
    _quantity_series,
    _realized_total,
)


def _trade(
    side: str,
    quantity: int,
    price: float = 100.0,
    trade_date: str | None = "2024-01-15",
    realized: float | None = None,
    trade_id: int = 1,
) -> Trade:
    t = Trade(
        user_id=1,
        symbol="600519",
        name="贵州茅台",
        side=side,
        price=price,
        quantity=quantity,
        trade_date=date.fromisoformat(trade_date) if trade_date else None,
    )
    t.id = trade_id
    if realized is not None:
        t.realized_pnl = realized
    return t


def test_realized_total_sums_only_realized() -> None:
    trades = [
        _trade("sell", 100, realized=123.45, trade_id=1),
        _trade("buy", 100, trade_id=2),
        _trade("sell", 100, realized=-50.0, trade_id=3),
    ]
    assert _realized_total(trades) == 73.45


def test_quantity_series_replays_ledger() -> None:
    dates = [date(2024, 1, 1), date(2024, 1, 10), date(2024, 1, 20), date(2024, 1, 30)]
    trades = [
        _trade("buy", 100, trade_date="2024-01-05", trade_id=1),
        _trade("buy", 200, trade_date="2024-01-15", trade_id=2),
        _trade("sell", 100, trade_date="2024-01-25", trade_id=3),
    ]
    series, approximated = _quantity_series(trades, current_qty=200, dates=dates)
    assert not approximated
    assert series[date(2024, 1, 1)] == 0
    assert series[date(2024, 1, 10)] == 100
    assert series[date(2024, 1, 20)] == 300
    assert series[date(2024, 1, 30)] == 200


def test_quantity_series_without_ledger_approximates() -> None:
    dates = [date(2024, 1, 1), date(2024, 1, 30)]
    series, approximated = _quantity_series([], current_qty=500, dates=dates)
    assert approximated
    assert all(q == 500 for q in series.values())


def test_quantity_series_trades_without_dates() -> None:
    dates = [date(2024, 1, 1), date(2024, 1, 30)]
    t = _trade("buy", 100, trade_date=None, trade_id=1)
    t.created_at = datetime(2024, 1, 15, 10, 0)
    series, approximated = _quantity_series([t], current_qty=100, dates=dates)
    assert not approximated
    assert series[date(2024, 1, 1)] == 0
    assert series[date(2024, 1, 30)] == 100


class _H:
    def __init__(self, symbol: str, name: str):
        self.symbol = symbol
        self.name = name


def test_build_attribution_contributions() -> None:
    holdings = [_H("600519", "茅台"), _H("000858", "五粮液"), _H("600000", "无日线")]
    common = [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)]
    qty_series = {
        "600519": {d: 100 for d in common},
        "000858": {d: 100 for d in common},
    }
    closes = {
        "600519": {date(2024, 1, 1): 100.0, date(2024, 1, 2): 100.0, date(2024, 1, 3): 110.0},
        "000858": {date(2024, 1, 1): 100.0, date(2024, 1, 2): 100.0, date(2024, 1, 3): 90.0},
    }
    items = _build_attribution(holdings, qty_series=qty_series, closes=closes, common=common)
    by_symbol = {i.symbol: i for i in items}
    assert by_symbol["600519"].return_pct == 10.0
    assert by_symbol["000858"].return_pct == -10.0
    # 权重按逐日市值平均：茅台从 50% 涨到 55%，均值 > 50%，贡献 > 5.0
    assert by_symbol["600519"].contribution_pct is not None
    assert by_symbol["600519"].contribution_pct > 5.0
    assert by_symbol["000858"].contribution_pct is not None
    assert by_symbol["000858"].contribution_pct < -4.0
    assert by_symbol["600000"].partial is True


def test_build_attribution_short_window_empty() -> None:
    assert _build_attribution([_H("600519", "茅台")], qty_series={}, closes={}, common=[]) == []
