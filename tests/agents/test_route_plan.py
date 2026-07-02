"""Route plan proposal tests — ReAct / Plan-Execute / preset."""

from stockresearch.agents.orchestrator.route_plan import (
    is_finance_related,
    needs_execution_choice,
    resolve_mode_with_preference,
)
from stockresearch.agents.orchestrator.complexity import ComplexityResult


def test_is_finance_related() -> None:
    assert is_finance_related("帮我分析一下600519")
    assert is_finance_related("今天大盘走势怎么样")
    assert is_finance_related("半导体行业深度研究")
    assert not is_finance_related("什么是机器学习")
    assert not is_finance_related("帮我写一首关于春天的诗")


def test_needs_execution_choice_disabled() -> None:
    """Plan-Execute is automatic; users are not asked to pick a mode."""
    assert not needs_execution_choice("对比茅台和五粮液的投资价值")
    assert not needs_execution_choice("如果美联储加息，A股科技板块会怎样，该怎么办")
    assert not needs_execution_choice("你好")
    assert not needs_execution_choice("今天大盘行情")


def test_resolve_mode_with_preference() -> None:
    msg = "对比茅台和五粮液的投资价值"
    mode, finance = resolve_mode_with_preference(msg, "react")
    assert mode == ComplexityResult.DIRECT
    assert finance

    mode, finance = resolve_mode_with_preference(msg, None)
    assert mode == ComplexityResult.PLAN_EXECUTE
    assert finance

    mode, finance = resolve_mode_with_preference(
        "如果地球引力减半会怎样", "plan_execute"
    )
    assert mode == ComplexityResult.PLAN_EXECUTE
    assert not finance

    mode, _ = resolve_mode_with_preference("今天大盘行情", "preset", enable_debate=False)
    assert mode == ComplexityResult.MARKET_RESEARCH
