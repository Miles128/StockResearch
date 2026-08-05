"""Orchestrator tool registry tests."""

from stockresearch.agents.orchestrator.skills import PACKAGED_SKILLS, SKILL_IDS
from stockresearch.agents.orchestrator.tools_registry import (
    FINANCE_TOOLS,
    ORCHESTRATOR_TOOLS,
    RESEARCH_SKILL_TOOLS,
    format_tools_for_prompt,
    get_tool,
)


def test_packaged_skills_registered() -> None:
    skill_names = {s.skill_id for s in PACKAGED_SKILLS}
    assert skill_names == SKILL_IDS
    assert RESEARCH_SKILL_TOOLS == SKILL_IDS


def test_all_tools_registered() -> None:
    names = {t.name for t in ORCHESTRATOR_TOOLS}
    assert SKILL_IDS.issubset(names)
    assert "get_market_data" in names
    assert "reply" in names
    assert names == FINANCE_TOOLS | {"reply"}


def test_get_tool_lookup() -> None:
    tool = get_tool("skill_stock_research")
    assert tool is not None
    assert tool.category == "skill"


def test_format_tools_for_prompt_includes_skills() -> None:
    text = format_tools_for_prompt(include_research_skills=True, include_portfolio_tools=True)
    assert "skill_stock_research" in text
    assert "skill_risk_checkup" in text
    assert "get_market_data" in text


def test_format_tools_for_prompt_hides_portfolio_without_context() -> None:
    text = format_tools_for_prompt(include_research_skills=True, include_portfolio_tools=False)
    assert "get_sector_holdings" not in text
    assert "skill_risk_checkup" not in text
    assert "get_market_data" in text


def test_format_tools_for_prompt_shows_portfolio_with_context() -> None:
    text = format_tools_for_prompt(include_research_skills=True, include_portfolio_tools=True)
    assert "get_sector_holdings" in text
    assert "skill_risk_checkup" in text
