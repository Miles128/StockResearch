"""Glossary service: load terms, match in text, wrap with <term> tags.

激活由 `enable_glossary` 控制（投顾模式默认开启，投研模式关闭），
与 reading_mode 解耦。详见 chat_response.finalize_chat_reply。
用户可在设置中追加 custom_glossary 条目，与内置词库合并。
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

from stockresearch.core.schemas import CustomGlossaryTermOut

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
def _load_builtin_glossary() -> dict[str, GlossaryTerm]:
    if not _GLOSSARY_PATH.exists():
        return {}
    with open(_GLOSSARY_PATH, encoding="utf-8") as f:
        raw: dict[str, Any] = json.load(f)
    return {k: GlossaryTerm(k, v) for k, v in raw.items()}


def get_builtin_glossary() -> dict[str, GlossaryTerm]:
    return _load_builtin_glossary()


def get_glossary() -> dict[str, GlossaryTerm]:
    """Backward-compatible alias for built-in glossary only."""
    return get_builtin_glossary()


def merge_glossary(
    custom: Sequence[CustomGlossaryTermOut] | None = None,
) -> dict[str, GlossaryTerm]:
    """Built-in terms plus user-defined overrides/additions."""
    merged = dict(_load_builtin_glossary())
    if custom:
        for item in custom:
            merged[item.id] = GlossaryTerm(
                item.id,
                {
                    "en": item.en,
                    "short": item.short,
                    "def": item.def_,
                    "analogy": item.analogy,
                },
            )
    return merged


def custom_glossary_ids(custom: Sequence[CustomGlossaryTermOut] | None = None) -> set[str]:
    if not custom:
        return set()
    return {item.id for item in custom}


def get_term(term_id: str) -> GlossaryTerm | None:
    return _load_builtin_glossary().get(term_id)


def list_glossary_payload(
    custom: Sequence[CustomGlossaryTermOut] | None = None,
) -> list[dict[str, str | bool]]:
    merged = merge_glossary(custom)
    custom_ids = custom_glossary_ids(custom)
    rows = [
        {
            "id": term.id,
            "short": term.short,
            "en": term.en,
            "def": term.def_,
            "analogy": term.analogy,
            "custom": term.id in custom_ids,
        }
        for term in merged.values()
    ]
    rows.sort(key=lambda row: (not bool(row["custom"]), str(row["short"])))
    return rows


def _build_pattern(label: str, *, term_id: str) -> re.Pattern[str]:
    """Build a regex pattern for a glossary surface form."""
    escaped = re.escape(label)
    if term_id in _SHORT_TERMS or (label.isascii() and len(label) <= 5):
        return re.compile(rf"(?<![A-Za-z]){escaped}(?![A-Za-z])")
    if not label.isascii():
        return re.compile(escaped)
    return re.compile(rf"(?<![一-龟A-Za-z]){escaped}(?![一-龟A-Za-z])")


def _match_labels(glossary: dict[str, GlossaryTerm]) -> list[tuple[str, str]]:
    """Return (surface label, canonical term_id) pairs, longest labels first."""
    label_to_id: dict[str, str] = {}
    for term_id, term in glossary.items():
        label_to_id[term_id] = term_id
        short = (term.short or "").strip()
        if short and short not in label_to_id:
            label_to_id[short] = term_id
    return sorted(label_to_id.items(), key=lambda item: len(item[0]), reverse=True)


def mark_terms(
    text: str,
    *,
    glossary: dict[str, GlossaryTerm] | None = None,
) -> str:
    """Wrap glossary terms in <term data-id="..."> tags."""
    terms = glossary if glossary is not None else _load_builtin_glossary()
    if not terms:
        return text

    matches: list[tuple[int, int, str]] = []
    for label, term_id in _match_labels(terms):
        pattern = _build_pattern(label, term_id=term_id)
        for m in pattern.finditer(text):
            matches.append((m.start(), m.end(), term_id))

    if not matches:
        return text

    matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    filtered: list[tuple[int, int, str]] = []
    last_end = -1
    for start, end, term_id in matches:
        if start >= last_end:
            filtered.append((start, end, term_id))
            last_end = end

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
    _load_builtin_glossary.cache_clear()


def reload_glossary() -> dict[str, GlossaryTerm]:
    """Force reload built-in glossary from disk."""
    _load_builtin_glossary.cache_clear()
    return _load_builtin_glossary()
