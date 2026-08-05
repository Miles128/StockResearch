"""Research viewpoint builder tests."""

from stockresearch.agents.research.viewpoints import build_viewpoints
from stockresearch.core.schemas import DimensionResult


def test_build_viewpoints_from_dimensions() -> None:
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
    viewpoints = build_viewpoints(dimensions)
    assert viewpoints["fundamental"] == "盈利质量较好"
    assert viewpoints["technical"] == "均线多头排列"
    assert viewpoints["risk"] == "短期波动加大"
    assert "sentiment" not in viewpoints
