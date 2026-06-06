"""Execution route proposal for complex chat queries — ReAct vs Plan-Execute vs preset."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from stockresearch.agents.orchestrator.complexity import (
    ANALYSIS_COMPLEX,
    ComplexityResult,
    _COMPLEX_PATTERNS,
    _SIMPLE_PATTERNS,
    classify_query,
    classify_research_scope,
    is_industry_research,
    is_risk_intent,
    resolve_execution_mode,
    wants_deep_research,
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
    label: str
    description: str


@dataclass(frozen=True)
class RouteProposal:
    finance_related: bool
    reason: str
    preset_mode: str | None
    preset_label: str | None
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
    analysis_mode: str | None = None,
    execution_preference: str | None = None,
    confirmed_symbol: str | None = None,
) -> bool:
    """Whether to pause and ask the user to pick ReAct / Plan-Execute / preset."""
    if execution_preference and execution_preference not in ("auto", None):
        return False
    if confirmed_symbol:
        return False

    msg = message.strip()
    if not msg or is_risk_intent(msg):
        return False

    for pattern in _SIMPLE_PATTERNS:
        if re.search(pattern, msg):
            return False

    if analysis_mode == ANALYSIS_COMPLEX:
        return True

    for pattern in _COMPLEX_PATTERNS:
        if re.search(pattern, msg):
            return True

    auto = classify_query(msg)
    if auto == ComplexityResult.PLAN_EXECUTE:
        return True

    if len(msg) >= 60 and wants_deep_research(msg):
        return True

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
    analysis_mode: str | None = None,
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

    return resolve_execution_mode(
        message,
        analysis_mode,
        enable_debate=enable_debate,
    ), True


def build_route_proposal(message: str, *, enable_debate: bool = False) -> RouteProposal:
    """Build options shown before running a complex query."""
    msg = message.strip()
    finance = is_finance_related(msg)
    preset_mode: str | None = None
    preset_label: str | None = None

    if finance:
        preset_mode = resolve_preset_mode(msg, enable_debate=enable_debate)
        preset_label = _MODE_LABELS.get(preset_mode, preset_mode)

    if finance and preset_mode:
        reason = f"检测到较复杂的{'金融' if finance else ''}分析问题，请选择执行方式。"
    else:
        reason = "检测到较复杂的问题。本问题与股票投资无直接关系，将不使用联网搜索或行情工具。"

    options: list[RouteOption] = []
    if finance and preset_mode and preset_label:
        options.append(
            RouteOption(
                id="preset",
                label=f"预定路线 · {preset_label}",
                description="按系统推荐的专业投研流程执行（推荐）",
            )
        )
    options.extend(
        [
            RouteOption(
                id="react",
                label="ReAct 快速分析",
                description="逐步调用工具并即时回答，适合需要较快结论的场景"
                if finance
                else "基于模型知识直接回答，不调用行情、新闻等金融工具",
            ),
            RouteOption(
                id="plan_execute",
                label="规划执行",
                description="先制定多步研究计划，再逐步执行并综合报告"
                if finance
                else "先规划步骤再执行，仅使用通用推理，不调用金融数据工具",
            ),
        ]
    )

    return RouteProposal(
        finance_related=finance,
        reason=reason,
        preset_mode=preset_mode,
        preset_label=preset_label,
        options=options,
    )


def route_choice_card(original_message: str, proposal: RouteProposal) -> dict[str, object]:
    return {
        "type": "route_choice",
        "data": {
            "message": proposal.reason,
            "original_message": original_message,
            "finance_related": proposal.finance_related,
            "preset_mode": proposal.preset_mode,
            "preset_label": proposal.preset_label,
            "options": [
                {"id": o.id, "label": o.label, "description": o.description}
                for o in proposal.options
            ],
        },
    }
