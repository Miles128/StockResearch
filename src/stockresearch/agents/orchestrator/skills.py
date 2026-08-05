"""Packaged analysis skills — LLM-invokable workflows with streamable process."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from stockresearch.agents.industry.stream import run_industry_research_stream
from stockresearch.agents.market.research_stream import run_market_research_stream
from stockresearch.agents.orchestrator.complexity import extract_industry_sector
from stockresearch.agents.research.stream import run_research_stream
from stockresearch.agents.risk.stream import run_risk_checkup_stream
from stockresearch.core.schemas import ModeSettingsOut, ResearchReportOut, RiskCheckupOut
from stockresearch.services.chat.message_stock import resolve_message_stock, stock_choice_card
from stockresearch.services.stock_lookup import StockLookupResult
from stockresearch.utils.symbols import resolve_name

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from stockresearch.db.models import Holding
    from stockresearch.utils.llm import LLMClient

logger = logging.getLogger(__name__)

EventCallback = Callable[[dict[str, object]], Awaitable[None]]


@dataclass(frozen=True)
class PackagedSkill:
    skill_id: str
    label: str
    description: str
    args_hint: str


PACKAGED_SKILLS: tuple[PackagedSkill, ...] = (
    PackagedSkill(
        "skill_risk_checkup",
        "持仓风控体检",
        "对当前用户持仓做规则+LLM 风控体检，含集中度、止损、板块暴露",
        "无参数；需用户有持仓",
    ),
    PackagedSkill(
        "skill_stock_research",
        "个股四维投研",
        "基本面/技术面/情绪/筹码四维分析；可选多空辩论；"
        "analysis_depth=standard|comprehensive|deep（标准/综合/深度预算）；"
        "用户说「只补缺口再跑/补充数据」时必须调用本 Skill，"
        "analysis_depth≥comprehensive，并在 context 列出待补缺口",
        '{"symbol": "600519", "with_debate": false, "analysis_depth": "comprehensive", '
        '"context": "可选：缺口列表或前文补充说明"}',
    ),
    PackagedSkill(
        "skill_market_research",
        "大盘四维投研",
        "宏观/行业/技术/情绪市场级分析；可选多空辩论",
        '{"query": "可选聚焦问题", "with_debate": false, "context": "可选"}',
    ),
    PackagedSkill(
        "skill_industry_research",
        "行业板块投研",
        "板块四维分析、龙头扫描",
        '{"sector": "半导体", "query": "可选", "with_debate": false}',
    ),
    PackagedSkill(
        "skill_bull_bear_debate",
        "多空辩论",
        "对已完成的投研报告或指定个股启动多空辩论+裁判（需 symbol 或依赖上文投研）",
        '{"symbol": "600519", "context": "可选：前文摘要或焦点"}',
    ),
    PackagedSkill(
        "skill_chart_overlays",
        "K线画线解说",
        "基于日线计算趋势线/支撑压力位并给出一句描述性解读（不荐股、不给交易指令）；"
        "用户说「画趋势线/支撑位在哪/压力位在哪」时调用",
        '{"symbol": "600519"}',
    ),
)

SKILL_IDS: frozenset[str] = frozenset(s.skill_id for s in PACKAGED_SKILLS)


@dataclass
class SkillRunResult:
    summary: str
    cards: list[dict[str, object]] = field(default_factory=list)
    intent: str = "chat"
    partial: bool = False
    error: str | None = None


def format_skills_for_prompt() -> str:
    lines = ["\n打包 Skill（复杂分析请按需调用，可读取对话与前序工具结果）："]
    for s in PACKAGED_SKILLS:
        lines.append(f"- {s.skill_id}: {s.description}。参数: {s.args_hint}")
    return "\n".join(lines)


class SkillRunner:
    """Execute packaged skills with nested SSE-friendly events."""

    def __init__(
        self,
        *,
        db: Session,
        llm: LLMClient,
        user_id: int,
        holdings: list[Holding],
        mode_settings: ModeSettingsOut,
        debate_default: bool,
        confirmed_symbol: str | None = None,
        confirmed_name: str | None = None,
        on_event: EventCallback | None = None,
    ) -> None:
        self._db = db
        self._llm = llm
        self._user_id = user_id
        self._holdings = holdings
        self._settings = mode_settings
        self._debate_default = debate_default
        self._confirmed_symbol = confirmed_symbol
        self._confirmed_name = confirmed_name
        self._on_event = on_event

    async def _emit(self, event: dict[str, object]) -> None:
        if self._on_event:
            await self._on_event(event)

    async def run(self, skill_id: str, args: dict[str, Any]) -> SkillRunResult:
        run_id = str(uuid.uuid4())[:8]
        skill = next((s for s in PACKAGED_SKILLS if s.skill_id == skill_id), None)
        label = skill.label if skill else skill_id

        await self._emit(
            {
                "type": "skill_start",
                "skill_id": skill_id,
                "skill_run_id": run_id,
                "label": label,
            }
        )

        try:
            if skill_id == "skill_risk_checkup":
                result = await self._run_risk(run_id)
            elif skill_id == "skill_stock_research":
                result = await self._run_stock_research(run_id, args)
            elif skill_id == "skill_market_research":
                result = await self._run_market_research(run_id, args)
            elif skill_id == "skill_industry_research":
                result = await self._run_industry_research(run_id, args)
            elif skill_id == "skill_bull_bear_debate":
                result = await self._run_bull_bear(run_id, args)
            elif skill_id == "skill_chart_overlays":
                result = await self._run_chart_overlays(run_id, args)
            else:
                result = SkillRunResult(summary=f"未知 Skill: {skill_id}", error="unknown_skill")
        except Exception as exc:
            logger.warning("skill %s failed: %s", skill_id, exc, exc_info=True)
            result = SkillRunResult(summary=f"Skill {label} 执行失败: {exc}", error=str(exc))

        await self._emit(
            {
                "type": "skill_done",
                "skill_id": skill_id,
                "skill_run_id": run_id,
                "label": label,
                "summary": result.summary,
                "intent": result.intent,
                "partial": result.partial,
                "error": result.error,
            }
        )
        return result

    async def _forward(self, run_id: str, event: dict[str, object]) -> None:
        await self._emit({**event, "skill_run_id": run_id})

    async def _run_chart_overlays(self, run_id: str, args: dict[str, Any]) -> SkillRunResult:
        from stockresearch.services.chart_overlays import compute_chart_overlays

        symbol = str(args.get("symbol", "")).strip()
        if not (len(symbol) == 6 and symbol.isdigit()):
            symbol = self._confirmed_symbol or ""
        if not (len(symbol) == 6 and symbol.isdigit()):
            return SkillRunResult(summary="请先告诉我要画线的股票代码（6 位数字）。", partial=True)
        await self._forward(
            run_id, {"type": "status", "message": f"正在计算 {resolve_name(symbol)} 的趋势线…"}
        )
        overlay_set = await compute_chart_overlays(symbol)
        if not overlay_set.overlays:
            return SkillRunResult(
                summary=(
                    f"{resolve_name(symbol)}（{symbol}）近期日线未检测到有效趋势线，"
                    "可能缺少清晰的枢轴点或价格距离过远。"
                ),
                cards=[{"type": "chart_overlays", "data": overlay_set.model_dump(mode="json")}],
                intent="chat",
                partial=True,
            )
        lines = "\n".join(
            f"- {overlay.rationale}" for overlay in overlay_set.overlays if overlay.rationale
        )
        summary = f"{resolve_name(symbol)}（{symbol}）当前识别到 {len(overlay_set.overlays)} 条趋势线：\n{lines}"
        return SkillRunResult(
            summary=summary,
            cards=[{"type": "chart_overlays", "data": overlay_set.model_dump(mode="json")}],
            intent="chat",
        )

    async def _run_risk(self, run_id: str) -> SkillRunResult:
        if not self._holdings:
            return SkillRunResult(summary="暂无持仓，无法做风控体检。", partial=True)
        payload: dict[str, object] | None = None
        async for event in run_risk_checkup_stream(self._holdings, llm=self._llm):
            if event.get("type") == "done":
                raw = event.get("result")
                if isinstance(raw, dict):
                    payload = raw
            else:
                await self._forward(run_id, event)
        if payload is None:
            return SkillRunResult(summary="风控体检暂时无法完成。", partial=True, intent="risk")
        result = RiskCheckupOut.model_validate(payload)
        return SkillRunResult(
            summary=result.portfolio_summary,
            cards=[{"type": "risk", "data": payload}],
            intent="risk",
        )

    async def _run_stock_research(self, run_id: str, args: dict[str, Any]) -> SkillRunResult:
        symbol = str(args.get("symbol", "")).strip()
        if not symbol:
            query = str(
                args.get("query") or args.get("context") or args.get("message") or ""
            ).strip()
            if query:
                resolved = await resolve_message_stock(
                    query,
                    self._llm,
                    confirmed_symbol=self._confirmed_symbol,
                    confirmed_name=self._confirmed_name,
                )
                if isinstance(resolved, StockLookupResult):
                    card = stock_choice_card(query, resolved)
                    return SkillRunResult(
                        summary=resolved.message,
                        cards=[card],
                        intent="chat",
                    )
                symbol = resolved.symbol
        if not symbol:
            return SkillRunResult(summary="请提供 symbol 参数", error="missing_symbol")
        with_debate = bool(args.get("with_debate", self._debate_default))
        from stockresearch.agents.research.budget import resolve_analysis_depth

        utterance = " ".join(
            str(args.get(k) or "") for k in ("context", "query", "message", "utterance")
        ).strip()
        depth = resolve_analysis_depth(
            explicit=args.get("analysis_depth"),
            utterance=utterance or None,
            settings_depth=self._settings.analysis_depth,
        )
        payload: dict[str, object] | None = None
        async for event in run_research_stream(
            symbol,
            llm=self._llm,
            with_debate=with_debate,
            mode_settings=self._settings,
            analysis_depth=depth,
        ):
            if event.get("type") == "done":
                raw = event.get("result")
                if isinstance(raw, dict):
                    payload = raw
            else:
                await self._forward(run_id, event)
        if payload is None:
            return SkillRunResult(
                summary=f"{resolve_name(symbol)} 投研暂时无法完成。",
                partial=True,
                intent="research",
            )
        report = ResearchReportOut.model_validate(payload)
        return SkillRunResult(
            summary=report.summary,
            cards=[{"type": "research", "data": payload}],
            intent="research",
        )

    async def _run_market_research(self, run_id: str, args: dict[str, Any]) -> SkillRunResult:
        query = str(args.get("query") or args.get("context") or "A股市场").strip()
        with_debate = bool(args.get("with_debate", self._debate_default))
        payload: dict[str, object] | None = None
        async for event in run_market_research_stream(
            query,
            llm=self._llm,
            with_debate=with_debate,
        ):
            if event.get("type") == "done":
                raw = event.get("result")
                if isinstance(raw, dict):
                    payload = raw
            else:
                await self._forward(run_id, event)
        if payload is None:
            return SkillRunResult(summary="大盘投研暂时无法完成。", partial=True, intent="research")
        report = ResearchReportOut.model_validate(payload)
        return SkillRunResult(
            summary=report.summary,
            cards=[{"type": "research", "data": payload}],
            intent="research",
        )

    async def _run_industry_research(self, run_id: str, args: dict[str, Any]) -> SkillRunResult:
        sector = str(args.get("sector", "")).strip()
        if not sector:
            sectors = [h.sector for h in self._holdings]
            sector = extract_industry_sector(str(args.get("query", "")), sectors) or "行业"
        query = str(args.get("query") or f"{sector}行业研究").strip()
        with_debate = bool(args.get("with_debate", self._debate_default))
        payload: dict[str, object] | None = None
        async for event in run_industry_research_stream(
            self._db,
            self._user_id,
            sector,
            query,
            self._llm,
            with_debate=with_debate,
        ):
            if event.get("type") == "done":
                raw = event.get("result")
                if isinstance(raw, dict):
                    payload = raw
            else:
                await self._forward(run_id, event)
        if payload is None:
            return SkillRunResult(
                summary=f"{sector} 板块投研暂时无法完成。", partial=True, intent="research"
            )
        report = ResearchReportOut.model_validate(payload)
        return SkillRunResult(
            summary=report.summary,
            cards=[{"type": "research", "data": payload}],
            intent="research",
        )

    async def _run_bull_bear(self, run_id: str, args: dict[str, Any]) -> SkillRunResult:
        symbol = str(args.get("symbol", "")).strip()
        if not symbol:
            return SkillRunResult(summary="多空辩论需要 symbol 参数", error="missing_symbol")
        return await self._run_stock_research(
            run_id,
            {"symbol": symbol, "with_debate": True, **args},
        )
