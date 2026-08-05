"""Risk routes."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Body, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from stockresearch.agents.risk.engine import run_risk_checkup
from stockresearch.agents.risk.stream import run_risk_checkup_stream
from stockresearch.api.deps import get_current_user
from stockresearch.api.llm_deps import llm_from_headers
from stockresearch.core.output_style import (
    get_custom_glossary,
    get_enable_glossary,
    output_style_scope,
)
from stockresearch.core.schemas import RiskCheckupOut, RiskCheckupRequest
from stockresearch.db.models import Holding, RiskAlertRecord, User
from stockresearch.db.session import get_db
from stockresearch.services.glossary import mark_terms, merge_glossary
from stockresearch.services.user_preferences import get_mode_settings
from stockresearch.utils.llm import LLMClient

router = APIRouter(prefix="/risk", tags=["risk"])


def _persist_alerts(db: Session, user_id: int, result: RiskCheckupOut) -> None:
    for alert in result.alerts:
        db.add(
            RiskAlertRecord(
                user_id=user_id,
                rule_id=alert.rule_id,
                severity=alert.severity,
                symbol=alert.symbol,
                message=alert.message,
            )
        )
    db.commit()


def _mark_text(text: str) -> str:
    """词库标注：仅在用户开启词库解释时生效，不污染 DB 原文。"""
    if not text or not get_enable_glossary():
        return text
    return mark_terms(text, glossary=merge_glossary(get_custom_glossary()))


def _mark_risk_result(result: RiskCheckupOut) -> RiskCheckupOut:
    """返回层词库标注（仅展示用，DB 落库原文已在此之前完成）。"""
    result.portfolio_summary = _mark_text(result.portfolio_summary)
    for alert in result.alerts:
        alert.human_message = _mark_text(alert.human_message)
    if result.llm_analysis:
        a = result.llm_analysis
        a.market_assessment = _mark_text(a.market_assessment)
        a.correlation_analysis = _mark_text(a.correlation_analysis)
        a.risk_narrative = _mark_text(a.risk_narrative)
        a.scenario_analysis = [_mark_text(x) for x in a.scenario_analysis]
        a.position_action = _mark_text(a.position_action)
        a.analysis_process = _mark_text(a.analysis_process)
    return result


def _llm_analysis_on(payload: RiskCheckupRequest) -> bool:
    """PRD §四: 可选 LLM 解读。payload 显式传入优先;默认 True 保持向后兼容。"""
    if payload.enable_llm_analysis is not None:
        return bool(payload.enable_llm_analysis)
    return True


@router.post("/checkup", response_model=RiskCheckupOut)
async def risk_checkup(
    payload: RiskCheckupRequest = Body(default_factory=RiskCheckupRequest),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
) -> RiskCheckupOut:
    holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
    settings = get_mode_settings(db, user.id)
    with output_style_scope(
        reading_mode=payload.reading_mode,
        locale=payload.output_locale,
    ):
        result = await run_risk_checkup(
            holdings,
            llm=llm,
            enable_llm_analysis=_llm_analysis_on(payload),
            mode_settings=settings,
        )
        _persist_alerts(db, user.id, result)
        # 返回层词库标注（不污染 DB 原文）
        result = _mark_risk_result(result)
    return result


@router.post("/checkup/stream")
async def risk_checkup_stream(
    payload: RiskCheckupRequest = Body(default_factory=RiskCheckupRequest),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
) -> StreamingResponse:
    holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
    settings = get_mode_settings(db, user.id)

    async def event_generator() -> AsyncIterator[str]:
        final: RiskCheckupOut | None = None
        with output_style_scope(
            reading_mode=payload.reading_mode,
            locale=payload.output_locale,
        ):
            async for event in run_risk_checkup_stream(
                holdings,
                llm=llm,
                enable_llm_analysis=_llm_analysis_on(payload),
                mode_settings=settings,
            ):
                if event.get("type") == "done":
                    payload_data = event.get("result")
                    if isinstance(payload_data, dict):
                        final = RiskCheckupOut.model_validate(payload_data)
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        if final is not None:
            _persist_alerts(db, user.id, final)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
