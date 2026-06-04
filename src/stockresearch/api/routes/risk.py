"""Risk routes."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from stockresearch.agents.risk.engine import run_risk_checkup
from stockresearch.agents.risk.stream import run_risk_checkup_stream
from stockresearch.api.deps import get_current_user
from stockresearch.api.llm_deps import llm_from_headers
from stockresearch.utils.llm import LLMClient
from stockresearch.core.schemas import RiskCheckupOut
from stockresearch.db.models import Holding, RiskAlertRecord, User
from stockresearch.db.session import get_db

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


@router.post("/checkup", response_model=RiskCheckupOut)
async def risk_checkup(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
) -> RiskCheckupOut:
    holdings = db.query(Holding).filter(Holding.user_id == user.id).all()
    result = await run_risk_checkup(holdings, llm=llm)
    _persist_alerts(db, user.id, result)
    return result


@router.post("/checkup/stream")
async def risk_checkup_stream(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
) -> StreamingResponse:
    holdings = db.query(Holding).filter(Holding.user_id == user.id).all()

    async def event_generator() -> AsyncIterator[str]:
        final: RiskCheckupOut | None = None
        async for event in run_risk_checkup_stream(holdings, llm=llm):
            if event.get("type") == "done":
                payload = event.get("result")
                if isinstance(payload, dict):
                    final = RiskCheckupOut.model_validate(payload)
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        if final is not None:
            _persist_alerts(db, user.id, final)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
