"""Research routes."""

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from stockresearch.agents.industry.research import run_industry_research
from stockresearch.agents.research.budget import resolve_analysis_depth
from stockresearch.agents.research.runner import run_research
from stockresearch.agents.research.stream import run_research_stream
from stockresearch.api.deps import get_current_user
from stockresearch.api.llm_deps import llm_from_headers
from stockresearch.api.sse import sse_response
from stockresearch.core.config import get_settings
from stockresearch.core.exceptions import NotFoundError
from stockresearch.core.output_style import (
    get_custom_glossary,
    get_enable_glossary,
    output_style_scope,
    style_instruction_suffix,
)
from stockresearch.core.schemas import (
    BatchResearchItemOut,
    BatchResearchOut,
    BatchResearchRequest,
    CompareRequest,
    CompareTableOut,
    EventStudyBatchOut,
    EventStudyBatchRequest,
    EventStudyOut,
    HypothesisVerifyOut,
    HypothesisVerifyRequest,
    IndustryResearchRequest,
    MemorySearchOut,
    PlainReportOut,
    RefillGapsRequest,
    ReportPostHocOut,
    ResearchReportListItem,
    ResearchReportOut,
    ResearchTimelineOut,
    SignalBacktestOut,
)
from stockresearch.db.models import ReportPlainVersion, ResearchReport, User
from stockresearch.db.session import get_db
from stockresearch.services.cache import CacheService
from stockresearch.services.compare_table import build_compare_table, flatten_compare_csv
from stockresearch.services.event_study import compute_event_study, compute_event_study_batch
from stockresearch.services.glossary import mark_terms, merge_glossary
from stockresearch.services.hypothesis_verify import HYPOTHESIS_PRESETS, verify_hypothesis
from stockresearch.services.refill_gaps import classify_gaps, evict_gap_caches
from stockresearch.services.report_export import (
    report_to_csv,
    report_to_json,
    report_to_markdown,
    report_to_pdf,
)
from stockresearch.services.research_memory import search_research_memory
from stockresearch.services.research_timeline import compute_research_timeline
from stockresearch.services.signal_backtest import compute_report_post_hoc, compute_signal_backtest
from stockresearch.services.user_preferences import get_mode_settings
from stockresearch.utils.llm import LLMClient
from stockresearch.utils.symbols import resolve_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/research", tags=["research"])


def _mark_text(text: str) -> str:
    if not text or not get_enable_glossary():
        return text
    return mark_terms(text, glossary=merge_glossary(get_custom_glossary()))


def _mark_report_terms(report: ResearchReportOut) -> ResearchReportOut:
    """研报返回层词库标注（不污染缓存与 DB 原文）。"""
    report.summary = _mark_text(report.summary)
    report.brief_summary = _mark_text(report.brief_summary)
    if report.text_factor_summary:
        report.text_factor_summary = _mark_text(report.text_factor_summary)
    if report.factor_alignment_note:
        report.factor_alignment_note = _mark_text(report.factor_alignment_note)
    report.follow_up_questions = [_mark_text(q) for q in report.follow_up_questions]
    report.data_gaps = [_mark_text(g) for g in report.data_gaps]
    report.viewpoints = {k: _mark_text(v) for k, v in report.viewpoints.items()}
    for dimension in report.dimensions.values():
        if dimension.analysis:
            dimension.analysis = _mark_text(dimension.analysis)
    return report


def _research_cache_key(symbol: str, depth: str, reading_mode: str) -> str:
    return f"research:{symbol}:{depth}:{reading_mode}"


# PRD §五 分层降级：研报缓存 TTL 由配置项控制（默认 24h），禁止散落 magic number。
research_cache_ttl = get_settings().research_cache_ttl_seconds


