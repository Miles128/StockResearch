"""Upcoming events for holdings/watchlist: earnings disclosure calendar + lockup expiry.

数据源：东方财富 via AkShare（`stock_yysj_em` 预约披露时间 / `stock_restricted_release_queue_em`
个股解禁批次）。任何源失败均显式 ``partial``，禁止编造。内存缓存 6h。
"""

from __future__ import annotations

import asyncio
import math
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from stockresearch.core.schemas import PortfolioEventOut, PortfolioEventsOut
from stockresearch.db.models import Holding, WatchlistItem

_CACHE_TTL = timedelta(hours=6)
_LOCKUP_MAX_SYMBOLS = 12
_earnings_cache: dict[str, tuple[datetime, dict[str, date]]] = {}
_lockup_cache: dict[str, tuple[datetime, list[tuple[date, str | None]]]] = {}

_PERIOD_LABELS = {"0331": "一季报", "0630": "中报", "0930": "三季报", "1231": "年报"}


def _beijing_today() -> date:
    return (datetime.now(UTC) + timedelta(hours=8)).date()


def _current_period_end(today: date) -> str:
    if today.month <= 4:
        return f"{today.year - 1}1231"
    if today.month <= 8:
        return f"{today.year}0630"
    return f"{today.year}0930"


def _period_label(period: str) -> str:
    year = period[:4]
    return f"{year}{_PERIOD_LABELS.get(period[4:], '报告期')}"


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


async def _fetch_earnings_schedule(period: str) -> dict[str, date]:
    """symbol -> 预约披露日期（整市场一张表，按报告期）。"""
    cached = _earnings_cache.get(period)
    if cached and datetime.now(UTC) - cached[0] < _CACHE_TTL:
        return cached[1]
    import akshare as ak

    df = await asyncio.to_thread(ak.stock_yysj_em, symbol="沪深A股", date=period)
    out: dict[str, date] = {}
    code_col = next((c for c in df.columns if "代码" in str(c)), None)
    date_col = next((c for c in df.columns if "披露" in str(c)), None)
    if code_col is None or date_col is None:
        return out
    for _, row in df.iterrows():
        parsed = _parse_date(str(row[date_col]))
        if parsed is None:
            continue
        out[str(row[code_col]).zfill(6)] = parsed
    _earnings_cache[period] = (datetime.now(UTC), out)
    return out


async def _fetch_lockups(symbol: str) -> list[tuple[date, str | None]]:
    cached = _lockup_cache.get(symbol)
    if cached and datetime.now(UTC) - cached[0] < _CACHE_TTL:
        return cached[1]
    import akshare as ak

    df = await asyncio.to_thread(ak.stock_restricted_release_queue_em, symbol=symbol)
    out: list[tuple[date, str | None]] = []
    date_col = next((c for c in df.columns if "解禁" in str(c) and "时间" in str(c)), None)
    qty_col = next((c for c in df.columns if "解禁" in str(c) and "数量" in str(c)), None)
    if date_col is None:
        return out
    for _, row in df.iterrows():
        parsed = _parse_date(str(row[date_col]))
        if parsed is None:
            continue
        detail: str | None = None
        if qty_col is not None:
            qty = row[qty_col]
            if isinstance(qty, int | float) and not math.isnan(float(qty)) and qty > 0:
                detail = (
                    f"解禁 {qty / 1e8:.2f} 亿股" if qty >= 1e8 else f"解禁 {qty / 1e4:.0f} 万股"
                )
        out.append((parsed, detail))
    _lockup_cache[symbol] = (datetime.now(UTC), out)
    return out


async def upcoming_events(db: Session, user_id: int, *, days: int = 45) -> PortfolioEventsOut:
    days = max(7, min(int(days), 120))
    today = _beijing_today()
    window_end = today + timedelta(days=days)

    holdings = db.query(Holding).filter(Holding.user_id == user_id).all()
    watchlist = db.query(WatchlistItem).filter(WatchlistItem.user_id == user_id).all()
    universe: dict[str, tuple[str, str]] = {}
    for w in watchlist:
        universe[w.symbol] = (w.name, "watchlist")
    for h in holdings:  # holdings win on conflict
        universe[h.symbol] = (h.name, "holding")

    base = PortfolioEventsOut(days=days)
    if not universe:
        base.message = "暂无持仓或自选，添加后可查看事件日历"
        return base

    period = _current_period_end(today)
    base.period = _period_label(period)
    failures: list[str] = []
    events: list[PortfolioEventOut] = []

    try:
        schedule = await _fetch_earnings_schedule(period)
        for symbol, (name, scope) in universe.items():
            event_date = schedule.get(symbol)
            if event_date and today <= event_date <= window_end:
                events.append(
                    PortfolioEventOut(
                        symbol=symbol,
                        name=name,
                        kind="earnings",
                        event_date=event_date,
                        detail=f"{base.period}预约披露",
                        scope=scope,  # type: ignore[arg-type]
                    )
                )
    except Exception:
        failures.append("财报日历")

    lockup_symbols = [h.symbol for h in holdings[:_LOCKUP_MAX_SYMBOLS]]
    if lockup_symbols:
        results = await asyncio.gather(
            *[_fetch_lockups(s) for s in lockup_symbols], return_exceptions=True
        )
        lockup_failed = 0
        for symbol, result in zip(lockup_symbols, results):
            if isinstance(result, BaseException):
                lockup_failed += 1
                continue
            name, scope = universe.get(symbol, (symbol, "holding"))
            for event_date, detail in result:
                if today <= event_date <= window_end:
                    events.append(
                        PortfolioEventOut(
                            symbol=symbol,
                            name=name,
                            kind="lockup",
                            event_date=event_date,
                            detail=detail,
                            scope=scope,  # type: ignore[arg-type]
                        )
                    )
        if lockup_failed:
            failures.append("解禁日历")

    events.sort(key=lambda e: (e.event_date, e.symbol))
    base.events = events
    if failures:
        base.partial = True
        base.message = (
            "部分数据暂时没取到（" + "、".join(sorted(set(failures))) + "），其余事件已展示"
        )
    return base
