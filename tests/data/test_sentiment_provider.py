"""Sentiment / Xueqiu data provider tests."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from stockresearch.data.providers.market import (
    SentimentDataProvider,
    _fetch_xueqiu_hot_sync,
    _lookup_xueqiu_row,
)
from stockresearch.services.cache import clear_cache, get_cached


def test_lookup_xueqiu_row_by_code() -> None:
    df = pd.DataFrame(
        {
            "股票代码": ["SH600519", "SZ000001"],
            "股票简称": ["贵州茅台", "平安银行"],
            "关注": [100, 50],
        }
    )
    row = _lookup_xueqiu_row(df, "SH600519", "贵州茅台")
    assert row is not None
    assert int(row["关注"]) == 100


@patch("stockresearch.data.providers.market.sentiment.ak.stock_hot_follow_xq")
@patch("stockresearch.data.providers.market.sentiment.ak.stock_hot_tweet_xq")
@patch("stockresearch.data.providers.market.sentiment.ak.stock_hot_deal_xq")
@patch("stockresearch.data.providers.market.sentiment.ak.stock_comment_em")
@patch("stockresearch.data.providers.market.sentiment.ak.stock_comment_detail_scrd_desire_em")
@patch("stockresearch.data.providers.market.sentiment.ak.stock_comment_detail_zhpj_lspf_em")
def test_fetch_xueqiu_hot_sync_uses_fast_em_path(
    mock_score: MagicMock,
    mock_desire: MagicMock,
    mock_comment: MagicMock,
    mock_deal: MagicMock,
    mock_tweet: MagicMock,
    mock_follow: MagicMock,
) -> None:
    clear_cache()
    mock_score.return_value = pd.DataFrame({"交易日": ["2026-06-05"], "评分": [74.2]})
    mock_desire.return_value = pd.DataFrame({"交易日期": ["2026-06-05"], "参与意愿": [45.74]})

    result = _fetch_xueqiu_hot_sync("600519", "贵州茅台")

    assert result["available"] is True
    assert result["heat_score"] == 74
    assert result["bull_ratio"] == 0.46
    assert "em_score" in str(result["source"])
    # Slow full-market scrapes must not run on the hot path.
    mock_comment.assert_not_called()
    mock_deal.assert_not_called()
    mock_tweet.assert_not_called()
    mock_follow.assert_not_called()


@patch("stockresearch.data.providers.market.sentiment.ak.stock_comment_detail_scrd_desire_em")
@patch("stockresearch.data.providers.market.sentiment.ak.stock_comment_detail_zhpj_lspf_em")
def test_fetch_xueqiu_hot_enriches_from_warm_cache(
    mock_score: MagicMock,
    mock_desire: MagicMock,
) -> None:
    clear_cache()
    mock_score.return_value = pd.DataFrame({"交易日": ["2026-06-05"], "评分": [74.2]})
    mock_desire.return_value = pd.DataFrame({"交易日期": ["2026-06-05"], "参与意愿": [45.74]})
    get_cached(
        "xq_hot_deal",
        900.0,
        lambda: pd.DataFrame({"股票代码": ["SH600519"], "股票简称": ["贵州茅台"], "关注": [128]}),
    )
    get_cached(
        "xq_hot_follow",
        900.0,
        lambda: pd.DataFrame(
            {"股票代码": ["SH600519"], "股票简称": ["贵州茅台"], "关注": [3645293]}
        ),
    )

    result = _fetch_xueqiu_hot_sync("600519", "贵州茅台")
    assert result["available"] is True
    assert result["post_count"] == 128
    assert result["follow_count"] == 3645293
    assert "xueqiu_deal" in str(result["source"])


@pytest.mark.asyncio
async def test_sentiment_provider_returns_unavailable_when_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """网络不可用时，get_xueqiu_hot 应返回 available=False，不抛异常。"""
    from stockresearch.data.providers.market import sentiment as market_mod

    async def fake_run_sync_fetch(*args, **kwargs):  # type: ignore[no-untyped-def]
        return kwargs.get("fallback")

    monkeypatch.setattr(market_mod, "run_sync_fetch", fake_run_sync_fetch)

    provider = SentimentDataProvider()
    hot = await provider.get_xueqiu_hot("600519", "贵州茅台")
    assert hot["available"] is False
    assert hot["source"] == "unavailable"
