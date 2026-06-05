"""LLM usage tracking tests."""

from stockresearch.utils.llm_usage import (
    clear_usage,
    estimate_tokens,
    get_usage,
    record_usage,
    reset_usage,
    usage_to_out,
)


def test_estimate_tokens_nonempty() -> None:
    assert estimate_tokens("你好世界") >= 1


def test_usage_accumulation_and_cost() -> None:
    clear_usage()
    reset_usage(model="deepseek-chat")
    record_usage(prompt_tokens=1000, completion_tokens=500, is_estimate=True)
    out = usage_to_out(get_usage())
    assert out is not None
    assert out.total_tokens == 1500
    assert out.is_estimate is True
    assert out.estimated_cost_cny is not None
    assert out.estimated_cost_cny > 0
    clear_usage()


def test_usage_to_out_empty() -> None:
    clear_usage()
    assert usage_to_out(get_usage()) is None
