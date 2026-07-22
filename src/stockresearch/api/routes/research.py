"""Research routes."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from stockresearch.agents.industry.research import run_industry_research
from stockresearch.agents.research.runner import run_research
from stockresearch.agents.research.stream import run_research_stream
from stockresearch.api.deps import get_current_user
from stockresearch.api.llm_deps import llm_from_headers
from stockresearch.core.exceptions import NotFoundError
from stockresearch.core.schemas import (
    BatchResearchItemOut,
    BatchResearchOut,
    BatchResearchRequest,
    CompareRequest,
    CompareTableOut,
    EventStudyOut,
    HypothesisVerifyOut,
    HypothesisVerifyRequest,
    IndustryResearchRequest,
    MemorySearchOut,
    ReportPostHocOut,
    ResearchReportListItem,
    ResearchReportOut,
    SignalBacktestOut,
)
from stockresearch.db.models import ResearchReport, User
from stockresearch.db.session import get_db
from stockresearch.agents.research.budget import resolve_analysis_depth
from stockresearch.services.cache import CacheService
from stockresearch.services.compare_table import build_compare_table, flatten_compare_csv
from stockresearch.services.event_study import compute_event_study
from stockresearch.services.hypothesis_verify import HYPOTHESIS_PRESETS, verify_hypothesis
from stockresearch.services.report_export import (
    report_to_csv,
    report_to_json,
    report_to_markdown,
    report_to_pdf,
)
from stockresearch.services.research_memory import search_research_memory
from stockresearch.services.signal_backtest import compute_report_post_hoc, compute_signal_backtest
from stockresearch.services.user_preferences import get_mode_settings
from stockresearch.utils.llm import LLMClient
from stockresearch.utils.symbols import resolve_name

router = APIRouter(prefix="/research", tags=["research"])


def persist_report(db: Session, user_id: int, report: ResearchReportOut) -> ResearchReport:
    payload = report.model_dump(mode="json")
    row = ResearchReport(
        user_id=user_id,
        symbol=report.symbol,
        name=report.name,
        report_json=payload,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    payload["id"] = row.id
    row.report_json = payload
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def stamp_report_id(report: ResearchReportOut, report_id: int) -> ResearchReportOut:
    return report.model_copy(update={"id": report_id})


def attach_report_ids_to_cards(
    cards: list[dict[str, object]],
    id_by_symbol: dict[str, int],
) -> list[dict[str, object]]:
    updated: list[dict[str, object]] = []
    for card in cards:
        if card.get("type") != "research":
            updated.append(card)
            continue
        data = card.get("data")
        if not isinstance(data, dict):
            updated.append(card)
            continue
        symbol = str(data.get("symbol", ""))
        report_id = id_by_symbol.get(symbol)
        if report_id is None:
            updated.append(card)
            continue
        marked = dict(data)
        marked["id"] = report_id
        updated.append({**card, "data": marked})
    return updated


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
    analysis_depth: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
) -> ResearchReportOut:
    settings = get_mode_settings(db, user.id)
    depth = resolve_analysis_depth(
        explicit=analysis_depth,
        settings_depth=settings.analysis_depth,
    )
    cache = CacheService()
    cache_key = f"research:{symbol}:{depth}"
    cached = cache.get_json(cache_key)
    if cached:
        report = ResearchReportOut.model_validate({**cached, "cached": True})
    else:
        report = await run_research(
            symbol, llm=llm, mode_settings=settings, analysis_depth=depth
        )
        cache.set_json(cache_key, report.model_dump(mode="json"), ttl_seconds=86400)

    row = persist_report(db, user.id, report)
    return stamp_report_id(report, row.id)


@router.get("/analyze/stream")
async def analyze_stock_stream(
    symbol: str = Query(min_length=6, max_length=6, pattern=r"^\d{6}$"),
    analysis_depth: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
) -> StreamingResponse:
    settings = get_mode_settings(db, user.id)
    depth = resolve_analysis_depth(
        explicit=analysis_depth,
        settings_depth=settings.analysis_depth,
    )
    cache = CacheService()
    cache_key = f"research:{symbol}:{depth}"

    async def event_generator() -> AsyncIterator[str]:
        cached = cache.get_json(cache_key)
        if cached:
            report = ResearchReportOut.model_validate({**cached, "cached": True})
            yield f"data: {json.dumps({'type': 'status', 'message': '命中缓存，直接返回报告'}, ensure_ascii=False)}\n\n"
            payload = {"type": "done", "result": report.model_dump(mode="json")}
            yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
            return

        final: ResearchReportOut | None = None
        async for event in run_research_stream(
            symbol,
            llm=llm,
            mode_settings=settings,
            analysis_depth=depth,
        ):
            if event.get("type") == "done":
                raw = event.get("result")
                if isinstance(raw, dict):
                    final = ResearchReportOut.model_validate(raw)
                    cache.set_json(cache_key, final.model_dump(mode="json"), ttl_seconds=86400)
                    row = persist_report(db, user.id, final)
                    stamped = stamp_report_id(final, row.id)
                    event = {**event, "result": stamped.model_dump(mode="json")}
                    final = stamped
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

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


@router.post("/export/markdown", response_class=PlainTextResponse)
def export_report_markdown_body(
    report: ResearchReportOut,
    user: User = Depends(get_current_user),
) -> PlainTextResponse:
    _ = user
    filename = f"stockresearch-{report.symbol}-export.md"
    return PlainTextResponse(
        content=report_to_markdown(report),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/export/pdf")
def export_report_pdf_body(
    report: ResearchReportOut,
    user: User = Depends(get_current_user),
) -> Response:
    _ = user
    filename = f"stockresearch-{report.symbol}-export.pdf"
    return Response(
        content=report_to_pdf(report),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/export/json", response_class=PlainTextResponse)
def export_report_json_body(
    report: ResearchReportOut,
    user: User = Depends(get_current_user),
) -> PlainTextResponse:
    _ = user
    filename = f"stockresearch-{report.symbol}-export.json"
    return PlainTextResponse(
        content=report_to_json(report),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/export/csv", response_class=PlainTextResponse)
def export_report_csv_body(
    report: ResearchReportOut,
    user: User = Depends(get_current_user),
) -> PlainTextResponse:
    _ = user
    filename = f"stockresearch-{report.symbol}-factors.csv"
    return PlainTextResponse(
        content=report_to_csv(report),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


@router.get("/reports/{report_id}/pdf")
def export_report_pdf(
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    row = (
        db.query(ResearchReport)
        .filter(ResearchReport.id == report_id, ResearchReport.user_id == user.id)
        .first()
    )
    if row is None:
        raise NotFoundError("报告不存在")
    report = ResearchReportOut.model_validate(row.report_json)
    filename = f"stockresearch-{report.symbol}-{row.id}.pdf"
    return Response(
        content=report_to_pdf(report),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/industry")
async def industry_research(
    payload: IndustryResearchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
) -> dict[str, object]:
    reply, cards = await run_industry_research(
        db,
        llm,
        user.id,
        payload.sector,
        payload.query or payload.sector,
    )
    for card in cards:
        if card.get("type") == "research":
            data = card.get("data")
            if isinstance(data, dict):
                report = ResearchReportOut.model_validate(data)
                row = persist_report(db, user.id, report)
                data["id"] = row.id
    return {"reply": reply, "cards": cards}


@router.get("/industry/stream")
async def industry_research_stream(
    sector: str = Query(min_length=1, max_length=50),
    query: str = Query(default=""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
) -> StreamingResponse:
    from stockresearch.agents.industry.stream import run_industry_research_stream

    async def event_generator() -> AsyncIterator[str]:
        final: ResearchReportOut | None = None
        async for event in run_industry_research_stream(
            db,
            user.id,
            sector,
            query or sector,
            llm,
        ):
            if event.get("type") == "done":
                raw = event.get("result")
                if isinstance(raw, dict):
                    final = ResearchReportOut.model_validate(raw)
                    row = persist_report(db, user.id, final)
                    stamped = stamp_report_id(final, row.id)
                    event = {**event, "result": stamped.model_dump(mode="json")}
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/signal-backtest", response_model=SignalBacktestOut)
async def signal_backtest(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SignalBacktestOut:
    return await compute_signal_backtest(db, user.id)


@router.get("/reports/{report_id}/post-hoc", response_model=ReportPostHocOut)
async def report_post_hoc(
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportPostHocOut:
    row = (
        db.query(ResearchReport)
        .filter(ResearchReport.id == report_id, ResearchReport.user_id == user.id)
        .one_or_none()
    )
    if row is None:
        raise NotFoundError("研报不存在")
    horizons = await compute_report_post_hoc(db, user.id, report_id)
    return ReportPostHocOut(
        report_id=report_id,
        symbol=row.symbol,
        horizons=horizons,
        signal_as_of=row.created_at.date().isoformat(),
        point_in_time=True,
    )


@router.post("/compare", response_model=CompareTableOut)
async def compare_symbols(
    payload: CompareRequest,
    user: User = Depends(get_current_user),
) -> CompareTableOut:
    _ = user
    return await build_compare_table(payload.symbols)


@router.post("/compare/csv", response_class=PlainTextResponse)
async def compare_symbols_csv(
    payload: CompareRequest,
    user: User = Depends(get_current_user),
) -> PlainTextResponse:
    _ = user
    table = await build_compare_table(payload.symbols)
    return PlainTextResponse(
        content=flatten_compare_csv(table),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="stockresearch-compare.csv"'},
    )


@router.get("/event-study", response_model=EventStudyOut)
async def event_study(
    symbol: str = Query(min_length=6, max_length=6, pattern=r"^\d{6}$"),
    event_filter: str = Query(default="earnings"),
    user: User = Depends(get_current_user),
) -> EventStudyOut:
    _ = user
    allowed = {"earnings", "risk", "all"}
    filt = event_filter if event_filter in allowed else "earnings"
    return await compute_event_study(symbol, event_filter=filt)


@router.get("/hypothesis/presets")
def hypothesis_presets(user: User = Depends(get_current_user)) -> dict[str, str]:
    _ = user
    return dict(HYPOTHESIS_PRESETS)


@router.post("/hypothesis/verify", response_model=HypothesisVerifyOut)
async def hypothesis_verify(
    payload: HypothesisVerifyRequest,
    user: User = Depends(get_current_user),
) -> HypothesisVerifyOut:
    _ = user
    return await verify_hypothesis(
        payload.symbol,
        rule=payload.rule,
        lookback_days=payload.lookback_days,
    )


@router.post("/batch", response_model=BatchResearchOut)
async def batch_research(
    payload: BatchResearchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
) -> BatchResearchOut:
    from datetime import UTC, datetime

    settings = get_mode_settings(db, user.id)
    depth = resolve_analysis_depth(
        explicit=payload.analysis_depth,
        settings_depth=settings.analysis_depth,
    )
    items: list[BatchResearchItemOut] = []
    cleaned: list[str] = []
    for raw in payload.symbols:
        sym = str(raw).strip()
        if len(sym) == 6 and sym.isdigit() and sym not in cleaned:
            cleaned.append(sym)
        if len(cleaned) >= 8:
            break
    for symbol in cleaned:
        name = resolve_name(symbol)
        try:
            report = await run_research(
                symbol,
                llm=llm,
                with_debate=payload.with_debate,
                mode_settings=settings,
                analysis_depth=depth,
            )
            row = persist_report(db, user.id, report)
            stamped = stamp_report_id(report, row.id)
            items.append(
                BatchResearchItemOut(
                    symbol=symbol,
                    name=name,
                    report=stamped,
                    partial=bool(stamped.data_gaps),
                )
            )
        except Exception as exc:
            items.append(
                BatchResearchItemOut(
                    symbol=symbol,
                    name=name,
                    error=str(exc),
                    partial=True,
                )
            )
    return BatchResearchOut(
        items=items,
        as_of=datetime.now(UTC).date().isoformat(),
        notes=[
            f"批量四维（depth={depth}，debate={payload.with_debate}），最多 8 只。",
            "结果已写入研报历史，可导出 JSON/CSV 或做事后核对。",
        ],
    )


@router.get("/memory/search", response_model=MemorySearchOut)
def memory_search(
    q: str = Query(min_length=1, max_length=100),
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemorySearchOut:
    return search_research_memory(db, user.id, q, limit=limit)
