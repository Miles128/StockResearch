"""Stock analysis should route to streaming research, not ReAct direct."""

from stockresearch.agents.orchestrator.complexity import (
    ComplexityResult,
    classify_research_scope,
    is_stock_analysis_intent,
    resolve_execution_mode,
)
from stockresearch.services.chat.message_stock import match_holding_in_message


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


def test_direct_mode_without_analysis_intent_stays() -> None:
    assert resolve_execution_mode("什么是市盈率") == ComplexityResult.DIRECT
