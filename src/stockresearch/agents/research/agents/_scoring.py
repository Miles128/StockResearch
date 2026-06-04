"""Shared scoring helpers for dimension agents."""

from typing import Literal

from stockresearch.core.constants import CONFIDENCE_HIGH, CONFIDENCE_LOW, CONFIDENCE_MEDIUM

ConfidenceLevel = Literal["high", "medium", "low"]


def as_confidence(value: str) -> ConfidenceLevel:
    if value == CONFIDENCE_HIGH:
        return "high"
    if value == CONFIDENCE_LOW:
        return "low"
    return "medium"
