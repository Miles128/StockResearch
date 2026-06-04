"""Intent router tests."""

import pytest

from stockresearch.agents.orchestrator.intent_router import route_intent
from stockresearch.core.constants import INTENT_CHAT, INTENT_MARKET, INTENT_NEWS, INTENT_RESEARCH, INTENT_RISK
from stockresearch.utils.llm import MockLLMClient


@pytest.mark.asyncio
async def test_route_research_by_name() -> None:
    intent, symbols, sectors = await route_intent("帮我分析一下贵州茅台", MockLLMClient())
    assert intent == INTENT_RESEARCH
    assert "600519" in symbols


@pytest.mark.asyncio
async def test_route_news() -> None:
    intent, _, _ = await route_intent("茅台今天怎么了", MockLLMClient())
    assert intent == INTENT_NEWS


@pytest.mark.asyncio
async def test_route_risk() -> None:
    intent, _, _ = await route_intent("我的持仓风险大吗", MockLLMClient())
    assert intent == INTENT_RISK


@pytest.mark.asyncio
async def test_route_market() -> None:
    intent, _, sectors = await route_intent("中国股市未来走势如何", MockLLMClient())
    assert intent == INTENT_MARKET


@pytest.mark.asyncio
async def test_route_market_sector() -> None:
    intent, _, sectors = await route_intent("半导体板块最近怎么样", MockLLMClient())
    assert intent == INTENT_MARKET
    assert "半导体" in sectors


@pytest.mark.asyncio
async def test_route_education_chat() -> None:
    intent, _, _ = await route_intent("什么是 MACD 金叉", MockLLMClient())
    assert intent == INTENT_CHAT


@pytest.mark.asyncio
async def test_route_fallback_on_invalid_json() -> None:
    class BrokenLLM(MockLLMClient):
        async def complete(self, system: str, user: str) -> str:
            return "not valid json"

    intent, _, _ = await route_intent("帮我分析一下贵州茅台", BrokenLLM())
    assert intent == INTENT_RESEARCH
