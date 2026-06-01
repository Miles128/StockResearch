"""Intent router tests."""

import pytest

from invesbao.agents.orchestrator.intent_router import route_intent
from invesbao.core.constants import INTENT_CHAT, INTENT_NEWS, INTENT_RESEARCH, INTENT_RISK
from invesbao.utils.llm import MockLLMClient


@pytest.mark.asyncio
async def test_route_research_by_name() -> None:
    intent, symbols = await route_intent("帮我分析一下贵州茅台", MockLLMClient())
    assert intent == INTENT_RESEARCH
    assert "600519" in symbols


@pytest.mark.asyncio
async def test_route_news() -> None:
    intent, _ = await route_intent("茅台今天怎么了", MockLLMClient())
    assert intent == INTENT_NEWS


@pytest.mark.asyncio
async def test_route_risk() -> None:
    intent, _ = await route_intent("我的持仓风险大吗", MockLLMClient())
    assert intent == INTENT_RISK


@pytest.mark.asyncio
async def test_route_education_chat() -> None:
    intent, _ = await route_intent("什么是 MACD 金叉", MockLLMClient())
    assert intent == INTENT_CHAT


@pytest.mark.asyncio
async def test_route_fallback_on_invalid_json() -> None:
    class BrokenLLM(MockLLMClient):
        async def complete(self, system: str, user: str) -> str:
            return "not valid json"

    intent, _ = await route_intent("帮我分析一下贵州茅台", BrokenLLM())
    assert intent == INTENT_RESEARCH
