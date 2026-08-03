"""News agent — 3-layer filter + 3s SLA feed path (no LLM)."""

import asyncio
import logging
import time

from sqlalchemy.orm import Session

from stockresearch.agents.news.filter import NEWS_FEED_SLA_SEC, filter_and_rank
from stockresearch.core.exceptions import StockResearchError
from stockresearch.core.schemas import NewsItemOut
from stockresearch.db.models import NewsItem
from stockresearch.services.news_interests import (
    UserNewsInterests,
    load_user_news_interests,
)

logger = logging.getLogger(__name__)


class NewsFeedTimeoutError(StockResearchError):
    """News feed exceeded SLA."""


# 空兴趣画像：market 域不做任何持仓/自选/板块加权，仅 market 类新闻能幸存 classify_news
_EMPTY_INTERESTS = UserNewsInterests(symbols=(), names=(), sectors=frozenset())


def _interests_for_scope(
    db: Session,
    user_id: int,
    news_scope: str,
    industry: str | None,
) -> tuple[UserNewsInterests, bool]:
    """按新闻域构造兴趣画像；返回 (interests, 是否强制 related_only)。"""
    if news_scope == "market":
        return _EMPTY_INTERESTS, False
    if news_scope == "industry" and industry:
        # 行业域：仅板块匹配，不做个股兴趣加权；强制 related_only 过滤掉 market 类
        return UserNewsInterests(symbols=(), names=(), sectors=frozenset({industry})), True
    return load_user_news_interests(db, user_id), False


async def _fetch_feed_rows(
    db: Session,
    user_id: int,
    related_only: bool,
    limit: int,
    news_scope: str = "personalized",
    industry: str | None = None,
) -> list[tuple[NewsItem, bool, str]]:
    interests, force_related = _interests_for_scope(db, user_id, news_scope, industry)
    candidates = db.query(NewsItem).order_by(NewsItem.published_at.desc()).limit(limit * 8).all()
    ranked = filter_and_rank(
        candidates,
        interests,
        related_only=related_only or force_related,
        limit=limit,
    )
    return [(row.item, row.related, row.category) for row in ranked]


async def get_news_for_user(
    db: Session,
    user_id: int,
    related_only: bool = False,
    limit: int = 10,
    *,
    news_scope: str = "personalized",
    industry: str | None = None,
) -> list[NewsItemOut]:
    """Return ranked news cards within PRD 3-second SLA (DB + rules only).

    news_scope: personalized（现状）/ market（全市场，不加权）/ industry（按板块过滤）。
    """
    started = time.perf_counter()
    try:
        rows = await asyncio.wait_for(
            _fetch_feed_rows(db, user_id, related_only, limit, news_scope, industry),
            timeout=NEWS_FEED_SLA_SEC,
        )
    except TimeoutError as exc:
        elapsed = time.perf_counter() - started
        logger.warning("news feed SLA exceeded user=%s elapsed=%.2fs", user_id, elapsed)
        raise NewsFeedTimeoutError(
            f"新闻流响应超时（>{NEWS_FEED_SLA_SEC:.0f}s），请稍后重试"
        ) from exc

    elapsed = time.perf_counter() - started
    logger.info(
        "news feed user=%s items=%d elapsed=%.3fs sla=%.1fs",
        user_id,
        len(rows),
        elapsed,
        NEWS_FEED_SLA_SEC,
    )
    return [
        NewsItemOut(
            id=item.id,
            title=item.title,
            summary=item.summary,
            source=item.source,
            sentiment=item.sentiment,
            impact_level=item.impact_level,
            entities=item.entities,
            related_to_user=related,
            category=category,
            published_at=item.published_at,
        )
        for item, related, category in rows
    ]
