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
from stockresearch.core.output_style import output_style_scope
from stockresearch.core.schemas import RiskCheckupOut, RiskCheckupRequest
from stockresearch.db.models import Holding, RiskAlertRecord, User
from stockresearch.db.session import get_db
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


def _master_on(payload: RiskCheckupRequest, settings) -> bool:
    if payload.enable_master_commentary is not None:
        return bool(payload.enable_master_commentary)
    return bool(settings.enable_master_commentary)


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
            enable_master_commentary=_master_on(payload, settings),
            enable_llm_analysis=_llm_analysis_on(payload),
            mode_settings=settings,
        )
    _persist_alerts(db, user.id, result)
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
                enable_master_commentary=_master_on(payload, settings),
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
