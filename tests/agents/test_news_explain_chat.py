"""News explain chat path tests."""

import pytest
from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.complexity import is_simple_news_explanation
from stockresearch.agents.orchestrator.react_agent import OrchestratorAgent
from stockresearch.db.models import User
from stockresearch.utils.llm import MockLLMClient


def test_news_explain_intent_matches_panel_buttons() -> None:
    assert is_simple_news_explanation("解释这条新闻：茅台发布年报")
    assert is_simple_news_explanation("对持仓有什么影响：央行降准")


@pytest.mark.asyncio
async def test_news_explain_blocks_research_skill(db_session: Session) -> None:
    user = User(username="news-explain", password_hash="")
    db_session.add(user)
    db_session.commit()

    agent = OrchestratorAgent(
        db_session,
        MockLLMClient(),
        user_id=user.id,
        news_explain_only=True,
    )
    result = await agent._execute_tool(
        "skill_stock_research",
        {"symbol": "600519"},
    )
    assert "不可用" in result
    assert "新闻解读" in result


@pytest.mark.asyncio
async def test_mock_llm_prefers_news_over_stock_skill() -> None:
    llm = MockLLMClient()
    system = "你是编排 Agent，可调用工具"
    user = "解释这条新闻：茅台发布年报业绩超预期"
    reply = await llm.complete(system, user)
    assert "skill_stock_research" not in reply
    assert "get_news" in reply
