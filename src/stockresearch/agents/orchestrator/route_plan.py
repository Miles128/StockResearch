"""Execution route proposal for complex chat queries — ReAct vs Plan-Execute vs preset.

Legacy module: kept for unit tests and future execution-choice UI.
Production chat (/chat, /chat/stream) uses skill-first ReAct via chat_execute.py.
"""

from __future__ import annotations

from typing import Literal

from stockresearch.agents.orchestrator.tools_registry import FINANCE_TOOLS
from stockresearch.agents.orchestrator.complexity import (
    ComplexityResult,
    classify_query,
    classify_research_scope,
    is_industry_research,
    is_risk_intent,
    is_simple_news_explanation,
    is_stock_analysis_intent,
    resolve_execution_mode,
    should_auto_plan_execute,
    should_skip_debate,
    should_skip_multi_agent,
)
from stockresearch.agents.orchestrator.intent_router import route_intent
from stockresearch.core.constants import (
    INTENT_CHAT,
    INTENT_COMPOSITE,
    INTENT_MARKET,
    INTENT_NEWS,
    INTENT_RESEARCH,
)
from stockresearch.services.message_stock import (
    ResolvedStock,
    match_holding_in_message,
    resolve_message_stock,
)
from stockresearch.utils.llm import LLMClient

ExecutionPreference = Literal["react", "plan_execute", "preset", "auto"]

_FINANCE_KEYWORDS: tuple[str, ...] = (
    "股票",
    "股市",
    "a股",
    "大盘",
    "指数",
    "基金",
    "etf",
    "债券",
    "期货",
    "选股",
    "财报",
    "市盈率",
    "市净率",
    "估值",
    "板块",
    "持仓",
    "投资",
    "行情",
    "北向",
    "涨停",
    "跌停",
    "券商",
    "研报",
)

_MODE_LABELS: dict[str, str] = {
    ComplexityResult.DIRECT: "ReAct 直接回答",
    ComplexityResult.RESEARCH: "个股多维投研",
    ComplexityResult.MARKET_RESEARCH: "大盘多维投研",
    ComplexityResult.DEBATE: "个股深度投研·多空辩论",
    ComplexityResult.MARKET_DEBATE: "大盘深度投研·多空辩论",
    ComplexityResult.PLAN_EXECUTE: "规划执行",
    ComplexityResult.INDUSTRY_RESEARCH: "行业深度研究",
}


def is_finance_related(message: str) -> bool:
    """True when the query is scoped to stocks, markets, sectors, or risk."""
    msg = message.strip()
    if not msg:
        return False
    if classify_research_scope(msg):
        return True
    if is_industry_research(msg):
        return True
    if is_risk_intent(msg):
        return True
    compact = msg.lower().replace("Ａ", "a")
    return any(kw in compact for kw in _FINANCE_KEYWORDS)


def needs_execution_choice(
    message: str,
    *,
    execution_preference: str | None = None,
    confirmed_symbol: str | None = None,
) -> bool:
    """DEPRECATED — Permanent no-op.
    
    Plan-Execute and preset routes are chosen automatically via
    resolve_mode_with_preference() — no manual picker needed.
    The route_choice UI flow is intentionally disabled.
    """
    _ = (message, execution_preference, confirmed_symbol)
    return False


def resolve_preset_mode(message: str, *, enable_debate: bool = False) -> str:
    """Predetermined finance route — never bare ReAct for scoped finance queries."""
    msg = message.strip()
    if should_auto_plan_execute(msg):
        return ComplexityResult.PLAN_EXECUTE
    scope = classify_research_scope(msg)
    use_debate = enable_debate and not should_skip_debate(msg)
    if scope == "stock":
        return ComplexityResult.DEBATE if use_debate else ComplexityResult.RESEARCH
    if scope == "market":
        return ComplexityResult.MARKET_DEBATE if use_debate else ComplexityResult.MARKET_RESEARCH
    if is_industry_research(msg):
        return ComplexityResult.INDUSTRY_RESEARCH

    auto = classify_query(msg)
    if auto == ComplexityResult.DEBATE:
        return ComplexityResult.DEBATE if enable_debate else ComplexityResult.RESEARCH
    if auto == ComplexityResult.MARKET_DEBATE:
        return ComplexityResult.MARKET_DEBATE if enable_debate else ComplexityResult.MARKET_RESEARCH
    if auto == ComplexityResult.INDUSTRY_RESEARCH:
        return ComplexityResult.INDUSTRY_RESEARCH

    return ComplexityResult.MARKET_RESEARCH


