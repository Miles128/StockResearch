"""Orchestrator tool registry — light tools + packaged skills."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from stockresearch.agents.orchestrator.skills import PACKAGED_SKILLS, SKILL_IDS, format_skills_for_prompt

ToolCategory = Literal["market", "quote", "news", "portfolio", "output", "skill"]


@dataclass(frozen=True)
class OrchestratorTool:
    name: str
    description: str
    category: ToolCategory
    finance_only: bool = True


ORCHESTRATOR_TOOLS: tuple[OrchestratorTool, ...] = (
    OrchestratorTool(
        "get_market_data",
        "获取大盘指数、北向资金、涨跌家数等市场整体数据",
        "market",
    ),
    OrchestratorTool(
        "get_stock_quote",
        '获取个股实时行情（参数: symbol 如 "600519"）',
        "quote",
    ),
    OrchestratorTool(
        "get_financial_ratios",
        "获取个股财报比率（参数: symbol）含 PE/PB/ROE/毛利率等",
        "quote",
    ),
    OrchestratorTool(
        "get_news",
        "获取财经新闻；解读个股走势/涨跌原因时传 symbol（可选 name）",
        "news",
    ),
    OrchestratorTool(
        "get_sector_holdings",
        "获取用户持仓中某板块的股票（参数: sector）",
        "portfolio",
    ),
    OrchestratorTool(
        "get_sector_news",
        "获取与某板块相关的快讯（参数: sector）",
        "news",
    ),
    *(
        OrchestratorTool(
            s.skill_id,
            s.description,
            "skill",
        )
        for s in PACKAGED_SKILLS
    ),
    OrchestratorTool(
        "reply",
        "生成最终回复给用户（先给出总体结论，过程已展开时可调用）",
        "output",
        finance_only=False,
    ),
)

FINANCE_TOOLS: frozenset[str] = frozenset(
    t.name for t in ORCHESTRATOR_TOOLS if t.finance_only
)
RESEARCH_SKILL_TOOLS: frozenset[str] = SKILL_IDS

_TOOL_BY_NAME: dict[str, OrchestratorTool] = {t.name: t for t in ORCHESTRATOR_TOOLS}


def get_tool(name: str) -> OrchestratorTool | None:
    return _TOOL_BY_NAME.get(name)


def format_tools_for_prompt(
    *,
    include_research_skills: bool = True,
    include_portfolio_tools: bool = False,
) -> str:
    """Build the tool list section for orchestrator system prompts."""
    lines: list[str] = []
    for tool in ORCHESTRATOR_TOOLS:
        if tool.name == "reply":
            continue
        if tool.category == "skill" and not include_research_skills:
            continue
        if tool.category == "portfolio" and not include_portfolio_tools:
            continue
        if tool.name == "skill_risk_checkup" and not include_portfolio_tools:
            continue
        lines.append(f"- {tool.name}: {tool.description}")
    lines.append("- reply: 生成最终回复给用户（当你认为数据足够时调用）")
    return "\n".join(lines)


def research_skills_prompt_note(*, skills_available: bool) -> str:
    if not skills_available:
        return ""
    return format_skills_for_prompt()
