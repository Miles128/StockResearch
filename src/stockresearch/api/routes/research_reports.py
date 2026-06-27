"""Research reports routes — 东方财富机构研报查询。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from stockresearch.api.deps import get_current_user
from stockresearch.core.schemas import ResearchReportItemOut
from stockresearch.data.providers.research_reports import ResearchReportProvider
from stockresearch.db.models import Holding, User
from stockresearch.db.session import get_db

router = APIRouter(prefix="/research-reports", tags=["research-reports"])


@router.get("/symbol/{symbol}", response_model=list[ResearchReportItemOut])
async def symbol_research_reports(
    symbol: str,
    name: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=50),
    _user: User = Depends(get_current_user),
) -> list[ResearchReportItemOut]:
    """查询单只股票最近的东方财富机构研报。"""
    items = await ResearchReportProvider().fetch_reports(symbol, name, limit=limit)
    return [_to_out(item) for item in items]


@router.get("/holdings", response_model=list[ResearchReportItemOut])
async def holdings_research_reports(
    per_symbol_limit: int = Query(default=5, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ResearchReportItemOut]:
    """批量查询当前用户所有持仓股票的最近研报，按发布时间倒序合并。"""
    holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
    if not holdings:
        return []
    symbol_pairs = [(h.symbol, h.name or "") for h in holdings]
    items = await ResearchReportProvider().fetch_latest_for_symbols(
        symbol_pairs,
        per_symbol_limit=per_symbol_limit,
    )
    return [_to_out(item) for item in items]


def _to_out(item) -> ResearchReportItemOut:  # type: ignore[no-untyped-def]
    return ResearchReportItemOut(
        title=item.title,
        institution=item.institution,
        analyst=item.analyst,
        rating=item.rating,
        target_price=item.target_price,
        publish_date=item.publish_date,
        symbol=item.symbol,
        name=item.name,
        summary=item.summary,
        source="eastmoney",
    )
