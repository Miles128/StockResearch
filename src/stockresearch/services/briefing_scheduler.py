"""Scheduled morning/closing briefing generation."""

import logging
from datetime import date, datetime, time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from stockresearch.db.models import BriefingRecord, User
from stockresearch.db.session import SessionLocal
from stockresearch.services.briefing import generate_briefing
from stockresearch.services.trading_calendar import is_a_share_trading_day
from stockresearch.utils.llm import LLMClient

logger = logging.getLogger(__name__)

_MORNING_HOUR = 9
_MORNING_MINUTE = 0
_CLOSING_HOUR = 15
_CLOSING_MINUTE = 30


class BriefingScheduler:
    """Cron scheduler that auto-generates morning and closing briefings."""

    def __init__(self) -> None:
        self._scheduler: AsyncIOScheduler | None = None
        self.enabled = True
        self._job_ids: set[str] = set()

    def start(self) -> None:
        if self._scheduler is not None:
            return
        self._scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self._scheduler.add_job(
            self._generate_morning,
            trigger=CronTrigger(
                hour=_MORNING_HOUR,
                minute=_MORNING_MINUTE,
                day_of_week="mon-fri",
            ),
            id="briefing-morning",
            replace_existing=True,
        )
        self._scheduler.add_job(
            self._generate_closing,
            trigger=CronTrigger(
                hour=_CLOSING_HOUR,
                minute=_CLOSING_MINUTE,
                day_of_week="mon-fri",
            ),
            id="briefing-closing",
            replace_existing=True,
        )
        self._job_ids = {"briefing-morning", "briefing-closing"}
        self._scheduler.start()
        logger.info("Briefing scheduler started (enabled=%s)", self.enabled)

    def shutdown(self) -> None:
        if self._scheduler is None:
            return
        self._scheduler.shutdown(wait=False)
        self._scheduler = None
        self._job_ids.clear()

    def set_enabled(self, enabled: bool) -> None:
        if self.enabled == enabled:
            return
        self.enabled = enabled
        if self._scheduler is None:
            return
        for job_id in self._job_ids:
            job = self._scheduler.get_job(job_id)
            if job is not None:
                if enabled:
                    self._scheduler.resume_job(job_id)
                else:
                    self._scheduler.pause_job(job_id)
        logger.info("Briefing scheduler enabled set to %s", enabled)

    async def _generate_morning(self) -> None:
        await self._generate_if_trading_day("morning")

    async def _generate_closing(self) -> None:
        await self._generate_if_trading_day("closing")

    async def _generate_if_trading_day(self, kind: str) -> None:
        if not self.enabled:
            logger.debug("Briefing scheduler disabled; skipping %s", kind)
            return
        today = date.today()
        try:
            if not is_a_share_trading_day(today):
                logger.info("Skipping %s briefing: %s is not an A-share trading day", kind, today)
                return
        except Exception as exc:
            logger.warning(
                "Trading calendar check failed for %s: %s; falling back to weekday", kind, exc
            )
            if today.weekday() >= 5:
                return
        await self._generate_for_all_users(kind)

    async def _generate_for_all_users(self, kind: str) -> None:
        db = SessionLocal()
        try:
            users = db.query(User).all()
            for user in users:
                try:
                    await self._generate_for_user(db, user.id, kind)
                except Exception as exc:
                    logger.exception(
                        "Failed to generate %s briefing for user %s: %s", kind, user.id, exc
                    )
        finally:
            db.close()

    async def _generate_for_user(self, db: Session, user_id: int, kind: str) -> None:
        today = date.today()
        start = datetime.combine(today, time.min)
        end = datetime.combine(today, time.max)
        existing = (
            db.query(BriefingRecord)
            .filter(
                BriefingRecord.user_id == user_id,
                BriefingRecord.kind == kind,
                BriefingRecord.generated_at >= start,
                BriefingRecord.generated_at <= end,
            )
            .first()
        )
        if existing is not None:
            logger.info("%s briefing already exists for user %s today", kind, user_id)
            return

        logger.info("Generating %s briefing for user %s", kind, user_id)
        briefing = await generate_briefing(db, user_id, kind, llm=LLMClient())
        generated_at = briefing.generated_at
        if generated_at.tzinfo:
            generated_at = generated_at.replace(tzinfo=None)
        record = BriefingRecord(
            user_id=user_id,
            kind=kind,
            title=briefing.title,
            summary=briefing.summary,
            sections=[{"title": s.title, "content": s.content} for s in briefing.sections],
            generated_at=generated_at,
        )
        db.add(record)
        db.commit()
        logger.info("Saved %s briefing for user %s", kind, user_id)


scheduler = BriefingScheduler()


def get_scheduler() -> BriefingScheduler:
    return scheduler
