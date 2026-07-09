"""Packaged analysis skills — LLM-invokable workflows with streamable process."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from stockresearch.agents.industry.stream import run_industry_research_stream
from stockresearch.agents.market.research_stream import run_market_research_stream
from stockresearch.agents.master_commentary.debate import stream_master_debate
from stockresearch.agents.master_commentary.registry import resolve_master_ids
from stockresearch.agents.master_commentary.schemas import MasterCommentaryOut
from stockresearch.agents.master_commentary.stream import stream_master_commentary
from stockresearch.agents.orchestrator.complexity import extract_industry_sector
from stockresearch.agents.research.stream import run_research_stream
from stockresearch.agents.risk.stream import run_risk_checkup_stream
from stockresearch.core.schemas import ModeSettingsOut, ResearchReportOut, RiskCheckupOut
from stockresearch.db.models import Holding
from stockresearch.services.message_stock import resolve_message_stock, stock_choice_card
from stockresearch.services.stock_lookup import StockLookupResult
from stockresearch.utils.llm import LLMClient
from stockresearch.utils.symbols import resolve_name

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
        "基本面/技术面/情绪/筹码四维分析；可选多空辩论",
        '{"symbol": "600519", "with_debate": false, "context": "可选：结合前文的补充说明"}',
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
        "skill_master_commentary",
        "大师风格点评",
        "基于上文投研/风控/新闻摘要，按用户选定大师生成点评；多大师时可互相辩论",
        '{"subject": "标的或主题", "context": "必填：待点评的摘要或报告", '
        '"master_ids": ["buffett","munger"], "debate_masters": true}',
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
        master_default: bool,
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
        self._master_default = master_default
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
            elif skill_id == "skill_master_commentary":
                result = await self._run_master_commentary(run_id, args)
            else:
                result = SkillRunResult(summary=f"未知 Skill: {skill_id}", error="unknown_skill")
        except Exception as exc:
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

    async def _run_risk(self, run_id: str) -> SkillRunResult:
        if not self._holdings:
            return SkillRunResult(summary="暂无持仓，无法做风控体检。", partial=True)
        master_kwargs: dict[str, object] = {}
        if self._master_default:
            master_kwargs = {
                "enable_master_commentary": True,
                "mode_settings": self._settings,
                "master_ids": resolve_master_ids(self._settings),
            }
        payload: dict[str, object] | None = None
        async for event in run_risk_checkup_stream(self._holdings, llm=self._llm, **master_kwargs):
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
        master_kwargs: dict[str, object] = {}
        if self._master_default:
            master_kwargs = {
                "enable_master_commentary": True,
                "mode_settings": self._settings,
                "master_ids": resolve_master_ids(self._settings),
            }
        payload: dict[str, object] | None = None
        async for event in run_research_stream(
            symbol,
            llm=self._llm,
            with_debate=with_debate,
            **master_kwargs,
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
        master_kwargs: dict[str, object] = {}
        if self._master_default:
            master_kwargs = {
                "enable_master_commentary": True,
                "mode_settings": self._settings,
                "master_ids": resolve_master_ids(self._settings),
            }
        payload: dict[str, object] | None = None
        async for event in run_market_research_stream(
            query,
            llm=self._llm,
            with_debate=with_debate,
            **master_kwargs,
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
        master_kwargs: dict[str, object] = {}
        if self._master_default:
            master_kwargs = {
                "enable_master_commentary": True,
                "mode_settings": self._settings,
                "master_ids": resolve_master_ids(self._settings),
            }
        payload: dict[str, object] | None = None
        async for event in run_industry_research_stream(
            self._db,
            self._user_id,
            sector,
            query,
            self._llm,
            with_debate=with_debate,
            **master_kwargs,
        ):
            if event.get("type") == "done":
                raw = event.get("result")
                if isinstance(raw, dict):
                    payload = raw
            else:
                await self._forward(run_id, event)
        if payload is None:
            return SkillRunResult(summary=f"{sector} 板块投研暂时无法完成。", partial=True, intent="research")
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

    async def _run_master_commentary(self, run_id: str, args: dict[str, Any]) -> SkillRunResult:
        context = str(args.get("context", "")).strip()
        subject = str(args.get("subject", "分析标的")).strip()
        if not context:
            return SkillRunResult(
                summary="大师点评需要 context 参数（前文投研/风控/新闻摘要）",
                error="missing_context",
            )
        master_ids = args.get("master_ids")
        if not isinstance(master_ids, list) or not master_ids:
            master_ids = resolve_master_ids(self._settings)
        else:
            master_ids = [str(m) for m in master_ids]
        debate_masters = bool(args.get("debate_masters", len(master_ids) >= 2))

        commentary_payloads: list[dict[str, Any]] = []
        master_models: list[MasterCommentaryOut] = []

        async for event in stream_master_commentary(
            self._llm,
            subject,
            context,
            settings=self._settings,
            masters=master_ids,
        ):
            if event.get("type") == "master_commentary":
                raw = event.get("commentary")
                if isinstance(raw, list):
                    commentary_payloads = raw
            else:
                await self._forward(run_id, event)

        for item in commentary_payloads:
            sig = str(item.get("signal", "neutral"))
            if sig not in ("bullish", "neutral", "bearish"):
                sig = "neutral"
            master_models.append(
                MasterCommentaryOut(
                    master=str(item.get("master", "")),
                    signal=sig,  # type: ignore[arg-type]
                    confidence=float(item.get("confidence", 0.5)),
                    reasoning=str(item.get("reasoning", "")),
                    key_metric=str(item.get("key_metric", "")),
                )
            )

        debate_summary = ""
        if debate_masters and len(master_models) >= 2:
            async for event in stream_master_debate(
                self._llm,
                subject,
                master_models,
                settings=self._settings,
            ):
                await self._forward(run_id, event)
                if event.get("type") == "master_debate_done":
                    debate_summary = (
                        f"共识：{event.get('consensus', '')}；分歧：{event.get('divergence', '')}"
                    )

        lines = [f"[{c.get('name', c.get('master', ''))}] {c.get('reasoning', '')}" for c in commentary_payloads]
        summary = "\n".join(lines)
        if debate_summary:
            summary = f"{summary}\n\n大师交叉辩论：{debate_summary}"

        card_data: dict[str, object] = {
            "subject": subject,
            "commentary": commentary_payloads,
        }
        if debate_summary:
            card_data["master_debate_summary"] = debate_summary

        return SkillRunResult(
            summary=summary or "大师点评已完成",
            cards=[{"type": "master", "data": card_data}],
            intent="research",
        )
