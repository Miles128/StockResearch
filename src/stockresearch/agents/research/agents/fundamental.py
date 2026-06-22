"""Fundamental dimension agent — isolated financial/valuation tools."""

from stockresearch.agents.research.agents._scoring import as_confidence
from stockresearch.agents.research.context import ResearchContext
from stockresearch.agents.research.react import DimensionAgent, ResearchTool
from stockresearch.agents.voice import AGENT_VOICE
from stockresearch.core.constants import CONFIDENCE_HIGH, CONFIDENCE_LOW
from stockresearch.core.schemas import DimensionResult
from stockresearch.data.providers.market import FinancialDataProvider

_SYSTEM = f"你是 A 股基本面分析师。{AGENT_VOICE} 不要给出买入卖出建议。"


async def _tool_financials(ctx: ResearchContext) -> dict[str, object]:
    provider = FinancialDataProvider()
    return await provider.get_financials(ctx.symbol)


async def _tool_valuation(ctx: ResearchContext) -> dict[str, object]:
    provider = FinancialDataProvider()
    return await provider.get_valuation(ctx.symbol)


async def _tool_peers(ctx: ResearchContext) -> dict[str, object]:
    provider = FinancialDataProvider()
    peers = await provider.get_industry_peers(ctx.symbol)
    return {"peers": peers}


def _build(data: dict[str, object], analysis: str) -> DimensionResult:
    fin = data["akshare_financials"]
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
        confidence=as_confidence(CONFIDENCE_HIGH if fin else CONFIDENCE_LOW),
        highlights=highlights,
        risks=risks,
        data_sources=["akshare_financials", "akshare_valuation", "akshare_peers"],
    )


FUNDAMENTAL_AGENT = DimensionAgent(
    agent_id="fundamental",
    label="基本面",
    system_prompt=_SYSTEM,
    tools=(
        ResearchTool("akshare_financials", "上市公司财务指标", _tool_financials),
        ResearchTool("akshare_valuation", "估值与分位", _tool_valuation),
        ResearchTool("akshare_peers", "同行业可比公司", _tool_peers),
    ),
    build=_build,
)
