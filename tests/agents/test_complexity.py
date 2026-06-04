"""Query complexity routing tests."""

from stockresearch.agents.orchestrator.complexity import (
    ANALYSIS_COMPLEX,
    ANALYSIS_SIMPLE,
    ComplexityResult,
    classify_query,
    is_market_scope,
    needs_analysis_choice,
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


def test_needs_analysis_choice() -> None:
    assert needs_analysis_choice("今天大盘行情", has_holdings=False)
    assert not needs_analysis_choice("帮我做风控体检", has_holdings=True)


def test_resolve_execution_mode() -> None:
    assert resolve_execution_mode("今天大盘行情", ANALYSIS_SIMPLE) == ComplexityResult.DIRECT
    assert resolve_execution_mode("今天大盘行情", ANALYSIS_COMPLEX) == ComplexityResult.PLAN_EXECUTE
    assert resolve_execution_mode("600519 深度分析", ANALYSIS_COMPLEX) == ComplexityResult.DEBATE
    assert resolve_execution_mode("600519 深度分析", ANALYSIS_SIMPLE) == ComplexityResult.DIRECT
