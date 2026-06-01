"""Research routes."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from invesbao.agents.research.runner import run_research
from invesbao.agents.research.stream import run_research_stream
from invesbao.api.deps import get_current_user
from invesbao.core.schemas import ResearchReportOut
from invesbao.db.models import ResearchReport, User
from invesbao.db.session import get_db
from invesbao.services.cache import CacheService

router = APIRouter(prefix="/research", tags=["research"])


def _persist_report(db: Session, user_id: int, report: ResearchReportOut) -> None:
    db.add(
        ResearchReport(
            user_id=user_id,
            symbol=report.symbol,
            name=report.name,
            report_json=report.model_dump(mode="json"),
        )
    )
    db.commit()


@router.get("/analyze", response_model=ResearchReportOut)
async def analyze_stock(
    symbol: str = Query(min_length=6, max_length=6, pattern=r"^\d{6}$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchReportOut:
    cache = CacheService()
    cache_key = f"research:{symbol}"
    cached = cache.get_json(cache_key)
    if cached:
        report = ResearchReportOut.model_validate({**cached, "cached": True})
    else:
        report = await run_research(symbol)
        cache.set_json(cache_key, report.model_dump(mode="json"), ttl_seconds=86400)

    _persist_report(db, user.id, report)
    return report


@router.get("/analyze/stream")
async def analyze_stock_stream(
    symbol: str = Query(min_length=6, max_length=6, pattern=r"^\d{6}$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    cache = CacheService()
    cache_key = f"research:{symbol}"

    async def event_generator() -> AsyncIterator[str]:
        cached = cache.get_json(cache_key)
        if cached:
            report = ResearchReportOut.model_validate({**cached, "cached": True})
            yield f"data: {json.dumps({'type': 'status', 'message': '命中缓存，直接返回报告'}, ensure_ascii=False)}\n\n"
            payload = {"type": "done", "result": report.model_dump(mode="json")}
            yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
            return

        final: ResearchReportOut | None = None
        async for event in run_research_stream(symbol):
            if event.get("type") == "done":
                raw = event.get("result")
                if isinstance(raw, dict):
                    final = ResearchReportOut.model_validate(raw)
                    cache.set_json(cache_key, final.model_dump(mode="json"), ttl_seconds=86400)
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        if final is not None:
            _persist_report(db, user.id, final)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
