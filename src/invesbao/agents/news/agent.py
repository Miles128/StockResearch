"""News agent wrapper."""

from sqlalchemy.orm import Session

from invesbao.core.schemas import NewsItemOut
from invesbao.data.pipeline.news import NewsPipeline
from invesbao.services.news_interests import load_user_news_interests


async def get_news_for_user(
    db: Session,
    user_id: int,
    related_only: bool = False,
    limit: int = 10,
) -> list[NewsItemOut]:
    interests = load_user_news_interests(db, user_id)
    pipeline = NewsPipeline()
    rows = pipeline.list_feed(db, interests, related_only=related_only, limit=limit)
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
