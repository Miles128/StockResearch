"""Formatted macro snapshot — reads Kimi prefetched cache only (no live calls).

The ``kimi_prefetch_scheduler`` worker keeps the macro cache warm; chat and
market research paths read it synchronously to stay latency-free. Returns an
empty string when no cached macro data exists so callers degrade gracefully.
"""

from __future__ import annotations

from stockresearch.data.providers.kimi_macro import MACRO_CACHE_KEY
from stockresearch.services.sqlite_cache import get_sqlite_cached

_DEFAULT_MAX_LINES = 8


def format_macro_snapshot(*, max_lines: int | None = _DEFAULT_MAX_LINES) -> str:
    """Format cached Kimi macro payload into a prompt block.

    ``max_lines=None`` means no cap (used by briefings to keep full detail).
    """
    macro = get_sqlite_cached(MACRO_CACHE_KEY)
    if not macro:
        return ""

    lines: list[str] = [f"【宏观数据(Kimi, {macro.get('as_of', '?')})】"]
    for ind in macro.get("indicators") or []:
        if isinstance(ind, dict):
            trend = ind.get("trend")
            trend_str = f" 趋势:{trend}" if trend else ""
            lines.append(
                f"- {ind.get('name')}: {ind.get('value')}({ind.get('period')}){trend_str}{ind.get('comment', '')}"
            )
    for hl in macro.get("industry_highlights") or []:
        if isinstance(hl, dict):
            lines.append(f"- 行业·{hl.get('industry')}: {hl.get('summary')}")

    if len(lines) <= 1:
        return ""
    if max_lines is not None:
        lines = lines[: max_lines + 1]
    return "\n".join(lines)