def resolve_mode_with_preference(
    message: str,
    execution_preference: str | None,
    *,
    enable_debate: bool = False,
) -> tuple[str, bool]:
    """Return (execution_mode, finance_tools_allowed)."""
    pref = execution_preference or "auto"
    finance = is_finance_related(message)

    if pref == "react":
        return ComplexityResult.DIRECT, finance
    if pref == "plan_execute":
        return ComplexityResult.PLAN_EXECUTE, finance
    if pref == "preset":
        return resolve_preset_mode(message, enable_debate=enable_debate), True

    return resolve_execution_mode(message, enable_debate=enable_debate), True


async def resolve_chat_route(
    message: str,
    llm: LLMClient,
    *,
    execution_preference: str | None,
    enable_debate: bool = False,
) -> tuple[str, bool, bool, str]:
    """Intent-aware routing: mode, finance tools, research tools, intent label."""
    pref = execution_preference or "auto"
    if pref != "auto":
        mode, finance = resolve_mode_with_preference(
            message,
            execution_preference,
            enable_debate=enable_debate,
        )
        research_tools = mode in (
            ComplexityResult.RESEARCH,
            ComplexityResult.DEBATE,
            ComplexityResult.MARKET_RESEARCH,
            ComplexityResult.MARKET_DEBATE,
            ComplexityResult.INDUSTRY_RESEARCH,
        )
        return mode, finance, research_tools, INTENT_CHAT

    if should_auto_plan_execute(message):
        return ComplexityResult.PLAN_EXECUTE, True, True, INTENT_COMPOSITE

    if should_skip_multi_agent(message):
        return ComplexityResult.DIRECT, is_finance_related(message), False, INTENT_NEWS if is_simple_news_explanation(message) else INTENT_CHAT

    intent, symbols, _sectors = await route_intent(message, llm)

    if intent == INTENT_COMPOSITE:
        return ComplexityResult.PLAN_EXECUTE, True, True, intent

    if intent == INTENT_NEWS or is_simple_news_explanation(message):
        return ComplexityResult.DIRECT, True, False, INTENT_NEWS

    if intent == INTENT_CHAT:
        return ComplexityResult.DIRECT, is_finance_related(message), False, intent

    if intent == INTENT_RESEARCH:
        if should_skip_multi_agent(message):
            return ComplexityResult.DIRECT, True, False, intent
        if classify_research_scope(message) == "stock" or (
            symbols and is_stock_analysis_intent(message)
        ):
            use_debate = enable_debate and not should_skip_debate(message)
            mode = ComplexityResult.DEBATE if use_debate else ComplexityResult.RESEARCH
            return mode, True, True, intent
        return ComplexityResult.DIRECT, True, False, intent

    if intent == INTENT_MARKET:
        if classify_research_scope(message) == "market":
            use_debate = enable_debate and not should_skip_debate(message)
            mode = (
                ComplexityResult.MARKET_DEBATE
                if use_debate
                else ComplexityResult.MARKET_RESEARCH
            )
            return mode, True, True, intent
        return ComplexityResult.DIRECT, True, False, intent

    mode = resolve_execution_mode(message, enable_debate=enable_debate)
    research_tools = mode in (
        ComplexityResult.RESEARCH,
        ComplexityResult.DEBATE,
        ComplexityResult.MARKET_RESEARCH,
        ComplexityResult.MARKET_DEBATE,
        ComplexityResult.INDUSTRY_RESEARCH,
    )
    return mode, is_finance_related(message), research_tools, intent


async def upgrade_stock_research_route(
    message: str,
    llm: LLMClient,
    holdings: list[object],
    *,
    mode: str,
    debate_on: bool,
    execution_preference: str | None,
    confirmed_symbol: str | None,
    confirmed_name: str | None,
) -> tuple[str, str | None, str | None]:
    """Send holding/name stock analysis to research instead of ReAct direct."""
    if execution_preference == "react":
        return mode, confirmed_symbol, confirmed_name
    if mode in (
        ComplexityResult.DEBATE,
        ComplexityResult.RESEARCH,
        ComplexityResult.MARKET_DEBATE,
        ComplexityResult.MARKET_RESEARCH,
        ComplexityResult.INDUSTRY_RESEARCH,
    ):
        return mode, confirmed_symbol, confirmed_name

    if not is_stock_analysis_intent(message):
        return mode, confirmed_symbol, confirmed_name

    holding = match_holding_in_message(message, holdings)
    if holding:
        upgraded = ComplexityResult.DEBATE if debate_on else ComplexityResult.RESEARCH
        return upgraded, holding.symbol, holding.name

    if mode != ComplexityResult.DIRECT:
        return mode, confirmed_symbol, confirmed_name

    resolved = await resolve_message_stock(
        message,
        llm,
        confirmed_symbol=confirmed_symbol,
        confirmed_name=confirmed_name,
    )
    if isinstance(resolved, ResolvedStock):
        upgraded = ComplexityResult.DEBATE if debate_on else ComplexityResult.RESEARCH
        return upgraded, resolved.symbol, resolved.name

    return mode, confirmed_symbol, confirmed_name
