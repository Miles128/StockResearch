"""ReAct agent finance tool gating."""

from unittest.mock import MagicMock

import pytest

from stockresearch.agents.orchestrator.react_agent import OrchestratorAgent


@pytest.mark.asyncio
async def test_finance_tools_disabled_blocks_news() -> None:
    db = MagicMock()
    llm = MagicMock()
    agent = OrchestratorAgent(db=db, llm=llm, user_id=1, finance_tools=False)
    result = await agent._execute_tool("get_news", {})
    assert "禁用" in result
    assert "get_market_data" not in result or "禁用" in await agent._execute_tool(
        "get_market_data", {}
    )
