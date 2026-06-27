"""Portfolio briefing routes."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from stockresearch.api.deps import get_current_user
from stockresearch.api.llm_deps import llm_from_headers
from stockresearch.core.schemas import BriefingOut, BriefingRecordOut, BriefingScheduleStatus
from stockresearch.db.models import BriefingRecord, User
from stockresearch.db.session import get_db
from stockresearch.services.briefing import generate_briefing
from stockresearch.services.briefing_scheduler import get_scheduler
from stockresearch.utils.llm import LLMClient

router = APIRouter(prefix="/briefing", tags=["briefing"])


@router.post("/generate", response_model=BriefingOut)
async def generate_portfolio_briefing(
    kind: Literal["morning", "closing"] = Query(default="morning"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
) -> BriefingOut:
    return await generate_briefing(db, user.id, kind, llm=llm)


@router.get("/latest", response_model=BriefingRecordOut | None)
def get_latest_briefing(
    kind: Literal["morning", "closing"] = Query(default="morning"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BriefingRecordOut | None:
    record = (
        db.query(BriefingRecord)
        .filter(BriefingRecord.user_id == user.id, BriefingRecord.kind == kind)
        .order_by(BriefingRecord.generated_at.desc())
        .first()
    )
    if record is None:
        return None
    return BriefingRecordOut.model_validate(record)


@router.get("/history", response_model=list[BriefingRecordOut])
def get_briefing_history(
    kind: Literal["morning", "closing", "all"] = Query(default="all"),
    limit: int = Query(default=10, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BriefingRecordOut]:
    query = db.query(BriefingRecord).filter(BriefingRecord.user_id == user.id)
    if kind != "all":
        query = query.filter(BriefingRecord.kind == kind)
    records = query.order_by(BriefingRecord.generated_at.desc()).limit(limit).all()
    return [BriefingRecordOut.model_validate(r) for r in records]


@router.get("/schedule", response_model=BriefingScheduleStatus)
def get_briefing_schedule_status() -> BriefingScheduleStatus:
    return BriefingScheduleStatus(enabled=get_scheduler().enabled)


@router.put("/schedule", response_model=BriefingScheduleStatus)
def set_briefing_schedule_status(
    enabled: bool = Query(...),
) -> BriefingScheduleStatus:
    get_scheduler().set_enabled(enabled)
    return BriefingScheduleStatus(enabled=get_scheduler().enabled)
