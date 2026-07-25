"""A-share continuous trading session (Asia/Shanghai)."""

import logging
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from stockresearch.services.trading_calendar import is_a_share_trading_day

logger = logging.getLogger(__name__)

_SH_TZ = ZoneInfo("Asia/Shanghai")
MarketSession = Literal["trading", "closed"]


def a_share_market_session(now: datetime | None = None) -> MarketSession:
    """Return trading when continuous matching is open; otherwise closed (use closing price)."""
    dt = (now or datetime.now(tz=_SH_TZ)).astimezone(_SH_TZ)
    if dt.weekday() >= 5:
        return "closed"
    try:
        if not is_a_share_trading_day(date(dt.year, dt.month, dt.day)):
            return "closed"
    except Exception:
        logger.warning(
            "trading calendar check failed; falling back to weekday+session hours",
            exc_info=True,
        )
    minutes = dt.hour * 60 + dt.minute
    morning = 9 * 60 + 30 <= minutes < 11 * 60 + 30
    afternoon = 13 * 60 <= minutes < 15 * 60
    return "trading" if morning or afternoon else "closed"


def price_label_for_session(session: MarketSession) -> str:
    return "现价" if session == "trading" else "收盘"
