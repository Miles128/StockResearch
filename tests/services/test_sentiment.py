"""Tests for unified sentiment service."""

import pytest

from stockresearch.services.sentiment import SentimentResult, SentimentService


@pytest.mark.asyncio
async def test_market_sentiment():
    result = await SentimentService().compute_market_sentiment()
    assert isinstance(result, SentimentResult)
    assert 0 <= result.score <= 100
    assert result.label in ("极度恐慌", "恐慌", "中性", "乐观", "极度乐观")
    assert len(result.drivers) > 0


@pytest.mark.asyncio
async def test_sector_sentiment():
    result = await SentimentService().compute_sector_sentiment("银行")
    assert isinstance(result, SentimentResult)
    assert 0 <= result.score <= 100


@pytest.mark.asyncio
async def test_stock_sentiment():
    result = await SentimentService().compute_stock_sentiment("600519", "贵州茅台")
    assert isinstance(result, SentimentResult)
    assert 0 <= result.score <= 100
