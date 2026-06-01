"""Research sub-agents with isolated toolsets."""

import asyncio
from dataclasses import dataclass
from typing import Literal

from invesbao.agents.research.debate import run_debate
from invesbao.agents.voice import AGENT_VOICE
from invesbao.core.constants import CONFIDENCE_HIGH, CONFIDENCE_LOW, CONFIDENCE_MEDIUM, DISCLAIMER
from invesbao.core.schemas import DebateResult, DimensionResult, ResearchReportOut
from invesbao.data.providers.market import (
    ChipsDataProvider,
    FinancialDataProvider,
    QuoteProvider,
    SentimentDataProvider,
    TechnicalDataProvider,
)
from invesbao.utils.llm import LLMClient, get_llm_client
from invesbao.utils.symbols import resolve_name

_SYSTEM_SUFFIX = (
    f"{AGENT_VOICE} 不要给出买入卖出建议。"
    f"末尾标注：{DISCLAIMER}"
)

ConfidenceLevel = Literal["high", "medium", "low"]
BiasLevel = Literal["bullish", "bearish", "neutral"]


def _as_confidence(value: str) -> ConfidenceLevel:
    if value == CONFIDENCE_HIGH:
        return "high"
    if value == CONFIDENCE_LOW:
        return "low"
    return "medium"


@dataclass
class ResearchContext:
    symbol: str
    llm: LLMClient


async def prepare_fundamental(ctx: ResearchContext) -> tuple[str, str, dict[str, object]]:
    fin_provider = FinancialDataProvider()
    fin = await fin_provider.get_financials(ctx.symbol)
    val = await fin_provider.get_valuation(ctx.symbol)
    peers = await fin_provider.get_industry_peers(ctx.symbol)
    system = f"你是 A 股基本面分析师。{_SYSTEM_SUFFIX}"
    user = f"财务数据：{fin}\n估值：{val}\n同行：{peers}"
    return system, user, {"fin": fin, "val": val, "peers": peers}


def build_fundamental(data: dict[str, object], analysis: str) -> DimensionResult:
    fin = data["fin"]
    assert isinstance(fin, dict)
    revenue_yoy = float(fin.get("revenue_yoy", 0))
    roe = float(fin.get("roe", 0))
    pe_pct = float(fin.get("pe_percentile", 0.5))

    score = 5.0
    if revenue_yoy > 0.15:
        score += 1.5
    if roe > 0.15:
        score += 1.0
    if pe_pct < 0.4:
        score += 0.5
    if float(fin.get("debt_ratio", 0.5)) > 0.6:
        score -= 1.0
    score = max(1.0, min(10.0, score))

    highlights = [line for line in analysis.split("。") if "亮点" in line or "增长" in line][:3]
    risks = [line for line in analysis.split("。") if "风险" in line or "竞争" in line][:3]
    if not highlights:
        highlights = [f"营收增速 {revenue_yoy:.0%}", f"ROE {roe:.0%}"]
    if not risks:
        risks = [f"PE 历史分位 {pe_pct:.0%}"]

    return DimensionResult(
        agent="fundamental",
        score=round(score, 1),
        confidence=_as_confidence(CONFIDENCE_HIGH if fin else CONFIDENCE_LOW),
        highlights=highlights,
        risks=risks,
        data_sources=["akshare_financials", "akshare_valuation"],
    )


async def run_fundamental(ctx: ResearchContext) -> DimensionResult:
    system, user, data = await prepare_fundamental(ctx)
    analysis = await ctx.llm.complete(system, user)
    return build_fundamental(data, analysis)


async def prepare_technical(ctx: ResearchContext) -> tuple[str, str, dict[str, object]]:
    tech = TechnicalDataProvider()
    kline = await tech.get_kline(ctx.symbol)
    closes = [bar["close"] for bar in kline]
    ma20 = tech.calc_ma(closes, 20)
    indicators = tech.calc_macd_rsi(closes)
    quote = await QuoteProvider().get_quote(ctx.symbol)
    system = f"你是 A 股技术分析师。{_SYSTEM_SUFFIX}"
    user = f"现价 {quote.price}，MA20 {ma20:.2f}，指标 {indicators}，涨跌幅 {quote.change_pct}%"
    return system, user, {"quote": quote, "ma20": ma20, "indicators": indicators}


def build_technical(data: dict[str, object], analysis: str) -> DimensionResult:
    quote = data["quote"]
    ma20 = float(data["ma20"])
    indicators = data["indicators"]
    assert isinstance(quote, object)
    assert isinstance(indicators, dict)

    score = 5.0
    if float(getattr(quote, "price", 0)) > ma20:
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
        confidence=_as_confidence(CONFIDENCE_MEDIUM),
        highlights=[analysis.strip()] if analysis.strip() else [f"RSI {indicators['rsi']}"],
        risks=[f"支撑位参考 MA20={ma20:.2f}"],
        data_sources=["akshare_kline", "sina_quote"],
    )


async def run_technical(ctx: ResearchContext) -> DimensionResult:
    system, user, data = await prepare_technical(ctx)
    analysis = await ctx.llm.complete(system, user)
    return build_technical(data, analysis)


async def prepare_sentiment(ctx: ResearchContext) -> tuple[str, str, dict[str, object]]:
    provider = SentimentDataProvider()
    name = resolve_name(ctx.symbol)
    hot = await provider.get_xueqiu_hot(ctx.symbol, name)
    news = await provider.get_symbol_news(ctx.symbol, name)
    news_score = provider.score_titles([item["title"] for item in news])
    headlines = "；".join(item["title"] for item in news[:5]) or "暂无近期新闻"
    system = f"你是 A 股市场情绪分析师。{_SYSTEM_SUFFIX}"
    user = f"新闻标题：{headlines}\n热度 {hot}，情感得分 {news_score:.2f}"
    return system, user, {"hot": hot, "news": news, "news_score": news_score}


