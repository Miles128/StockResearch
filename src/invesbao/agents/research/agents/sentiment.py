"""Sentiment dimension agent — isolated news/hot tools."""

from invesbao.agents.research.agents._scoring import as_confidence
from invesbao.agents.research.react import DimensionAgent, ResearchTool
from invesbao.agents.research.context import ResearchContext
from invesbao.agents.voice import AGENT_VOICE
from invesbao.core.constants import CONFIDENCE_LOW, CONFIDENCE_MEDIUM, DISCLAIMER
from invesbao.core.schemas import DimensionResult
from invesbao.data.providers.market import SentimentDataProvider
from invesbao.utils.symbols import resolve_name

_SYSTEM = f"你是 A 股市场情绪分析师。{AGENT_VOICE} 不要给出买入卖出建议。末尾标注：{DISCLAIMER}"


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
    score = 4.0 + bull_ratio * 6
    if news_score < -0.2:
        score -= 1.0
    if news_score > 0.2:
        score += 1.0
    score = max(1.0, min(10.0, score))

    risks = ["情绪指标波动较大，需结合基本面"]
    if news_score < -0.3:
        risks.insert(0, "近期新闻偏负面")

    highlight = (
        analysis.strip()
        if analysis.strip()
        else f"新闻 {len(items)} 条，看多比例 {bull_ratio:.0%}"
    )
    return DimensionResult(
        agent="sentiment",
        score=round(score, 1),
        confidence=as_confidence(CONFIDENCE_MEDIUM if items else CONFIDENCE_LOW),
        highlights=[highlight],
        risks=risks,
        data_sources=["xueqiu_hot", "akshare_news"],
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
