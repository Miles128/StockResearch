"""Sentiment / Xueqiu data provider tests."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from stockresearch.data.providers.market import (
    SentimentDataProvider,
    _fetch_xueqiu_hot_sync,
    _lookup_xueqiu_row,
)


def test_lookup_xueqiu_row_by_code() -> None:
    df = pd.DataFrame(
        {"股票代码": ["SH600519", "SZ000001"], "股票简称": ["贵州茅台", "平安银行"], "关注": [100, 50]}
    )
    row = _lookup_xueqiu_row(df, "SH600519", "贵州茅台")
    assert row is not None
    assert int(row["关注"]) == 100


@patch("stockresearch.data.providers.market.ak.stock_hot_follow_xq")
@patch("stockresearch.data.providers.market.ak.stock_hot_tweet_xq")
@patch("stockresearch.data.providers.market.ak.stock_hot_deal_xq")
@patch("stockresearch.data.providers.market.ak.stock_comment_em")
@patch("stockresearch.data.providers.market.ak.stock_comment_detail_scrd_desire_em")
@patch("stockresearch.data.providers.market.ak.stock_comment_detail_zhpj_lspf_em")
def test_fetch_xueqiu_hot_sync_uses_real_metrics(
    mock_score: MagicMock,
    mock_desire: MagicMock,
    mock_comment: MagicMock,
    mock_deal: MagicMock,
    mock_tweet: MagicMock,
    mock_follow: MagicMock,
) -> None:
    mock_score.return_value = pd.DataFrame({"交易日": ["2026-06-05"], "评分": [74.2]})
    mock_desire.return_value = pd.DataFrame(
        {"交易日期": ["2026-06-05"], "参与意愿": [45.74]}
    )
    mock_comment.return_value = pd.DataFrame(
        {"代码": ["600519"], "关注指数": [94.0]}
    )
    mock_deal.return_value = pd.DataFrame(
        {"股票代码": ["SH600519"], "股票简称": ["贵州茅台"], "关注": [128]}
    )
    mock_tweet.return_value = pd.DataFrame(
        {"股票代码": ["SH600519"], "股票简称": ["贵州茅台"], "关注": [101463]}
    )
    mock_follow.return_value = pd.DataFrame(
        {"股票代码": ["SH600519"], "股票简称": ["贵州茅台"], "关注": [3645293]}
    )

    result = _fetch_xueqiu_hot_sync("600519", "贵州茅台")

    assert result["available"] is True
    assert result["heat_score"] == 74
    assert result["post_count"] == 128
    assert result["follow_count"] == 3645293
    assert result["bull_ratio"] == 0.46
    assert "xueqiu" in str(result["source"])


@pytest.mark.asyncio
async def test_sentiment_provider_mock_mode() -> None:
    provider = SentimentDataProvider()
    hot = await provider.get_xueqiu_hot("600519", "贵州茅台")
    assert hot["available"] is True
    assert int(hot["post_count"]) > 0
