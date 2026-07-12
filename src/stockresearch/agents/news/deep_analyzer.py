"""News deep analysis agent — single-stock cross-reference with K-line, financials, sentiment."""

import asyncio
import logging
from collections.abc import AsyncIterator

from stockresearch.agents.voice import AGENT_VOICE
from stockresearch.core.schemas import NewsAnalysisOut, NewsAnalysisStockImpact
from stockresearch.data.providers.market import (
    FinancialDataProvider,
    QuoteProvider,
    SentimentDataProvider,
    TechnicalDataProvider,
)
from stockresearch.i18n.status_events import status_event
from stockresearch.utils.llm import LLMClient, get_llm_client
from stockresearch.utils.symbols import resolve_name

logger = logging.getLogger(__name__)

_CROSS_ANALYSIS_SYSTEM = (
    "你是 A 股投研分析师，负责评估新闻事件对具体股票的影响。\n"
    f"要求：{AGENT_VOICE}\n\n"
    "严格按以下结构输出，每部分用 ##标题 分隔：\n\n"
    "## 影响定性\n"
    "一句话判断新闻对该标的的影响方向（正面/负面/中性），说明核心理由。\n\n"
    "## 基本面交叉验证\n"
    "结合营收增速、净利率、ROE、负债率、估值水平，分析新闻是否改变基本面预期。\n\n"
    "## 技术面交叉验证\n"
    "结合当前 K 线趋势、均线位置、RSI、MACD，分析技术形态是否强化或削弱新闻效应。\n\n"
    "## 情绪面交叉验证\n"
    "结合新闻情绪评分与市场热度，判断情绪是否一致或有背离。\n\n"
    "## 综合结论\n"
    "2-3 句总结：新闻可信度 + 与数据的匹配度 + 操作参考。\n\n"
    "## 关键要点\n"
    "每行 - 开头，列出 3-5 条关键发现。禁止 markdown 其他格式。不要建议买卖。"
)

_OUTPUT_SECTIONS = (
    "影响定性",
    "基本面交叉验证",
    "技术面交叉验证",
    "情绪面交叉验证",
    "综合结论",
    "关键要点",
)


async def _fetch_stock_data(symbol: str) -> dict:
    quote_provider = QuoteProvider()
    tech_provider = TechnicalDataProvider()
    fin_provider = FinancialDataProvider()
    sent_provider = SentimentDataProvider()

    quote, kline, financials, sentiment = await asyncio.gather(
        quote_provider.get_quote(symbol),
        tech_provider.get_kline_chart(symbol, days=60),
        fin_provider.get_financials(symbol),
        sent_provider.get_news_sentiment_score(symbol),
        return_exceptions=True,
    )

    return {
        "quote": quote if not isinstance(quote, Exception) else None,
        "kline": kline if not isinstance(kline, Exception) else None,
        "financials": financials if not isinstance(financials, Exception) else None,
        "sentiment": sentiment if not isinstance(sentiment, Exception) else None,
    }


def _build_stock_context(symbol: str, data: dict) -> str:
    name = resolve_name(symbol)
    lines = [f"{name}({symbol}) 当前数据：\n"]

    quote = data.get("quote")
    if quote and hasattr(quote, "price"):
        lines.append(
            f"【行情】现价 {quote.price:.2f}，涨跌幅 {quote.change_pct:+.2f}%，"
            f"日内最高 {quote.high:.2f}，最低 {quote.low:.2f}"
        )

    financials = data.get("financials")
    if isinstance(financials, dict):
        lines.append(
            f"【基本面】营收增速 {_pct(financials.get('revenue_yoy'))}，"
            f"净利率 {_pct(financials.get('net_margin'))}，"
            f"ROE {_pct(financials.get('roe'))}，"
            f"负债率 {_pct(financials.get('debt_ratio'))}，"
            f"商誉占比 {_pct(financials.get('goodwill_ratio'))}"
        )

    kline = data.get("kline")
    if isinstance(kline, dict) and kline.get("bars"):
        bars = kline["bars"]
        indicators = kline.get("indicators", {})
        if len(bars) >= 5:
            recent_closes = [float(b["close"]) for b in bars[-5:]]
            trend_5d = (recent_closes[-1] / recent_closes[0] - 1) * 100
            ma20 = indicators.get("ma20", [])
            rsi = indicators.get("rsi", [])
            macd_hist = indicators.get("macd_histogram", [])
            lines.append(
                f"【技术面·K线】近 5 日趋势 {trend_5d:+.2f}%，"
                f"最新收盘 {recent_closes[-1]:.2f}，"
                f"MA20 {_last_float(ma20)}，RSI(14) {_last_float(rsi)}，"
                f"MACD 柱 {_last_float(macd_hist)}"
            )

    sentiment = data.get("sentiment")
    if isinstance(sentiment, dict):
        score = sentiment.get("score", sentiment.get("sentiment_score", 0))
        heat = sentiment.get("heat_score", sentiment.get("xueqiu_heat", 0))
        lines.append(f"【情绪面】新闻情绪评分 {score}，雪球热度 {heat}")

    return "\n".join(lines)


def _pct(v: object) -> str:
    if v is None:
        return "N/A"
    if isinstance(v, (int, float)):
        return f"{float(v) * 100:.1f}%"
    return str(v)