def build_sentiment(data: dict[str, object], analysis: str) -> DimensionResult:
    hot = data["hot"]
    news = data["news"]
    news_score = float(data["news_score"])
    assert isinstance(hot, dict)
    assert isinstance(news, list)

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
        else f"新闻 {len(news)} 条，看多比例 {bull_ratio:.0%}"
    )
    return DimensionResult(
        agent="sentiment",
        score=round(score, 1),
        confidence=_as_confidence(CONFIDENCE_MEDIUM if news else CONFIDENCE_LOW),
        highlights=[highlight],
        risks=risks,
        data_sources=["akshare_news"],
    )


async def run_sentiment(ctx: ResearchContext) -> DimensionResult:
    system, user, data = await prepare_sentiment(ctx)
    analysis = await ctx.llm.complete(system, user)
    return build_sentiment(data, analysis)


async def prepare_chips(ctx: ResearchContext) -> tuple[str, str, dict[str, object]]:
    provider = ChipsDataProvider()
    dragon = await provider.get_dragon_tiger(ctx.symbol)
    fund = await provider.get_fund_flow(ctx.symbol)
    north = await provider.get_northbound_flow(ctx.symbol)
    holders = await provider.get_holder_count(ctx.symbol)
    lockup = await provider.get_lockup(ctx.symbol)
    system = f"你是 A 股筹码分析专家。{_SYSTEM_SUFFIX}"
    user = f"龙虎榜 {dragon}，主力资金 {fund}，股东户数 {holders}，限售解禁 {lockup}"
    return system, user, {
        "dragon": dragon,
        "fund": fund,
        "north": north,
        "holders": holders,
        "lockup": lockup,
    }


def build_chips(data: dict[str, object], analysis: str) -> DimensionResult:
    dragon = data["dragon"]
    fund = data["fund"]
    north = data["north"]
    holders = data["holders"]
    lockup = data["lockup"]
    assert isinstance(dragon, dict)
    assert isinstance(fund, dict)
    assert isinstance(north, dict)
    assert isinstance(holders, dict)
    assert isinstance(lockup, dict)

    main_net = float(fund.get("main_net_inflow", north.get("net_inflow", 0)))
    score = 5.0
    if main_net > 0:
        score += 1.0
    if float(holders.get("qoq_change", 0)) < 0:
        score += 0.5
    if str(dragon.get("signal", "")) == "净买入":
        score += 0.5
    if float(lockup.get("ratio_pct", 0)) > 5:
        score -= 1.0
    score = max(1.0, min(10.0, score))

    risks = ["筹码数据存在滞后"]
    if float(lockup.get("ratio_pct", 0)) > 3:
        risks.insert(0, f"近期待解禁占比约 {float(lockup['ratio_pct']):.1f}%")

    sources = sorted(
        {
            str(dragon.get("source", "akshare_lhb")),
            str(fund.get("source", "akshare_fund_flow")),
            str(holders.get("source", "akshare_gdhs")),
            str(lockup.get("source", "akshare_lockup")),
        }
    )

    return DimensionResult(
        agent="chips",
        score=round(score, 1),
        confidence=_as_confidence(CONFIDENCE_MEDIUM),
        highlights=[analysis.strip()] if analysis.strip() else [f"主力净流入 {main_net:.0f}"],
        risks=risks,
        data_sources=sources,
    )


async def run_chips(ctx: ResearchContext) -> DimensionResult:
    system, user, data = await prepare_chips(ctx)
    analysis = await ctx.llm.complete(system, user)
    return build_chips(data, analysis)


async def run_research(
    symbol: str,
    llm: LLMClient | None = None,
    *,
    with_debate: bool = True,
) -> ResearchReportOut:
    client = llm or get_llm_client()
    ctx = ResearchContext(symbol=symbol, llm=client)
    name = resolve_name(symbol)

    fundamental, technical, sentiment, chips = await asyncio.gather(
        run_fundamental(ctx),
        run_technical(ctx),
        run_sentiment(ctx),
        run_chips(ctx),
    )

    dimensions = {
        "fundamental": fundamental,
        "technical": technical,
        "sentiment": sentiment,
        "chips": chips,
    }

    scores = [d.score for d in dimensions.values()]
    composite = round(sum(scores) / len(scores), 1)

    confidences = [_as_confidence(d.confidence) for d in dimensions.values()]
    if confidences.count("high") >= 2:
        composite_confidence: ConfidenceLevel = "high"
    elif "low" in confidences:
        composite_confidence = "low"
    else:
        composite_confidence = "medium"

    if composite >= 6.5:
        bias: BiasLevel = "bullish"
    elif composite <= 4.5:
        bias = "bearish"
    else:
        bias = "neutral"

    summary = (
        f"{name}({symbol}) 综合评分 {composite}/10，"
        f"四维投票倾向{'偏多' if bias == 'bullish' else '偏空' if bias == 'bearish' else '中性'}。"
        f"基本面 {fundamental.score}，技术面 {technical.score}，"
        f"情绪面 {sentiment.score}，筹码面 {chips.score}。"
    )

    debate: DebateResult | None = None
    if with_debate:
        debate = await run_debate(symbol, name, dimensions, client)
        bias_label = (
            "偏多" if debate.final_bias == "bullish"
            else "偏空" if debate.final_bias == "bearish"
            else "中性"
        )
        summary += f" 裁判倾向：{bias_label}。"

    return ResearchReportOut(
        symbol=symbol,
        name=name,
        dimensions=dimensions,
        composite_score=composite,
        composite_confidence=composite_confidence,
        bias=bias,
        summary=summary,
        debate=debate,
    )
