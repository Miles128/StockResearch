"""In-memory news ingest job registry for async background ingestion."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from stockresearch.data.pipeline.news import NewsPipeline
from stockresearch.db.session import SessionLocal
from stockresearch.services.news_interests import UserNewsInterests, purge_irrelevant_news

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

JobStatus = Literal["queued", "running", "completed", "failed"]


@dataclass
class NewsIngestJob:
    job_id: str
    user_id: int
    status: JobStatus = "queued"
    inserted: int = 0
    scanned: int = 0
    skipped: int = 0
    purged: int = 0
    message: str = ""
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None


_jobs: dict[str, NewsIngestJob] = {}


def create_job(user_id: int) -> NewsIngestJob:
    job = NewsIngestJob(job_id=str(uuid.uuid4()), user_id=user_id)
    _jobs[job.job_id] = job
    return job


def get_job(job_id: str) -> NewsIngestJob | None:
    return _jobs.get(job_id)


def clear_jobs() -> None:
    """Test helper: reset in-memory job store."""
    _jobs.clear()


async def run_ingest_job(
    job_id: str,
    user_id: int,
    interests: UserNewsInterests,
    limit: int,
    db_factory: Callable[[], Session] = SessionLocal,
) -> None:
    job = _jobs.get(job_id)
    if job is None:
        return
    job.status = "running"
    db: Session = db_factory()
    try:
        pipeline = NewsPipeline()
        result = await pipeline.ingest(db, interests, limit=limit)
        purged = purge_irrelevant_news(db, interests)
        job.inserted = result.inserted
        job.scanned = result.scanned
        job.skipped = result.skipped
        job.purged = purged
        job.message = f"{result.message}；清理旧快讯 {purged} 条"
        job.status = "completed"
        job.finished_at = datetime.now(UTC)
    except Exception as exc:
        logger.exception("News ingest job %s failed for user %s: %s", job_id, user_id, exc)
        job.status = "failed"
        job.error = str(exc) or "news ingest failed"
        job.message = job.error
        job.finished_at = datetime.now(UTC)
    finally:
        db.close()
