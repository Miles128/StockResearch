"""Portfolio NAV curve vs benchmark (沪深300), reconstructed from trade ledger + qfq daily bars.

口径戳记：仅前复权日线收盘价；组合与基准均归一化到窗口首日 = 100。
无交易流水的持仓按当前股数近似覆盖整个窗口，并显式 ``partial=True``。
"""

from __future__ import annotations

from datetime import date as date_type

from sqlalchemy.orm import Session

from stockresearch.core.schemas import (
    PerformancePoint,
    PortfolioPerformanceOut,
)
from stockresearch.data.providers.market import TechnicalDataProvider
from stockresearch.db.models import Holding, Trade

BENCHMARK_SYMBOL = "000300"
BENCHMARK_NAME = "沪深300"
MIN_POINTS = 2


def _realized_total(trades: list[Trade]) -> float:
    return round(sum(t.float_realized_pnl for t in trades if t.realized_pnl is not None), 2)


def _quantity_series(
    trades: list[Trade],
    *,
    current_qty: int,
    dates: list[date_type],
) -> tuple[dict[date_type, int], bool]:
    """Daily quantity for one symbol over ``dates``.

    With ledger entries the position is fully reconstructible; without any
    ledger entry we fall back to the current holding quantity for the whole
    window and flag ``approximated=True``.
    """
    if not trades:
        return {d: current_qty for d in dates}, True

    ordered = sorted(trades, key=lambda t: (t.trade_date or t.created_at.date(), t.id))
    # Position at the beginning of time is 0; replay ledger onto dates.
    idx = 0
    qty = 0
    out: dict[date_type, int] = {}
    for d in dates:
        while (
            idx < len(ordered) and (ordered[idx].trade_date or ordered[idx].created_at.date()) <= d
        ):
            t = ordered[idx]
            qty += t.quantity if t.side == "buy" else -t.quantity
            idx += 1
        out[d] = max(qty, 0)
    return out, False


async def build_portfolio_performance(
    db: Session,
    user_id: int,
    *,
    days: int = 90,
) -> PortfolioPerformanceOut:
    days = max(20, min(int(days), 250))
    holdings = db.query(Holding).filter(Holding.user_id == user_id).all()
    trades = db.query(Trade).filter(Trade.user_id == user_id).order_by(Trade.id).all()
    base = PortfolioPerformanceOut(
        days=days,
        realized_pnl_total=_realized_total(trades),
        trade_count=len(trades),
    )
    if not holdings:
        base.message = "暂无持仓，添加持仓后可查看净值曲线"
        return base

    from stockresearch.services.daily_bars import load_bars

    closes: dict[str, dict[date_type, float]] = {}
    missing: list[str] = []
    approximated = False
    trades_by_symbol: dict[str, list[Trade]] = {}
    for t in trades:
        trades_by_symbol.setdefault(t.symbol, []).append(t)

    for h in holdings:
        bars, _adj = load_bars(db, h.symbol, days=days, require_adj="qfq")
        if not bars:
            missing.append(h.name or h.symbol)
            continue
        closes[h.symbol] = {
            date_type.fromisoformat(str(b["date"])): float(b["close"]) for b in bars
        }

    benchmark_bars = await TechnicalDataProvider().get_kline_bars(BENCHMARK_SYMBOL, days=days)
    benchmark: dict[date_type, float] = {
        date_type.fromisoformat(str(b["date"])): float(b["close"]) for b in benchmark_bars
    }

    if not benchmark:
        base.partial = True
        base.message = "基准指数日线暂不可用，净值曲线稍后再试"
        return base
    if not closes:
        base.partial = True
        base.message = "持仓日线数据尚未就绪（日线仓增量缓存中），请稍后再试"
        return base

    # Common trading dates where every priced holding + benchmark has a close.
    common = sorted(set.intersection(*[set(c) for c in closes.values()], set(benchmark)))
    common = common[-days:]

    if len(common) < MIN_POINTS:
        base.partial = True
        base.message = "可用共同交易日不足，净值曲线暂不可算"
        return base

    qty_series: dict[str, dict[date_type, int]] = {}
    for h in holdings:
        if h.symbol not in closes:
            continue
        series, approx = _quantity_series(
            trades_by_symbol.get(h.symbol, []),
            current_qty=h.quantity,
            dates=common,
        )
        qty_series[h.symbol] = series
        approximated = approximated or approx

    points: list[PerformancePoint] = []
    value0: float | None = None
    bench0: float | None = None
    for d in common:
        value = sum(qty_series[sym][d] * closes[sym][d] for sym in qty_series)
        if value <= 0:
            continue
        if value0 is None:
            value0 = value
            bench0 = benchmark[d]
        assert bench0 is not None and value0 is not None
        points.append(
            PerformancePoint(
                date=d,
                portfolio_index=round(value / value0 * 100, 2),
                benchmark_index=round(benchmark[d] / bench0 * 100, 2),
            )
        )

    if len(points) < MIN_POINTS:
        base.partial = True
        base.message = "窗口内有效持仓市值点不足，净值曲线暂不可算"
        return base

    base.series = points
    base.portfolio_return_pct = round(points[-1].portfolio_index - 100, 2)
    base.benchmark_return_pct = round(points[-1].benchmark_index - 100, 2)

    notes: list[str] = []
    if missing:
        notes.append(f"{'、'.join(missing)} 日线缺失，未计入曲线")
    if approximated:
        notes.append("部分持仓无交易流水，按当前股数近似")
    if notes:
        base.partial = True
        base.message = "；".join(notes)
    return base
