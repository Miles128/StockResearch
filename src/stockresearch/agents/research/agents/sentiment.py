"""Sentiment dimension agent — isolated news/hot tools."""

from stockresearch.agents.research.agents._scoring import as_confidence
from stockresearch.agents.research.context import ResearchContext
from stockresearch.agents.research.react import DimensionAgent, ResearchTool
from stockresearch.agents.research.dimension_text import REPORT_DIM_VOICE, finalize_dimension
from stockresearch.core.constants import CONFIDENCE_LOW, CONFIDENCE_MEDIUM
from stockresearch.core.schemas import DimensionResult
from stockresearch.data.providers.market import SentimentDataProvider
from stockresearch.utils.symbols import resolve_name

_SYSTEM = f"你是 A 股市场情绪分析师。{REPORT_DIM_VOICE}"


async def _tool_hot(ctx: ResearchContext) -> dict[str, object]:
    name = resolve_name(ctx.symbol)
    return await SentimentDataProvider().get_xueqiu_hot(ctx.symbol, name)


async def _tool_news(ctx: ResearchContext) -> dict[str, object]:
    name = resolve_name(ctx.symbol)
    news = await SentimentDataProvider().get_symbol_news(ctx.symbol, name)
    score = SentimentDataProvider().score_titles([item["title"] for item in news])
    return {"items": news, "news_score": score}


def _build(data: dict[str, object], analysis: str) -> DimensionResult:
    hot = data["xueqiu_hot"]
    news = data["akshare_news"]
    assert isinstance(hot, dict)
    assert isinstance(news, dict)

    items = news.get("items", [])
    assert isinstance(items, list)
    news_score = float(news.get("news_score", 0))

    bull_ratio = float(hot.get("bull_ratio", 0.5))
    available = bool(hot.get("available", True))
    heat_score = int(hot.get("heat_score", 0))
    post_count = int(hot.get("post_count", 0))
    source = str(hot.get("source", "unknown"))

    score = 4.0 + bull_ratio * 6
    if news_score < -0.2:
        score -= 1.0
    if news_score > 0.2:
        score += 1.0
    if not available:
        score = max(1.0, min(10.0, score - 0.5))
    score = max(1.0, min(10.0, score))

    risks = ["情绪指标波动较大，需结合基本面"]
    if not available:
        risks.insert(0, "雪球/东财情绪数据未成功拉取，结论置信度降低")
    if news_score < -0.3:
        risks.insert(0, "近期新闻偏负面")
    if not items:
        risks.append("个股新闻为空，需核对数据源")

    fallback_highlight = (
        f"热度 {heat_score}、讨论 {post_count}、多空比 {bull_ratio:.0%}、新闻 {len(items)} 条"
        f"（来源 {source}）"
    )
    has_data = available or bool(items)
    sources: list[str] = []
    if available:
        sources.append("xueqiu_hot")
    if items:
        sources.append("akshare_news")
    gaps: list[str] = []
    if not available:
        gaps.append("雪球/东财情绪未取到")
    if not items:
        gaps.append("个股新闻为空")
    return finalize_dimension(
        agent="sentiment",
        score=score,
        confidence=as_confidence(CONFIDENCE_MEDIUM if has_data else CONFIDENCE_LOW),
        raw_analysis=analysis,
        data_sources=sources,
        fallback_highlights=[fallback_highlight],
        fallback_risks=risks,
        gaps=gaps,
        partial=not available or not items,
    )


SENTIMENT_AGENT = DimensionAgent(
    agent_id="sentiment",
    label="情绪面",
    system_prompt=_SYSTEM,
    tools=(
        ResearchTool("xueqiu_hot", "雪球热度与多空比", _tool_hot),
        ResearchTool("akshare_news", "个股相关新闻", _tool_news),
    ),
    build=_build,
)
