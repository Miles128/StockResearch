"""Factor-condition screener over holdings / watchlist universe.

复用 :func:`compute_numeric_factors` 的因子口径（前复权日线 + 估值快照）。
任何因子 ``partial`` 或无法计算的标的计入 ``skipped``，禁止编造。
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.orm import Session

from stockresearch.core.schemas import ScreenCondition, ScreenHit, ScreenOut, ScreenRequest
from stockresearch.db.models import Holding, WatchlistItem
from stockresearch.services.factors import compute_numeric_factors

logger = logging.getLogger(__name__)

_MAX_SYMBOLS = 40
_CONCURRENCY = 6

_OPS = {
    "<=": lambda a, b: a <= b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    ">": lambda a, b: a > b,
}


def _factor_value(factors: dict[str, object], key: str) -> float | None:
    """Extract comparable value for a condition key (all in percent units)."""
    factor = factors.get(key)
    if factor is None:
        return None
    value = getattr(factor, "value", None)
    if value is None and key == "pe_percentile":
        pct = getattr(factor, "percentile", None)
        if pct is not None:
            value = round(float(pct) * 100.0, 1) if float(pct) <= 1.0 else float(pct)
    return None if value is None else float(value)


def _passes(factors: dict[str, object], conditions: list[ScreenCondition]) -> bool:
    for cond in conditions:
        value = _factor_value(factors, cond.key)
        if value is None:
            return False
        if not _OPS[cond.op](value, cond.value):
            return False
    return True


async def run_screen(db: Session, user_id: int, payload: ScreenRequest) -> ScreenOut:
    holdings = db.query(Holding).filter(Holding.user_id == user_id).all()
    watchlist = db.query(WatchlistItem).filter(WatchlistItem.user_id == user_id).all()

    universe: dict[str, tuple[str, str | None, str]] = {}  # symbol -> (name, sector, scope)
    if payload.universe in ("watchlist", "all"):
        for w in watchlist:
            universe[w.symbol] = (w.name, None, "watchlist")
    if payload.universe in ("holdings", "all"):
        for h in holdings:  # holdings win on conflict
            universe[h.symbol] = (h.name, h.sector, "holding")

    if not universe:
        return ScreenOut(message="暂无可筛选的持仓或自选标的")

    truncated = len(universe) > _MAX_SYMBOLS
    symbols = list(universe)[:_MAX_SYMBOLS]
    needed_keys = tuple({c.key for c in payload.conditions})
    semaphore = asyncio.Semaphore(_CONCURRENCY)

    async def scan(symbol: str) -> tuple[str, dict[str, object] | None]:
        async with semaphore:
            try:
                factors, _prov = await compute_numeric_factors(symbol, factor_keys=needed_keys)
                return symbol, {f.key: f for f in factors}
            except Exception:
                logger.warning("screener: factor computation failed for %s", symbol)
                return symbol, None

    results = await asyncio.gather(*(scan(s) for s in symbols))

    hits: list[ScreenHit] = []
    skipped = 0
    for symbol, factors in results:
        name, sector, scope = universe[symbol]
        if factors is None:
            skipped += 1
            continue
        values = {key: _factor_value(factors, key) for key in needed_keys}
        if any(v is None for v in values.values()):
            skipped += 1
            continue
        if _passes(factors, payload.conditions):
            hits.append(
                ScreenHit(
                    symbol=symbol,
                    name=name,
                    sector=sector,
                    scope=scope,  # type: ignore[arg-type]
                    factors=values,
                )
            )

    hits.sort(key=lambda h: h.symbol)
    message = f"标的过多，仅筛选前 {_MAX_SYMBOLS} 个" if truncated else None
    return ScreenOut(hits=hits, scanned=len(symbols), skipped=skipped, message=message)
