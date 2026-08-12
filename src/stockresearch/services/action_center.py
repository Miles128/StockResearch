"""Daily Action Center — rule-based morning signal digest.

Generates ≤5 prioritized signals from holdings, news, and risk alerts.
Each signal = type + reason + action_button. Zero LLM for the signal engine.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from stockresearch.agents.news.agent import get_news_for_user
from stockresearch.core.schemas import ActionSignal, DailyActionCenterOut
from stockresearch.data.providers.market import QuoteProvider
from stockresearch.data.providers.market_overview import MarketOverviewProvider
from stockresearch.db.models import Holding
from stockresearch.services.news_interests import load_user_news_interests
from stockresearch.services.research_radar import collect_research_radar_signals

logger = logging.getLogger(__name__)

_MAX_SIGNALS = 6
_STOP_LOSS_YELLOW = 0.08
_STOP_LOSS_RED = 0.15
_SUPPORT_DISTANCE_PCT = 0.03
_SECTOR_CONCENTRATION_LIMIT = 0.40
_DAILY_DROP_PCT = -5.0  # 单日跌幅阈值（%），低于此值触发价格信号
_NEWS_TITLE_MAX_LEN = 60  # 新闻标题截断长度
_NEWS_SIGNAL_LIMIT = 5  # 新闻信号最大数量

# ── 市场级信号阈值 ──
_SENTIMENT_EXTREME_FEAR = 20  # 极度恐慌
_SENTIMENT_EXTREME_GREED = 80  # 极度乐观
_NORTHBOUND_LARGE_OUTFLOW = -50.0  # 北向大幅净流出（亿）
_NORTHBOUND_LARGE_INFLOW = 80.0  # 北向大幅净流入（亿）
_INDEX_SURGE_PCT = 2.0  # 指数大涨阈值（%）
_INDEX_PLUNGE_PCT = -2.0  # 指数大跌阈值（%）
_BREADTH_EXTREME_BULL = 0.70  # 普涨：上涨家数占比
_BREADTH_EXTREME_BEAR = 0.30  # 普跌：上涨家数占比


async def generate_daily_actions(
    db: Session,
    user_id: int,
) -> DailyActionCenterOut:
    """Build the daily action center: holdings + news + risk → ≤5 signals."""
    holdings = db.query(Holding).filter(Holding.user_id == user_id).all()
    if not holdings:
        return DailyActionCenterOut(
            signals=[],
            summary="暂无持仓，可在「持仓」页添加示例数据开始体验。",
            generated_at=datetime.now(UTC),
        )

    quote_provider = QuoteProvider()
    quote_available = True
    try:
        quote_map = await quote_provider.get_quotes([h.symbol for h in holdings])
    except Exception:
        logger.warning("action center quotes failed for user_id=%s", user_id, exc_info=True)
        quote_map = {}
        quote_available = False
    quotes = {sym: q for sym, q in quote_map.items()}

    news = await get_news_for_user(db, user_id, related_only=True, limit=10)
    interests = load_user_news_interests(db, user_id)

    signals: list[ActionSignal] = []

    # ── 1. Price / drawdown signals ──
    for h in holdings:
        q = quotes.get(h.symbol)
        if q is None:
            continue
        drawdown = (h.float_cost_price - q.price) / h.float_cost_price
        if drawdown >= _STOP_LOSS_RED:
            signals.append(
                ActionSignal(
                    type="risk",
                    severity="critical",
                    title=f"{h.name}跌幅 {drawdown:.1%}，触及止损红线",
                    detail=f"成本 {h.float_cost_price:.2f}，现价 {q.price:.2f}",
                    action="查看风控",
                    action_target="risk",
                    symbol=h.symbol,
                    weight=100,
                )
            )
        elif drawdown >= _STOP_LOSS_YELLOW:
            signals.append(
                ActionSignal(
                    type="risk",
                    severity="warning",
                    title=f"{h.name}回撤 {drawdown:.1%}，接近止损关注线",
                    detail=f"成本 {h.float_cost_price:.2f}，现价 {q.price:.2f}",
                    action="查看风控",
                    action_target="risk",
                    symbol=h.symbol,
                    weight=80,
                )
            )
        if q.change_pct <= _DAILY_DROP_PCT:
            signals.append(
                ActionSignal(
                    type="price",
                    severity="warning",
                    title=f"{h.name}今日跌幅 {q.change_pct:+.1f}%",
                    detail=f"现价 {q.price:.2f}",
                    action="查看行情",
                    action_target="chat",
                    symbol=h.symbol,
                    weight=70,
                )
            )

    # ── 2. News signals ──
    for item in news[:_NEWS_SIGNAL_LIMIT]:
        related_symbols = [s for s in (item.entities or []) if s in interests.symbols]
        if not related_symbols:
            continue
        for sym in related_symbols:
            matched_name = next((h.name for h in holdings if h.symbol == sym), sym)
            signals.append(
                ActionSignal(
                    type="news",
                    severity="info" if item.sentiment != "bearish" else "warning",
                    title=item.title[:_NEWS_TITLE_MAX_LEN],
                    detail=f"→ {matched_name}（{item.source}）",
                    action="深度解析",
                    action_target="news",
                    symbol=sym,
                    weight=50 if item.impact_level == "major" else 30,
                )
            )

    # ── 3. Sector concentration signal ──
    sector_values: dict[str, float] = {}
    total = 0.0
    for h in holdings:
        val = h.float_cost_price * h.quantity
        sector_values[h.sector] = sector_values.get(h.sector, 0) + val
        total += val
    if total > 0:
        for sector, val in sector_values.items():
            ratio = val / total
            if ratio > _SECTOR_CONCENTRATION_LIMIT:
                signals.append(
                    ActionSignal(
                        type="risk",
                        severity="warning",
                        title=f"{sector}板块仓位 {ratio:.0%}，集中度偏高",
                        detail="建议关注板块分散度",
                        action="查看风控",
                        action_target="risk",
                        symbol=None,
                        weight=40,
                    )
                )

    # ── 4. Research radar (bias flip / factor divergence on holdings+watchlist) ──
    signals.extend(collect_research_radar_signals(db, user_id, holdings))

    # ── 5. Market-level signals (overview + sentiment) ──
    market_signals = await _collect_market_signals()
    signals.extend(market_signals)

    # ── Deduplicate by symbol + type, keep highest weight ──
    seen: dict[str, ActionSignal] = {}
    for s in signals:
        key = f"{s.type}:{s.symbol or 'global'}:{s.title[:20]}"
        if key not in seen or s.weight > seen[key].weight:
            seen[key] = s
    ranked = sorted(seen.values(), key=lambda s: s.weight, reverse=True)[:_MAX_SIGNALS]

    if not ranked:
        summary = "暂无明显变化"
        if not quote_available:
            summary = "行情源暂不可用，价格类信号未能计算"
    else:
        risk_count = sum(1 for s in ranked if s.type == "risk")
        news_count = sum(1 for s in ranked if s.type == "news")
        price_count = sum(1 for s in ranked if s.type == "price")
        market_count = sum(1 for s in ranked if s.type == "market")
        research_count = sum(1 for s in ranked if s.type == "research")
        parts: list[str] = []
        if risk_count:
            parts.append(f"{risk_count}条风控")
        if news_count:
            parts.append(f"{news_count}条新闻")
        if price_count:
            parts.append(f"{price_count}条行情")
        if market_count:
            parts.append(f"{market_count}条市场")
        if research_count:
            parts.append(f"{research_count}条研究雷达")
        if not quote_available:
            parts.append("行情源暂不可用")
        summary = "、".join(parts) if parts else "有待关注事项"

    return DailyActionCenterOut(
        signals=ranked,
        summary=summary,
        generated_at=datetime.now(UTC),
    )


async def _collect_market_signals() -> list[ActionSignal]:
    """采集市场级信号：情绪极端、北向资金大幅流出入、指数大涨大跌、涨跌家数极端。

    全部规则驱动，零 LLM。任一数据源失败时静默跳过该信号。
    """
    signals: list[ActionSignal] = []

    # 获取市场概览（指数涨跌、涨跌家数、北向资金）
    try:
        overview = await MarketOverviewProvider().get_overview()
    except Exception as exc:
        logger.warning("Market overview for action center failed: %s", exc)
        overview = None

    if overview:
        # ── 4a. 指数大涨大跌 ──
        for idx in overview.indices:
            if idx.change_pct >= _INDEX_SURGE_PCT:
                signals.append(
                    ActionSignal(
                        type="market",
                        severity="info",
                        title=f"{idx.name}涨 {idx.change_pct:+.2f}%，市场走强",
                        detail=f"现价 {idx.price:.2f}",
                        action="查看市场",
                        action_target="market",
                        symbol=None,
                        weight=60,
                    )
                )
            elif idx.change_pct <= _INDEX_PLUNGE_PCT:
                signals.append(
                    ActionSignal(
                        type="market",
                        severity="warning",
                        title=f"{idx.name}跌 {idx.change_pct:+.2f}%，市场走弱",
                        detail=f"现价 {idx.price:.2f}",
                        action="查看市场",
                        action_target="market",
                        symbol=None,
                        weight=65,
                    )
                )

        # ── 4b. 涨跌家数极端（普涨/普跌）──
        adv = overview.advancers
        dec = overview.decliners
        if adv is not None and dec is not None and (adv + dec) > 0:
            bull_ratio = adv / (adv + dec)
            if bull_ratio >= _BREADTH_EXTREME_BULL:
                signals.append(
                    ActionSignal(
                        type="market",
                        severity="info",
                        title=f"市场普涨：{adv}涨 / {dec}跌（{bull_ratio:.0%}）",
                        detail="上涨家数占比极高，注意次日分化",
                        action="查看市场",
                        action_target="market",
                        symbol=None,
                        weight=45,
                    )
                )
            elif bull_ratio <= _BREADTH_EXTREME_BEAR:
                signals.append(
                    ActionSignal(
                        type="market",
                        severity="warning",
                        title=f"市场普跌：{adv}涨 / {dec}跌（{1 - bull_ratio:.0%}跌）",
                        detail="下跌家数占比极高，注意恐慌蔓延",
                        action="查看市场",
                        action_target="market",
                        symbol=None,
                        weight=55,
                    )
                )

        # ── 4c. 北向资金大幅流入/流出 ──
        north = overview.northbound_net_yi
        if north is not None:
            if north <= _NORTHBOUND_LARGE_OUTFLOW:
                signals.append(
                    ActionSignal(
                        type="market",
                        severity="warning",
                        title=f"北向资金净流出 {abs(north):.1f}亿，外资大幅撤离",
                        detail="北向连续大额流出时需警惕系统性风险",
                        action="查看市场",
                        action_target="market",
                        symbol=None,
                        weight=58,
                    )
                )
            elif north >= _NORTHBOUND_LARGE_INFLOW:
                signals.append(
                    ActionSignal(
                        type="market",
                        severity="info",
                        title=f"北向资金净流入 {north:.1f}亿，外资大幅抢筹",
                        detail="北向大额流入通常利好短期情绪",
                        action="查看市场",
                        action_target="market",
                        symbol=None,
                        weight=50,
                    )
                )

    # ── 4d. 市场情绪极端 ──
    try:
        from stockresearch.services.sentiment import SentimentService

        sentiment = await SentimentService().compute_market_sentiment()
        if sentiment.score <= _SENTIMENT_EXTREME_FEAR:
            signals.append(
                ActionSignal(
                    type="market",
                    severity="warning",
                    title=f"市场情绪极度恐慌（{sentiment.score}分）",
                    detail="恐慌区间可能存在超跌反弹机会，但也需警惕恐慌蔓延",
                    action="查看市场",
                    action_target="market",
                    symbol=None,
                    weight=62,
                )
            )
        elif sentiment.score >= _SENTIMENT_EXTREME_GREED:
            signals.append(
                ActionSignal(
                    type="market",
                    severity="info",
                    title=f"市场情绪极度乐观（{sentiment.score}分）",
                    detail="乐观区间需警惕获利回吐风险",
                    action="查看市场",
                    action_target="market",
                    symbol=None,
                    weight=52,
                )
            )
    except Exception as exc:
        logger.warning("Market sentiment for action center failed: %s", exc)

    return signals
