"""Research viewpoint builder tests."""

from stockresearch.agents.research.viewpoints import build_viewpoints
from stockresearch.core.schemas import DebateResult, DimensionResult


def test_build_viewpoints_from_dimensions_and_debate() -> None:
    dimensions = {
        "fundamental": DimensionResult(
            agent="fundamental",
            score=7,
            confidence="high",
            highlights=["盈利质量较好"],
            risks=[],
            data_sources=["akshare_financials"],
        ),
        "technical": DimensionResult(
            agent="technical",
            score=6,
            confidence="medium",
            highlights=["均线多头排列"],
            risks=["短期波动加大"],
            data_sources=["akshare_kline"],
        ),
    }
    debate = DebateResult(
        rounds=[],
        judge_verdict="",
        consensus="多空分歧不大，但需关注估值",
        core_divergence="",
        final_bias="neutral",
        confidence="medium",
    )
    viewpoints = build_viewpoints(dimensions, debate, news_text_factor="政策面偏暖")
    assert viewpoints["fundamental"] == "盈利质量较好"
    assert viewpoints["technical"] == "均线多头排列"
    assert viewpoints["sentiment"] == "政策面偏暖"
    assert viewpoints["risk"] == "多空分歧不大，但需关注估值"
