"""Query complexity routing tests."""

from stockresearch.agents.orchestrator.complexity import (
    ANALYSIS_SIMPLE,
    ComplexityResult,
    classify_query,
    classify_research_scope,
    is_market_scope,
    resolve_execution_mode,
    wants_deep_research,
)


def test_market_deep_routes_to_market_debate() -> None:
    assert classify_query("大盘走势深度分析") == ComplexityResult.MARKET_DEBATE
    assert classify_query("请对A股市场进行辩论投研") == ComplexityResult.MARKET_DEBATE
    assert classify_query("宏观深度研究 指数走势") == ComplexityResult.MARKET_DEBATE


def test_simple_market_stays_direct() -> None:
    assert classify_query("今天大盘行情") == ComplexityResult.DIRECT
    assert classify_query("最新市场指数") == ComplexityResult.DIRECT


def test_stock_deep_routes_to_debate() -> None:
    assert classify_query("600519 深度分析") == ComplexityResult.DEBATE
    assert classify_query("茅台 辩论投研") == ComplexityResult.DEBATE


def test_market_with_stock_code_is_stock_debate() -> None:
    assert classify_query("600519 大盘深度分析") == ComplexityResult.DEBATE


def test_helpers() -> None:
    assert wants_deep_research("深度投研辩论")
    assert is_market_scope("沪深300走势")


def test_classify_research_scope() -> None:
    assert classify_research_scope("帮我分析一下600519") == "stock"
    assert classify_research_scope("今天大盘走势") == "market"
    assert classify_research_scope("A 股走势如何") == "market"
    assert classify_research_scope("最近市场怎么样") == "market"
    assert classify_research_scope("沪深市场如何") == "market"
    assert classify_research_scope("什么是市盈率") is None


def test_a_share_spaced_query_routes_to_market_debate() -> None:
    assert (
        resolve_execution_mode("A 股走势如何", enable_debate=True)
        == ComplexityResult.MARKET_DEBATE
    )


def test_resolve_execution_mode() -> None:
    assert resolve_execution_mode("今天大盘行情", ANALYSIS_SIMPLE) == ComplexityResult.DIRECT
    assert (
        resolve_execution_mode("今天大盘行情", enable_debate=False)
        == ComplexityResult.MARKET_RESEARCH
    )
    assert (
        resolve_execution_mode("今天大盘行情", enable_debate=True)
        == ComplexityResult.MARKET_DEBATE
    )
    assert (
        resolve_execution_mode("帮我分析一下600519", enable_debate=True)
        == ComplexityResult.DEBATE
    )
    assert (
        resolve_execution_mode("帮我分析一下600519", enable_debate=False)
        == ComplexityResult.RESEARCH
    )
    assert resolve_execution_mode("600519 深度分析", ANALYSIS_SIMPLE) == ComplexityResult.DIRECT
