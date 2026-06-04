"""News routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from stockresearch.agents.news.agent import get_news_for_user
from stockresearch.api.deps import get_current_user
from stockresearch.core.constants import AVAILABLE_SECTORS
from stockresearch.core.schemas import NewsIngestOut, NewsItemOut, SectorPreferencesOut, SectorPreferencesUpdate
from stockresearch.data.pipeline.news import NewsPipeline
from stockresearch.db.models import User
from stockresearch.db.session import get_db
from stockresearch.services.news_interests import (
    load_user_news_interests,
    list_user_sectors,
    purge_irrelevant_news,
    save_user_sectors,
)

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
