"""Fundamental dimension agent — financials, valuation, peers, filings, broker reports."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from stockresearch.agents.research.agents._scoring import as_confidence
from stockresearch.agents.research.context import ResearchContext
from stockresearch.agents.research.react import DimensionAgent, ResearchTool
from stockresearch.agents.research.dimension_text import REPORT_DIM_VOICE, finalize_dimension
from stockresearch.core.config import get_settings
from stockresearch.core.constants import CONFIDENCE_HIGH, CONFIDENCE_LOW, CONFIDENCE_MEDIUM
from stockresearch.core.schemas import DimensionEvidence, DimensionResult
from stockresearch.data.providers.announcements import AnnouncementProvider
from stockresearch.data.providers.market import FinancialDataProvider
from stockresearch.data.providers.research_reports import ResearchReportProvider
from stockresearch.utils.symbols import resolve_name

_SYSTEM = (
    f"你是 A 股基本面分析师。{REPORT_DIM_VOICE} "
    "引用公告标题/日期与研报机构评级时须与工具返回一致，禁止编造。"
)

_MAJOR_ANN_KEYWORDS = (
    "年报",
    "半年报",
    "季报",
    "业绩",
    "预告",
    "快报",
    "减持",
    "增持",
    "回购",
    "问询",
    "立案",
    "重大",
    "重组",
    "停牌",
)


async def _tool_financials(ctx: ResearchContext) -> dict[str, object]:
    provider = FinancialDataProvider()
    return await provider.get_financials(ctx.symbol)


async def _tool_valuation(ctx: ResearchContext) -> dict[str, object]:
    provider = FinancialDataProvider()
    return await provider.get_valuation(ctx.symbol)


async def _tool_peers(ctx: ResearchContext) -> dict[str, object]:
    provider = FinancialDataProvider()
    peers = await provider.get_industry_peers(ctx.symbol)
    seed_only = bool(peers) and all(str(p.get("source", "")) == "seed" for p in peers)
    gaps: list[str] = []
    if not peers:
        gaps.append("可比公司不足")
    elif seed_only:
        gaps.append("可比公司仅种子兜底，非行业成份动态匹配")
    return {
        "peers": peers,
        "partial": len(peers) == 0 or seed_only,
        "gaps": gaps,
        "source": "seed" if seed_only else ("akshare_industry" if peers else "none"),
    }


async def _tool_ratio_snapshot(ctx: ResearchContext) -> dict[str, object]:
    if get_settings().use_mock_market_data:
        return {
            "symbol": ctx.symbol,
            "name": resolve_name(ctx.symbol),
            "ratios": [{"name": "ROE", "value": "18%", "reference": "—", "assessment": "良好", "trend": ""}],
            "raw_data": {"roe": 18.0},
            "partial": False,
        }
    from stockresearch.agents.financial.agent import FinancialRatioAgent

    agent = FinancialRatioAgent(llm=None)
    return await agent.fetch_structured(ctx.symbol, resolve_name(ctx.symbol))


async def _tool_announcements(ctx: ResearchContext) -> dict[str, object]:
    if get_settings().use_mock_market_data:
        return {
            "items": [
                {
                    "title": "2024年年度报告",
                    "announcement_type": "年报",
                    "announcement_time": "2025-03-01T00:00:00+00:00",
                    "url": "",
                    "source": "cninfo",
                }
            ],
            "count": 1,
            "partial": False,
        }
    result = await AnnouncementProvider().fetch_announcements_result(
        ctx.symbol,
        resolve_name(ctx.symbol),
        days=60,
        limit=8,
    )
    items = result.items
    gap = (
        "公告源暂时失败"
        if result.source_failed
        else ("近60天无公告" if not items else None)
    )
    return {
        "items": [
            {
                "title": it.title,
                "announcement_type": it.announcement_type,
                "announcement_time": it.announcement_time.isoformat(),
                "url": it.url,
                "source": "cninfo",
            }
            for it in items
        ],
        "count": len(items),
        "partial": len(items) == 0,
        "source_failed": result.source_failed,
        "gaps": [gap] if gap else [],
    }


async def _tool_research_reports(ctx: ResearchContext) -> dict[str, object]:
    if get_settings().use_mock_market_data:
        return {
            "items": [
                {
                    "title": "深度报告",
                    "institution": "模拟券商",
                    "rating": "增持",
                    "publish_date": "2025-02-01T00:00:00+00:00",
                    "summary": "模拟研报摘要",
                    "source": "eastmoney",
                }
            ],
            "count": 1,
            "partial": False,
        }
    result = await ResearchReportProvider().fetch_reports_result(
        ctx.symbol,
        resolve_name(ctx.symbol),
        limit=6,
    )
    items = result.items
    gap = (
        "研报源暂时失败"
        if result.source_failed
        else ("近期无机构研报" if not items else None)
    )
    return {
        "items": [
            {
                "title": it.title,
                "institution": it.institution,
                "rating": it.rating,
                "publish_date": it.publish_date.isoformat(),
                "summary": (it.summary or "")[:200],
                "source": "eastmoney",
            }
            for it in items
        ],
        "count": len(items),
        "partial": len(items) == 0,
        "source_failed": result.source_failed,
        "gaps": [gap] if gap else [],
    }


def _as_dict(data: dict[str, object], key: str) -> dict[str, object]:
    raw = data.get(key)
    return raw if isinstance(raw, dict) else {}


def _as_list(data: dict[str, object], key: str) -> list[object]:
    raw = data.get(key)
    return raw if isinstance(raw, list) else []


def _collect_evidence(data: dict[str, object]) -> list[DimensionEvidence]:
    evidence: list[DimensionEvidence] = []
    ann = _as_dict(data, "cninfo_announcements")
    for item in _as_list(ann, "items")[:5]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        evidence.append(
            DimensionEvidence(
                source="cninfo",
                date=str(item.get("announcement_time", ""))[:10] or None,
                snippet=title[:120],
                url=str(item.get("url", "")) or None,
                kind="announcement",
            )
        )
    reports = _as_dict(data, "em_research_reports")
    for item in _as_list(reports, "items")[:4]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        inst = str(item.get("institution", "")).strip()
        rating = str(item.get("rating", "")).strip()
        snippet = f"{inst} {rating} · {title}".strip(" ·")
        if not snippet:
            continue
        evidence.append(
            DimensionEvidence(
                source="eastmoney",
                date=str(item.get("publish_date", ""))[:10] or None,
                snippet=snippet[:120],
                kind="research_report",
            )
        )
    fin = _as_dict(data, "akshare_financials")
    if fin and not bool(fin.get("partial")):
        rev = fin.get("revenue_yoy")
        roe = fin.get("roe")
        parts = []
        if isinstance(rev, (int, float)):
            parts.append(f"营收YoY {float(rev):.0%}")
        if isinstance(roe, (int, float)):
            parts.append(f"ROE {float(roe):.0%}")
        if parts:
            evidence.append(
                DimensionEvidence(
                    source="akshare",
                    date=str(fin.get("as_of") or fin.get("period") or "")[:10] or None,
                    snippet="财务：" + " · ".join(parts),
                    kind="financial",
                )
            )
    val = _as_dict(data, "akshare_valuation")
    pe_pct = val.get("pe_percentile", fin.get("pe_percentile"))
    if isinstance(pe_pct, (int, float)) and not bool(val.get("partial")):
        evidence.append(
            DimensionEvidence(
                source="akshare",
                date=str(val.get("as_of") or "")[:10] or None,
                snippet=f"PE 历史分位 {float(pe_pct):.0%}",
                kind="financial",
            )
        )
    return evidence


def _has_major_announcement(data: dict[str, object]) -> bool:
    ann = _as_dict(data, "cninfo_announcements")
    cutoff = datetime.now(UTC) - timedelta(days=30)
    for item in _as_list(ann, "items"):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", ""))
        ann_type = str(item.get("announcement_type", ""))
        blob = f"{title}{ann_type}"
        if not any(k in blob for k in _MAJOR_ANN_KEYWORDS):
            continue
        raw_ts = str(item.get("announcement_time", ""))
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except ValueError:
            return True
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        if ts >= cutoff:
            return True
    return False


def _optional_metric(raw: object) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _fmt_ratio(value: float | None, *, missing: str) -> str:
    if value is None:
        return missing
    return f"{value:.0%}"


def _build(data: dict[str, object], analysis: str) -> DimensionResult:
    fin = _as_dict(data, "akshare_financials")
    val = _as_dict(data, "akshare_valuation")
    peers_payload = _as_dict(data, "akshare_peers")
    ann = _as_dict(data, "cninfo_announcements")
    reports = _as_dict(data, "em_research_reports")
    ratios = _as_dict(data, "ths_ratio_snapshot")

    revenue_yoy = _optional_metric(fin.get("revenue_yoy"))
    roe = _optional_metric(fin.get("roe"))
    debt_ratio = _optional_metric(fin.get("debt_ratio"))

    pe_pct = _optional_metric(val.get("pe_percentile", fin.get("pe_percentile")))
    pe_partial = bool(val.get("partial") or pe_pct is None)
    fin_missing_core = roe is None and revenue_yoy is None

    score = 5.0
    if revenue_yoy is not None and revenue_yoy > 0.15:
        score += 1.5
    if roe is not None and roe > 0.15:
        score += 1.0
    if pe_pct is not None and pe_pct < 0.4:
        score += 0.5
    if debt_ratio is not None and debt_ratio > 0.6:
        score -= 1.0
    if fin_missing_core:
        score -= 0.5
    score = max(1.0, min(10.0, score))

    fallback_highlights = [
        f"营收增速 {_fmt_ratio(revenue_yoy, missing='缺失')}",
        f"ROE {_fmt_ratio(roe, missing='缺失')}",
    ]
    if ratios.get("ratios"):
        fallback_highlights.append("已加载同花顺年度比率摘要")
    fallback_risks = (
        ["估值历史分位不可用（partial）"]
        if pe_partial
        else [f"PE 历史分位 {_fmt_ratio(pe_pct, missing='缺失')}"]
    )

    gaps: list[str] = []
    if pe_partial:
        gaps.append("估值历史分位缺失")
    if bool(fin.get("partial")) or fin_missing_core:
        gaps.append("财务序列不完整" if not fin_missing_core else "核心财务指标缺失")
    for gap in _as_list(fin, "gaps"):
        text = str(gap).strip()
        if text and text not in gaps:
            gaps.append(text)
    if bool(peers_payload.get("partial")) or not _as_list(peers_payload, "peers"):
        peer_gaps = [str(g) for g in _as_list(peers_payload, "gaps") if str(g).strip()]
        gaps.extend(peer_gaps or ["可比公司不足"])
    if bool(ann.get("partial")) or int(ann.get("count", 0) or 0) == 0:
        ann_gaps = [str(g) for g in _as_list(ann, "gaps") if str(g).strip()]
        gaps.extend(ann_gaps or ["近期公告未取到"])
    if bool(reports.get("partial")) or int(reports.get("count", 0) or 0) == 0:
        report_gaps = [str(g) for g in _as_list(reports, "gaps") if str(g).strip()]
        gaps.extend(report_gaps or ["机构研报未取到"])

    sources = [
        "akshare_financials",
        "akshare_valuation",
        "akshare_peers",
        "ths_ratio_snapshot",
        "cninfo_announcements",
        "em_research_reports",
    ]
    if int(ann.get("count", 0) or 0) == 0:
        sources = [s for s in sources if s != "cninfo_announcements"]
    if int(reports.get("count", 0) or 0) == 0:
        sources = [s for s in sources if s != "em_research_reports"]

    evidence = _collect_evidence(data)
    has_fin = bool(fin) and not fin_missing_core
    confidence = CONFIDENCE_HIGH if has_fin and not pe_partial else CONFIDENCE_MEDIUM
    if not has_fin or (pe_partial and not evidence):
        confidence = CONFIDENCE_LOW
    if _has_major_announcement(data) and confidence == CONFIDENCE_HIGH:
        confidence = CONFIDENCE_MEDIUM

    seen: set[str] = set()
    unique_gaps: list[str] = []
    for g in gaps:
        if g not in seen:
            seen.add(g)
            unique_gaps.append(g)

    return finalize_dimension(
        agent="fundamental",
        score=score,
        confidence=as_confidence(confidence),
        raw_analysis=analysis,
        data_sources=sources,
        fallback_highlights=fallback_highlights,
        fallback_risks=fallback_risks,
        evidence=evidence,
        gaps=unique_gaps[:5],
        partial=bool(unique_gaps),
    )


FUNDAMENTAL_AGENT = DimensionAgent(
    agent_id="fundamental",
    label="基本面",
    system_prompt=_SYSTEM,
    tools=(
        ResearchTool("akshare_financials", "上市公司财务指标与多期序列", _tool_financials),
        ResearchTool("akshare_valuation", "估值与历史分位", _tool_valuation),
        ResearchTool("akshare_peers", "同行业可比公司", _tool_peers),
        ResearchTool("ths_ratio_snapshot", "同花顺年度比率摘要", _tool_ratio_snapshot),
        ResearchTool("cninfo_announcements", "巨潮近期公告", _tool_announcements),
        ResearchTool("em_research_reports", "东方财富机构研报", _tool_research_reports),
    ),
    build=_build,
)
