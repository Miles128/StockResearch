"""Stock analysis should route to streaming research, not ReAct direct."""

import pytest

from stockresearch.agents.orchestrator.complexity import (
    classify_research_scope,
    is_stock_analysis_intent,
    resolve_execution_mode,
)
from stockresearch.agents.orchestrator.stream import _upgrade_stock_research_route
from stockresearch.agents.orchestrator.complexity import ComplexityResult
from stockresearch.services.message_stock import match_holding_in_message
from stockresearch.utils.llm import MockLLMClient


class _Holding:
    def __init__(self, symbol: str, name: str) -> None:
        self.symbol = symbol
        self.name = name


def test_citic_stock_name_in_scope() -> None:
    assert classify_research_scope("分析中信证券") == "stock"


def test_is_stock_analysis_intent_for_holding_query() -> None:
    assert is_stock_analysis_intent("分析中信证券")
    assert is_stock_analysis_intent("600030怎么样")


def test_match_holding_in_message() -> None:
    holdings = [_Holding("600030", "中信证券")]
    matched = match_holding_in_message("分析中信证券", holdings)
    assert matched is not None
    assert matched.symbol == "600030"


@pytest.mark.asyncio
async def test_upgrade_route_from_direct_to_debate() -> None:
    holdings = [_Holding("600030", "中信证券")]
    mode, symbol, name = await _upgrade_stock_research_route(
        "分析中信证券",
        MockLLMClient(),
        holdings,
        mode=ComplexityResult.DIRECT,
        debate_on=True,
        execution_preference="auto",
        confirmed_symbol=None,
        confirmed_name=None,
    )
    assert mode == ComplexityResult.DEBATE
    assert symbol == "600030"
    assert name == "中信证券"


def test_direct_mode_without_analysis_intent_stays() -> None:
    assert resolve_execution_mode("什么是市盈率", enable_debate=True) == ComplexityResult.DIRECT
