"""Query complexity routing tests."""

from stockresearch.agents.orchestrator.complexity import (
    ComplexityResult,
    classify_query,
    classify_research_scope,
    is_market_scope,
    is_news_intent,
    is_simple_news_explanation,
    resolve_execution_mode,
    should_skip_debate,
    should_skip_multi_agent,
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
    assert is_news_intent("今天有什么新闻")


def test_classify_research_scope() -> None:
    assert classify_research_scope("帮我分析一下600519") == "stock"
    assert classify_research_scope("今天大盘走势") is None
    assert classify_research_scope("A 股走势如何") is None
    assert classify_research_scope("最近市场怎么样") is None
    assert classify_research_scope("沪深市场如何") is None
    assert classify_research_scope("什么是市盈率") is None
    assert classify_research_scope("今天有什么新闻") is None
    assert classify_research_scope("大盘深度分析") == "market"


def test_a_share_spaced_query_routes_to_market_debate() -> None:
    assert (
        resolve_execution_mode("A 股走势深度分析", enable_debate=True)
        == ComplexityResult.MARKET_DEBATE
    )


def test_resolve_execution_mode() -> None:
    assert (
        resolve_execution_mode("今天大盘行情", enable_debate=False)
        == ComplexityResult.DIRECT
    )
    assert (
        resolve_execution_mode("今天大盘行情", enable_debate=True)
        == ComplexityResult.DIRECT
    )
    assert (
        resolve_execution_mode("帮我分析一下600519", enable_debate=True)
        == ComplexityResult.DEBATE
    )
    assert (
        resolve_execution_mode("帮我分析一下600519", enable_debate=False)
        == ComplexityResult.RESEARCH
    )


def test_simple_news_stays_direct_even_with_debate() -> None:
    assert is_simple_news_explanation("解释这条新闻对持仓有什么影响")
    assert (
        resolve_execution_mode("解释这条新闻对持仓有什么影响", enable_debate=True)
        == ComplexityResult.DIRECT
    )
    assert (
        resolve_execution_mode("这条消息什么意思", enable_debate=True)
        == ComplexityResult.DIRECT
    )
    assert should_skip_debate("600519 现价多少")
    assert (
        resolve_execution_mode("600519 现价多少", enable_debate=True)
        == ComplexityResult.DIRECT
    )


def test_deep_stock_still_debates_when_enabled() -> None:
    assert (
        resolve_execution_mode("600519 深度分析", enable_debate=True)
        == ComplexityResult.DEBATE
    )
    assert not should_skip_debate("600519 深度分析")
