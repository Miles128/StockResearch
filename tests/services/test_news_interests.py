"""News interest filtering tests."""

from datetime import UTC, datetime

from stockresearch.core.constants import IMPACT_MAJOR, IMPACT_NORMAL
from stockresearch.data.pipeline.news import NewsPipeline
from stockresearch.db.models import NewsItem, User, UserSectorPreference
from stockresearch.services.auth import hash_password
from stockresearch.services.news_interests import (
    UserNewsInterests,
    classify_news,
    load_user_news_interests,
    purge_irrelevant_news,
    save_user_sectors,
)


def test_unrelated_news_without_entities_is_excluded() -> None:
    item = NewsItem(
        title="某娱乐公司跨界并购",
        content="",
        summary="与公司主业无关",
        source="test",
        sentiment="neutral",
        impact_level=IMPACT_NORMAL,
        entities=[],
        content_hash="abc0",
        published_at=datetime.now(UTC),
    )
    interests = UserNewsInterests(symbols=("600519",), names=("贵州茅台",), sectors=frozenset({"白酒"}))
    assert classify_news(item, interests) is None


def test_classify_market_news() -> None:
    item = NewsItem(
        title="央行开展逆回购操作",
        content="",
        summary="流动性保持合理充裕",
        source="test",
        sentiment="neutral",
        impact_level=IMPACT_MAJOR,
        entities=[],
        content_hash="abc1",
        published_at=datetime.now(UTC),
    )
    interests = UserNewsInterests(symbols=(), names=(), sectors=frozenset())
    assert classify_news(item, interests) == "market"


def test_classify_sector_news(db_session: object) -> None:
    user = User(username="newsuser", password_hash=hash_password("password1"))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    save_user_sectors(db_session, user.id, ["白酒"])

    item = NewsItem(
        title="白酒板块今日走强",
        content="",
        summary="龙头白酒股上涨",
        source="test",
        sentiment="bullish",
        impact_level=IMPACT_NORMAL,
        entities=["白酒"],
        content_hash="abc2",
        published_at=datetime.now(UTC),
    )
    interests = load_user_news_interests(db_session, user.id)
    assert classify_news(item, interests) == "sector"


def test_list_feed_excludes_unrelated(db_session: object) -> None:
    user = User(username="feeduser", password_hash=hash_password("password1"))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserSectorPreference(user_id=user.id, sector="半导体"))
    db_session.add(
        NewsItem(
            title="某娱乐公司跨界并购",
            content="",
            summary="与公司主业无关",
            source="test",
            sentiment="neutral",
            impact_level=IMPACT_NORMAL,
            entities=["传媒"],
            content_hash="abc3",
            published_at=datetime.now(UTC),
        )
    )
    db_session.add(
        NewsItem(
            title="半导体设备国产化加速",
            content="",
            summary="板块受关注",
            source="test",
            sentiment="bullish",
            impact_level=IMPACT_NORMAL,
            entities=["半导体"],
            content_hash="abc4",
            published_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    interests = load_user_news_interests(db_session, user.id)
    rows = NewsPipeline().list_feed(db_session, interests, limit=10)
    titles = [item.title for item, _, _ in rows]
    assert "半导体设备国产化加速" in titles
    assert "某娱乐公司跨界并购" not in titles


def test_purge_irrelevant_news(db_session: object) -> None:
    user = User(username="purgeuser", password_hash=hash_password("password1"))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(UserSectorPreference(user_id=user.id, sector="半导体"))
    db_session.add(
        NewsItem(
            title="某娱乐公司跨界并购",
            content="",
            summary="与公司主业无关",
            source="test",
            sentiment="neutral",
            impact_level=IMPACT_NORMAL,
            entities=["传媒"],
            content_hash="purge1",
            published_at=datetime.now(UTC),
        )
    )
    db_session.add(
        NewsItem(
            title="半导体设备国产化加速",
            content="",
            summary="板块受关注",
            source="test",
            sentiment="bullish",
            impact_level=IMPACT_NORMAL,
            entities=["半导体"],
            content_hash="purge2",
            published_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    interests = load_user_news_interests(db_session, user.id)
    deleted = purge_irrelevant_news(db_session, interests)
    assert deleted == 1
    remaining = [row.title for row in db_session.query(NewsItem).all()]
    assert remaining == ["半导体设备国产化加速"]
