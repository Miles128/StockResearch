"""Portfolio briefing routes."""

from typing import Literal

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from stockresearch.agents.output_style import output_style_scope
from stockresearch.api.deps import get_current_user
from stockresearch.api.llm_deps import llm_from_headers
from stockresearch.core.schemas import (
    BriefingGenerateRequest,
    BriefingOut,
    BriefingRecordOut,
    BriefingScheduleStatus,
    BriefingSection,
)
from stockresearch.db.models import BriefingRecord, User
from stockresearch.db.session import get_db
from stockresearch.services.briefing import (
    briefing_kind_aliases,
    generate_briefing,
    normalize_briefing_kind,
)
from stockresearch.services.briefing_scheduler import get_scheduler
from stockresearch.services.user_preferences import get_mode_settings
from stockresearch.utils.llm import LLMClient

router = APIRouter(prefix="/briefing", tags=["briefing"])

BriefingKindParam = Literal["premarket", "intraday", "postmarket", "morning", "closing", "pre_market"]


def _record_to_out(record: BriefingRecord) -> BriefingRecordOut:
    sections = [
        BriefingSection.model_validate(item) if isinstance(item, dict) else item
        for item in (record.sections or [])
    ]
    return BriefingRecordOut(
        id=record.id,
        kind=normalize_briefing_kind(record.kind),
        title=record.title,
        summary=record.summary,
        sections=sections,
        generated_at=record.generated_at,
    )


@router.post("/generate", response_model=BriefingOut)
async def generate_portfolio_briefing(
    kind: BriefingKindParam = Query(default="intraday"),
    payload: BriefingGenerateRequest = Body(default_factory=BriefingGenerateRequest),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
) -> BriefingOut:
    settings = get_mode_settings(db, user.id)
    normalized = normalize_briefing_kind(kind)
    with output_style_scope(
        reading_mode=payload.reading_mode or settings.reading_mode,
        locale=payload.output_locale or "zh",
        enable_glossary=settings.enable_glossary,
    ):
        return await generate_briefing(db, user.id, normalized, llm=llm)


@router.get("/latest", response_model=BriefingRecordOut | None)
def get_latest_briefing(
    kind: BriefingKindParam = Query(default="intraday"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BriefingRecordOut | None:
    aliases = briefing_kind_aliases(kind)
    record = (
        db.query(BriefingRecord)
        .filter(BriefingRecord.user_id == user.id, BriefingRecord.kind.in_(aliases))
        .order_by(BriefingRecord.generated_at.desc())
        .first()
    )
    if record is None:
        return None
    return _record_to_out(record)


@router.get("/history", response_model=list[BriefingRecordOut])
def get_briefing_history(
    kind: Literal["premarket", "intraday", "postmarket", "morning", "closing", "pre_market", "all"] = Query(default="all"),
    limit: int = Query(default=10, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BriefingRecordOut]:
    query = db.query(BriefingRecord).filter(BriefingRecord.user_id == user.id)
    if kind != "all":
        query = query.filter(BriefingRecord.kind.in_(briefing_kind_aliases(kind)))
    records = query.order_by(BriefingRecord.generated_at.desc()).limit(limit).all()
    return [_record_to_out(r) for r in records]


@router.get("/schedule", response_model=BriefingScheduleStatus)
def get_briefing_schedule_status() -> BriefingScheduleStatus:
    return BriefingScheduleStatus(enabled=get_scheduler().enabled)


@router.put("/schedule", response_model=BriefingScheduleStatus)
def set_briefing_schedule_status(
    enabled: bool = Query(...),
) -> BriefingScheduleStatus:
    get_scheduler().set_enabled(enabled)
    return BriefingScheduleStatus(enabled=get_scheduler().enabled)
