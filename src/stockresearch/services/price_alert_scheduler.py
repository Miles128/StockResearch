"""Interval scheduler for price change alerts."""

from __future__ import annotations

import logging
from datetime import date, datetime, time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from stockresearch.db.session import SessionLocal
from stockresearch.services.price_alerts import check_price_alerts_for_all_users
from stockresearch.services.trading_calendar import is_a_share_trading_day

logger = logging.getLogger(__name__)

_MARKET_OPEN = time(9, 25)
_MARKET_CLOSE = time(15, 10)


class PriceAlertScheduler:
    def __init__(self) -> None:
        self._scheduler: AsyncIOScheduler | None = None
        self.enabled = True

    def start(self) -> None:
        if self._scheduler is not None:
            return
        self._scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self._scheduler.add_job(
            self._run_check,
            trigger=IntervalTrigger(minutes=5),
            id="price-alerts",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("Price alert scheduler started")

    def shutdown(self) -> None:
        if self._scheduler is None:
            return
        self._scheduler.shutdown(wait=False)
        self._scheduler = None

    async def _run_check(self) -> None:
        if not self.enabled:
            return
        now = datetime.now()
        today = date.today()
        try:
            if not is_a_share_trading_day(today):
                return
        except Exception:
            if today.weekday() >= 5:
                return
        if not (_MARKET_OPEN <= now.time() <= _MARKET_CLOSE):
            return
        await check_price_alerts_for_all_users(SessionLocal)


price_alert_scheduler = PriceAlertScheduler()


def get_price_alert_scheduler() -> PriceAlertScheduler:
    return price_alert_scheduler
