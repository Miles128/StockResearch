"""Research routes."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session

from stockresearch.agents.research.runner import run_research
from stockresearch.agents.research.stream import run_research_stream
from stockresearch.api.deps import get_current_user
from stockresearch.api.llm_deps import llm_from_headers
from stockresearch.core.exceptions import NotFoundError
from stockresearch.core.schemas import ResearchReportListItem, ResearchReportOut
from stockresearch.db.models import ResearchReport, User
from stockresearch.db.session import get_db
from stockresearch.services.cache import CacheService
from stockresearch.services.report_export import report_to_markdown
from stockresearch.utils.llm import LLMClient

router = APIRouter(prefix="/research", tags=["research"])


def persist_report(db: Session, user_id: int, report: ResearchReportOut) -> ResearchReport:
    row = ResearchReport(
        user_id=user_id,
        symbol=report.symbol,
        name=report.name,
        report_json=report.model_dump(mode="json"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def extract_reports_from_cards(cards: list[dict[str, object]]) -> list[ResearchReportOut]:
    reports: list[ResearchReportOut] = []
    for card in cards:
        if card.get("type") != "research":
            continue
        data = card.get("data")
        if isinstance(data, dict):
            reports.append(ResearchReportOut.model_validate(data))
    return reports


@router.get("/analyze", response_model=ResearchReportOut)
async def analyze_stock(
    symbol: str = Query(min_length=6, max_length=6, pattern=r"^\d{6}$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
) -> ResearchReportOut:
    cache = CacheService()
    cache_key = f"research:{symbol}"
    cached = cache.get_json(cache_key)
    if cached:
        report = ResearchReportOut.model_validate({**cached, "cached": True})
    else:
        report = await run_research(symbol, llm=llm)
        cache.set_json(cache_key, report.model_dump(mode="json"), ttl_seconds=86400)

    persist_report(db, user.id, report)
    return report


@router.get("/analyze/stream")
async def analyze_stock_stream(
    symbol: str = Query(min_length=6, max_length=6, pattern=r"^\d{6}$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
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
        async for event in run_research_stream(symbol, llm=llm):
            if event.get("type") == "done":
                raw = event.get("result")
                if isinstance(raw, dict):
                    final = ResearchReportOut.model_validate(raw)
                    cache.set_json(cache_key, final.model_dump(mode="json"), ttl_seconds=86400)
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        if final is not None:
            persist_report(db, user.id, final)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/reports", response_model=list[ResearchReportListItem])
def list_reports(
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ResearchReportListItem]:
    rows = (
        db.query(ResearchReport)
        .filter(ResearchReport.user_id == user.id)
        .order_by(ResearchReport.created_at.desc())
        .limit(limit)
        .all()
    )
    items: list[ResearchReportListItem] = []
    for row in rows:
        payload = row.report_json if isinstance(row.report_json, dict) else {}
        items.append(
            ResearchReportListItem(
                id=row.id,
                symbol=row.symbol,
                name=row.name,
                composite_score=float(payload.get("composite_score", 0)),
                bias=str(payload.get("bias", "neutral")),
                summary=str(payload.get("summary", ""))[:200],
                has_debate=payload.get("debate") is not None,
                created_at=row.created_at,
            )
        )
    return items


@router.get("/reports/{report_id}", response_model=ResearchReportOut)
def get_report(
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchReportOut:
    row = (
        db.query(ResearchReport)
        .filter(ResearchReport.id == report_id, ResearchReport.user_id == user.id)
        .first()
    )
    if row is None:
        raise NotFoundError("报告不存在")
    return ResearchReportOut.model_validate(row.report_json)


@router.get("/reports/{report_id}/markdown", response_class=PlainTextResponse)
def export_report_markdown(
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    row = (
        db.query(ResearchReport)
        .filter(ResearchReport.id == report_id, ResearchReport.user_id == user.id)
        .first()
    )
    if row is None:
        raise NotFoundError("报告不存在")
    report = ResearchReportOut.model_validate(row.report_json)
    filename = f"stockresearch-{report.symbol}-{row.id}.md"
    return PlainTextResponse(
        content=report_to_markdown(report),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
