"""Fundamental dimension agent — financials, valuation, peers, filings, broker reports."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from stockresearch.agents.research.agents._scoring import as_confidence
from stockresearch.agents.research.context import ResearchContext
from stockresearch.agents.research.react import DimensionAgent, ResearchTool
from stockresearch.agents.voice import AGENT_VOICE
from stockresearch.core.config import get_settings
from stockresearch.core.constants import CONFIDENCE_HIGH, CONFIDENCE_LOW, CONFIDENCE_MEDIUM
from stockresearch.core.schemas import DimensionEvidence, DimensionResult
from stockresearch.data.providers.announcements import AnnouncementProvider
from stockresearch.data.providers.market import FinancialDataProvider
from stockresearch.data.providers.research_reports import ResearchReportProvider
from stockresearch.utils.symbols import resolve_name

_SYSTEM = (
    f"你是 A 股基本面分析师。{AGENT_VOICE} 不要给出买入卖出建议。"
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
    return {"peers": peers, "partial": len(peers) == 0}


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
    items = await AnnouncementProvider().fetch_announcements(
        ctx.symbol,
        resolve_name(ctx.symbol),
        days=60,
        limit=8,
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
    items = await ResearchReportProvider().fetch_reports(
        ctx.symbol,
        resolve_name(ctx.symbol),
        limit=6,
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


def _build(data: dict[str, object], analysis: str) -> DimensionResult:
    fin = _as_dict(data, "akshare_financials")
    val = _as_dict(data, "akshare_valuation")
    peers_payload = _as_dict(data, "akshare_peers")
    ann = _as_dict(data, "cninfo_announcements")
    reports = _as_dict(data, "em_research_reports")
    ratios = _as_dict(data, "ths_ratio_snapshot")

    revenue_yoy = float(fin.get("revenue_yoy", 0) or 0)
    roe = float(fin.get("roe", 0) or 0)
    debt_ratio = float(fin.get("debt_ratio", 0.5) or 0.5)

    pe_raw = val.get("pe_percentile", fin.get("pe_percentile"))
    pe_pct: float | None
    try:
        pe_pct = float(pe_raw) if pe_raw is not None else None
    except (TypeError, ValueError):
        pe_pct = None
    pe_partial = bool(val.get("partial") or fin.get("partial") or pe_pct is None)

    score = 5.0
    if revenue_yoy > 0.15:
        score += 1.5
    if roe > 0.15:
        score += 1.0
    if pe_pct is not None and pe_pct < 0.4:
        score += 0.5
    if debt_ratio > 0.6:
        score -= 1.0
    score = max(1.0, min(10.0, score))

    highlights = [line for line in analysis.split("。") if "亮点" in line or "增长" in line][:3]
    risks = [line for line in analysis.split("。") if "风险" in line or "竞争" in line][:3]
    if not highlights:
        highlights = [f"营收增速 {revenue_yoy:.0%}", f"ROE {roe:.0%}"]
        if ratios.get("ratios"):
            highlights.append("已加载同花顺年度比率摘要")
    if not risks:
        if pe_partial:
            risks = ["估值历史分位不可用（partial）"]
        else:
            risks = [f"PE 历史分位 {pe_pct:.0%}"]

    gaps: list[str] = []
    if pe_partial:
        gaps.append("估值历史分位缺失")
    if bool(fin.get("partial")):
        gaps.append("财务序列不完整")
    if bool(peers_payload.get("partial")) or not _as_list(peers_payload, "peers"):
        gaps.append("可比公司不足")
    if bool(ann.get("partial")) or int(ann.get("count", 0) or 0) == 0:
        gaps.append("近期公告未取到")
    if bool(reports.get("partial")) or int(reports.get("count", 0) or 0) == 0:
        gaps.append("机构研报未取到")

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
    confidence = CONFIDENCE_HIGH if fin and not pe_partial else CONFIDENCE_MEDIUM
    if not fin or (pe_partial and not evidence):
        confidence = CONFIDENCE_LOW
    if _has_major_announcement(data) and confidence == CONFIDENCE_HIGH:
        confidence = CONFIDENCE_MEDIUM

    return DimensionResult(
        agent="fundamental",
        score=round(score, 1),
        confidence=as_confidence(confidence),
        highlights=highlights,
        risks=risks,
        data_sources=sources,
        evidence=evidence,
        gaps=gaps[:5],
        partial=bool(gaps),
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
