"""Portfolio briefing routes."""

from typing import Literal

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from stockresearch.api.deps import get_current_user
from stockresearch.api.llm_deps import llm_from_headers
from stockresearch.core.output_style import (
    get_custom_glossary,
    get_enable_glossary,
    output_style_scope,
)
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
from stockresearch.services.glossary import mark_terms, merge_glossary
from stockresearch.services.user_preferences import get_mode_settings
from stockresearch.utils.llm import LLMClient

router = APIRouter(prefix="/briefing", tags=["briefing"])

BriefingKindParam = Literal[
    "premarket", "intraday", "postmarket", "morning", "closing", "pre_market"
]


def _mark_text(text: str) -> str:
    """词库标注：仅在用户开启词库解释时生效，不污染 DB 原文。"""
    if not text or not get_enable_glossary():
        return text
    return mark_terms(text, glossary=merge_glossary(get_custom_glossary()))


def _record_to_out(record: BriefingRecord, db: Session, user_id: int) -> BriefingRecordOut:
    settings = get_mode_settings(db, user_id)
    with output_style_scope(
        reading_mode=settings.reading_mode,
        locale="zh",
        enable_glossary=settings.enable_glossary,
    ):
        sections = [
            BriefingSection.model_validate(item) if isinstance(item, dict) else item
            for item in (record.sections or [])
        ]
        return BriefingRecordOut(
            id=record.id,
            kind=normalize_briefing_kind(record.kind),
            title=_mark_text(record.title),
            summary=_mark_text(record.summary),
            sections=[
                BriefingSection(title=_mark_text(s.title), content=_mark_text(s.content))
                for s in sections
            ],
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
        briefing = await generate_briefing(db, user.id, normalized, llm=llm)
        # 返回层词库标注（不污染 DB 原文）
        briefing.title = _mark_text(briefing.title)
        briefing.summary = _mark_text(briefing.summary)
        briefing.sections = [
            BriefingSection(title=_mark_text(s.title), content=_mark_text(s.content))
            for s in briefing.sections
        ]
    return briefing


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
    return _record_to_out(record, db, user.id)


@router.get("/history", response_model=list[BriefingRecordOut])
def get_briefing_history(
    kind: Literal[
        "premarket", "intraday", "postmarket", "morning", "closing", "pre_market", "all"
    ] = Query(default="all"),
    limit: int = Query(default=10, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BriefingRecordOut]:
    query = db.query(BriefingRecord).filter(BriefingRecord.user_id == user.id)
    if kind != "all":
        query = query.filter(BriefingRecord.kind.in_(briefing_kind_aliases(kind)))
    records = query.order_by(BriefingRecord.generated_at.desc()).limit(limit).all()
    return [_record_to_out(r, db, user.id) for r in records]


@router.get("/schedule", response_model=BriefingScheduleStatus)
def get_briefing_schedule_status() -> BriefingScheduleStatus:
    return BriefingScheduleStatus(enabled=get_scheduler().enabled)


@router.put("/schedule", response_model=BriefingScheduleStatus)
def set_briefing_schedule_status(
    enabled: bool = Query(...),
) -> BriefingScheduleStatus:
    get_scheduler().set_enabled(enabled)
    return BriefingScheduleStatus(enabled=get_scheduler().enabled)
