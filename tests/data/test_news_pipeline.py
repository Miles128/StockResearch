"""News pipeline tests."""

from invesbao.core.constants import IMPACT_NOISE, SENTIMENT_BULLISH
from invesbao.data.pipeline.news import (
    content_hash,
    extract_entities,
    score_impact,
    score_sentiment,
)


def test_extract_entities_symbol_and_industry() -> None:
    entities = extract_entities("宁德时代新能源板块受关注 300750")
    assert "300750" in entities
    assert "新能源" in entities


def test_sentiment_bullish() -> None:
    assert score_sentiment("公司净利润大幅增长，利好频出") == SENTIMENT_BULLISH


def test_impact_noise_for_clickbait() -> None:
    assert score_impact("某股暴涨惊爆全网", []) == IMPACT_NOISE


def test_content_hash_stable() -> None:
    assert content_hash("title", "src") == content_hash("title", "src")
    assert content_hash("a", "src") != content_hash("b", "src")
