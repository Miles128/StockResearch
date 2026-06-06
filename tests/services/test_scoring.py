"""Weighted composite scoring tests."""

from stockresearch.agents.research.scoring import (
    composite_confidence,
    dimension_weight,
    score_bias,
    weighted_composite_score,
)
from stockresearch.core.schemas import DimensionResult


def _dim(score: float, confidence: str = "medium", highlights: list[str] | None = None) -> DimensionResult:
    return DimensionResult(
        agent="测试",
        score=score,
        confidence=confidence,  # type: ignore[arg-type]
        highlights=highlights or [],
        risks=[],
        data_sources=[],
    )


def test_weighted_composite_prefers_high_confidence() -> None:
    dimensions = {
        "a": _dim(8.0, "high", ["h1", "h2"]),
        "b": _dim(4.0, "low"),
    }
    composite, weights = weighted_composite_score(dimensions)
    assert weights["a"] > weights["b"]
    assert composite > 6.0


def test_dimension_weight_richness_bonus() -> None:
    sparse = dimension_weight(_dim(5.0, "medium"))
    rich = dimension_weight(_dim(5.0, "medium", ["a", "b", "c"]))
    assert rich > sparse


def test_score_bias_thresholds() -> None:
    assert score_bias(7.0) == "bullish"
    assert score_bias(4.0) == "bearish"
    assert score_bias(5.5) == "neutral"


def test_composite_confidence_majority_high() -> None:
    dims = {"a": _dim(5, "high"), "b": _dim(5, "high"), "c": _dim(5, "low")}
    assert composite_confidence(dims) == "high"
