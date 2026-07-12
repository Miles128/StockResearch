"""Post-close daily bar warehouse refresh scheduler."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from stockresearch.services.daily_bars import refresh_universe_bars

logger = logging.getLogger(__name__)


class DailyBarScheduler:
    """Refresh local OHLCV for holdings + watchlist after the close."""

    def __init__(self) -> None:
        self._scheduler: AsyncIOScheduler | None = None
        self.enabled = True

    def start(self) -> None:
        if self._scheduler is not None:
            return
        self._scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self._scheduler.add_job(
            self._refresh,
            trigger=CronTrigger(hour=16, minute=5, day_of_week="mon-fri"),
            id="daily-bars-refresh",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("Daily bar scheduler started (enabled=%s)", self.enabled)

    def shutdown(self) -> None:
        if self._scheduler is None:
            return
        self._scheduler.shutdown(wait=False)
        self._scheduler = None
        logger.info("Daily bar scheduler stopped")

    async def _refresh(self) -> None:
        if not self.enabled:
            return
        try:
            updated = await refresh_universe_bars(days=120)
            logger.info("Daily bar refresh done: %s symbols", len(updated))
        except Exception as exc:
            logger.warning("Daily bar refresh failed: %s", exc)


_scheduler: DailyBarScheduler | None = None


def get_daily_bar_scheduler() -> DailyBarScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = DailyBarScheduler()
    return _scheduler
