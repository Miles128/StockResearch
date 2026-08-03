"""Unified sentiment service — market / sector / stock."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from stockresearch.data.providers.market import SentimentDataProvider
from stockresearch.data.providers.market_overview import MarketOverviewProvider
from stockresearch.data.providers.news import NewsProvider
from stockresearch.data.providers.sector import SectorDataProvider
from stockresearch.utils.format import arrow_for_change, news_score_to_label

logger = logging.getLogger(__name__)


@dataclass
class SentimentDriver:
    label: str
    value: str
    impact: str  # positive / negative / neutral


@dataclass
class SentimentResult:
    score: int  # 0-100
    label: str  # 极度恐慌/恐慌/中性/乐观/极度乐观
    drivers: list[SentimentDriver] = field(default_factory=list)
    source: str = "composite"


def _score_to_label(score: int) -> str:
    if score <= 20:
        return "极度恐慌"
    if score <= 40:
        return "恐慌"
    if score <= 60:
        return "中性"
    if score <= 80:
        return "乐观"
    return "极度乐观"


def _clamp_score(score: float) -> int:
    return max(0, min(100, round(score)))


class SentimentService:
    """Unified sentiment calculator for market / sector / stock."""

    async def compute_market_sentiment(self) -> SentimentResult:
        """从指数涨跌幅、涨跌家数、北向资金、市场新闻情感 计算 0-100 情绪指数。"""
        overview = await MarketOverviewProvider().get_overview()
        drivers: list[SentimentDriver] = []
        score = 50.0  # 基准 50

        # 1. 指数综合涨跌幅 (30%)
        if overview.indices:
            avg_change = sum(idx.change_pct for idx in overview.indices) / len(overview.indices)
            index_score = max(-20, min(20, avg_change * 4))  # -20 ~ +20
            score += index_score * 0.75  # weight 30% → *1.5 → *0.75 to get 0-30 range
            arrow = arrow_for_change(avg_change)
            drivers.append(
                SentimentDriver(
                    label="主要指数",
                    value=f"{arrow} {avg_change:+.2f}%",
                    impact="positive"
                    if avg_change > 0.3
                    else "negative"
                    if avg_change < -0.3
                    else "neutral",
                )
            )

        # 2. 涨跌家数比 (30%)
        adv = overview.advancers
        dec = overview.decliners
        if adv is not None and dec is not None and (adv + dec) > 0:
            bull_ratio = adv / (adv + dec)
            breadth_score = (bull_ratio - 0.5) * 30  # -15 ~ +15
            score += breadth_score
            drivers.append(
                SentimentDriver(
                    label="涨跌家数",
                    value=f"{adv}涨 / {dec}跌",
                    impact="positive"
                    if bull_ratio > 0.55
                    else "negative"
                    if bull_ratio < 0.45
                    else "neutral",
                )
            )

        # 3. 北向资金 (15%)
        north = overview.northbound_net_yi
        if north is not None:
            north_score = max(-10, min(10, north * 2))  # -10 ~ +10
            score += north_score
            direction = "净流入" if north > 0 else "净流出"
            drivers.append(
                SentimentDriver(
                    label="北向资金",
                    value=f"{direction} {abs(north):.1f}亿",
                    impact="positive" if north > 0 else "negative",
                )
            )

        # 4. 市场新闻情感 (25%)
        try:
            news_provider = NewsProvider()
            news_items = await news_provider.fetch_latest(limit=20)
            titles = [item.title for item in news_items]
            news_score = SentimentDataProvider().score_titles(titles)
            # news_score: -1 ~ +1 → -12.5 ~ +12.5
            score += news_score * 12.5
            label = news_score_to_label(news_score)
            drivers.append(
                SentimentDriver(
                    label="新闻情感",
                    value=f"{len(titles)}条新闻 {label}",
                    impact="positive"
                    if news_score > 0.2
                    else "negative"
                    if news_score < -0.2
                    else "neutral",
                )
            )
        except Exception as exc:
            logger.warning("Market news sentiment failed: %s", exc)

        final_score = _clamp_score(score)
        return SentimentResult(
            score=final_score,
            label=_score_to_label(final_score),
            drivers=drivers,
            source="composite",
        )

    async def compute_sector_sentiment(self, sector_name: str) -> SentimentResult:
        """从板块涨跌幅 + 板块新闻情感 计算行业情绪。"""
        drivers: list[SentimentDriver] = []
        score = 50.0

        # 1. 板块涨跌幅
        try:
            boards = await SectorDataProvider().fetch_industry_boards()
            target = next(
                (b for b in boards if sector_name in b.name or b.name in sector_name), None
            )
            if target:
                change = target.change_pct
                score += max(-20, min(20, change * 4))
                arrow = arrow_for_change(change)
                drivers.append(
                    SentimentDriver(
                        label="板块涨跌",
                        value=f"{arrow} {change:+.2f}%",
                        impact="positive"
                        if change > 0.5
                        else "negative"
                        if change < -0.5
                        else "neutral",
                    )
                )
        except Exception as exc:
            logger.warning("Sector data for sentiment failed: %s", exc)

        # 2. 板块新闻情感
        try:
            news_provider = NewsProvider()
            news_items = await news_provider.fetch_for_user([], frozenset({sector_name}), limit=15)
            titles = [item.title for item in news_items]
            news_score = SentimentDataProvider().score_titles(titles)
            score += news_score * 15
            label = news_score_to_label(news_score)
            drivers.append(
                SentimentDriver(
                    label="板块新闻",
                    value=f"{len(titles)}条 {label}",
                    impact="positive"
                    if news_score > 0.2
                    else "negative"
                    if news_score < -0.2
                    else "neutral",
                )
            )
        except Exception as exc:
            logger.warning("Sector news sentiment failed: %s", exc)

        final_score = _clamp_score(score)
        return SentimentResult(
            score=final_score,
            label=_score_to_label(final_score),
            drivers=drivers,
            source="sector",
        )

    async def compute_stock_sentiment(self, symbol: str, name: str = "") -> SentimentResult:
        """从雪球热度 + 个股新闻情感 计算个股情绪。复用 SentimentDataProvider。"""
        provider = SentimentDataProvider()
        drivers: list[SentimentDriver] = []
        score = 50.0

        # 1. 雪球热度 + 多空比
        try:
            hot = await provider.get_xueqiu_hot(symbol, name)
            bull_ratio = float(hot.get("bull_ratio", 0.5))
            heat_score = int(hot.get("heat_score", 0))
            post_count = int(hot.get("post_count", 0))
            available = bool(hot.get("available", True))
            if available:
                score += (bull_ratio - 0.5) * 30  # -15 ~ +15
                drivers.append(
                    SentimentDriver(
                        label="雪球多空比",
                        value=f"{bull_ratio:.0%}看多 · 热度{heat_score} · {post_count}帖",
                        impact="positive"
                        if bull_ratio > 0.55
                        else "negative"
                        if bull_ratio < 0.45
                        else "neutral",
                    )
                )
        except Exception as exc:
            logger.warning("Xueqiu hot for %s failed: %s", symbol, exc)

        # 2. 个股新闻情感
        try:
            news = await provider.get_symbol_news(symbol, name, limit=12)
            titles = [item["title"] for item in news]
            news_score = provider.score_titles(titles)
            score += news_score * 15  # -15 ~ +15
            label = news_score_to_label(news_score)
            drivers.append(
                SentimentDriver(
                    label="个股新闻",
                    value=f"{len(titles)}条 {label}",
                    impact="positive"
                    if news_score > 0.2
                    else "negative"
                    if news_score < -0.2
                    else "neutral",
                )
            )
        except Exception as exc:
            logger.warning("Stock news sentiment for %s failed: %s", symbol, exc)

        final_score = _clamp_score(score)
        return SentimentResult(
            score=final_score,
            label=_score_to_label(final_score),
            drivers=drivers,
            source="stock",
        )
