"""Neutral guard: post-processing layer to enforce investment neutrality.

Applies three sub-guards to LLM output:
1. Ban filter: regex-replace prohibited advisory patterns
2. Tone calibrator: soften directive language
3. Attribution engine: reframe system suggestions as user-data observations

This module does NOT rely on LLM compliance — it's a hard mechanical filter.
"""

from __future__ import annotations

import re

from stockresearch.core.constants import OUTPUT_BANNED_PATTERNS


def apply_ban_filter(text: str) -> str:
    """Replace banned advisory patterns with neutral alternatives."""
    for pattern, replacement in OUTPUT_BANNED_PATTERNS:
        if replacement is None:
            text = re.sub(pattern, "", text)
        else:
            text = re.sub(pattern, replacement, text)
    return text


# Tone calibration: softer alternatives for directive language
# Note: "建议买入/卖出/加仓/减仓" is already handled by OUTPUT_BANNED_PATTERNS.
# These patterns catch remaining directive language not covered by the ban filter.
_TONE_CALIBRATIONS: list[tuple[str, str]] = [
    (r"应该\s*买", "可能值得留意"),
    (r"应该\s*卖", "可能需要评估"),
    (r"应该\s*持有", "可以考虑持有"),
    (r"应该\s*分散", "分散化可能降低风险"),
    (r"推荐\s*买入", "关注"),
    (r"推荐\s*卖出", "评估"),
    (r"预计\s*将", "历史上类似情况可能"),
    (r"将会", "可能"),
    (r"系统建议", "你的数据显示"),
    (r"我们建议", "从数据看"),
]


def apply_tone_calibration(text: str) -> str:
    """Soften directive language to neutral tone."""
    for pattern, replacement in _TONE_CALIBRATIONS:
        text = re.sub(pattern, replacement, text)
    return text


# Attribution patterns: reframe system-origin statements as user-data observations
_ATTRIBUTION_PATTERNS: list[tuple[str, str]] = [
    (r"建议关注(.+?)板块", r"你持仓中\1板块占比突出，近期有相关动态"),
    (r"应该适当分散", "当前集中度评分偏低，分散化或可降低波动"),
    (r"建议止损", "已接近你设定的止损关注线"),
    (r"建议\s+(.*?)仓位", r"\1的仓位数据发生变化，值得关注"),
]


def apply_attribution(text: str) -> str:
    """Reframe advisory statements as user-data observations."""
    for pattern, replacement in _ATTRIBUTION_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


def neutral_guard(text: str) -> str:
    """Apply all neutral guard layers in sequence.

    Order: ban filter → tone calibration → attribution.
    """
    text = apply_ban_filter(text)
    text = apply_tone_calibration(text)
    text = apply_attribution(text)
    return text
