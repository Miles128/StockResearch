"""Sentiment provider — EM stock comment + Xueqiu warm-cache heat."""

import logging
from typing import Any

import akshare as ak  # type: ignore[import-untyped]

from stockresearch.data.providers.base import run_sync_fetch
from stockresearch.data.providers.market.common import (
    _DATA_TIMEOUT_SEC,
    _NEGATIVE_NEWS,
    _POSITIVE_NEWS,
    _use_mock_market_data,
)
from stockresearch.services.cache import peek_cached
from stockresearch.utils.symbols import resolve_name

logger = logging.getLogger(__name__)


def _xueqiu_market_code(symbol: str) -> str:
    if symbol.startswith(("4", "8")):
        return f"BJ{symbol}"
    if symbol.startswith("6"):
        return f"SH{symbol}"
    return f"SZ{symbol}"


def _lookup_xueqiu_row(df: Any, code: str, name: str) -> Any | None:
    if df is None or df.empty or "股票代码" not in df.columns:
        return None
    matches = df[df["股票代码"].astype(str) == code]
    if matches.empty and name:
        matches = df[df["股票简称"].astype(str) == name]
    if matches.empty:
        return None
    return matches.iloc[0]


def _fetch_xueqiu_hot_sync(symbol: str, name: str) -> dict[str, float | int | str | bool]:
    """Eastmoney stock-comment APIs first; Xueqiu hot lists only from warm cache.

    Full-market scrapes (stock_comment_em / stock_hot_*_xq) take 20–60s and would
    trip the async timeout, so they are never fetched on the hot path.
    """
    result: dict[str, float | int | str | bool] = {
        "heat_score": 0,
        "post_count": 0,
        "bull_ratio": 0.5,
        "follow_count": 0,
        "attention_index": 0.0,
        "source": "unavailable",
        "available": False,
    }
    sources: list[str] = []
    code = _xueqiu_market_code(symbol)

    try:
        score_df = ak.stock_comment_detail_zhpj_lspf_em(symbol=symbol)
        if not score_df.empty:
            latest_score = float(score_df.iloc[-1]["评分"])
            result["heat_score"] = min(100, max(1, round(latest_score)))
            sources.append("em_score")
    except Exception as exc:
        logger.warning("EM sentiment score failed for %s: %s", symbol, exc)

    try:
        desire_df = ak.stock_comment_detail_scrd_desire_em(symbol=symbol)
        if not desire_df.empty:
            desire = float(desire_df.iloc[-1]["参与意愿"])
            result["bull_ratio"] = round(max(0.15, min(0.85, desire / 100)), 2)
            sources.append("em_desire")
    except Exception as exc:
        logger.warning("EM participation desire failed for %s: %s", symbol, exc)

    # Warm-cache enrichments only — never block on full-market scrapes.
    df_deal = peek_cached("xq_hot_deal", 900.0)
    if df_deal is not None:
        try:
            deal_row = _lookup_xueqiu_row(df_deal, code, name)
            if deal_row is not None:
                result["post_count"] = int(float(deal_row["关注"]))
                rank = int(deal_row.name) + 1
                xq_heat = min(100, max(5, round(100 - (rank / max(len(df_deal), 1)) * 95)))
                if int(result["heat_score"]) == 0:
                    result["heat_score"] = xq_heat
                sources.append("xueqiu_deal")
        except Exception as exc:
            logger.warning("Xueqiu deal hot (cache) failed for %s: %s", symbol, exc)

    df_tweet = peek_cached("xq_hot_tweet", 900.0)
    if df_tweet is not None:
        try:
            tweet_row = _lookup_xueqiu_row(df_tweet, code, name)
            if tweet_row is not None:
                result["tweet_heat"] = int(float(tweet_row["关注"]))
                sources.append("xueqiu_tweet")
        except Exception as exc:
            logger.warning("Xueqiu tweet hot (cache) failed for %s: %s", symbol, exc)

    df_follow = peek_cached("xq_hot_follow", 900.0)
    if df_follow is not None:
        try:
            follow_row = _lookup_xueqiu_row(df_follow, code, name)
            if follow_row is not None:
                result["follow_count"] = int(float(follow_row["关注"]))
                sources.append("xueqiu_follow")
        except Exception as exc:
            logger.warning("Xueqiu follow hot (cache) failed for %s: %s", symbol, exc)

    if sources:
        result["source"] = "+".join(sources)
        result["available"] = True
        # Honest labeling when Xueqiu warm cache is cold — EM stock-comment only.
        has_xq = any(s.startswith("xueqiu_") for s in sources)
        if not has_xq and any(s.startswith("em_") for s in sources):
            result["coverage_note"] = "仅东财个股情绪（雪球热榜暖缓存未命中）"
            result["partial"] = True
    return result


class SentimentDataProvider:
    async def get_symbol_news(self, symbol: str, name: str, limit: int = 8) -> list[dict[str, str]]:
        if _use_mock_market_data():
            return [{"title": f"{name or symbol} 行业政策讨论", "source": "mock"}]
        from stockresearch.data.providers.news import NewsProvider

        provider = NewsProvider()
        queries: list[str] = []
        for query in (name, symbol):
            if query and query not in queries:
                queries.append(query)
        items = []
        for query in queries:
            batch = await provider.fetch_symbol_news(query, symbol=symbol, limit=limit, enrich=True)
            if batch:
                items = batch
                break
        return [
            {
                "title": item.title,
                "source": item.source,
                "url": item.url,
                "content": item.content[:200],
            }
            for item in items[:limit]
        ]

    def score_titles(self, titles: list[str]) -> float:
        if not titles:
            return 0.0
        score = 0.0
        for title in titles:
            if any(kw in title for kw in _POSITIVE_NEWS):
                score += 1.0
            if any(kw in title for kw in _NEGATIVE_NEWS):
                score -= 1.0
        return max(-1.0, min(1.0, score / max(len(titles), 1)))

    async def get_xueqiu_hot(
        self, symbol: str, name: str = ""
    ) -> dict[str, float | int | str | bool]:
        if _use_mock_market_data():
            return {
                "bull_ratio": 0.55,
                "heat_score": 42,
                "post_count": 120,
                "available": True,
                "source": "mock",
            }
        result = await run_sync_fetch(
            f"xueqiu hot {symbol}",
            lambda: _fetch_xueqiu_hot_sync(symbol, name or resolve_name(symbol)),
            timeout=_DATA_TIMEOUT_SEC * 3,
            fallback={
                "heat_score": 0,
                "post_count": 0,
                "bull_ratio": 0.5,
                "follow_count": 0,
                "attention_index": 0.0,
                "source": "unavailable",
                "available": False,
            },
        )
        assert result is not None
        return result

    async def get_news_sentiment_score(self, symbol: str, name: str = "") -> float:
        news = await self.get_symbol_news(symbol, name)
        return self.score_titles([item["title"] for item in news])
