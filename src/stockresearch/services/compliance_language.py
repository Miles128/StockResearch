"""PRD §9.1 output language — position bias vocabulary and forbidden-term scrubbing."""

from __future__ import annotations

import re

# Canonical position bias terms (internal schema + UI)
POSITION_BIAS_HIGH = "仓位偏高"
POSITION_BIAS_LOW = "仓位偏低"
POSITION_BIAS_NEUTRAL = "仓位适中"
POSITION_CONTROL = "建议控制仓位"
HOLDING_NO_CHANGE = "暂不调整"

PORTFOLIO_POSITION_ACTIONS = frozenset(
    {POSITION_BIAS_HIGH, POSITION_BIAS_LOW, POSITION_BIAS_NEUTRAL, POSITION_CONTROL}
)
HOLDING_POSITION_ACTIONS = frozenset(PORTFOLIO_POSITION_ACTIONS | {HOLDING_NO_CHANGE})

_LEGACY_POSITION_MAP: dict[str, str] = {
    "加仓": POSITION_BIAS_LOW,
    "减仓": POSITION_BIAS_HIGH,
    "持有观望": POSITION_BIAS_NEUTRAL,
    "观望": POSITION_BIAS_NEUTRAL,
    "Add": POSITION_BIAS_LOW,
    "Reduce": POSITION_BIAS_HIGH,
    "Hold & watch": POSITION_BIAS_NEUTRAL,
    "Watch": POSITION_BIAS_NEUTRAL,
}

# Longer phrases first when scrubbing free text.
_FORBIDDEN_TEXT_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("持有观望", POSITION_BIAS_NEUTRAL),
    ("建议加仓", POSITION_CONTROL),
    ("建议减仓", POSITION_CONTROL),
    ("加仓", POSITION_BIAS_LOW),
    ("减仓", POSITION_BIAS_HIGH),
)


def normalize_position_action(action: str, *, portfolio: bool = False) -> str:
    """Map legacy or LLM actions to PRD §9.1 vocabulary."""
    cleaned = action.strip()
    if not cleaned:
        fallback = POSITION_BIAS_NEUTRAL if portfolio else HOLDING_NO_CHANGE
        return fallback
    mapped = _LEGACY_POSITION_MAP.get(cleaned, cleaned)
    allowed = PORTFOLIO_POSITION_ACTIONS if portfolio else HOLDING_POSITION_ACTIONS
    if mapped in allowed:
        return mapped
    if mapped in _LEGACY_POSITION_MAP.values():
        return mapped
    return POSITION_BIAS_NEUTRAL if portfolio else HOLDING_NO_CHANGE


def scrub_forbidden_position_language(text: str) -> str:
    """Replace forbidden position terms in arbitrary assistant text."""
    if not text:
        return text
    for old, new in _FORBIDDEN_TEXT_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def contains_forbidden_position_language(text: str) -> bool:
    return any(re.search(re.escape(old), text) for old, _ in _FORBIDDEN_TEXT_REPLACEMENTS)
