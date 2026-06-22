"""News routes."""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from stockresearch.agents.news.agent import get_news_for_user
from stockresearch.agents.news.deep_analyzer import run_news_deep_analysis_stream
from stockresearch.api.deps import get_current_user
from stockresearch.api.llm_deps import llm_from_headers
from stockresearch.core.constants import AVAILABLE_SECTORS
from stockresearch.core.schemas import (
    NewsIngestOut,
    NewsItemOut,
    SectorPreferencesOut,
    SectorPreferencesUpdate,
)
from stockresearch.data.pipeline.news import NewsPipeline
from stockresearch.db.models import NewsItem, User
from stockresearch.db.session import get_db
from stockresearch.services.news_interests import (
    list_user_sectors,
    load_user_news_interests,
    purge_irrelevant_news,
    save_user_sectors,
)
from stockresearch.utils.llm import LLMClient

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


@router.post("/ingest", response_model=NewsIngestOut)
async def ingest_news(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=20, le=50),
) -> NewsIngestOut:
    interests = load_user_news_interests(db, user.id)
    pipeline = NewsPipeline()
    result = await pipeline.ingest(db, interests, limit=limit)
    purged = purge_irrelevant_news(db, interests)
    return NewsIngestOut(
        inserted=result.inserted,
        scanned=result.scanned,
        skipped=result.skipped,
        purged=purged,
        message=f"{result.message}；清理旧快讯 {purged} 条",
    )


@router.get("/feed", response_model=list[NewsItemOut])
async def news_feed(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    related_only: bool = False,
    limit: int = Query(default=20, le=50),
) -> list[NewsItemOut]:
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

    async def event_generator():
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
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
