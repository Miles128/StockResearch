"""Shared formatting helpers for display strings."""

from __future__ import annotations


def arrow_for_change(pct: float) -> str:
    """Return an up/down/flat arrow for a percentage change."""
    if pct > 0:
        return "↑"
    if pct < 0:
        return "↓"
    return "→"


def news_score_to_label(score: float) -> str:
    """Map a normalized news sentiment score (-1..+1) to a Chinese label.

    Threshold ±0.2: above → 偏多, below → 偏空, otherwise → 中性.
    """
    if score > 0.2:
        return "偏多"
    if score < -0.2:
        return "偏空"
    return "中性"
