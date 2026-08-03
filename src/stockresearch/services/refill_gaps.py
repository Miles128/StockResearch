"""Gap-driven refill: classify report data_gaps and evict related caches.

Research reports list free-form Chinese gap notes (e.g. 「公告仅标题」、
「财务序列不完整」). A refill maps those notes to data categories, evicts
the related provider/report caches so the next research run re-fetches
fresh data, then the caller re-runs the four-dimension research.
"""

from __future__ import annotations

import logging

from stockresearch.services.cache import evict_memory_prefixes
from stockresearch.services.sqlite_cache import evict_sqlite_prefixes

logger = logging.getLogger(__name__)

# gap 文本关键词 -> 数据类别
_GAP_KEYWORDS: dict[str, tuple[str, ...]] = {
    "announcements": ("公告",),
    "financial": ("财务", "估值", "可比公司", "分位"),
    "news_sentiment": ("新闻", "舆情", "情绪", "雪球"),
    "chips": ("筹码",),
    "quotes": ("行情", "停牌", "陈旧"),
    "reports": ("研报",),
}

# 数据类别 -> provider 缓存键前缀（sqlite provider_cache 与内存缓存共用）
_CATEGORY_CACHE_PREFIXES: dict[str, tuple[str, ...]] = {
    "announcements": ("announcements:",),
    "financial": ("financial:", "financials:"),
    "news_sentiment": ("news:", "sentiment:"),
    "chips": (
        "fund_flow:",
        "holder_count:",
        "lockup:",
        "margin:",
        "northbound:",
        "dragon_tiger:",
    ),
    "quotes": ("quote:", "kline:", "market:"),
    "reports": ("reports:",),
}

_RESEARCH_CACHE_PREFIX = ("research:",)


def classify_gaps(gaps: list[str] | None) -> list[str]:
    """Map free-form gap notes to data categories (deduped, stable order)."""
    categories: list[str] = []
    for gap in gaps or []:
        text = str(gap).strip()
        if not text:
            continue
        for category, keywords in _GAP_KEYWORDS.items():
            if any(keyword in text for keyword in keywords) and category not in categories:
                categories.append(category)
    return categories


def evict_gap_caches(symbol: str, categories: list[str]) -> int:
    """Evict report cache + provider caches for the given categories.

    Always evicts the research report cache for the symbol (a refill must
    never return the cached report). Returns total evicted entry count.
    """
    evicted = evict_memory_prefixes(_RESEARCH_CACHE_PREFIX, contains=symbol)
    evicted += evict_memory_prefixes(("market:", "quote:", "kline:"), contains=symbol)
    prefixes: list[str] = []
    for category in categories:
        prefixes.extend(_CATEGORY_CACHE_PREFIXES.get(category, ()))
    if prefixes:
        evicted += evict_sqlite_prefixes(tuple(prefixes), contains=symbol)
        evicted += evict_memory_prefixes(tuple(prefixes), contains=symbol)
    logger.info(
        "refill caches evicted for %s (categories=%s): %d entries",
        symbol,
        ",".join(categories) or "-",
        evicted,
    )
    return evicted
