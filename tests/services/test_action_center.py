"""Tests for Action Center market-level signals."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stockresearch.core.schemas import IndexQuoteOut, MarketOverviewOut
from stockresearch.db.models import Holding, User
from stockresearch.services.action_center import (
    _INDEX_PLUNGE_PCT,
    _INDEX_SURGE_PCT,
    _NORTHBOUND_LARGE_INFLOW,
    _NORTHBOUND_LARGE_OUTFLOW,
    _collect_market_signals,
    generate_daily_actions,
)
from stockresearch.services.sentiment import SentimentResult


@pytest.fixture
def user(db_session):
    u = User(username=f"ac-{uuid.uuid4().hex[:8]}", password_hash="x")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _make_overview(
    *,
    index_change: float = 0.5,
    northbound: float | None = 10.0,
    advancers: int | None = 2500,
    decliners: int | None = 2000,
) -> MarketOverviewOut:
    return MarketOverviewOut(
        indices=[
            IndexQuoteOut(name="上证指数", symbol="000001", price=3200.0, change_pct=index_change),
        ],
        northbound_net_yi=northbound,
        advancers=advancers,
        decliners=decliners,
        source="test",
        updated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_index_surge_signal():
    """指数大涨 >= +2% 触发 market 信号。"""
    overview = _make_overview(index_change=_INDEX_SURGE_PCT)
    with patch(
        "stockresearch.services.action_center.MarketOverviewProvider"
    ) as provider_cls, patch(
        "stockresearch.services.sentiment.SentimentService.compute_market_sentiment",
        new_callable=AsyncMock,
        return_value=SentimentResult(score=50, label="中性", drivers=[], source="composite"),
    ):
        provider_cls.return_value.get_overview = AsyncMock(return_value=overview)
        signals = await _collect_market_signals()

    surge_signals = [s for s in signals if "市场走强" in s.title]
    assert len(surge_signals) == 1
    assert surge_signals[0].type == "market"
    assert surge_signals[0].action_target == "market"
    assert surge_signals[0].severity == "info"


@pytest.mark.asyncio
async def test_index_plunge_signal():
    """指数大跌 <= -2% 触发 warning 信号。"""
    overview = _make_overview(index_change=_INDEX_PLUNGE_PCT)
    with patch(
        "stockresearch.services.action_center.MarketOverviewProvider"
    ) as provider_cls, patch(
        "stockresearch.services.sentiment.SentimentService.compute_market_sentiment",
        new_callable=AsyncMock,
        return_value=SentimentResult(score=50, label="中性", drivers=[], source="composite"),
    ):
        provider_cls.return_value.get_overview = AsyncMock(return_value=overview)
        signals = await _collect_market_signals()

    plunge_signals = [s for s in signals if "市场走弱" in s.title]
    assert len(plunge_signals) == 1
    assert plunge_signals[0].severity == "warning"


@pytest.mark.asyncio
async def test_breadth_extreme_bull():
    """普涨：上涨家数占比 >= 70% 触发信号。"""
    overview = _make_overview(advancers=3500, decliners=1000)
    with patch(
        "stockresearch.services.action_center.MarketOverviewProvider"
    ) as provider_cls, patch(
        "stockresearch.services.sentiment.SentimentService.compute_market_sentiment",
        new_callable=AsyncMock,
        return_value=SentimentResult(score=50, label="中性", drivers=[], source="composite"),
    ):
        provider_cls.return_value.get_overview = AsyncMock(return_value=overview)
        signals = await _collect_market_signals()

    bull_signals = [s for s in signals if "普涨" in s.title]
    assert len(bull_signals) == 1
    assert bull_signals[0].severity == "info"


@pytest.mark.asyncio
async def test_breadth_extreme_bear():
    """普跌：上涨家数占比 <= 30% 触发 warning 信号。"""
    overview = _make_overview(advancers=1000, decliners=3500)
    with patch(
        "stockresearch.services.action_center.MarketOverviewProvider"
    ) as provider_cls, patch(
        "stockresearch.services.sentiment.SentimentService.compute_market_sentiment",
        new_callable=AsyncMock,
        return_value=SentimentResult(score=50, label="中性", drivers=[], source="composite"),
    ):
        provider_cls.return_value.get_overview = AsyncMock(return_value=overview)
        signals = await _collect_market_signals()

    bear_signals = [s for s in signals if "普跌" in s.title]
    assert len(bear_signals) == 1
    assert bear_signals[0].severity == "warning"


@pytest.mark.asyncio
async def test_northbound_large_outflow():
    """北向大幅净流出 <= -50亿 触发 warning 信号。"""
    overview = _make_overview(northbound=_NORTHBOUND_LARGE_OUTFLOW)
    with patch(
        "stockresearch.services.action_center.MarketOverviewProvider"
    ) as provider_cls, patch(
        "stockresearch.services.sentiment.SentimentService.compute_market_sentiment",
        new_callable=AsyncMock,
        return_value=SentimentResult(score=50, label="中性", drivers=[], source="composite"),
    ):
        provider_cls.return_value.get_overview = AsyncMock(return_value=overview)
        signals = await _collect_market_signals()

    outflow = [s for s in signals if "净流出" in s.title]
    assert len(outflow) == 1
    assert outflow[0].severity == "warning"


@pytest.mark.asyncio
async def test_northbound_large_inflow():
    """北向大幅净流入 >= +80亿 触发 info 信号。"""
    overview = _make_overview(northbound=_NORTHBOUND_LARGE_INFLOW)
    with patch(
        "stockresearch.services.action_center.MarketOverviewProvider"
    ) as provider_cls, patch(
        "stockresearch.services.sentiment.SentimentService.compute_market_sentiment",
        new_callable=AsyncMock,
        return_value=SentimentResult(score=50, label="中性", drivers=[], source="composite"),
    ):
        provider_cls.return_value.get_overview = AsyncMock(return_value=overview)
        signals = await _collect_market_signals()

    inflow = [s for s in signals if "净流入" in s.title]
    assert len(inflow) == 1
    assert inflow[0].severity == "info"


@pytest.mark.asyncio
async def test_sentiment_extreme_fear():
    """市场情绪极度恐慌 (score <= 20) 触发 warning 信号。"""
    overview = _make_overview()
    fear_result = SentimentResult(score=15, label="极度恐慌", drivers=[], source="composite")
    with patch(
        "stockresearch.services.action_center.MarketOverviewProvider"
    ) as provider_cls, patch(
        "stockresearch.services.sentiment.SentimentService.compute_market_sentiment",
        new_callable=AsyncMock,
        return_value=fear_result,
    ):
        provider_cls.return_value.get_overview = AsyncMock(return_value=overview)
        signals = await _collect_market_signals()

    fear_signals = [s for s in signals if "极度恐慌" in s.title]
    assert len(fear_signals) == 1
    assert fear_signals[0].severity == "warning"


@pytest.mark.asyncio
async def test_sentiment_extreme_greed():
    """市场情绪极度乐观 (score >= 80) 触发 info 信号。"""
    overview = _make_overview()
    greed_result = SentimentResult(score=85, label="极度乐观", drivers=[], source="composite")
    with patch(
        "stockresearch.services.action_center.MarketOverviewProvider"
    ) as provider_cls, patch(
        "stockresearch.services.sentiment.SentimentService.compute_market_sentiment",
        new_callable=AsyncMock,
        return_value=greed_result,
    ):
        provider_cls.return_value.get_overview = AsyncMock(return_value=overview)
        signals = await _collect_market_signals()

    greed_signals = [s for s in signals if "极度乐观" in s.title]
    assert len(greed_signals) == 1
    assert greed_signals[0].severity == "info"


@pytest.mark.asyncio
async def test_no_market_signals_on_neutral():
    """中性市场不产生 market 信号。"""
    overview = _make_overview(index_change=0.5, northbound=10.0, advancers=2500, decliners=2500)
    neutral_result = SentimentResult(score=50, label="中性", drivers=[], source="composite")
    with patch(
        "stockresearch.services.action_center.MarketOverviewProvider"
    ) as provider_cls, patch(
        "stockresearch.services.sentiment.SentimentService.compute_market_sentiment",
        new_callable=AsyncMock,
        return_value=neutral_result,
    ):
        provider_cls.return_value.get_overview = AsyncMock(return_value=overview)
        signals = await _collect_market_signals()

    assert len(signals) == 0


@pytest.mark.asyncio
async def test_generate_daily_actions_includes_market_signals(db_session, user):
    """完整流程：持仓 + 市场级信号同时存在时，market 信号参与排序。"""
    db_session.add(Holding(
        user_id=user.id,
        symbol="600519",
        name="贵州茅台",
        cost_price=1000,
        quantity=100,
        sector="白酒",
    ))
    db_session.commit()

    overview = _make_overview(index_change=_INDEX_PLUNGE_PCT, northbound=_NORTHBOUND_LARGE_OUTFLOW)
    quote = MagicMock(symbol="600519", name="贵州茅台", price=1000, change_pct=0)

    with patch(
        "stockresearch.services.action_center.MarketOverviewProvider"
    ) as overview_cls, patch(
        "stockresearch.services.action_center.QuoteProvider"
    ) as quote_cls, patch(
        "stockresearch.agents.news.agent.get_news_for_user",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "stockresearch.services.sentiment.SentimentService.compute_market_sentiment",
        new_callable=AsyncMock,
        return_value=SentimentResult(score=15, label="极度恐慌", drivers=[], source="composite"),
    ):
        overview_cls.return_value.get_overview = AsyncMock(return_value=overview)
        quote_cls.return_value.get_quotes = AsyncMock(return_value={"600519": quote})
        result = await generate_daily_actions(db_session, user.id)

    market_signals = [s for s in result.signals if s.type == "market"]
    assert len(market_signals) >= 2  # 至少有指数大跌 + 北向流出 + 情绪恐慌中的两条
    assert "市场" in result.summary


@pytest.mark.asyncio
async def test_market_signals_resilient_on_provider_failure():
    """数据源失败时不抛异常，返回空列表。"""
    with patch(
        "stockresearch.services.action_center.MarketOverviewProvider"
    ) as provider_cls, patch(
        "stockresearch.services.sentiment.SentimentService.compute_market_sentiment",
        new_callable=AsyncMock,
        side_effect=RuntimeError("network error"),
    ):
        provider_cls.return_value.get_overview = AsyncMock(side_effect=RuntimeError("network error"))
        signals = await _collect_market_signals()

    assert signals == []
