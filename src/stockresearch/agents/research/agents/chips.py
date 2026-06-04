"""Chips dimension agent — isolated fund-flow/holder tools."""

from stockresearch.agents.research.agents._scoring import as_confidence
from stockresearch.agents.research.react import DimensionAgent, ResearchTool
from stockresearch.agents.research.context import ResearchContext
from stockresearch.agents.voice import AGENT_VOICE
from stockresearch.core.constants import CONFIDENCE_MEDIUM, DISCLAIMER
from stockresearch.core.schemas import DimensionResult
from stockresearch.data.providers.market import ChipsDataProvider

_SYSTEM = f"你是 A 股筹码分析专家。{AGENT_VOICE} 不要给出买入卖出建议。末尾标注：{DISCLAIMER}"


async def _tool_dragon(ctx: ResearchContext) -> dict[str, object]:
    return await ChipsDataProvider().get_dragon_tiger(ctx.symbol)


async def _tool_fund(ctx: ResearchContext) -> dict[str, object]:
    return await ChipsDataProvider().get_fund_flow(ctx.symbol)


async def _tool_holders(ctx: ResearchContext) -> dict[str, object]:
    return await ChipsDataProvider().get_holder_count(ctx.symbol)


async def _tool_lockup(ctx: ResearchContext) -> dict[str, object]:
    return await ChipsDataProvider().get_lockup(ctx.symbol)


def _build(data: dict[str, object], analysis: str) -> DimensionResult:
    dragon = data["akshare_lhb"]
    fund = data["akshare_fund_flow"]
    holders = data["akshare_gdhs"]
    lockup = data["akshare_lockup"]
    assert isinstance(dragon, dict)
    assert isinstance(fund, dict)
    assert isinstance(holders, dict)
    assert isinstance(lockup, dict)

    main_net = float(fund.get("main_net_inflow", 0))
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

    return DimensionResult(
        agent="chips",
        score=round(score, 1),
        confidence=as_confidence(CONFIDENCE_MEDIUM),
        highlights=[analysis.strip()] if analysis.strip() else [f"主力净流入 {main_net:.0f}"],
        risks=risks,
        data_sources=["akshare_lhb", "akshare_fund_flow", "akshare_gdhs", "akshare_lockup"],
    )


CHIPS_AGENT = DimensionAgent(
    agent_id="chips",
    label="筹码面",
    system_prompt=_SYSTEM,
    tools=(
        ResearchTool("akshare_lhb", "龙虎榜", _tool_dragon),
        ResearchTool("akshare_fund_flow", "主力资金流向", _tool_fund),
        ResearchTool("akshare_gdhs", "股东户数", _tool_holders),
        ResearchTool("akshare_lockup", "限售解禁", _tool_lockup),
    ),
    build=_build,
)
