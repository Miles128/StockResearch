"""Local daily OHLCV warehouse for holdings / watchlist universe."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from stockresearch.data.providers.market import TechnicalDataProvider
from stockresearch.db.models import DailyBar, Holding, WatchlistItem
from stockresearch.db.session import SessionLocal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BarsMeta:
    bars: list[dict[str, float | str]]
    source: str
    adjust: str
    as_of: str | None
    partial: bool = False
    note: str | None = None


def _parse_trade_date(value: object) -> date | None:
    text = str(value or "")[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def upsert_bars(
    db: Session,
    symbol: str,
    bars: list[dict[str, float | str]],
    *,
    adj: str = "qfq",
    source: str = "unknown",
) -> int:
    """Insert or update bars; returns number of rows touched.

    Refuses to mix adjust modes on the same symbol: if existing rows use a
    different adj, they are deleted before writing the new series.
    """
    if not bars:
        return 0
    existing_adj = db.execute(
        select(DailyBar.adj).where(DailyBar.symbol == symbol).limit(1)
    ).scalar_one_or_none()
    if existing_adj and existing_adj != adj:
        logger.info(
            "daily_bars adj mismatch for %s (%s -> %s); replacing series",
            symbol,
            existing_adj,
            adj,
        )
        db.query(DailyBar).filter(DailyBar.symbol == symbol).delete()
        db.commit()

    touched = 0
    for bar in bars:
        trade_date = _parse_trade_date(bar.get("date"))
        if trade_date is None:
            continue
        existing = db.execute(
            select(DailyBar).where(DailyBar.symbol == symbol, DailyBar.trade_date == trade_date)
        ).scalar_one_or_none()
        payload = {
            "open": float(bar["open"]),
            "high": float(bar["high"]),
            "low": float(bar["low"]),
            "close": float(bar["close"]),
            "volume": float(bar.get("volume", 0) or 0),
            "adj": adj,
        }
        if existing is None:
            db.add(DailyBar(symbol=symbol, trade_date=trade_date, **payload))
        else:
            for key, value in payload.items():
                setattr(existing, key, value)
        touched += 1
    if touched:
        db.commit()
        logger.debug("upserted %d bars for %s adj=%s source=%s", touched, symbol, adj, source)
    return touched


def load_bars(
    db: Session,
    symbol: str,
    *,
    days: int = 90,
    require_adj: str | None = "qfq",
) -> tuple[list[dict[str, float | str]], str | None]:
    """Load bars; returns (bars, adj). Empty if require_adj not satisfied."""
    rows = (
        db.execute(
            select(DailyBar)
            .where(DailyBar.symbol == symbol)
            .order_by(DailyBar.trade_date.desc())
            .limit(days)
        )
        .scalars()
        .all()
    )
    if not rows:
        return [], None
    adj = rows[0].adj
    if require_adj and any(r.adj != require_adj for r in rows):
        return [], adj
    if require_adj and adj != require_adj:
        return [], adj
    rows = list(reversed(rows))
    bars = [
        {
            "date": row.trade_date.isoformat(),
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume,
        }
        for row in rows
    ]
    return bars, adj


async def get_bars_meta_for_symbol(symbol: str, days: int = 90) -> BarsMeta:
    """Prefer local qfq warehouse; fall back to unadjusted bars when qfq is down."""
    db = SessionLocal()
    try:
        cached, cached_adj = load_bars(db, symbol, days=days, require_adj="qfq")
        as_of = str(cached[-1]["date"]) if cached else None
        if len(cached) >= min(days, 20):
            return BarsMeta(
                bars=cached[-days:],
                source="warehouse",
                adjust="qfq",
                as_of=as_of,
            )

        provider = TechnicalDataProvider()
        bars, source, adjust = await provider.get_kline_bars_meta(
            symbol, days=max(days, 60), prefer_qfq=True
        )
        if bars and adjust == "qfq":
            upsert_bars(db, symbol, bars, adj="qfq", source=source)
            as_of = str(bars[-1].get("date", ""))[:10] or None
            return BarsMeta(
                bars=bars[-days:],
                source=source,
                adjust="qfq",
                as_of=as_of,
            )

        # AkShare/EM qfq often flakes; use unadjusted bars for short-window factors.
        none_bars, none_source, none_adj = await provider.get_kline_bars_meta(
            symbol, days=max(days, 60), prefer_qfq=False
        )
        if none_bars:
            as_of = str(none_bars[-1].get("date", ""))[:10] or None
            return BarsMeta(
                bars=none_bars[-days:],
                source=none_source,
                adjust=none_adj or "none",
                as_of=as_of,
                partial=True,
                note="前复权(qfq)不可用，动量/波动暂用未复权日线（分红/送转窗口会偏）",
            )

        if cached:
            return BarsMeta(
                bars=cached[-days:],
                source="warehouse",
                adjust=cached_adj or "qfq",
                as_of=as_of,
                partial=len(cached) < min(days, 20),
                note="日线样本偏短" if len(cached) < min(days, 20) else None,
            )
        return BarsMeta(
            bars=[],
            source="unavailable",
            adjust="none",
            as_of=None,
            partial=True,
            note="日线不可用",
        )
    finally:
        db.close()


async def get_bars_for_symbol(symbol: str, days: int = 90) -> list[dict[str, float | str]]:
    """Prefer local warehouse; fetch + upsert on miss / short history (qfq only)."""
    meta = await get_bars_meta_for_symbol(symbol, days=days)
    return meta.bars


def universe_symbols(db: Session) -> list[str]:
    holding_syms = {row[0] for row in db.query(Holding.symbol).distinct()}
    watch_syms = {row[0] for row in db.query(WatchlistItem.symbol).distinct()}
    return sorted(holding_syms | watch_syms)


async def refresh_universe_bars(*, days: int = 120) -> dict[str, int]:
    """Incremental refresh for all holdings + watchlist symbols (qfq only)."""
    db = SessionLocal()
    provider = TechnicalDataProvider()
    updated: dict[str, int] = {}
    try:
        symbols = universe_symbols(db)
        for symbol in symbols:
            try:
                bars, source, adjust = await provider.get_kline_bars_meta(
                    symbol, days=days, prefer_qfq=True
                )
                if bars and adjust == "qfq":
                    updated[symbol] = upsert_bars(db, symbol, bars, adj="qfq", source=source)
                else:
                    logger.warning(
                        "skip non-qfq refresh for %s (source=%s adjust=%s)",
                        symbol,
                        source,
                        adjust,
                    )
                    updated[symbol] = 0
            except Exception as exc:
                logger.warning("daily bar refresh failed for %s: %s", symbol, exc)
                updated[symbol] = 0
        return updated
    finally:
        db.close()
