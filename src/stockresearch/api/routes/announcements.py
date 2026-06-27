"""Announcements routes — 巨潮公告查询。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from stockresearch.api.deps import get_current_user
from stockresearch.core.schemas import AnnouncementItemOut
from stockresearch.data.providers.announcements import AnnouncementProvider
from stockresearch.db.models import Holding, User
from stockresearch.db.session import get_db

router = APIRouter(prefix="/announcements", tags=["announcements"])


@router.get("/symbol/{symbol}", response_model=list[AnnouncementItemOut])
async def symbol_announcements(
    symbol: str,
    name: str = Query(default=""),
    category: str = Query(default="", description="公告类别筛选关键字，如 年报/减持/重大事项"),
    days: int = Query(default=30, ge=1, le=180),
    limit: int = Query(default=20, ge=1, le=50),
    _user: User = Depends(get_current_user),
) -> list[AnnouncementItemOut]:
    """查询单只股票最近 N 天的巨潮公告。"""
    items = await AnnouncementProvider().fetch_announcements(
        symbol,
        name,
        category=category,
        days=days,
        limit=limit,
    )
    return [_to_out(item) for item in items]


@router.get("/holdings", response_model=list[AnnouncementItemOut])
async def holdings_announcements(
    category: str = Query(default=""),
    days: int = Query(default=30, ge=1, le=180),
    per_symbol_limit: int = Query(default=5, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AnnouncementItemOut]:
    """批量查询当前用户所有持仓股票的最近公告，按时间倒序合并。"""
    holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
    if not holdings:
        return []
    symbol_pairs = [(h.symbol, h.name or "") for h in holdings]
    items = await AnnouncementProvider().fetch_latest_for_symbols(
        symbol_pairs,
        category=category,
        days=days,
        per_symbol_limit=per_symbol_limit,
    )
    return [_to_out(item) for item in items]


def _to_out(item) -> AnnouncementItemOut:  # type: ignore[no-untyped-def]
    return AnnouncementItemOut(
        title=item.title,
        announcement_type=item.announcement_type,
        announcement_time=item.announcement_time,
        symbol=item.symbol,
        name=item.name,
        url=item.url,
        source="cninfo",
    )