async def _enrich_regime(db: Session, report_id: int | None) -> None:
    """Phase 12f：异步回填预测快照的市场 regime（失败静默）。"""
    if not report_id:
        return
    try:
        from stockresearch.services.prediction_journal import (
            enrich_prediction_regime_for_report,
        )

        await enrich_prediction_regime_for_report(db, report_id)
    except Exception:
        logger.debug("regime enrichment skipped", exc_info=True)


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
    # Phase 12a 预测日记：研报事实层自动留存预测记录（幂等）。
    try:
        from stockresearch.services.prediction_journal import record_prediction_for_report

        record_prediction_for_report(db, user_id, report, report_id=row.id)
    except Exception:
        logger.warning("prediction record failed for %s", report.symbol, exc_info=True)
    # Phase 12e 假设自动验证：deep 档 Thesis 自动创建验证计划（幂等）。
    try:
        from stockresearch.services.thesis_verification import record_thesis_for_report

        record_thesis_for_report(db, user_id, report, report_id=row.id)
    except Exception:
        logger.warning("thesis verification record failed for %s", report.symbol, exc_info=True)
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
    cache_key = _research_cache_key(symbol, depth, settings.reading_mode)
    cached = cache.get_json(cache_key)
    if cached:
        report = ResearchReportOut.model_validate({**cached, "cached": True})
        with output_style_scope(
            reading_mode=settings.reading_mode,
            enable_glossary=settings.enable_glossary,
            custom_glossary=settings.custom_glossary,
        ):
            return _mark_report_terms(report)
    with output_style_scope(
        reading_mode=settings.reading_mode, enable_glossary=settings.enable_glossary
    ):
        report = await run_research(symbol, llm=llm, mode_settings=settings, analysis_depth=depth)
    cache.set_json(cache_key, report.model_dump(mode="json"), ttl_seconds=research_cache_ttl)

    row = persist_report(db, user.id, report)
    await _enrich_regime(db, row.id)
    return _mark_report_terms(stamp_report_id(report, row.id))


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
    cache_key = _research_cache_key(symbol, depth, settings.reading_mode)

    async def event_generator() -> AsyncIterator[dict[str, object]]:
        cached = cache.get_json(cache_key)
        if cached:
            report = ResearchReportOut.model_validate({**cached, "cached": True})
            with output_style_scope(
                reading_mode=settings.reading_mode,
                enable_glossary=settings.enable_glossary,
                custom_glossary=settings.custom_glossary,
            ):
                marked = _mark_report_terms(report)
            yield {"type": "status", "message": "命中缓存， 直接返回报告"}
            yield {"type": "done", "result": marked.model_dump(mode="json")}
            return

        final: ResearchReportOut | None = None
        with output_style_scope(
            reading_mode=settings.reading_mode, enable_glossary=settings.enable_glossary
        ):
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
                        cache.set_json(
                            cache_key, final.model_dump(mode="json"), ttl_seconds=research_cache_ttl
                        )
                        row = persist_report(db, user.id, final)
                        await _enrich_regime(db, row.id)
                        stamped = _mark_report_terms(stamp_report_id(final, row.id))
                        event = {**event, "result": stamped.model_dump(mode="json")}
                        final = stamped
                yield event

    return sse_response(event_generator(), keep_alive_seconds=15.0)


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
        composite_raw = payload.get("composite_score")
        composite_score = float(composite_raw) if isinstance(composite_raw, int | float) else 0.0
        items.append(
            ResearchReportListItem(
                id=row.id,
                symbol=row.symbol,
                name=row.name,
                composite_score=composite_score,
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


def _get_report_row(db: Session, report_id: int, user_id: int) -> ResearchReport:
    """按用户归属取研报行，不存在抛 404。"""
    row = (
        db.query(ResearchReport)
        .filter(ResearchReport.id == report_id, ResearchReport.user_id == user_id)
        .first()
    )
    if row is None:
        raise NotFoundError("报告不存在")
    return row


@router.get("/reports/{report_id}", response_model=ResearchReportOut)
def get_report(
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchReportOut:
    row = _get_report_row(db, report_id, user.id)
    report = ResearchReportOut.model_validate(row.report_json)
    return _mark_report_terms(report)


_PLAIN_REWRITE_PROMPT = (
    "你是一名把投研报告翻译成普通人语言的改写助手。\n"
    "正在改写报告的【{label}】部分。\n"
    "{style}\n"
    "改写要求：\n"
    "1. 保留全部事实、数字与结论，只换说法，不增删信息\n"
    "2. 结论一句话在前，原因不超过 3 条\n"
    "3. 专业名词第一次出现用「术语——意思」解释\n"
    "4. 数字翻译成对用户的影响（如「每 100 元亏 12 元」）\n"
    "5. 风险提示保留在结论附近，不省略\n"
    "6. 不编造、不外推、不下交易指令\n"
    "直接输出改写后的文本本身，不要标题、不要解释。\n\n"
    "待改写文本：\n{text}"
)


async def _plain_rewrite_report(llm: LLMClient, report: ResearchReportOut) -> ResearchReportOut:
    """在 friendly scope 内并行改写文本字段，单项失败保留原文，全部失败则抛错触发降级。"""
    data = report.model_dump(mode="json")
    state = {"total": 0, "failed": 0}

    async def _rewrite(label: str, text: object) -> object:
        if not isinstance(text, str) or not text.strip():
            return text
        state["total"] += 1
        try:
            out = await llm.complete(
                "你是把投研报告翻译成普通人语言的改写助手。",
                _PLAIN_REWRITE_PROMPT.format(
                    label=label, style=style_instruction_suffix(), text=text
                ),
            )
            return (out or "").strip() or text
        except Exception:
            state["failed"] += 1
            logger.warning("plain rewrite failed for %s", label, exc_info=True)
            return text

    sem = asyncio.Semaphore(3)

    async def _limited(label: str, text: object) -> object:
        async with sem:
            return await _rewrite(label, text)

    async def _rewrite_field(key: str, label: str, text: object) -> None:
        data[key] = await _limited(label, text)

    async def _viewpoint(key: str, text: object) -> None:
        (data.setdefault("viewpoints", {}) or {})[key] = await _limited(f"viewpoint:{key}", text)

    async def _dimension(dim: dict[str, object]) -> None:
        analysis = dim.get("analysis")
        if isinstance(analysis, str) and analysis.strip():
            dim["analysis"] = await _limited("维度分析", analysis)

    tasks: list[asyncio.Task[object]] = [
        asyncio.create_task(_rewrite_field("summary", "summary", data.get("summary"))),
        asyncio.create_task(
            _rewrite_field("brief_summary", "brief_summary", data.get("brief_summary"))
        ),
        asyncio.create_task(
            _rewrite_field(
                "text_factor_summary", "text_factor_summary", data.get("text_factor_summary")
            )
        ),
        asyncio.create_task(
            _rewrite_field(
                "factor_alignment_note", "factor_alignment_note", data.get("factor_alignment_note")
            )
        ),
    ]
    for key, value in (data.get("viewpoints") or {}).items():
        tasks.append(asyncio.create_task(_viewpoint(key, value)))
    for dim in (data.get("dimensions") or {}).values():
        if isinstance(dim, dict):
            tasks.append(asyncio.create_task(_dimension(dim)))

    if tasks:
        await asyncio.gather(*tasks)
    if state["total"] > 0 and state["failed"] >= state["total"]:
        raise RuntimeError("plain rewrite: all fields failed")
    return ResearchReportOut.model_validate(data)


@router.post("/reports/{report_id}/plain", response_model=PlainReportOut)
async def get_report_plain_version(
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
) -> PlainReportOut:
    """单篇普通版：优先缓存，无则 friendly 改写落库；失败降级返回专业版原文。"""
    row = _get_report_row(db, report_id, user.id)

    cached = db.query(ReportPlainVersion).filter(ReportPlainVersion.report_id == report_id).first()
    if cached is not None:
        report = ResearchReportOut.model_validate(cached.report_json)
        return PlainReportOut(report=_mark_report_terms(report), source="cache")

    settings = get_mode_settings(db, user.id)
    try:
        with output_style_scope(
            reading_mode="friendly",
            locale="zh",
            enable_glossary=settings.enable_glossary,
        ):
            plain = await _plain_rewrite_report(
                llm, ResearchReportOut.model_validate(row.report_json)
            )
        db.add(ReportPlainVersion(report_id=report_id, report_json=plain.model_dump(mode="json")))
        db.commit()
        return PlainReportOut(report=_mark_report_terms(plain), source="generated")
    except Exception:
        logger.warning("plain version generation failed", exc_info=True)
        original = ResearchReportOut.model_validate(row.report_json)
        return PlainReportOut(
            report=original,
            source="degraded",
            message="普通版生成失败，先展示专业版原文",
        )


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

    async def event_generator() -> AsyncIterator[dict[str, object]]:
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
            yield event

    return sse_response(event_generator(), keep_alive_seconds=15.0)


@router.get("/signal-backtest", response_model=SignalBacktestOut)
async def signal_backtest(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SignalBacktestOut:
    return await compute_signal_backtest(db, user.id)


@router.get("/timeline", response_model=ResearchTimelineOut)
async def research_timeline(
    symbol: str = Query(min_length=6, max_length=6, pattern=r"^\d{6}$"),
    include_post_hoc: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchTimelineOut:
    return await compute_research_timeline(
        db,
        user.id,
        symbol,
        include_post_hoc=include_post_hoc,
        limit=limit,
    )


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


@router.post("/event-study/batch", response_model=EventStudyBatchOut)
async def event_study_batch(
    payload: EventStudyBatchRequest,
    user: User = Depends(get_current_user),
) -> EventStudyBatchOut:
    _ = user
    items = await compute_event_study_batch(
        payload.symbols,
        event_filter=payload.event_filter,
    )
    return EventStudyBatchOut(
        items=items,
        event_filter=payload.event_filter,
        as_of=datetime.now(UTC).date().isoformat(),
        notes=["自选池事件研究批量入口；逐标的独立统计，非组合回测。"],
        disclaimer=items[0].disclaimer if items else "",
    )


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
            with output_style_scope(
                reading_mode=settings.reading_mode, enable_glossary=settings.enable_glossary
            ):
                report = await run_research(
                    symbol,
                    llm=llm,
                    with_debate=payload.with_debate,
                    mode_settings=settings,
                    analysis_depth=depth,
                )
            row = persist_report(db, user.id, report)
            stamped = _mark_report_terms(stamp_report_id(report, row.id))
            items.append(
                BatchResearchItemOut(
                    symbol=symbol,
                    name=name,
                    report=stamped,
                    partial=bool(stamped.data_gaps),
                )
            )
        except Exception as exc:
            logger.warning("batch research failed for %s: %s", symbol, exc, exc_info=True)
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


@router.post("/refill", response_model=ResearchReportOut)
async def refill_gaps(
    payload: RefillGapsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(llm_from_headers),
) -> ResearchReportOut:
    """定向补跑：按 data_gaps 驱逐相关缓存后重跑四维研究。

    gaps 缺省时回退到该标的最近一份研报记录的 data_gaps。
    """
    symbol = payload.symbol
    gaps = [str(g).strip() for g in payload.gaps if str(g).strip()]
    if not gaps:
        latest = (
            db.query(ResearchReport)
            .filter(ResearchReport.symbol == symbol)
            .order_by(ResearchReport.created_at.desc())
            .first()
        )
        if latest is not None and isinstance(latest.report_json, dict):
            raw = latest.report_json.get("data_gaps")
            if isinstance(raw, list):
                gaps = [str(g).strip() for g in raw if str(g).strip()][:10]
    categories = classify_gaps(gaps)
    evict_gap_caches(symbol, categories)

    settings = get_mode_settings(db, user.id)
    depth = resolve_analysis_depth(
        explicit=payload.analysis_depth,
        settings_depth=settings.analysis_depth,
    )
    with output_style_scope(
        reading_mode=settings.reading_mode, enable_glossary=settings.enable_glossary
    ):
        report = await run_research(symbol, llm=llm, mode_settings=settings, analysis_depth=depth)
    cache = CacheService()
    cache.set_json(
        _research_cache_key(symbol, depth, settings.reading_mode),
        report.model_dump(mode="json"),
        ttl_seconds=research_cache_ttl,
    )
    row = persist_report(db, user.id, report)
    await _enrich_regime(db, row.id)
    return _mark_report_terms(stamp_report_id(report, row.id))


@router.get("/memory/search", response_model=MemorySearchOut)
def memory_search(
    q: str = Query(min_length=1, max_length=100),
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemorySearchOut:
    return search_research_memory(db, user.id, q, limit=limit)
