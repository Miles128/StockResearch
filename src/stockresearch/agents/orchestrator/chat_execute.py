"""Shared chat turn execution — sync (/chat graph) and stream paths."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from stockresearch.agents.orchestrator.card_merge import merge_plan_cards
from stockresearch.agents.orchestrator.complexity import (
    is_market_scope,
    is_simple_news_explanation,
    is_trend_explanation_intent,
)
from stockresearch.agents.orchestrator.plan_execute import PlanExecuteAgent
from stockresearch.agents.orchestrator.react_agent import OrchestratorAgent
from stockresearch.agents.risk.engine import run_risk_checkup
from stockresearch.core.config import get_settings
from stockresearch.core.constants import INTENT_RISK
from stockresearch.core.schemas import ChatUserContext, ModeSettingsOut, RiskCheckupOut
from stockresearch.services.chat.scope import ChatContextScope, build_chat_context_scope

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from stockresearch.db.models import Holding

ProgressCallback = Callable[[dict[str, object]], Awaitable[None]]

logger = logging.getLogger(__name__)


@dataclass
class ChatExecuteResult:
    reply: str = ""
    cards: list[dict[str, object]] = field(default_factory=list)
    intent: str = "chat"
    partial: bool = False


@dataclass
class ChatRunContext:
    """单轮对话执行的共享上下文 — 收敛 ReAct / plan-execute 分支的公共参数。"""

    db: Session
    llm: object
    user_id: int
    message: str
    mode_settings: ModeSettingsOut
    holdings: list[Holding]
    debate_on: bool
    finance_tools: bool = True
    long_term_context: str = ""
    user_context_text: str = ""
    history: list[dict[str, str]] | None = None
    confirmed_symbol: str | None = None
    confirmed_name: str | None = None
    portfolio_context: bool = False
    page_context_kind: str | None = None
    scope: ChatContextScope | None = None
    on_progress: ProgressCallback | None = None
    trace_id: str | None = None


async def execute_chat_turn(
    *,
    db: Session,
    user_id: int,
    message: str,
    llm: object,
    holdings: list[Holding],
    debate_on: bool,
    mode_settings: ModeSettingsOut,
    long_term_context: str = "",
    user_context_text: str = "",
    history: list[dict[str, str]] | None = None,
    confirmed_symbol: str | None = None,
    confirmed_name: str | None = None,
    execution_preference: str | None = None,
    user_context: ChatUserContext | None = None,
    scope: ChatContextScope | None = None,
    on_progress: ProgressCallback | None = None,
    session_id: str | None = None,
) -> ChatExecuteResult:
    """Run one chat turn — ReAct skills, plan-execute, or risk shortcut."""
    msg = message.strip()
    turn_scope = scope or await build_chat_context_scope(
        msg,
        holdings,
        user_context,
        llm=llm,  # type: ignore[arg-type]
        mode_settings=mode_settings,
        confirmed_symbol=confirmed_symbol,
        confirmed_name=confirmed_name,
    )
    if turn_scope.secondary_block:
        # 次要域附录块（如「【附：你的持仓概况】」）作为独立段落附在用户消息后
        msg = f"{msg}\n\n{turn_scope.secondary_block}"
    page_kind = user_context.kind if user_context else None

    if turn_scope.run_portfolio_risk_shortcut and turn_scope.holdings:
        return await _run_risk_sync(
            turn_scope.holdings,
            llm,
            mode_settings=mode_settings,
        )

    ctx = ChatRunContext(
        db=db,
        llm=llm,
        user_id=user_id,
        message=msg,
        mode_settings=mode_settings,
        holdings=turn_scope.holdings,
        debate_on=debate_on,
        long_term_context=long_term_context,
        user_context_text=user_context_text,
        history=history,
        confirmed_symbol=confirmed_symbol,
        confirmed_name=confirmed_name,
        portfolio_context=turn_scope.portfolio_tools,
        page_context_kind=page_kind,
        scope=turn_scope,
        on_progress=on_progress,
        trace_id=session_id,
    )
    if execution_preference == "plan_execute":
        return await _run_plan_execute_sync(ctx)
    if execution_preference in ("auto", "preset"):
        from stockresearch.agents.orchestrator.complexity import (
            ComplexityResult,
            resolve_execution_mode,
        )

        routed = resolve_execution_mode(msg, enable_debate=debate_on)
        if routed == ComplexityResult.PLAN_EXECUTE:
            return await _run_plan_execute_sync(ctx)
    return await _run_react_sync(ctx)


async def _run_risk_sync(
    holdings: list[Holding],
    llm: object,
    *,
    mode_settings: ModeSettingsOut,
) -> ChatExecuteResult:
    try:
        result = await asyncio.wait_for(
            run_risk_checkup(
                holdings,
                llm=llm,  # type: ignore[arg-type]
                mode_settings=mode_settings,
            ),
            timeout=get_settings().agent_timeout_seconds,
        )
    except TimeoutError:
        return ChatExecuteResult(
            reply="抱歉，风控体检超时，请您稍后再试。",
            partial=True,
            intent=INTENT_RISK,
        )
    if not isinstance(result, RiskCheckupOut):
        return ChatExecuteResult(
            reply="抱歉，风控体检暂时无法完成，请您稍后再试。",
            partial=True,
            intent=INTENT_RISK,
        )
    return ChatExecuteResult(
        reply=result.portfolio_summary,
        cards=[{"type": "risk", "data": result.model_dump(mode="json")}],
        intent=INTENT_RISK,
    )


def _build_orchestrator_agent(
    ctx: ChatRunContext, *, news_explain_only: bool = False
) -> OrchestratorAgent:
    agent = OrchestratorAgent(
        db=ctx.db,
        llm=ctx.llm,  # type: ignore[arg-type]
        user_id=ctx.user_id,
        finance_tools=ctx.finance_tools,
        mode_settings=ctx.mode_settings,
        holdings=ctx.holdings,
        debate_default=ctx.debate_on,
        portfolio_context=ctx.portfolio_context,
        news_explain_only=news_explain_only,
        confirmed_symbol=ctx.confirmed_symbol,
        confirmed_name=ctx.confirmed_name,
        page_context_kind=ctx.page_context_kind,
        scope=ctx.scope,
        trace_id=ctx.trace_id,
    )
    if ctx.on_progress:
        agent.set_progress_callback(ctx.on_progress)
    return agent


def _intent_from_cards(cards: list[dict[str, object]]) -> str:
    intent = "chat"
    for card in cards:
        ctype = card.get("type")
        if ctype == "research":
            intent = "research"
        elif ctype == "risk":
            intent = INTENT_RISK
    return intent


async def _run_plan_execute_sync(ctx: ChatRunContext) -> ChatExecuteResult:
    if ctx.on_progress:
        from stockresearch.i18n.status_events import status_event

        await ctx.on_progress(status_event("status.planning"))

    react_agent = _build_orchestrator_agent(ctx)

    async def tool_executor(name: str, args: dict) -> str:
        return await react_agent._execute_tool(name, args)

    agent = PlanExecuteAgent(
        llm=ctx.llm,  # type: ignore[arg-type]
        tool_executor=tool_executor,
        finance_tools=ctx.finance_tools,
    )
    if ctx.on_progress:
        agent.set_progress_callback(ctx.on_progress)

    try:
        reply, plan_cards = await asyncio.wait_for(
            agent.run(
                ctx.message,
                history=ctx.history,
                long_term_context=ctx.long_term_context,
                user_context_text=ctx.user_context_text,
            ),
            timeout=get_settings().agent_timeout_seconds,
        )
    except TimeoutError:
        logger.warning(
            "[sid=%s] plan-execute turn timed out after %ss",
            ctx.trace_id or "-",
            get_settings().agent_timeout_seconds,
        )
        return ChatExecuteResult(
            reply="分析耗时较长已超时，请您稍后重试，或把问题描述得更具体一些。",
            partial=True,
        )
    merged = merge_plan_cards(plan_cards, react_agent.tool_cards())
    return ChatExecuteResult(reply=reply, cards=merged, intent=_intent_from_cards(merged))


async def _run_react_sync(ctx: ChatRunContext) -> ChatExecuteResult:
    if ctx.on_progress:
        from stockresearch.i18n.status_events import status_event

        await ctx.on_progress(status_event("status.react.thinking", step=1))

    news_explain = is_simple_news_explanation(ctx.message)
    agent = _build_orchestrator_agent(ctx, news_explain_only=news_explain)

    run_message = ctx.message
    if ctx.finance_tools:
        if news_explain:
            run_message = await _augment_news_message(
                agent,
                ctx.message,
                scope=ctx.scope,
                on_progress=ctx.on_progress,
            )
        elif is_trend_explanation_intent(ctx.message):
            run_message = await _augment_trend_message(
                agent,
                ctx.message,
                scope=ctx.scope,
                on_progress=ctx.on_progress,
            )

    try:
        reply, cards = await asyncio.wait_for(
            agent.run(
                run_message,
                history=ctx.history,
                long_term_context=ctx.long_term_context,
                user_context_text=ctx.user_context_text,
            ),
            timeout=get_settings().agent_timeout_seconds,
        )
    except TimeoutError:
        logger.warning(
            "[sid=%s] react turn timed out after %ss",
            ctx.trace_id or "-",
            get_settings().agent_timeout_seconds,
        )
        return ChatExecuteResult(
            reply="分析耗时较长已超时，请您稍后重试，或把问题描述得更具体一些。",
            partial=True,
        )
    return ChatExecuteResult(reply=reply, cards=cards, intent=_intent_from_cards(cards))


async def _augment_trend_message(
    agent: OrchestratorAgent,
    message: str,
    *,
    scope: ChatContextScope | None,
    on_progress: ProgressCallback | None,
) -> str:
    """Pre-fetch quote + news for trend/move questions without full 4D research."""
    from stockresearch.i18n.status_events import status_event
    from stockresearch.utils.symbols import resolve_name

    blocks: list[str] = []
    sym: str | None = None
    name: str | None = None
    if scope and scope.subject_symbol:
        sym = scope.subject_symbol
        name = scope.subject_name or resolve_name(sym)

    if sym:
        if on_progress:
            await on_progress(status_event("status.react.stock_quote", symbol=sym))
        blocks.append(await agent._execute_tool("get_stock_quote", {"symbol": sym}))
        if on_progress:
            await on_progress(status_event("status.react.news"))
        blocks.append(await agent._execute_tool("get_news", {"symbol": sym, "name": name or sym}))
        hint = "请结合上述行情与相关新闻解读走势及可能驱动因素，无需启动四维投研 Skill。"
    elif is_market_scope(message):
        if on_progress:
            await on_progress(status_event("status.react.market_data"))
        blocks.append(await agent._execute_tool("get_market_data", {}))
        if on_progress:
            await on_progress(status_event("status.react.news"))
        blocks.append(await agent._execute_tool("get_news", {}))
        hint = (
            "请结合上述大盘数据（含外围市场与宏观指标）与相关新闻解读市场走势及可能驱动因素，"
            "归因须综合宏观经济、政策、资金面、海外市场与板块结构；"
            "未落地/未证实的单一公司新闻不得作为大盘确定性主驱动，引用时注明“尚未落地、影响不确定”，"
            "无需启动四维投研 Skill。"
        )
    else:
        return message

    return f"{message}\n\n[系统已预取数据]\n" + "\n\n".join(blocks) + f"\n\n{hint}"


async def _augment_news_message(
    agent: OrchestratorAgent,
    message: str,
    *,
    scope: ChatContextScope | None,
    on_progress: ProgressCallback | None,
) -> str:
    """Pre-fetch news for explain/impact questions — avoid full research skills."""
    from stockresearch.i18n.status_events import status_event
    from stockresearch.utils.symbols import resolve_name

    blocks: list[str] = []
    sym = scope.subject_symbol if scope else None
    name = (scope.subject_name if scope else None) or (resolve_name(sym) if sym else None)

    if on_progress:
        await on_progress(status_event("status.react.news"))
    if sym:
        blocks.append(await agent._execute_tool("get_news", {"symbol": sym, "name": name or sym}))
        hint = (
            "请基于上述快讯与用户问题中的新闻标题/摘要进行解读；"
            "若涉及持仓影响，仅就问题范围说明，勿启动四维投研 Skill。"
        )
    else:
        blocks.append(await agent._execute_tool("get_news", {}))
        hint = "请基于上述快讯解读用户问题，勿启动四维投研或多空辩论 Skill。"

    return f"{message}\n\n[系统已预取新闻]\n" + "\n\n".join(blocks) + f"\n\n{hint}"
