"""News agent — 3-layer filter + 3s SLA feed path (no LLM)."""

import asyncio
import logging
import time

from sqlalchemy.orm import Session

from invesbao.agents.news.filter import NEWS_FEED_SLA_SEC, filter_and_rank
from invesbao.core.exceptions import InvesBaoError
from invesbao.core.schemas import NewsItemOut
from invesbao.db.models import NewsItem
from invesbao.services.news_interests import load_user_news_interests

logger = logging.getLogger(__name__)


class NewsFeedTimeoutError(InvesBaoError):
    """News feed exceeded SLA."""


async def _fetch_feed_rows(
    db: Session,
    user_id: int,
    related_only: bool,
    limit: int,
) -> list[tuple[NewsItem, bool, str]]:
    interests = load_user_news_interests(db, user_id)
    candidates = (
        db.query(NewsItem)
        .order_by(NewsItem.published_at.desc())
        .limit(limit * 8)
        .all()
    )
    ranked = filter_and_rank(
        candidates,
        interests,
        related_only=related_only,
        limit=limit,
    )
    return [(row.item, row.related, row.category) for row in ranked]


async def get_news_for_user(
    db: Session,
    user_id: int,
    related_only: bool = False,
    limit: int = 10,
) -> list[NewsItemOut]:
    """Return ranked news cards within PRD 3-second SLA (DB + rules only)."""
    started = time.perf_counter()
    try:
        rows = await asyncio.wait_for(
            _fetch_feed_rows(db, user_id, related_only, limit),
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
