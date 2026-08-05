"""Price change alert checks for holdings and watchlist."""

from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy.orm import Session

from stockresearch.core.constants import DISCLAIMER
from stockresearch.data.providers.market_overview import BatchQuoteProvider
from stockresearch.db.models import (
    Holding,
    PriceAlertNotification,
    PriceAlertSetting,
    WatchlistItem,
)

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD_PCT = 5.0


def get_or_create_settings(db: Session, user_id: int) -> PriceAlertSetting:
    row = db.query(PriceAlertSetting).filter(PriceAlertSetting.user_id == user_id).first()
    if row is not None:
        return row
    row = PriceAlertSetting(user_id=user_id, enabled=True, threshold_pct=DEFAULT_THRESHOLD_PCT)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _format_message(name: str, symbol: str, change_pct: float, threshold_pct: float) -> str:
    direction = "上涨" if change_pct >= 0 else "下跌"
    return (
        f"{name}（{symbol}）今日{direction}{abs(change_pct):.2f}%，"
        f"已超过你设定的提醒线 ±{threshold_pct:.1f}%。"
        f"下一步：先看最新研报和风险体检，再决定要不要调整。{DISCLAIMER}"
    )


async def check_price_alerts_for_user(db: Session, user_id: int) -> int:
    """Evaluate quotes and create deduped in-app notifications. Returns new alert count."""
    settings = get_or_create_settings(db, user_id)
    if not settings.enabled:
        return 0

    threshold = float(settings.threshold_pct)
    holdings = db.query(Holding).filter(Holding.user_id == user_id).all()
    watchlist = db.query(WatchlistItem).filter(WatchlistItem.user_id == user_id).all()
    symbols: list[str] = []
    names: dict[str, str] = {}
    for h in holdings:
        symbols.append(h.symbol)
        names[h.symbol] = h.name
    for w in watchlist:
        if w.symbol not in names:
            symbols.append(w.symbol)
        names[w.symbol] = w.name

    unique_symbols = list(dict.fromkeys(symbols))
    if not unique_symbols:
        return 0

    quotes = await BatchQuoteProvider().get_quotes(unique_symbols)
    trading_day = date.today()
    created = 0

    for quote in quotes:
        change = float(quote.change_pct)
        if abs(change) < threshold:
            continue
        existing = (
            db.query(PriceAlertNotification)
            .filter(
                PriceAlertNotification.user_id == user_id,
                PriceAlertNotification.symbol == quote.symbol,
                PriceAlertNotification.trading_date == trading_day,
            )
            .first()
        )
        if existing is not None:
            continue
        display_name = names.get(quote.symbol) or quote.name or quote.symbol
        note = PriceAlertNotification(
            user_id=user_id,
            symbol=quote.symbol,
            name=display_name,
            change_pct=round(change, 2),
            threshold_pct=threshold,
            trading_date=trading_day,
            message=_format_message(display_name, quote.symbol, change, threshold),
            read=False,
            created_at=datetime.now(),
        )
        db.add(note)
        created += 1

    if created:
        db.commit()
        logger.info("Created %s price alert(s) for user %s", created, user_id)
    return created


async def check_price_alerts_for_all_users(db_factory) -> None:
    db = db_factory()
    try:
        from stockresearch.db.models import User

        users = db.query(User).all()
        for user in users:
            try:
                await check_price_alerts_for_user(db, user.id)
            except Exception as exc:
                logger.exception("Price alert check failed for user %s: %s", user.id, exc)
    finally:
        db.close()
