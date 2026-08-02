"""Portfolio briefing — LLM-synthesized intraday/postmarket digest."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.orm import Session

from stockresearch.agents.news.agent import get_news_for_user
from stockresearch.agents.structured_output import extract_json_dict
from stockresearch.core.constants import DISCLAIMER
from stockresearch.core.schemas import BriefingOut, BriefingSection, NewsItemOut
from stockresearch.data.providers.market import QuoteProvider
from stockresearch.data.providers.market_overview import MarketOverviewProvider
from stockresearch.db.models import Holding, RiskAlertRecord
from stockresearch.utils.format import arrow_for_change
from stockresearch.utils.llm import LLMClient

logger = logging.getLogger(__name__)

BriefingKind = Literal["premarket", "intraday", "postmarket"]

_LEGACY_PREMARKET = frozenset({"premarket", "morning", "pre_market"})
_LEGACY_INTRADAY = frozenset({"intraday", "closing"})
_LEGACY_POSTMARKET = frozenset({"postmarket", "post_market"})


def normalize_briefing_kind(kind: str) -> BriefingKind:
    key = kind.strip().lower()
    if key in _LEGACY_PREMARKET:
        return "premarket"
    if key in _LEGACY_INTRADAY:
        return "intraday"
    if key in _LEGACY_POSTMARKET:
        return "postmarket"
    return "intraday"


def briefing_kind_aliases(kind: str) -> tuple[str, ...]:
    """DB rows may still use legacy kind labels."""
    normalized = normalize_briefing_kind(kind)
    if normalized == "premarket":
        return ("premarket", "morning", "pre_market")
    if normalized == "intraday":
        return ("intraday", "closing")
    return ("postmarket", "post_market")


def briefing_title(kind: str) -> str:
    normalized = normalize_briefing_kind(kind)
    return {"premarket": "盘前简报", "intraday": "盘中简报", "postmarket": "盘后简报"}[normalized]


def _sentiment_label(sentiment: str) -> str:
    return {"bullish": "偏多", "bearish": "偏空"}.get(sentiment, "中性")


def _format_news_block(title: str, items: list[NewsItemOut], *, limit: int = 5) -> str:
    if not items:
        return f"【{title}】\n暂无相关新闻"
    lines = [f"【{title}】"]
    for item in items[:limit]:
        lines.append(
            f"- [{_sentiment_label(item.sentiment)}·{item.impact_level}] "
            f"{item.title}：{(item.summary or '')[:120]}"
        )
    return "\n".join(lines)


async def _collect_holdings_block(holdings: list[Holding], kind: BriefingKind) -> str:
    if not holdings:
        return "【持仓表现】\n暂无持仓，可在「持仓」页添加。"

    is_premarket = kind == "premarket"
    provider = QuoteProvider()
    symbols = [h.symbol for h in holdings[:12]]
    quotes = await provider.get_quotes(symbols)

    lines = ["【持仓表现】"]
    total_float_pnl = 0.0
    total_day_pnl = 0.0
    quoted = 0

    for h in holdings[:12]:
        q = quotes.get(h.symbol)
        if q is None:
            lines.append(f"- {h.name}({h.symbol}) · {h.sector}：行情暂不可用")
            continue
        quoted += 1
        float_pnl = (q.price - h.float_cost_price) * h.quantity
        if is_premarket:
            lines.append(
                f"- {h.name}({h.symbol}) · {h.sector}："
                f"盘前参考价 {q.price:.2f}（较昨收 {q.change_pct:+.2f}%），"
                f"浮动盈亏 {float_pnl:+.0f} 元；今日 09:30 开盘后才有实时涨跌"
            )
        else:
            day_pnl = q.price * h.quantity * (q.change_pct / 100.0)
            total_day_pnl += day_pnl
            lines.append(
                f"- {h.name}({h.symbol}) · {h.sector}："
                f"现价 {q.price:.2f}，今日 {q.change_pct:+.2f}%，"
                f"当日盈亏约 {day_pnl:+.0f} 元，浮动盈亏 {float_pnl:+.0f} 元"
            )
        total_float_pnl += float_pnl

    if quoted:
        if is_premarket:
            lines.append(f"合计浮动盈亏约 {total_float_pnl:+.0f} 元（盘前未开盘，无当日盈亏）")
        else:
            lines.append(
                f"合计：当日盈亏约 {total_day_pnl:+.0f} 元，浮动盈亏 {total_float_pnl:+.0f} 元"
            )
    return "\n".join(lines)


def _collect_market_block(overview) -> str:
    lines = ["【大盘概况】"]
    if not overview.indices:
        lines.append("指数数据暂不可用")
    else:
        for idx in overview.indices[:4]:
            arrow = arrow_for_change(idx.change_pct)
            lines.append(f"- {idx.name} {idx.price:.2f} {arrow}{idx.change_pct:+.2f}%")
    if overview.northbound_net_yi is not None:
        flow = "净流入" if overview.northbound_net_yi > 0 else "净流出"
        lines.append(f"- 北向资金 {abs(overview.northbound_net_yi):.1f} 亿{flow}")
    return "\n".join(lines)


def _collect_kimi_block() -> str:
    """读取 Kimi 预取的宏观/Wind 缓存，格式化为简报 prompt 块。无数据返回空串。"""
    from stockresearch.data.providers.kimi_macro import MACRO_CACHE_KEY
    from stockresearch.data.providers.kimi_wind import WIND_CACHE_KEY
    from stockresearch.services.sqlite_cache import get_sqlite_cached

    lines: list[str] = []
    macro = get_sqlite_cached(MACRO_CACHE_KEY)
    if macro:
        lines.append(f"【宏观数据(Kimi, {macro.get('as_of', '?')})】")
        for ind in macro.get("indicators") or []:
            if isinstance(ind, dict):
                trend = ind.get("trend")
                trend_str = f" 趋势:{trend}" if trend else ""
                lines.append(
                    f"- {ind.get('name')}: {ind.get('value')}({ind.get('period')}){trend_str}{ind.get('comment', '')}"
                )
        for hl in macro.get("industry_highlights") or []:
            if isinstance(hl, dict):
                lines.append(f"- 行业·{hl.get('industry')}: {hl.get('summary')}")
    wind = get_sqlite_cached(WIND_CACHE_KEY)
    if wind:
        lines.append(f"【市场公告与研报(Kimi, {wind.get('as_of', '?')})】")
        for ann in wind.get("announcements") or []:
            if isinstance(ann, dict):
                lines.append(f"- 公告: {ann.get('title')} — {ann.get('summary')}")
        for rep in wind.get("research_reports") or []:
            if isinstance(rep, dict):
                lines.append(
                    f"- 研报: {rep.get('title')}({rep.get('org')},{rep.get('rating')})— {rep.get('summary')}"
                )
    return "\n".join(lines)


def _split_news(news: list[NewsItemOut]) -> tuple[list[NewsItemOut], list[NewsItemOut], list[NewsItemOut]]:
    holding: list[NewsItemOut] = []
    sector: list[NewsItemOut] = []
    market: list[NewsItemOut] = []
    for item in news:
        if item.category == "holding" or item.related_to_user:
            holding.append(item)
        elif item.category == "sector":
            sector.append(item)
        else:
            market.append(item)
    return holding, sector, market


def _briefing_system_prompt(kind: BriefingKind) -> str:
    phase = {"premarket": "盘前", "intraday": "盘中", "postmarket": "盘后"}[kind]
    if kind == "premarket":
        focus = (
            "侧重隔夜新闻、外围/政策/行业要闻对A股开盘的影响，以及持仓个股盘前可参考的舆情。"
            "市场尚未开盘，不预测具体开盘点位，只给出值得关注的方向。"
        )
    elif kind == "intraday":
        focus = "侧重实时涨跌、盘中已发生事件对持仓的影响，以及新闻与行情的联动。"
    else:
        focus = "侧重全天表现回顾、新闻脉络梳理，以及收盘后值得跟踪的风险点。"

    return (
        f"你是A股持仓{phase}简报编辑。请根据下方事实数据撰写简报。\n"
        f"{focus}\n"
        "写作要求：\n"
        "1. 必须综合：持仓表现、持仓相关新闻、大盘新闻、行业新闻，形成有深度的结论\n"
        "2. 先摆事实，再给判断；结论要说清「对谁有利/不利、接下来关注什么」\n"
        "3. 不荐股、不给具体买卖价位\n"
        "4. 仅输出 JSON，不要 markdown 代码块：\n"
        '{"summary":"80-150字开篇总览","sections":[{"title":"持仓表现","content":"..."},'
        '{"title":"新闻脉络","content":"..."},{"title":"综合结论","content":"..."}]}\n'
        "sections 固定 3 段，content 允许换行。"
    )


def _parse_llm_briefing(raw: str) -> tuple[str, list[BriefingSection]] | None:
    data = extract_json_dict(raw)
    if not data:
        return None
    summary = str(data.get("summary", "")).strip()
    sections_raw = data.get("sections")
    if not summary or not isinstance(sections_raw, list):
        return None
    sections: list[BriefingSection] = []
    for item in sections_raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        content = str(item.get("content", "")).strip()
        if title and content:
            sections.append(BriefingSection(title=title, content=content))
    if len(sections) < 2:
        return None
    return summary, sections


def _fallback_sections(
    *,
    kind: BriefingKind,
    holdings_block: str,
    holding_news: list[NewsItemOut],
    sector_news: list[NewsItemOut],
    market_news: list[NewsItemOut],
    market_block: str,
    alerts: list[RiskAlertRecord],
    kimi_block: str = "",
) -> tuple[str, list[BriefingSection]]:
    news_content = "\n\n".join(
        [
            _format_news_block("持仓相关", holding_news),
            _format_news_block("行业动态", sector_news),
            _format_news_block("市场要闻", market_news),
        ]
    )
    sections = [
        BriefingSection(title="持仓表现", content=holdings_block.replace("【持仓表现】\n", "")),
        BriefingSection(title="新闻脉络", content=news_content),
        BriefingSection(
            title="综合结论",
            content=(
                f"{market_block.replace('【大盘概况】\n', '')}\n\n"
                + (
                    "风控提醒：\n"
                    + "\n".join(f"- [{a.severity}] {a.message}" for a in alerts[:3])
                    if alerts
                    else "暂无新增风控提醒，建议继续跟踪持仓波动与相关新闻。"
                )
            ),
        ),
    ]
    # 降级简报同样展示 Kimi 预取的宏观/市场数据块
    if kimi_block:
        sections.append(BriefingSection(title="宏观与市场动态(Kimi)", content=kimi_block))
    phase = {"premarket": "盘前", "intraday": "盘中", "postmarket": "盘后"}[kind]
    if kind == "premarket":
        summary = f"{phase}简报：已汇总隔夜新闻、行业/市场要闻及持仓盘前参考信息，开盘前请关注下方方向。"
    else:
        summary = f"{phase}简报：已汇总持仓涨跌、相关新闻及大盘/行业动态，详见下方分段。"
    return summary, sections


async def generate_briefing(
    db: Session,
    user_id: int,
    kind: str,
    *,
    llm: LLMClient | None = None,
) -> BriefingOut:
    normalized = normalize_briefing_kind(kind)
    title = briefing_title(normalized)

    holdings = db.query(Holding).filter(Holding.user_id == user_id).all()
    overview = await MarketOverviewProvider().get_overview()
    news = await get_news_for_user(db, user_id, related_only=False, limit=24)
    alerts = (
        db.query(RiskAlertRecord)
        .filter(RiskAlertRecord.user_id == user_id)
        .order_by(RiskAlertRecord.created_at.desc())
        .limit(5)
        .all()
    )

    holding_news, sector_news, market_news = _split_news(news)
    holdings_block = await _collect_holdings_block(holdings, normalized)
    market_block = _collect_market_block(overview)
    kimi_block = _collect_kimi_block()

    context_parts = [
        f"简报类型：{title}",
        holdings_block,
        market_block,
    ]
    if kimi_block:
        context_parts.append(kimi_block)
    context_parts.extend(
        [
            _format_news_block("持仓相关新闻", holding_news),
            _format_news_block("行业新闻", sector_news),
            _format_news_block("大盘新闻", market_news),
        ]
    )
    if alerts:
        context_parts.append(
            "【风控提醒】\n" + "\n".join(f"- [{a.severity}] {a.message}" for a in alerts)
        )
    context = "\n\n".join(context_parts)

    summary: str | None = None
    sections: list[BriefingSection] | None = None

    if llm is not None:
        try:
            raw = await llm.complete(_briefing_system_prompt(normalized), context)
            parsed = _parse_llm_briefing(raw)
            if parsed:
                summary, sections = parsed
        except Exception:
            logger.warning("LLM briefing synthesis failed", exc_info=True)

    if summary is None or sections is None:
        summary, sections = _fallback_sections(
            kind=normalized,
            holdings_block=holdings_block,
            holding_news=holding_news,
            sector_news=sector_news,
            market_news=market_news,
            market_block=market_block,
            alerts=alerts,
            kimi_block=kimi_block,
        )
        if llm is not None:
            try:
                polished = await llm.complete(
                    "你是简报编辑。根据以下结构化要点，写一段 80-120 字的流畅开篇摘要，不荐股。",
                    summary + "\n\n" + sections[0].content[:400],
                )
                if polished.strip():
                    summary = polished.strip()
            except Exception:
                logger.warning("LLM briefing polish failed", exc_info=True)

    return BriefingOut(
        kind=normalized,
        title=title,
        sections=sections,
        summary=summary,
        disclaimer=DISCLAIMER,
        generated_at=datetime.now(UTC),
    )
