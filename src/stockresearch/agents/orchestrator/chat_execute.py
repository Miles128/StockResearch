"""Shared chat turn execution — sync (/chat graph) and stream paths."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.card_merge import merge_plan_cards
from stockresearch.agents.orchestrator.complexity import (
    is_market_scope,
    is_simple_news_explanation,
    is_trend_explanation_intent,
)
from stockresearch.agents.orchestrator.plan_execute import PlanExecuteAgent
from stockresearch.agents.orchestrator.react_agent import OrchestratorAgent
from stockresearch.agents.risk.engine import run_risk_checkup
from stockresearch.agents.master_commentary.registry import resolve_master_ids
from stockresearch.core.config import get_settings
from stockresearch.core.constants import INTENT_RISK
from stockresearch.core.schemas import ModeSettingsOut, RiskCheckupOut, ChatUserContext
from stockresearch.db.models import Holding
from stockresearch.services.chat_scope import ChatContextScope, build_chat_context_scope

ProgressCallback = Callable[[dict[str, object]], Awaitable[None]]


@dataclass
class ChatExecuteResult:
    reply: str = ""
    cards: list[dict[str, object]] = field(default_factory=list)
    intent: str = "chat"
    partial: bool = False


async def execute_chat_turn(
    *,
    db: Session,
    user_id: int,
    message: str,
    llm: object,
    holdings: list[Holding],
    debate_on: bool,
    master_on: bool,
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
            master_on=master_on,
            mode_settings=mode_settings,
        )

    if execution_preference == "plan_execute":
        return await _run_plan_execute_sync(
            db=db,
            llm=llm,
            message=msg,
            user_id=user_id,
            finance_tools=True,
            long_term_context=long_term_context,
            user_context_text=user_context_text,
            history=history,
            mode_settings=mode_settings,
            holdings=turn_scope.holdings,
            debate_on=debate_on,
            master_on=master_on,
            confirmed_symbol=confirmed_symbol,
            confirmed_name=confirmed_name,
            on_progress=on_progress,
            portfolio_context=turn_scope.portfolio_tools,
            page_context_kind=page_kind,
            scope=turn_scope,
        )

    return await _run_react_sync(
        db=db,
        llm=llm,
        message=msg,
        user_id=user_id,
        finance_tools=True,
        long_term_context=long_term_context,
        user_context_text=user_context_text,
        history=history,
        mode_settings=mode_settings,
        holdings=turn_scope.holdings,
        debate_on=debate_on,
        master_on=master_on,
        confirmed_symbol=confirmed_symbol,
        confirmed_name=confirmed_name,
        on_progress=on_progress,
        portfolio_context=turn_scope.portfolio_tools,
        scope=turn_scope,
        page_context_kind=page_kind,
    )


async def _run_risk_sync(
    holdings: list[Holding],
    llm: object,
    *,
    master_on: bool,
    mode_settings: ModeSettingsOut,
) -> ChatExecuteResult:
    try:
        result = await asyncio.wait_for(
            run_risk_checkup(
                holdings,
                llm=llm,  # type: ignore[arg-type]
                enable_master_commentary=master_on,
                mode_settings=mode_settings,
                master_ids=resolve_master_ids(mode_settings) if master_on else None,
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


async def _run_plan_execute_sync(
    *,
    db: Session,
    llm: object,
    message: str,
    user_id: int,
    finance_tools: bool,
    long_term_context: str,
    user_context_text: str,
    history: list[dict[str, str]] | None,
    mode_settings: ModeSettingsOut,
    holdings: list[Holding],
    debate_on: bool,
    master_on: bool,
    confirmed_symbol: str | None = None,
    confirmed_name: str | None = None,
    on_progress: ProgressCallback | None,
    portfolio_context: bool = False,
    page_context_kind: str | None = None,
    scope: ChatContextScope | None = None,
) -> ChatExecuteResult:
    if on_progress:
        from stockresearch.i18n.status_events import status_event

        await on_progress(status_event("status.planning"))

    react_agent = OrchestratorAgent(
        db=db,
        llm=llm,  # type: ignore[arg-type]
        user_id=user_id,
        finance_tools=finance_tools,
        mode_settings=mode_settings,
        holdings=holdings,
        debate_default=debate_on,
        master_default=master_on,
        portfolio_context=portfolio_context,
        confirmed_symbol=confirmed_symbol,
        confirmed_name=confirmed_name,
        page_context_kind=page_context_kind,
        scope=scope,
    )
    if on_progress:
        react_agent.set_progress_callback(on_progress)

    async def tool_executor(name: str, args: dict) -> str:
        return await react_agent._execute_tool(name, args)

    agent = PlanExecuteAgent(
        llm=llm,  # type: ignore[arg-type]
        tool_executor=tool_executor,
        finance_tools=finance_tools,
    )
    if on_progress:
        agent.set_progress_callback(on_progress)

    reply, plan_cards = await agent.run(
        message,
        history=history,
        long_term_context=long_term_context,
        user_context_text=user_context_text,
    )
    merged = merge_plan_cards(plan_cards, react_agent.tool_cards())
    intent = "chat"
    for card in merged:
        ctype = card.get("type")
        if ctype == "research":
            intent = "research"
        elif ctype == "risk":
            intent = INTENT_RISK
    return ChatExecuteResult(reply=reply, cards=merged, intent=intent)


async def _run_react_sync(
    *,
    db: Session,
    llm: object,
    message: str,
    user_id: int,
    finance_tools: bool,
    long_term_context: str,
    user_context_text: str,
    history: list[dict[str, str]] | None,
    mode_settings: ModeSettingsOut,
    holdings: list[Holding],
    debate_on: bool,
    master_on: bool,
    confirmed_symbol: str | None,
    confirmed_name: str | None,
    on_progress: ProgressCallback | None,
    portfolio_context: bool = False,
    scope: ChatContextScope | None = None,
    page_context_kind: str | None = None,
) -> ChatExecuteResult:
    if on_progress:
        from stockresearch.i18n.status_events import status_event

        await on_progress(status_event("status.react.thinking", step=1))

    news_explain = is_simple_news_explanation(message)
    agent = OrchestratorAgent(
        db=db,
        llm=llm,  # type: ignore[arg-type]
        user_id=user_id,
        finance_tools=finance_tools,
        mode_settings=mode_settings,
        holdings=holdings,
        debate_default=debate_on,
        master_default=master_on,
        portfolio_context=portfolio_context,
        news_explain_only=news_explain,
        confirmed_symbol=confirmed_symbol,
        confirmed_name=confirmed_name,
        page_context_kind=page_context_kind,
        scope=scope,
    )
    if on_progress:
        agent.set_progress_callback(on_progress)

    run_message = message
    if finance_tools:
        if news_explain:
            run_message = await _augment_news_message(
                agent,
                message,
                scope=scope,
                on_progress=on_progress,
            )
        elif is_trend_explanation_intent(message):
            run_message = await _augment_trend_message(
                agent,
                message,
                scope=scope,
                on_progress=on_progress,
            )

    reply, cards = await agent.run(
        run_message,
        history=history,
        long_term_context=long_term_context,
        user_context_text=user_context_text,
    )
    intent = "chat"
    for card in cards:
        ctype = card.get("type")
        if ctype == "research":
            intent = "research"
        elif ctype == "risk":
            intent = INTENT_RISK
        elif ctype == "stock_choice":
            intent = "chat"
    return ChatExecuteResult(reply=reply, cards=cards, intent=intent)


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
        hint = "请结合上述大盘数据与相关新闻解读市场走势及可能驱动因素，无需启动四维投研 Skill。"
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
