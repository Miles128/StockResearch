"""Three-layer news noise filter per PRD: blacklist → source authority → relevance."""

from dataclasses import dataclass

from stockresearch.core.constants import (
    IMPACT_MAJOR,
    IMPACT_NORMAL,
    NEWS_BLACKLIST_KEYWORDS,
    NEWS_DEMOTION_KEYWORDS,
    NEWS_HEAVY_REJECT_KEYWORDS,
    NEWS_SOURCE_AUTHORITY,
)
from stockresearch.db.models import NewsItem
from stockresearch.services.news_interests import UserNewsInterests, classify_news

NEWS_FEED_SLA_SEC = 3.0

_RELEVANCE_WEIGHT: dict[str, float] = {
    "holding": 1.0,
    "sector": 0.85,
    "market": 0.65,
}

_IMPACT_WEIGHT: dict[str, float] = {
    IMPACT_MAJOR: 1.25,
    IMPACT_NORMAL: 1.0,
}


@dataclass(frozen=True)
class ScoredNews:
    item: NewsItem
    related: bool
    category: str
    rank_score: float
    rejected_reason: str | None = None


def layer1_blacklist_reject(title: str) -> bool:
    """Layer 1: drop blacklist + heavy demotion keywords."""
    return any(kw in title for kw in NEWS_BLACKLIST_KEYWORDS) or any(
        kw in title for kw in NEWS_HEAVY_REJECT_KEYWORDS
    )


def layer1b_title_demotion(title: str) -> float:
    """Layer 1b: multiply rank score when soft-clickbait keywords appear."""
    factor = 1.0
    for keyword, multiplier in NEWS_DEMOTION_KEYWORDS.items():
        if keyword in title:
            factor = min(factor, multiplier)
    return factor


def layer2_source_authority(source: str) -> float:
    """Layer 2: score 0–1 by publisher credibility."""
    normalized = source.strip()
    if not normalized:
        return NEWS_SOURCE_AUTHORITY["default"]
    best = NEWS_SOURCE_AUTHORITY["default"]
    for prefix, score in NEWS_SOURCE_AUTHORITY.items():
        if prefix == "default":
            continue
        if prefix in normalized:
            best = max(best, score)
    return best


def layer3_relevance(
    item: NewsItem,
    interests: UserNewsInterests,
) -> tuple[str | None, float]:
    """Layer 3: classify against user holdings/sectors; return category + weight."""
    category = classify_news(item, interests)
    if category is None:
        return None, 0.0
    return category, _RELEVANCE_WEIGHT.get(category, 0.5)


def compute_rank_score(
    *,
    authority: float,
    relevance: float,
    impact_level: str,
    demotion: float = 1.0,
) -> float:
    impact = _IMPACT_WEIGHT.get(impact_level, 0.4)
    return round(authority * relevance * impact * demotion, 4)


def filter_and_rank(
    items: list[NewsItem],
    interests: UserNewsInterests,
    *,
    related_only: bool = False,
    limit: int = 20,
) -> list[ScoredNews]:
    """Apply three layers, sort by composite rank score, return top N."""
    scored: list[ScoredNews] = []
    for item in items:
        if layer1_blacklist_reject(item.title):
            continue
        authority = layer2_source_authority(item.source)
        demotion = layer1b_title_demotion(item.title)
        category, relevance = layer3_relevance(item, interests)
        if category is None or relevance <= 0:
            continue
        related = category in ("holding", "sector")
        if related_only and not related:
            continue
        rank = compute_rank_score(
            authority=authority,
            relevance=relevance,
            impact_level=item.impact_level,
            demotion=demotion,
        )
        scored.append(
            ScoredNews(
                item=item,
                related=related,
                category=category,
                rank_score=rank,
            )
        )
    scored.sort(key=lambda row: (row.rank_score, row.item.published_at), reverse=True)
    return scored[:limit]
