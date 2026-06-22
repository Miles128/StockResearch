"""Daily Action Center — rule-based morning signal digest.

Generates ≤5 prioritized signals from holdings, news, and risk alerts.
Each signal = type + reason + action_button. Zero LLM for the signal engine.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from stockresearch.agents.news.agent import get_news_for_user
from stockresearch.core.schemas import ActionSignal, DailyActionCenterOut
from stockresearch.data.providers.market import QuoteProvider
from stockresearch.db.models import Holding
from stockresearch.services.news_interests import load_user_news_interests

_MAX_SIGNALS = 5
_STOP_LOSS_YELLOW = 0.08
_STOP_LOSS_RED = 0.15
_SUPPORT_DISTANCE_PCT = 0.03
_SECTOR_CONCENTRATION_LIMIT = 0.40
_DAILY_DROP_PCT = -5.0  # 单日跌幅阈值（%），低于此值触发价格信号
_NEWS_TITLE_MAX_LEN = 60  # 新闻标题截断长度
_NEWS_SIGNAL_LIMIT = 5  # 新闻信号最大数量


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
    quotes = {}
    for h in holdings:
        try:
            quotes[h.symbol] = await quote_provider.get_quote(h.symbol)
        except Exception:
            pass

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
            signals.append(ActionSignal(
                type="risk",
                severity="critical",
                title=f"{h.name}跌幅 {drawdown:.1%}，触及止损红线",
                detail=f"成本 {h.float_cost_price:.2f}，现价 {q.price:.2f}",
                action="查看风控",
                action_target="risk",
                symbol=h.symbol,
                weight=100,
            ))
        elif drawdown >= _STOP_LOSS_YELLOW:
            signals.append(ActionSignal(
                type="risk",
                severity="warning",
                title=f"{h.name}回撤 {drawdown:.1%}，接近止损关注线",
                detail=f"成本 {h.float_cost_price:.2f}，现价 {q.price:.2f}",
                action="查看风控",
                action_target="risk",
                symbol=h.symbol,
                weight=80,
            ))
        if q.change_pct <= _DAILY_DROP_PCT:
            signals.append(ActionSignal(
                type="price",
                severity="warning",
                title=f"{h.name}今日跌幅 {q.change_pct:+.1f}%",
                detail=f"现价 {q.price:.2f}",
                action="查看行情",
                action_target="chat",
                symbol=h.symbol,
                weight=70,
            ))

    # ── 2. News signals ──
    for item in news[:_NEWS_SIGNAL_LIMIT]:
        related_symbols = [
            s for s in (item.entities or []) if s in interests.symbols
        ]
        if not related_symbols:
            continue
        for sym in related_symbols:
            matched_name = next(
                (h.name for h in holdings if h.symbol == sym), sym
            )
            signals.append(ActionSignal(
                type="news",
                severity="info" if item.sentiment != "bearish" else "warning",
                title=item.title[:_NEWS_TITLE_MAX_LEN],
                detail=f"→ {matched_name}（{item.source}）",
                action="深度解析",
                action_target="news",
                symbol=sym,
                weight=50 if item.impact_level == "major" else 30,
            ))

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
                signals.append(ActionSignal(
                    type="risk",
                    severity="warning",
                    title=f"{sector}板块仓位 {ratio:.0%}，集中度偏高",
                    detail="建议关注板块分散度",
                    action="查看风控",
                    action_target="risk",
                    symbol=None,
                    weight=40,
                ))

    # ── Deduplicate by symbol + type, keep highest weight ──
    seen: dict[str, ActionSignal] = {}
    for s in signals:
        key = f"{s.type}:{s.symbol or 'global'}:{s.title[:20]}"
        if key not in seen or s.weight > seen[key].weight:
            seen[key] = s
    ranked = sorted(seen.values(), key=lambda s: s.weight, reverse=True)[:_MAX_SIGNALS]

    if not ranked:
        summary = "持仓暂无明显变化，市场整体平稳。"
    else:
        risk_count = sum(1 for s in ranked if s.type == "risk")
        news_count = sum(1 for s in ranked if s.type == "news")
        parts = []
        if risk_count:
            parts.append(f"{risk_count} 条风控信号")
        if news_count:
            parts.append(f"{news_count} 条相关新闻")
        summary = f"今日 {len(ranked)} 条关注信号：{'、'.join(parts)}。"

    return DailyActionCenterOut(
        signals=ranked,
        summary=summary,
        generated_at=datetime.now(UTC),
    )
