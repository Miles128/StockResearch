"""News three-layer filter tests."""

from datetime import UTC, datetime

from stockresearch.agents.news.filter import (
    filter_and_rank,
    layer1_blacklist_reject,
    layer1b_title_demotion,
    layer2_source_authority,
    layer3_relevance,
)
from stockresearch.db.models import NewsItem
from stockresearch.services.news_interests import UserNewsInterests


def _item(title: str, source: str, entities: list[str] | None = None) -> NewsItem:
    return NewsItem(
        title=title,
        content=title,
        summary=title,
        source=source,
        sentiment="neutral",
        impact_level="normal",
        entities=entities or [],
        content_hash=f"{source}:{title}",
        published_at=datetime.now(UTC),
    )


def test_layer1_rejects_clickbait() -> None:
    assert layer1_blacklist_reject("某股暴涨惊爆全网") is True
    assert layer1_blacklist_reject("央行发布政策") is False
    assert layer1_blacklist_reject("赶紧买这只妖股") is True
    assert layer1_blacklist_reject("揭秘内幕：某股或将上涨") is True


def test_layer1b_demotion_stacks_to_lowest_multiplier() -> None:
    assert layer1b_title_demotion("贵州茅台发布年报") == 1.0
    assert layer1b_title_demotion("行业解读盘点") == 0.70
    assert layer1b_title_demotion("行业前瞻展望") == 0.88


def test_demotion_lowers_rank_vs_clean_title() -> None:
    interests = UserNewsInterests(
        symbols=["600519"],
        names=["贵州茅台"],
        sectors=["白酒"],
    )
    clean = _item("贵州茅台发布年报", "证券时报", ["600519"])
    noisy = _item("十大解读：贵州茅台发布年报", "证券时报", ["600519"])
    clean_rank = filter_and_rank([clean], interests, limit=1)[0].rank_score
    noisy_rank = filter_and_rank([noisy], interests, limit=1)[0].rank_score
    assert noisy_rank < clean_rank


def test_layer2_authority_prefers_official() -> None:
    assert layer2_source_authority("财联社电报") > layer2_source_authority("未知自媒体")


def test_layer3_holding_beats_market() -> None:
    interests = UserNewsInterests(
        symbols=["600519"],
        names=["贵州茅台"],
        sectors=["白酒"],
    )
    holding = _item("贵州茅台发布年报", "证券时报", ["600519"])
    market = _item("A股整体震荡", "财联社", ["market"])
    _, holding_w = layer3_relevance(holding, interests)
    _, market_w = layer3_relevance(market, interests)
    assert holding_w > market_w


def test_filter_and_rank_orders_by_composite_score() -> None:
    interests = UserNewsInterests(
        symbols=["600519"],
        names=["贵州茅台"],
        sectors=["白酒"],
    )
    items = [
        _item("大盘综述", "财联社", ["market"]),
        _item("贵州茅台业绩超预期", "证券时报", ["600519"]),
    ]
    ranked = filter_and_rank(items, interests, limit=2)
    assert ranked[0].category == "holding"
    assert ranked[0].rank_score >= ranked[1].rank_score
