"""News routes."""

import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from stockresearch.agents.news.agent import get_news_for_user
from stockresearch.agents.news.deep_analyzer import run_news_deep_analysis_stream
from stockresearch.api.deps import get_current_user
from stockresearch.api.llm_deps import llm_from_headers
from stockresearch.api.sse import sse_response
from stockresearch.core.constants import AVAILABLE_SECTORS
from stockresearch.core.schemas import (
    NewsIngestAcceptedOut,
    NewsIngestJobOut,
    NewsItemOut,
    SectorPreferencesOut,
    SectorPreferencesUpdate,
)
from stockresearch.db.models import NewsItem, User
from stockresearch.db.session import get_db
from stockresearch.services.news_ingest_jobs import create_job, get_job, run_ingest_job
from stockresearch.services.news_interests import (
    list_user_sectors,
    load_user_news_interests,
    save_user_sectors,
)
from stockresearch.utils.llm import LLMClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/sectors", response_model=SectorPreferencesOut)
def sector_preferences(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SectorPreferencesOut:
    return SectorPreferencesOut(
        available=list(AVAILABLE_SECTORS),
        selected=list_user_sectors(db, user.id),
    )


@router.put("/sectors", response_model=SectorPreferencesOut)
def update_sector_preferences(
    payload: SectorPreferencesUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SectorPreferencesOut:
    selected = save_user_sectors(db, user.id, payload.sectors)
    return SectorPreferencesOut(available=list(AVAILABLE_SECTORS), selected=selected)


@router.post(
    "/ingest",
    response_model=NewsIngestAcceptedOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_news(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=20, le=50),
) -> NewsIngestAcceptedOut:
    interests = load_user_news_interests(db, user.id)
    job = create_job(user.id)
    background_tasks.add_task(run_ingest_job, job.job_id, user.id, interests, limit)
    return NewsIngestAcceptedOut(job_id=job.job_id, status="queued")


@router.get("/ingest/{job_id}", response_model=NewsIngestJobOut)
def ingest_job_status(
    job_id: str,
    user: User = Depends(get_current_user),
) -> NewsIngestJobOut:
    job = get_job(job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Ingest job not found")
    return NewsIngestJobOut(
        job_id=job.job_id,
        status=job.status,
        inserted=job.inserted,
        scanned=job.scanned,
        skipped=job.skipped,
        purged=job.purged,
        message=job.message,
        error=job.error,
    )


@router.get("/feed", response_model=list[NewsItemOut])
async def news_feed(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    related_only: bool = False,
    limit: int = Query(default=20, le=50),
) -> list[NewsItemOut]:
    from stockresearch.services.news_interests import purge_irrelevant_news

    interests = load_user_news_interests(db, user.id)
    purge_irrelevant_news(db, interests)
    return await get_news_for_user(db, user.id, related_only=related_only, limit=limit)


@router.get("/{news_id}/analyze/stream")
async def analyze_news_stream(
    news_id: int,
    symbol: str = Query(min_length=6, max_length=6, pattern=r"^\d{6}$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
) -> StreamingResponse:
    item = db.query(NewsItem).filter(NewsItem.id == news_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="News item not found")

    async def event_generator() -> AsyncIterator[dict[str, object]]:
        try:
            async for event in run_news_deep_analysis_stream(
                title=item.title,
                summary=item.summary,
                content=item.content or "",
                source=item.source,
                symbol=symbol,
                entities=item.entities or [],
                news_id=item.id,
                llm=llm,
            ):
                yield event
        except Exception as exc:
            logger.warning("news deep analysis stream failed: %s", exc, exc_info=True)
            yield {
                "type": "error",
                "code": "news_stream_failed",
                "message": str(exc) or "新闻分析流中断",
            }

    return sse_response(event_generator(), keep_alive_seconds=15.0)
