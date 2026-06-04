"""Orchestrator Agent — ReAct pattern, LLM decides which tools to call.

Like Claude Code: the LLM is the orchestrator, tools are sub-agent capabilities.
The LLM decides what data to fetch, when to analyze, and when to reply.
"""

import asyncio
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from stockresearch.agents.news.agent import get_news_for_user
from stockresearch.agents.research.runner import run_research
from stockresearch.core.config import get_settings
from stockresearch.core.constants import DISCLAIMER
from stockresearch.core.schemas import ResearchReportOut
from stockresearch.data.providers.market import QuoteProvider
from stockresearch.data.providers.market_overview import MarketOverviewProvider
from stockresearch.utils.llm import LLMClient
from stockresearch.utils.symbols import resolve_name

logger = logging.getLogger(__name__)

ORCHESTRATOR_SYSTEM = f"""你是「StockResearch」的编排 Agent，负责理解用户问题并调用工具获取数据后回答。

工作流程：
1. 分析用户问题，决定需要哪些数据
2. 调用工具获取数据（可以多次调用不同工具）
3. 基于获取的数据，生成最终回答

可用工具：
- get_market_data: 获取大盘指数、北向资金、涨跌家数等市场整体数据
- get_stock_quote: 获取个股实时行情（参数: symbol 如 "600519"）
- get_stock_research: 获取个股四维投研分析（参数: symbol 如 "600519"）
- debate_stock: 个股 Multi-Agent 多空辩论投研（参数: symbol, 可选 name）
- get_financial_ratios: 获取个股财报比率（参数: symbol）含PE/PB/ROE/毛利率等
- get_news: 获取最新财经新闻
- reply: 生成最终回复给用户（当你认为数据足够时调用）

调用格式：在回复中使用 JSON 块调用工具：
```tool
{{"tool": "工具名", "args": {{"参数名": "参数值"}}}}
```

规则：
- 先获取数据再回答，不要凭空编造
- 可以连续调用多个工具
- 当你认为数据足够时，调用 reply 工具生成最终回复
- 不给出买入、卖出、加仓、减仓等操作建议
- 简明扼要，先结论后分析
- 末尾加上：{DISCLAIMER}

示例：
用户：中国股市未来走势如何
```tool
{{"tool": "get_market_data", "args": {{}}}}
```
[系统返回数据后]
```tool
{{"tool": "get_news", "args": {{}}}}
```
[系统返回新闻后]
```tool
{{"tool": "reply", "args": {{"message": "基于数据的分析..."}}}}
```"""

_MAX_ITERATIONS = 6


