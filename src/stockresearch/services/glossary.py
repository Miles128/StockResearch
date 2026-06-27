"""Glossary service: load terms, match in text, wrap with <term> tags.

激活由 `enable_glossary` 控制（投顾模式默认开启，投研模式关闭），
与 reading_mode 解耦。详见 chat_response.finalize_chat_reply。
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_GLOSSARY_PATH = Path(__file__).resolve().parent.parent / "data" / "glossary.json"

# Terms that should NOT be matched inside other words (e.g. "PE" inside "TYPE")
# We use word-boundary matching for these short abbreviations.
_SHORT_TERMS = {"PE", "PB", "ROE", "ROA", "EPS", "VaR", "CVaR", "MACD", "RSI", "KDJ",
                "BOLL", "EMA", "MA", "PEG", "Beta", "Alpha", "VaR 95%"}


class GlossaryTerm:
    __slots__ = ("id", "en", "short", "def_", "analogy", "context_template")

    def __init__(self, term_id: str, data: dict[str, Any]) -> None:
        self.id = term_id
        self.en = data.get("en", "")
        self.short = data.get("short", term_id)
        self.def_ = data.get("def", "")
        self.analogy = data.get("analogy", "")
        self.context_template = data.get("context_template", "")


@lru_cache(maxsize=1)
def _load_glossary() -> dict[str, GlossaryTerm]:
    if not _GLOSSARY_PATH.exists():
        return {}
    with open(_GLOSSARY_PATH, encoding="utf-8") as f:
        raw: dict[str, Any] = json.load(f)
    return {k: GlossaryTerm(k, v) for k, v in raw.items()}


def get_glossary() -> dict[str, GlossaryTerm]:
    return _load_glossary()


def get_term(term_id: str) -> GlossaryTerm | None:
    return _load_glossary().get(term_id)


def _build_pattern(term_id: str) -> re.Pattern[str]:
    """Build a regex pattern for a glossary term.

    Short abbreviations (PE, ROE, etc.) use boundary matching that works
    with both ASCII word boundaries and CJK character adjacency.
    Chinese terms use lookahead/lookbehind for CJK boundaries.
    """
    escaped = re.escape(term_id)
    if term_id in _SHORT_TERMS:
        # Word boundary OR preceded/followed by non-word char (including CJK)
        return re.compile(rf"(?<![A-Za-z]){escaped}(?![A-Za-z])")
    # For Chinese terms: match when not preceded/followed by CJK character
    return re.compile(rf"(?<![一-龟]){escaped}(?![一-龟])")


def mark_terms(text: str) -> str:
    """Wrap glossary terms in <term data-id="..."> tags.

    仅在 enable_glossary=True（投顾模式）时由 finalize_chat_reply 调用。
    Longer terms are matched first to avoid partial matches
    (e.g. "VaR 95%" before "VaR").
    """
    glossary = _load_glossary()
    if not glossary:
        return text

    # Sort by length descending so longer terms match first
    sorted_terms = sorted(glossary.keys(), key=len, reverse=True)

    # Collect all match positions to avoid overlapping replacements
    matches: list[tuple[int, int, str]] = []  # (start, end, term_id)
    for term_id in sorted_terms:
        pattern = _build_pattern(term_id)
        for m in pattern.finditer(text):
            matches.append((m.start(), m.end(), term_id))

    if not matches:
        return text

    # Remove overlapping matches (keep the first/longest)
    matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    filtered: list[tuple[int, int, str]] = []
    last_end = -1
    for start, end, term_id in matches:
        if start >= last_end:
            filtered.append((start, end, term_id))
            last_end = end

    # Build output string
    result_parts: list[str] = []
    cursor = 0
    for start, end, term_id in filtered:
        result_parts.append(text[cursor:start])
        result_parts.append(f'<term data-id="{term_id}">{text[start:end]}</term>')
        cursor = end
    result_parts.append(text[cursor:])
    return "".join(result_parts)


def clear_glossary_cache() -> None:
    """Clear the cached glossary (for testing)."""
    _load_glossary.cache_clear()


def reload_glossary() -> dict[str, GlossaryTerm]:
    """Force reload glossary from disk and return the fresh terms.

    用于 glossary.json 被热更新后（如运维修改术语定义）无需重启进程即可生效。
    """
    _load_glossary.cache_clear()
    return _load_glossary()
