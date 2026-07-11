"""Research ReAct agent isolation tests."""

from stockresearch.agents.research.agents import AGENT_BY_ID, DIMENSION_AGENTS
from stockresearch.agents.research.agents.chips import CHIPS_AGENT
from stockresearch.agents.research.agents.fundamental import FUNDAMENTAL_AGENT


def test_four_independent_agents_registered() -> None:
    assert len(DIMENSION_AGENTS) == 4
    assert set(AGENT_BY_ID) == {"fundamental", "technical", "sentiment", "chips"}


def test_toolsets_are_isolated() -> None:
    fund_tools = {t.name for t in FUNDAMENTAL_AGENT.tools}
    chips_tools = {t.name for t in CHIPS_AGENT.tools}
    assert "akshare_financials" in fund_tools
    assert "cninfo_announcements" in fund_tools
    assert "akshare_lhb" in chips_tools
    assert fund_tools.isdisjoint(chips_tools)


def test_each_agent_has_system_prompt_and_build() -> None:
    for agent in DIMENSION_AGENTS:
        assert agent.system_prompt
        assert agent.tools
        assert callable(agent.build)