class OrchestratorAgent:
    def __init__(self, db: Session, llm: LLMClient, user_id: int = 1) -> None:
        self._db = db
        self._llm = llm
        self._user_id = user_id
        self._cards: list[dict[str, Any]] = []
        self._on_progress: Any = None  # optional async callback(str) -> None

    def set_progress_callback(self, cb: Any) -> None:
        """Set an async callback(msg: str) called at each step."""
        self._on_progress = cb

    async def _progress(self, msg: str) -> None:
        if self._on_progress:
            await self._on_progress(msg)

    async def run(self, message: str) -> tuple[str, list[dict[str, Any]]]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": ORCHESTRATOR_SYSTEM},
            {"role": "user", "content": message},
        ]

        for i in range(_MAX_ITERATIONS):
            await self._progress(f"正在思考… (第{i+1}步)")
            response = await self._llm.complete_messages(messages)
            logger.info("ReAct iter %d: response=%s", i, response[:200])

            tool_calls = _extract_tool_calls(response)
            logger.info("ReAct iter %d: tool_calls=%s", i, tool_calls)

            if not tool_calls:
                reply = _clean_reply(response)
                logger.info("ReAct final reply (no tool): %s", reply[:200])
                if not self._cards:
                    self._cards.append({"type": "text", "data": {"content": reply}})
                return reply, self._cards

            messages.append({"role": "assistant", "content": response})

            for tc in tool_calls:
                tool_name = tc.get("tool", "")
                tool_args = tc.get("args", {})
                # Progress hint based on tool
                tool_hints = {
                    "get_market_data": "正在获取大盘行情…",
                    "get_stock_quote": f"正在查询 {tool_args.get('symbol', '')} 行情…",
                    "get_stock_research": f"正在进行 {tool_args.get('symbol', '')} 投研分析…",
                    "debate_stock": f"正在对 {tool_args.get('symbol', '')} 进行多空辩论…",
                    "get_news": "正在获取财经新闻…",
                    "reply": "正在生成回复…",
                }
                hint = tool_hints.get(tool_name, f"正在执行 {tool_name}…")
                await self._progress(hint)

                result = await self._execute_tool(tool_name, tool_args)
                messages.append({"role": "user", "content": f"[工具 {tool_name} 返回]\n{result}"})

                if tool_name == "reply":
                    reply = tool_args.get("message", result)
                    logger.info("ReAct final reply (via reply tool): %s", reply[:200])
                    if not self._cards:
                        self._cards.append({"type": "text", "data": {"content": reply}})
                    return reply, self._cards

        reply = "抱歉，分析过程超出最大步骤数，以下是目前已获取的信息摘要。"
        if self._cards:
            last_card = self._cards[-1]
            if last_card.get("type") == "text":
                reply = str(last_card.get("data", {}).get("content", reply))
        else:
            self._cards.append({"type": "text", "data": {"content": reply}})
        return reply, self._cards

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> str:
        try:
            if name == "get_market_data":
                return await self._tool_market_data()
            if name == "get_stock_quote":
                return await self._tool_stock_quote(args.get("symbol", ""))
            if name == "get_stock_research":
                return await self._tool_stock_research(args.get("symbol", ""))
            if name == "debate_stock":
                return await self._tool_debate_stock(
                    args.get("symbol", ""),
                    str(args.get("name", "")),
                )
            if name == "get_financial_ratios":
                return await self._tool_financial_ratios(args.get("symbol", ""))
            if name == "get_news":
                return await self._tool_news()
            if name == "reply":
                return args.get("message", "")
            return f"未知工具: {name}"
        except Exception as exc:
            logger.warning("Tool %s failed: %s", name, exc)
            return f"工具 {name} 执行失败: {exc}"

    async def _tool_market_data(self) -> str:
        provider = MarketOverviewProvider()
        overview = await provider.get_overview()
        lines: list[str] = []
        if overview.indices:
            for idx in overview.indices:
                arrow = "↑" if idx.change_pct > 0 else "↓" if idx.change_pct < 0 else "→"
                lines.append(f"{idx.name}: {idx.price:.2f} {arrow} {idx.change_pct:+.2f}%")
        if overview.northbound_net_yi is not None:
            d = "净流入" if overview.northbound_net_yi > 0 else "净流出"
            lines.append(f"北向资金: {abs(overview.northbound_net_yi):.1f}亿{d}")
        if overview.advancers is not None and overview.decliners is not None:
            lines.append(f"涨跌家数: {overview.advancers}涨 / {overview.decliners}跌")
        lines.append(f"数据状态: {overview.data_status}")
        return "\n".join(lines) if lines else "市场数据暂不可用"

    async def _tool_stock_quote(self, symbol: str) -> str:
        if not symbol:
            return "请提供股票代码"
        provider = QuoteProvider()
        quote = await provider.get_quote(symbol)
        arrow = "↑" if quote.change_pct > 0 else "↓" if quote.change_pct < 0 else "→"
        self._cards.append({
            "type": "text",
            "data": {
                "content": (
                    f"{quote.name}({quote.symbol}) "
                    f"现价{quote.price:.2f} {arrow}{quote.change_pct:+.2f}%"
                )
            },
        })
        return (
            f"{quote.name}({quote.symbol})\n"
            f"现价: {quote.price:.2f} {arrow} {quote.change_pct:+.2f}%\n"
            f"最高: {quote.high:.2f} 最低: {quote.low:.2f}\n"
            f"成交量: {quote.volume:.0f}"
        )

    async def _tool_stock_research(self, symbol: str) -> str:
        if not symbol:
            return "请提供股票代码"
        return await self._format_research_report(
            symbol,
            await self._run_research_report(symbol),
        )

    async def _tool_debate_stock(self, symbol: str, name: str = "") -> str:
        if not symbol:
            return "请提供股票代码"
        result = await self._run_research_report(symbol)
        if result is None:
            return f"{name or resolve_name(symbol)} 多空辩论投研超时，请稍后重试"
        return await self._format_research_report(symbol, result, debate_focus=True)

    async def _run_research_report(self, symbol: str) -> ResearchReportOut | None:
        result, timed_out = await _run_with_timeout(
            run_research(symbol, self._llm, with_debate=True),
            get_settings().agent_timeout_seconds,
        )
        if timed_out or not isinstance(result, ResearchReportOut):
            return None
        self._cards.append({"type": "research", "data": result.model_dump(mode="json")})
        return result

    async def _format_research_report(
        self,
        symbol: str,
        result: ResearchReportOut | None,
        *,
        debate_focus: bool = False,
    ) -> str:
        if result is None:
            return f"{resolve_name(symbol)} 投研分析失败或超时，请稍后重试"
        dims = [f"  {dim_name}: 评分{dim_data.score}/10" for dim_name, dim_data in result.dimensions.items()]
        lines = [
            f"{result.name}({result.symbol}) 投研报告",
            f"综合评分: {result.composite_score}/10 倾向: {result.bias}",
            f"摘要: {result.summary}",
            *dims,
        ]
        debate = result.debate
        if debate_focus and debate:
            lines.extend(
                [
                    "多空辩论:",
                    f"  共识: {debate.consensus}",
                    f"  裁判结论: {debate.judge_verdict}",
                    f"  最终倾向: {debate.final_bias}",
                ]
            )
        elif debate:
            lines.append(f"裁判倾向: {debate.final_bias} — {debate.judge_verdict[:120]}")
        return "\n".join(lines)

    async def _tool_financial_ratios(self, symbol: str) -> str:
        if not symbol:
            return "请提供股票代码"
        from stockresearch.agents.financial.agent import FinancialRatioAgent

        agent = FinancialRatioAgent(llm=None)
        result = await agent.run(symbol, resolve_name(symbol))
        ratios = result.get("ratios", [])
        if not ratios:
            return f"{resolve_name(symbol)} 财报数据暂不可用"

        self._cards.append({"type": "financial", "data": result})

        lines = [f"{result.get('name', symbol)}({symbol}) 财报比率分析"]
        for r in ratios:
            lines.append(
                f"  {r['name']}: {r['value']} (参考: {r['reference']}, "
                f"评价: {r['assessment']})"
            )
        return "\n".join(lines)

    async def _tool_news(self) -> str:
        news = await get_news_for_user(self._db, self._user_id, related_only=False, limit=8)
        if not news:
            return "暂无最新新闻"
        self._cards.append({
            "type": "news",
            "data": {"items": [n.model_dump(mode="json") for n in news]},
        })
        lines = []
        for n in news[:8]:
            lines.append(f"- {n.title} [{n.sentiment}]")
        return "最新快讯:\n" + "\n".join(lines)


async def _run_with_timeout[T](coro, timeout: int) -> tuple[T | None, bool]:
    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
        return result, False
    except TimeoutError:
        return None, True


def _extract_tool_calls(text: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    parts = text.split("```tool")
    for part in parts[1:]:
        end = part.find("```")
        if end == -1:
            continue
        json_str = part[:end].strip()
        try:
            data = json.loads(json_str)
            if isinstance(data, dict) and "tool" in data:
                calls.append(data)
        except json.JSONDecodeError:
            continue
    return calls


def _clean_reply(text: str) -> str:
    """Clean LLM response when no tool calls are found — just return the text as-is."""
    # Remove any stray ```tool blocks that weren't parsed
    import re
    text = re.sub(r"```tool\s*.*?```", "", text, flags=re.DOTALL).strip()
    return text if text else "抱歉，我暂时无法回答，请稍后再试。"
