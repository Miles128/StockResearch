"""Execution route proposal for complex chat queries — ReAct vs Plan-Execute vs preset."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from stockresearch.agents.orchestrator.complexity import (
    ComplexityResult,
    classify_query,
    classify_research_scope,
    is_industry_research,
    is_risk_intent,
    resolve_execution_mode,
)

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

FINANCE_TOOLS: frozenset[str] = frozenset(
    {
        "get_market_data",
        "get_stock_quote",
        "get_stock_research",
        "debate_stock",
        "get_financial_ratios",
        "get_news",
        "get_sector_holdings",
        "get_sector_news",
    }
)


@dataclass(frozen=True)
class RouteOption:
    id: str
    label_key: str
    description_key: str
    label_params: dict[str, object] | None = None
    description_params: dict[str, object] | None = None


@dataclass(frozen=True)
class RouteProposal:
    finance_related: bool
    reason_key: str
    reason_params: dict[str, object] | None
    preset_mode: str | None
    options: list[RouteOption]


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
    """Predetermined finance route — never ReAct or Plan-Execute."""
    msg = message.strip()
    scope = classify_research_scope(msg)
    if scope == "stock":
        return ComplexityResult.DEBATE if enable_debate else ComplexityResult.RESEARCH
    if scope == "market":
        return ComplexityResult.MARKET_DEBATE if enable_debate else ComplexityResult.MARKET_RESEARCH
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


def build_route_proposal(message: str, *, enable_debate: bool = False) -> RouteProposal:
    """Build options shown before running a complex query."""
    msg = message.strip()
    finance = is_finance_related(msg)
    preset_mode: str | None = None

    if finance:
        preset_mode = resolve_preset_mode(msg, enable_debate=enable_debate)

    reason_key = "route.reason.finance_complex" if finance and preset_mode else "route.reason.non_finance"
    reason_params: dict[str, object] | None = None

    options: list[RouteOption] = []
    if finance and preset_mode:
        options.append(
            RouteOption(
                id="preset",
                label_key="route.option.preset",
                description_key="route.option.preset_desc",
                label_params={"mode": preset_mode},
            )
        )
    options.extend(
        [
            RouteOption(
                id="react",
                label_key="route.option.react",
                description_key=(
                    "route.option.react.desc" if finance else "route.option.react.desc_non_finance"
                ),
            ),
            RouteOption(
                id="plan_execute",
                label_key="route.option.plan_execute",
                description_key=(
                    "route.option.plan_execute.desc"
                    if finance
                    else "route.option.plan_execute.desc_non_finance"
                ),
            ),
        ]
    )

    return RouteProposal(
        finance_related=finance,
        reason_key=reason_key,
        reason_params=reason_params,
        preset_mode=preset_mode,
        options=options,
    )


def route_choice_card(original_message: str, proposal: RouteProposal) -> dict[str, object]:
    return {
        "type": "route_choice",
        "data": {
            "reason_key": proposal.reason_key,
            "reason_params": proposal.reason_params or {},
            "original_message": original_message,
            "finance_related": proposal.finance_related,
            "preset_mode": proposal.preset_mode,
            "options": [
                {
                    "id": o.id,
                    "label_key": o.label_key,
                    "description_key": o.description_key,
                    "label_params": o.label_params or {},
                    "description_params": o.description_params or {},
                }
                for o in proposal.options
            ],
        },
    }