def _last_float(arr: list | None) -> str:
    if arr:
        last = arr[-1]
        if last is not None:
            return f"{float(last):.2f}"
    return "N/A"


def _parse_section(text: str, section: str) -> str:
    start_marker = f"## {section}"
    idx = text.find(start_marker)
    if idx < 0:
        return ""
    start = idx + len(start_marker)
    for next_sec in _OUTPUT_SECTIONS:
        if next_sec == section:
            continue
        end_idx = text.find(f"## {next_sec}", start)
        if end_idx >= 0:
            return text[start:end_idx].strip()
    return text[start:].strip()


def _extract_key_points(text: str) -> list[str]:
    points: list[str] = []
    in_section = False
    for line in text.split("\n"):
        stripped = line.strip()
        if "关键要点" in stripped:
            in_section = True
            continue
        if in_section:
            if stripped.startswith("-"):
                points.append(stripped[1:].strip())
            elif stripped and not stripped.startswith("-"):
                break
    return points[:5]


def _classify_technical(kline: dict | None) -> str:
    if not kline or not kline.get("bars"):
        return "neutral"
    bars = kline["bars"]
    if len(bars) < 5:
        return "neutral"
    recent = [float(b["close"]) for b in bars[-5:]]
    if recent[-1] > recent[0] * 1.03:
        return "bullish"
    if recent[-1] < recent[0] * 0.97:
        return "bearish"
    return "neutral"


def _classify_impact(text: str) -> str:
    t = text[:300]
    if "正面" in t:
        return "positive"
    if "负面" in t:
        return "negative"
    return "neutral"


async def run_news_deep_analysis_stream(
    title: str,
    summary: str,
    content: str,
    source: str,
    symbol: str,
    entities: list[str],
    news_id: int,
    llm: LLMClient | None = None,
) -> AsyncIterator[dict[str, object]]:
    client = llm or get_llm_client()
    name = resolve_name(symbol)

    try:
        async for event in _run_news_deep_analysis_body(
            title=title,
            summary=summary,
            content=content,
            source=source,
            symbol=symbol,
            entities=entities,
            news_id=news_id,
            client=client,
            name=name,
        ):
            yield event
    except Exception as exc:
        logger.exception("News deep analysis failed news_id=%s symbol=%s", news_id, symbol)
        yield {
            "type": "error",
            "code": "news_analysis_failed",
            "message": str(exc) or "新闻深度分析失败，请稍后重试",
        }


async def _run_news_deep_analysis_body(
    *,
    title: str,
    summary: str,
    content: str,
    source: str,
    symbol: str,
    entities: list[str],
    news_id: int,
    client: LLMClient,
    name: str,
) -> AsyncIterator[dict[str, object]]:
    yield status_event("status.news.analyze", news=str(news_id), symbol=symbol, name=name)

    news_text = f"【{source}】{title}\n摘要：{summary}"
    if content:
        news_text += f"\n正文：{content[:1200]}"

    yield status_event("status.news.fetching", symbol=symbol, name=name)
    data = await _fetch_stock_data(symbol)
    stock_context = _build_stock_context(symbol, data)

    yield status_event("status.news.cross_analyze", symbol=symbol, name=name)
    user_prompt = (
        f"新闻事件：\n{news_text}\n\n"
        f"{stock_context}\n\n"
        f"请按指定结构交叉分析此新闻对 {name}({symbol}) 的影响。"
    )
    impact_text = (await client.complete(_CROSS_ANALYSIS_SYSTEM, user_prompt)).strip()

    quote = data.get("quote")
    price = quote.price if quote and hasattr(quote, "price") else 0.0
    change_pct = quote.change_pct if quote and hasattr(quote, "change_pct") else 0.0

    financials = data.get("financials")
    pe_ttm = None
    if isinstance(financials, dict) and "pe_ttm" in financials:
        pe_ttm = float(financials["pe_ttm"])

    tech_signal = _classify_technical(data.get("kline"))
    impact_dir = _classify_impact(impact_text)
    key_points = _extract_key_points(impact_text)

    stock_impact = NewsAnalysisStockImpact(
        symbol=symbol,
        name=name,
        price=round(price, 2),
        change_pct=round(change_pct, 2),
        pe_ttm=round(pe_ttm, 2) if pe_ttm else None,
        technical_signal=tech_signal,
        technical_summary=_parse_section(impact_text, "技术面交叉验证"),
        fundamental_summary=_parse_section(impact_text, "基本面交叉验证"),
        sentiment_summary=_parse_section(impact_text, "情绪面交叉验证"),
        impact_assessment=impact_text,
        impact_direction=impact_dir,
        key_points=key_points,
    )

    yield {
        "type": "stock_impact",
        "symbol": symbol,
        "name": name,
        "assessment": impact_text,
        "direction": impact_dir,
        "key_points": key_points,
    }

    conclusion = _parse_section(impact_text, "综合结论")
    result = NewsAnalysisOut(
        news_id=news_id,
        title=title,
        summary=summary,
        source=source,
        entities=entities,
        related_stocks=[stock_impact],
        market_context=conclusion,
        cross_analysis=_parse_section(impact_text, "影响定性"),
        overall_assessment=impact_text,
    )
    yield {"type": "done", "result": result.model_dump(mode="json")}
