"""Prediction scoring scheduler — daily after close, after daily-bar refresh."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from stockresearch.db.session import SessionLocal
from stockresearch.services.prediction_journal import score_due_predictions

logger = logging.getLogger(__name__)


class PredictionScoringScheduler:
    """Score due predictions (Phase 12a) once daily after the bar refresh."""

    def __init__(self) -> None:
        self._scheduler: AsyncIOScheduler | None = None
        self.enabled = True

    def start(self) -> None:
        if self._scheduler is not None:
            return
        self._scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self._scheduler.add_job(
            self._run,
            trigger=CronTrigger(hour=16, minute=20, day_of_week="mon-fri"),
            id="prediction-scoring",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("Prediction scoring scheduler started")

    def shutdown(self) -> None:
        if self._scheduler is None:
            return
        self._scheduler.shutdown(wait=False)
        self._scheduler = None

    async def _run(self) -> None:
        if not self.enabled:
            return
        try:
            scored = await score_due_predictions(SessionLocal)
            if scored:
                logger.info("Prediction scoring done: %s scored", scored)
        except Exception as exc:
            logger.warning("Prediction scoring failed: %s", exc)
        try:
            from stockresearch.services.thesis_verification import check_due_theses

            checked = await check_due_theses(SessionLocal)
            if checked:
                logger.info("Thesis verification done: %s checked", checked)
        except Exception as exc:
            logger.warning("Thesis verification failed: %s", exc)


_scheduler: PredictionScoringScheduler | None = None


def get_prediction_scoring_scheduler() -> PredictionScoringScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = PredictionScoringScheduler()
    return _scheduler
