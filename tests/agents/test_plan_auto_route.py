"""Auto Plan-Execute routing — no manual user choice."""

from stockresearch.agents.orchestrator.complexity import (
    ComplexityResult,
    is_multi_scope,
    is_single_focus_scope,
    is_stock_comparison,
    resolve_execution_mode,
    should_auto_plan_execute,
)


def test_stock_comparison_auto_plan() -> None:
    assert is_stock_comparison("对比茅台和五粮液的投资价值")
    assert is_stock_comparison("600519和000858哪个更好")
    assert should_auto_plan_execute("对比茅台和五粮液的投资价值")
    assert (
        resolve_execution_mode("对比茅台和五粮液的投资价值")
        == ComplexityResult.PLAN_EXECUTE
    )


def test_single_stock_not_plan() -> None:
    assert is_single_focus_scope("帮我分析一下600519")
    assert not should_auto_plan_execute("帮我分析一下600519")
    assert resolve_execution_mode("帮我分析一下600519") == ComplexityResult.RESEARCH


def test_single_market_not_plan() -> None:
    assert is_single_focus_scope("今天大盘走势怎么样")
    assert not should_auto_plan_execute("今天大盘行情")
    assert resolve_execution_mode("今天大盘行情") == ComplexityResult.DIRECT


def test_single_industry_not_plan() -> None:
    assert is_single_focus_scope("半导体行业深度投研分析")
    assert not should_auto_plan_execute("半导体行业深度投研分析")
    assert (
        resolve_execution_mode("半导体行业深度投研分析")
        == ComplexityResult.INDUSTRY_RESEARCH
    )


def test_multi_scope_auto_plan() -> None:
    assert is_multi_scope("如果美联储加息，对A股大盘和银行板块会有什么影响")
    assert should_auto_plan_execute("如果美联储加息，对A股大盘和银行板块会有什么影响")
    assert (
        resolve_execution_mode("如果美联储加息，对A股大盘和银行板块会有什么影响")
        == ComplexityResult.PLAN_EXECUTE
    )
