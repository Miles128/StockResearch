"""Confidence-weighted composite scoring for dimension agents."""

from typing import Literal

from stockresearch.core.schemas import DimensionResult

ConfidenceLevel = Literal["high", "medium", "low"]

_CONFIDENCE_WEIGHT: dict[str, float] = {
    "high": 1.0,
    "medium": 0.75,
    "low": 0.45,
}


def dimension_weight(dim: DimensionResult) -> float:
    """Weight by confidence and light richness bonus (highlights / data sources)."""
    base = _CONFIDENCE_WEIGHT.get(dim.confidence, 0.75)
    richness = min(0.12, len(dim.highlights) * 0.04)
    if dim.data_sources:
        richness += 0.05
    return round(base + richness, 3)


def weighted_composite_score(
    dimensions: dict[str, DimensionResult],
) -> tuple[float, dict[str, float]]:
    """Return (composite_score, per-dimension weights)."""
    if not dimensions:
        return 5.0, {}
    weights = {key: dimension_weight(dim) for key, dim in dimensions.items()}
    total_w = sum(weights.values())
    if total_w <= 0:
        avg = round(sum(d.score for d in dimensions.values()) / len(dimensions), 1)
        return avg, weights
    composite = round(
        sum(dim.score * weights[key] for key, dim in dimensions.items()) / total_w,
        1,
    )
    return composite, weights


def composite_confidence(dimensions: dict[str, DimensionResult]) -> ConfidenceLevel:
    confidences = [d.confidence for d in dimensions.values()]
    if confidences.count("high") >= 2:
        return "high"
    if "low" in confidences:
        return "low"
    return "medium"


def score_bias(composite: float) -> Literal["bullish", "bearish", "neutral"]:
    if composite >= 6.5:
        return "bullish"
    if composite <= 4.5:
        return "bearish"
    return "neutral"
