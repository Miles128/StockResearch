"""Route plan proposal tests — ReAct / Plan-Execute / preset."""

from stockresearch.agents.orchestrator.route_plan import (
    build_route_proposal,
    is_finance_related,
    needs_execution_choice,
    resolve_mode_with_preference,
    route_choice_card,
)
from stockresearch.agents.orchestrator.complexity import ComplexityResult


def test_is_finance_related() -> None:
    assert is_finance_related("帮我分析一下600519")
    assert is_finance_related("今天大盘走势怎么样")
    assert is_finance_related("半导体行业深度研究")
    assert not is_finance_related("什么是机器学习")
    assert not is_finance_related("帮我写一首关于春天的诗")


def test_needs_execution_choice_complex_patterns() -> None:
    assert needs_execution_choice("对比茅台和五粮液的投资价值")
    assert needs_execution_choice("如果美联储加息，A股科技板块会怎样，该怎么办")
    assert not needs_execution_choice("你好")
    assert not needs_execution_choice("今天大盘行情")
    assert not needs_execution_choice(
        "对比茅台和五粮液",
        execution_preference="react",
    )


def test_build_route_proposal_finance_has_preset() -> None:
    proposal = build_route_proposal("对比茅台和五粮液的投资价值", enable_debate=False)
    assert proposal.finance_related
    assert proposal.preset_mode == ComplexityResult.RESEARCH
    ids = [o.id for o in proposal.options]
    assert "preset" in ids
    assert "react" in ids
    assert "plan_execute" in ids


def test_build_route_proposal_non_finance_no_preset() -> None:
    proposal = build_route_proposal(
        "如果地球引力减半，人类日常生活会发生哪些连锁变化，请分步骤分析",
        enable_debate=False,
    )
    assert not proposal.finance_related
    ids = [o.id for o in proposal.options]
    assert "preset" not in ids
    assert "react" in ids
    assert "plan_execute" in ids


def test_resolve_mode_with_preference() -> None:
    msg = "对比茅台和五粮液的投资价值"
    mode, finance = resolve_mode_with_preference(msg, "react")
    assert mode == ComplexityResult.DIRECT
    assert finance

    mode, finance = resolve_mode_with_preference(
        "如果地球引力减半会怎样", "plan_execute"
    )
    assert mode == ComplexityResult.PLAN_EXECUTE
    assert not finance

    mode, _ = resolve_mode_with_preference(msg, "preset", enable_debate=False)
    assert mode == ComplexityResult.RESEARCH


def test_route_choice_card_shape() -> None:
    proposal = build_route_proposal("对比茅台和五粮液的投资价值")
    card = route_choice_card("对比茅台和五粮液的投资价值", proposal)
    assert card["type"] == "route_choice"
    data = card["data"]
    assert isinstance(data, dict)
    assert data["finance_related"] is True
    assert len(data["options"]) >= 2
