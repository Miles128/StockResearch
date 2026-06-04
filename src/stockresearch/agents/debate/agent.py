"""Multi-Agent debate for stock research — Fundamental vs Technical vs Sentiment vs Risk.

Supports both batch mode (run_debate) and streaming mode (run_debate_stream).
"""

import logging
from collections.abc import AsyncIterator
from typing import Any

from stockresearch.utils.llm import LLMClient

logger = logging.getLogger(__name__)

_FUNDAMENTAL_SYSTEM = """你是基本面分析 Agent。从财务数据、盈利能力、估值水平等角度分析股票。
给出你的核心观点（看多/看空/中性），附上2-3条关键论据。
格式：
立场：[看多/看空/中性]
论据1：...
论据2：...
论据3：...
不要建议买卖。"""

_TECHNICAL_SYSTEM = """你是技术面分析 Agent。从趋势、均线、量价关系、支撑压力等角度分析股票。
给出你的核心观点（看多/看空/中性），附上2-3条关键论据。
格式：
立场：[看多/看空/中性]
论据1：...
论据2：...
论据3：...
不要建议买卖。"""

_SENTIMENT_SYSTEM = (
    "你是市场情绪分析 Agent。"
    "从资金流向、北向资金、市场热度、舆论情绪等角度分析股票。\n"
    "给出你的核心观点（看多/看空/中性），附上2-3条关键论据。\n"
    "格式：\n立场：[看多/看空/中性]\n论据1：...\n论据2：...\n论据3：...\n"
    "不要建议买卖。"
)

_RISK_SYSTEM = """你是风险评估 Agent。从回撤风险、集中度、流动性、黑天鹅概率等角度分析股票。
给出你的核心观点（看多/看空/中性），附上2-3条关键论据。
格式：
立场：[看多/看空/中性]
论据1：...
论据2：...
论据3：...
不要建议买卖。"""

_SYNTHESIS_SYSTEM = """你是辩论裁判。综合四位分析师的观点，给出最终结论。

四位分析师的观点如下：
{debate_content}

请输出：
1. 综合立场：[看多/看空/中性]
2. 共识点：...
3. 分歧点：...
4. 最终结论：...
5. 风险提示：...
不要建议买卖。"""

_AGENTS = [
    ("基本面", _FUNDAMENTAL_SYSTEM),
    ("技术面", _TECHNICAL_SYSTEM),
    ("情绪面", _SENTIMENT_SYSTEM),
    ("风控", _RISK_SYSTEM),
]


def _parse_stance(text: str) -> str:
    """Extract stance from agent response."""
    for s in ("看多", "看空", "中性"):
        if f"立场：{s}" in text or f"立场: {s}" in text:
            return s
    return "中性"


class DebateAgent:
    """Multi-Agent debate for stock research."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def run_debate(
        self, symbol: str, name: str, market_data: str = ""
    ) -> dict[str, Any]:
        """Run a 4-agent debate and return structured results (batch mode)."""
        positions: list[dict[str, str]] = []
        async for event in self.run_debate_stream(symbol, name, market_data):
            if event.get("type") == "position":
                positions.append(event["position"])
            elif event.get("type") == "done":
                return event["result"]
        # Fallback
        return {
            "positions": positions,
            "vote_tally": {"看多": 0, "看空": 0, "中性": 0},
            "final_bias": "neutral",
            "synthesis": "",
            "symbol": symbol,
            "name": name,
        }

    async def run_debate_stream(
        self, symbol: str, name: str, market_data: str = ""
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream debate — yield each agent's result as it completes.

        Yields events:
        - {"type": "position", "agent": str, "position": dict}
        - {"type": "synthesizing"}
        - {"type": "done", "result": dict}
        """
        context = f"股票：{name}({symbol})"
        if market_data:
            context += f"\n市场数据：\n{market_data}"

        positions: list[dict[str, str]] = []
        debate_content_parts: list[str] = []

        # Run agents sequentially so each result can be streamed
        for agent_name, system in _AGENTS:
            yield {"type": "position_start", "agent": agent_name}
            try:
                text = await self._llm.complete(system, context)
                text = text.strip()
            except Exception as exc:
                text = f"分析失败: {exc}"

            stance = _parse_stance(text)
            position = {
                "agent": agent_name,
                "stance": stance,
                "arguments": text,
            }
            positions.append(position)
            debate_content_parts.append(
                f"## {agent_name}分析师\n立场：{stance}\n{text}"
            )
            yield {"type": "position", "agent": agent_name, "position": position}

        # Synthesis
        yield {"type": "synthesizing"}
        debate_content = "\n\n".join(debate_content_parts)
        try:
            synthesis = await self._llm.complete(
                _SYNTHESIS_SYSTEM.format(debate_content=debate_content),
                context,
            )
            synthesis = synthesis.strip()
        except Exception as exc:
            logger.warning("Synthesis failed: %s", exc)
            synthesis = "裁判综合分析暂时不可用。"

        # Count votes
        vote_tally = {"看多": 0, "看空": 0, "中性": 0}
        for p in positions:
            vote_tally[p["stance"]] = vote_tally.get(p["stance"], 0) + 1

        # Determine final bias
        if vote_tally["看多"] >= 3:
            final_bias = "bullish"
        elif vote_tally["看空"] >= 3:
            final_bias = "bearish"
        else:
            final_bias = "neutral"

        yield {
            "type": "done",
            "result": {
                "positions": positions,
                "vote_tally": vote_tally,
                "final_bias": final_bias,
                "synthesis": synthesis,
                "symbol": symbol,
                "name": name,
            },
        }
