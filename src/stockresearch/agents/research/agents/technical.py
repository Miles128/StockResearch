"""Technical dimension agent — isolated kline/quote tools."""

from stockresearch.agents.research.agents._scoring import as_confidence
from stockresearch.agents.research.context import ResearchContext
from stockresearch.agents.research.react import DimensionAgent, ResearchTool
from stockresearch.agents.voice import AGENT_VOICE
from stockresearch.core.constants import CONFIDENCE_MEDIUM
from stockresearch.core.schemas import DimensionResult
from stockresearch.data.providers.market import QuoteProvider, TechnicalDataProvider

_SYSTEM = f"你是 A 股技术分析师。{AGENT_VOICE} 不要给出买入卖出建议。"


async def _tool_kline(ctx: ResearchContext) -> dict[str, object]:
    tech = TechnicalDataProvider()
    kline = await tech.get_kline(ctx.symbol)
    closes = [bar["close"] for bar in kline]
    ma20 = tech.calc_ma(closes, 20)
    indicators = tech.calc_macd_rsi(closes)
    return {"kline_bars": len(kline), "ma20": ma20, "indicators": indicators}


async def _tool_quote(ctx: ResearchContext) -> dict[str, object]:
    quote = await QuoteProvider().get_quote(ctx.symbol)
    return {
        "price": quote.price,
        "change_pct": quote.change_pct,
        "volume": quote.volume,
    }


def _build(data: dict[str, object], analysis: str) -> DimensionResult:
    quote = data["sina_quote"]
    kline = data["akshare_kline"]
    assert isinstance(quote, dict)
    assert isinstance(kline, dict)

    ma20 = float(kline["ma20"])
    indicators = kline["indicators"]
    assert isinstance(indicators, dict)

    score = 5.0
    if float(quote.get("price", 0)) > ma20:
        score += 1.5
    if float(indicators["macd"]) > 0:
        score += 1.0
    if float(indicators["rsi"]) > 70:
        score -= 1.0
    if float(indicators["rsi"]) < 30:
        score += 0.5
    score = max(1.0, min(10.0, score))

    return DimensionResult(
        agent="technical",
        score=round(score, 1),
        confidence=as_confidence(CONFIDENCE_MEDIUM),
        highlights=[analysis.strip()] if analysis.strip() else [f"RSI {indicators['rsi']}"],
        risks=[f"支撑位参考 MA20={ma20:.2f}"],
        data_sources=["akshare_kline", "sina_quote"],
    )


TECHNICAL_AGENT = DimensionAgent(
    agent_id="technical",
    label="技术面",
    system_prompt=_SYSTEM,
    tools=(
        ResearchTool("akshare_kline", "K 线与 MACD/RSI", _tool_kline),
        ResearchTool("sina_quote", "实时行情", _tool_quote),
    ),
    build=_build,
)
