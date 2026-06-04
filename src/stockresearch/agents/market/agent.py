"""Market Analysis Agent — fetches real market data before answering."""

import asyncio
import logging

from stockresearch.core.config import get_settings
from stockresearch.core.constants import AVAILABLE_SECTORS, DISCLAIMER
from stockresearch.data.providers.market_overview import MarketOverviewProvider
from stockresearch.utils.llm import LLMClient, get_llm_client

logger = logging.getLogger(__name__)

_MARKET_ANALYSIS_SYSTEM = f"""你是「StockResearch」的市场分析专家。根据提供的市场数据，为用户分析市场走势。

规则：
- 基于提供的数据进行分析，不要编造数据
- 如果数据不可用，明确告知用户
- 简明扼要，先结论后分析
- 不给出买入卖出建议
- 展示多空观点
- 末尾加上：{DISCLAIMER}"""


async def run_market_analysis(
    query: str,
    sectors: list[str] | None = None,
    llm: LLMClient | None = None,
) -> str:
    client = llm or get_llm_client()
    provider = MarketOverviewProvider()

    data_parts: list[str] = []

    overview = await provider.get_overview()
    if overview.indices:
        data_parts.append("【大盘指数】")
        for idx in overview.indices:
            arrow = "↑" if idx.change_pct > 0 else "↓" if idx.change_pct < 0 else "→"
            data_parts.append(f"  {idx.name}: {idx.price:.2f} {arrow} {idx.change_pct:+.2f}%")
        if overview.northbound_net_yi is not None:
            direction = "净流入" if overview.northbound_net_yi > 0 else "净流出"
            data_parts.append(f"  北向资金: {abs(overview.northbound_net_yi):.1f}亿 {direction}")
        if overview.advancers is not None and overview.decliners is not None:
            data_parts.append(f"  涨跌家数: {overview.advancers}涨 / {overview.decliners}跌")
        data_parts.append(f"  数据来源: {overview.source} | 状态: {overview.data_status}")
    else:
        data_parts.append("【大盘指数】数据暂不可用")

    if sectors:
        matched = [s for s in sectors if s in AVAILABLE_SECTORS]
        if matched:
            data_parts.append(f"\n【关注板块】{', '.join(matched)}")

    data_context = "\n".join(data_parts)

    user_prompt = f"用户问题：{query}\n\n当前市场数据：\n{data_context}"

    try:
        reply = await asyncio.wait_for(
            client.complete(_MARKET_ANALYSIS_SYSTEM, user_prompt),
            timeout=get_settings().agent_timeout_seconds,
        )
        return reply
    except TimeoutError:
        return f"市场分析暂时超时，以下是当前数据摘要：\n\n{data_context}\n\n{DISCLAIMER}"
    except Exception as exc:
        logger.warning("Market analysis failed: %s", exc)
        return f"市场分析暂时不可用，以下是当前数据摘要：\n\n{data_context}\n\n{DISCLAIMER}"
