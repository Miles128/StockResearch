"""Portfolio briefing — rule-based morning/closing digest (manual trigger)."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from stockresearch.agents.news.agent import get_news_for_user
from stockresearch.core.constants import DISCLAIMER
from stockresearch.core.schemas import BriefingOut, BriefingSection
from stockresearch.data.providers.market import QuoteProvider
from stockresearch.data.providers.market_overview import MarketOverviewProvider
from stockresearch.db.models import Holding, RiskAlertRecord
from stockresearch.services.text_factor import build_news_text_factor, news_from_out
from stockresearch.utils.llm import LLMClient


async def generate_briefing(
    db: Session,
    user_id: int,
    kind: str,
    *,
    llm: LLMClient | None = None,
) -> BriefingOut:
    holdings = db.query(Holding).filter(Holding.user_id == user_id).all()
    overview = await MarketOverviewProvider().get_overview()
    news = await get_news_for_user(db, user_id, related_only=False, limit=6)
    alerts = (
        db.query(RiskAlertRecord)
        .filter(RiskAlertRecord.user_id == user_id)
        .order_by(RiskAlertRecord.created_at.desc())
        .limit(5)
        .all()
    )

    title = "盘前简报" if kind == "morning" else "收盘简报"
    sections: list[BriefingSection] = []

    market_lines: list[str] = []
    for idx in overview.indices[:3]:
        arrow = "↑" if idx.change_pct > 0 else "↓" if idx.change_pct < 0 else "→"
        market_lines.append(f"{idx.name} {idx.price:.2f} {arrow}{idx.change_pct:+.2f}%")
    if overview.northbound_net_yi is not None:
        flow = "净流入" if overview.northbound_net_yi > 0 else "净流出"
        market_lines.append(f"北向资金 {abs(overview.northbound_net_yi):.1f}亿{flow}")
    sections.append(
        BriefingSection(
            title="市场概览",
            content="\n".join(market_lines) if market_lines else "市场数据暂不可用",
        )
    )

    if holdings:
        quote_provider = QuoteProvider()
        holding_lines: list[str] = []
        total_pnl = 0.0
        for h in holdings[:8]:
            try:
                q = await quote_provider.get_quote(h.symbol)
                pnl = (q.price - h.float_cost_price) * h.quantity
                total_pnl += pnl
                holding_lines.append(
                    f"{h.name}({h.symbol}) {q.price:.2f} "
                    f"{'+' if pnl >= 0 else ''}{pnl:.0f}元 · {h.sector}"
                )
            except Exception:
                holding_lines.append(f"{h.name}({h.symbol}) 行情暂不可用 · {h.sector}")
        holding_lines.append(f"估算浮动盈亏合计：{total_pnl:+.0f} 元")
        sections.append(BriefingSection(title="持仓快照", content="\n".join(holding_lines)))
    else:
        sections.append(BriefingSection(title="持仓快照", content="暂无持仓，可在「持仓」页添加。"))

    if news:
        news_factor = build_news_text_factor(
            [news_from_out(n) for n in news[:6]],
            subject="持仓与市场",
        )
        sections.append(BriefingSection(title="新闻文本因子", content=news_factor))
    else:
        sections.append(
            BriefingSection(title="新闻文本因子", content="暂无快讯，可在「新闻」页刷新。")
        )

    if alerts:
        alert_lines = [f"· [{a.severity}] {a.message}" for a in alerts]
        sections.append(BriefingSection(title="风控提醒", content="\n".join(alert_lines)))

    summary = "\n".join(f"【{s.title}】{s.content[:120]}" for s in sections[:3])
    if llm is not None:
        try:
            polished = await llm.complete(
                "你是投研简报编辑。根据以下结构化要点写一段 80-120 字的摘要，不荐股。",
                summary,
            )
            if polished.strip():
                summary = polished.strip()
        except Exception:
            pass

    return BriefingOut(
        kind=kind,  # type: ignore[arg-type]
        title=title,
        sections=sections,
        summary=summary,
        disclaimer=DISCLAIMER,
        generated_at=datetime.now(UTC),
    )
