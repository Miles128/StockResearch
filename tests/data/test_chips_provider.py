"""Chips and sentiment provider tests."""

import pytest

from stockresearch.core.config import get_settings
from stockresearch.data.providers.market import ChipsDataProvider, SentimentDataProvider


@pytest.mark.asyncio
async def test_chips_provider_mock_mode() -> None:
    settings = get_settings()
    assert settings.use_mock_market_data
    provider = ChipsDataProvider()
    dragon = await provider.get_dragon_tiger("600519")
    fund = await provider.get_fund_flow("600519")
    northbound = await provider.get_northbound_flow("600519")
    margin = await provider.get_margin_trading("600519")
    holders = await provider.get_holder_count("600519")
    lockup = await provider.get_lockup("600519")
    assert dragon["source"] == "mock"
    assert fund["source"] == "mock"
    assert northbound["source"] == "mock"
    assert margin["source"] == "mock"
    assert holders["source"] == "mock"
    assert lockup["source"] == "mock"


@pytest.mark.asyncio
async def test_sentiment_provider_mock_news() -> None:
    provider = SentimentDataProvider()
    news = await provider.get_symbol_news("600519", "贵州茅台")
    score = provider.score_titles([item["title"] for item in news])
    hot = await provider.get_xueqiu_hot("600519", "贵州茅台")
    assert news
    assert -1.0 <= score <= 1.0
    assert 0.0 < float(hot["bull_ratio"]) < 1.0
