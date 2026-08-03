"""新闻管线按域过滤测试（内存 DB，不触网络/LLM）。"""

from datetime import datetime

from sqlalchemy.orm import Session

from stockresearch.agents.news.agent import get_news_for_user
from stockresearch.core.constants import IMPACT_MAJOR
from stockresearch.db.models import Holding, NewsItem, User


def _user_with_holding(db: Session) -> User:
    user = User(username="news-scope", password_hash="")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(
        Holding(
            user_id=user.id,
            symbol="600519",
            name="贵州茅台",
            cost_price=1800.0,
            quantity=10,
            sector="白酒",
        )
    )
    db.commit()
    return user


def _news(db: Session, *, hash_key: str, title: str, entities: list[str]) -> None:
    db.add(
        NewsItem(
            title=title,
            summary=title,
            source="财联社",
            sentiment="neutral",
            impact_level=IMPACT_MAJOR,
            entities=entities,
            content_hash=hash_key,
            published_at=datetime(2026, 8, 3, 10, 0),
        )
    )
    db.commit()


def _seed_three(db: Session) -> None:
    _news(db, hash_key="n-market", title="沪指收涨0.8% 两市成交活跃", entities=["market"])
    _news(db, hash_key="n-holding", title="贵州茅台二季度营收创新高", entities=["600519"])
    _news(db, hash_key="n-sector", title="白酒板块集体走强", entities=["白酒"])


async def test_market_scope_excludes_holding_and_sector_news(db_session: Session) -> None:
    user = _user_with_holding(db_session)
    _seed_three(db_session)

    items = await get_news_for_user(db_session, user.id, news_scope="market")

    assert [i.title for i in items] == ["沪指收涨0.8% 两市成交活跃"]
    assert all(not i.related_to_user for i in items)


async def test_industry_scope_keeps_only_matching_sector(db_session: Session) -> None:
    user = _user_with_holding(db_session)
    _seed_three(db_session)

    items = await get_news_for_user(db_session, user.id, news_scope="industry", industry="白酒")

    assert [i.title for i in items] == ["白酒板块集体走强"]


async def test_default_personalized_scope_ranks_holding_first(db_session: Session) -> None:
    user = _user_with_holding(db_session)
    _news(db_session, hash_key="p-market", title="沪指收涨0.8% 两市成交活跃", entities=["market"])
    _news(db_session, hash_key="p-holding", title="贵州茅台二季度营收创新高", entities=["600519"])

    items = await get_news_for_user(db_session, user.id)

    assert items[0].title == "贵州茅台二季度营收创新高"
    assert items[0].related_to_user
