"""Local daily OHLCV warehouse for holdings / watchlist universe."""

from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from stockresearch.data.providers.market import TechnicalDataProvider
from stockresearch.db.models import DailyBar, Holding, WatchlistItem
from stockresearch.db.session import SessionLocal

logger = logging.getLogger(__name__)


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
) -> int:
    """Insert or update bars; returns number of rows touched."""
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
    return touched


def load_bars(db: Session, symbol: str, *, days: int = 90) -> list[dict[str, float | str]]:
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
    rows = list(reversed(rows))
    return [
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


async def get_bars_for_symbol(symbol: str, days: int = 90) -> list[dict[str, float | str]]:
    """Prefer local warehouse; fetch + upsert on miss / short history."""
    db = SessionLocal()
    try:
        cached = load_bars(db, symbol, days=days)
        if len(cached) >= min(days, 20):
            return cached[-days:]
        provider = TechnicalDataProvider()
        bars = await provider.get_kline_bars(symbol, days=max(days, 60))
        if bars:
            upsert_bars(db, symbol, bars)
            return bars[-days:]
        return cached[-days:]
    finally:
        db.close()


def universe_symbols(db: Session) -> list[str]:
    holding_syms = {row[0] for row in db.query(Holding.symbol).distinct()}
    watch_syms = {row[0] for row in db.query(WatchlistItem.symbol).distinct()}
    return sorted(holding_syms | watch_syms)


async def refresh_universe_bars(*, days: int = 120) -> dict[str, int]:
    """Incremental refresh for all holdings + watchlist symbols."""
    db = SessionLocal()
    provider = TechnicalDataProvider()
    updated: dict[str, int] = {}
    try:
        symbols = universe_symbols(db)
        for symbol in symbols:
            try:
                bars = await provider.get_kline_bars(symbol, days=days)
                updated[symbol] = upsert_bars(db, symbol, bars) if bars else 0
            except Exception as exc:
                logger.warning("daily bar refresh failed for %s: %s", symbol, exc)
                updated[symbol] = 0
        return updated
    finally:
        db.close()
