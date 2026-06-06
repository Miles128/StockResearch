"""Textual factors — compress news and dimension findings into narrative snippets."""

from dataclasses import dataclass
from typing import Literal, Sequence

from stockresearch.core.schemas import DimensionResult, NewsItemOut

_MAX_NEWS_FACTOR_CHARS = 2000
_MAX_SUMMARY_CHARS = 2800

_SENTIMENT_LABEL = {
    "bullish": "偏多",
    "bearish": "偏空",
    "neutral": "中性",
    "positive": "偏多",
    "negative": "偏空",
}
_CATEGORY_LABEL = {
    "holding": "持仓相关",
    "sector": "板块相关",
    "market": "市场要闻",
}
_IMPACT_LABEL = {"high": "高影响", "medium": "中影响", "low": "低影响"}
_CONF_LABEL = {"high": "高", "medium": "中", "low": "低"}


@dataclass(frozen=True, slots=True)
class NewsSnippet:
    title: str
    summary: str = ""
    sentiment: str = "neutral"
    category: str = "market"
    impact_level: str = "low"
    source: str = ""


def news_from_out(item: NewsItemOut) -> NewsSnippet:
    return NewsSnippet(
        title=item.title,
        summary=item.summary,
        sentiment=item.sentiment,
        category=item.category,
        impact_level=item.impact_level,
        source=item.source,
    )


def news_from_title(title: str, *, category: str = "sector") -> NewsSnippet:
    return NewsSnippet(title=title, category=category)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _format_news_line(item: NewsSnippet) -> str:
    body = item.title
    if item.summary:
        body += f" — {item.summary[:80]}"
    tags: list[str] = []
    sent = _SENTIMENT_LABEL.get(item.sentiment, item.sentiment)
    if sent and sent != "中性":
        tags.append(sent)
    impact = _IMPACT_LABEL.get(item.impact_level, "")
    if impact and impact != "低影响":
        tags.append(impact)
    if item.source:
        tags.append(item.source)
    if tags:
        body += f"（{' · '.join(tags)}）"
    return f"· {body}"


def build_news_text_factor(
    items: Sequence[NewsSnippet | str],
    *,
    subject: str = "市场",
) -> str:
    """Compress filtered news into a single textual factor."""
    snippets: list[NewsSnippet] = []
    for item in items:
        if isinstance(item, str):
            snippets.append(news_from_title(item))
        else:
            snippets.append(item)

    if not snippets:
        return f"【{subject} · 新闻文本因子】暂无可用快讯。"

    buckets: dict[str, list[str]] = {"holding": [], "sector": [], "market": []}
    sentiment_tally = {"bullish": 0, "bearish": 0, "neutral": 0}
    for snippet in snippets[:12]:
        cat = snippet.category if snippet.category in buckets else "market"
        buckets[cat].append(_format_news_line(snippet))
        key = snippet.sentiment if snippet.sentiment in sentiment_tally else "neutral"
        if snippet.sentiment in ("positive",):
            key = "bullish"
        elif snippet.sentiment in ("negative",):
            key = "bearish"
        sentiment_tally[key] += 1

    parts = [
        f"【{subject} · 新闻文本因子】",
        f"收录 {min(len(snippets), 12)} 条高相关快讯；"
        f"情绪分布：偏多 {sentiment_tally['bullish']} · "
        f"偏空 {sentiment_tally['bearish']} · 中性 {sentiment_tally['neutral']}。",
    ]
    for label, key in (
        ("持仓相关", "holding"),
        ("板块相关", "sector"),
        ("市场要闻", "market"),
    ):
        if buckets[key]:
            parts.append(f"■ {label}")
            parts.extend(buckets[key][:4])

    return _truncate("\n".join(parts), _MAX_NEWS_FACTOR_CHARS)


def build_dimension_text_factor(
    dimensions: dict[str, DimensionResult],
    labels: dict[str, str],
) -> str:
    """Each dimension as a compact text factor line."""
    lines: list[str] = []
    for key, dim in dimensions.items():
        label = labels.get(key, dim.agent or key)
        highlight = "；".join(dim.highlights[:2]) if dim.highlights else "暂无要点"
        risk = f"风险：{'；'.join(dim.risks[:2])}" if dim.risks else ""
        line = f"· {label} {dim.score}/10（置信{dim.confidence}）：{highlight}"
        if risk:
            line += f"；{risk}"
        lines.append(line)
    return "\n".join(lines)


def build_text_factor_summary(
    *,
    subject: str,
    dimensions: dict[str, DimensionResult],
    dimension_labels: dict[str, str],
    composite_score: float,
    composite_confidence: str,
    dimension_weights: dict[str, float],
    news_text_factor: str | None = None,
    debate_consensus: str | None = None,
) -> str:
    """Merge weighted scores, dimension factors, and optional news factor."""
    conf = _CONF_LABEL.get(composite_confidence, composite_confidence)
    lines = [
        f"【{subject} · 文本因子·总结】",
        f"加权综合 {composite_score}/10（置信度{conf}），按各维置信度与信息完整度加权。",
    ]
    if dimension_weights:
        weight_parts = [
            f"{dimension_labels.get(k, k)}×{dimension_weights[k]:.2f}"
            for k in dimensions
        ]
        lines.append("维度权重：" + " · ".join(weight_parts))
    lines.append("")
    lines.append("■ 投研维度因子")
    lines.append(build_dimension_text_factor(dimensions, dimension_labels))
    if news_text_factor:
        lines.append("")
        lines.append(news_text_factor)
    if debate_consensus:
        lines.append("")
        lines.append(f"■ 多空合议：{debate_consensus}")
    return _truncate("\n".join(lines), _MAX_SUMMARY_CHARS)


async def fetch_symbol_news_snippets(symbol: str, name: str, limit: int = 8) -> list[NewsSnippet]:
    from stockresearch.data.providers.market import SentimentDataProvider

    raw = await SentimentDataProvider().get_symbol_news(symbol, name, limit)
    return [
        NewsSnippet(title=str(item.get("title", "")), source=str(item.get("source", "")))
        for item in raw
        if item.get("title")
    ]


async def fetch_market_news_snippets(limit: int = 8) -> list[NewsSnippet]:
    from stockresearch.data.providers.news import NewsProvider

    raw = await NewsProvider().fetch_latest(limit)
    return [
        NewsSnippet(
            title=item.title,
            summary=item.content[:160],
            source=item.source,
            category="market",
        )
        for item in raw
        if item.title
    ]
