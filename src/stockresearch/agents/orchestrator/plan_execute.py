"""Plan-and-Execute workflow for complex financial research queries.

The LLM first creates a plan (list of steps), then executes each step
using available tools, and finally synthesizes the results.
"""

import json
import logging
from typing import Any

from stockresearch.agents.orchestrator.route_plan import FINANCE_TOOLS
from stockresearch.utils.llm import LLMClient

logger = logging.getLogger(__name__)

_PLAN_GENERAL_SYSTEM = """你是「StockResearch」的研究规划 Agent。用户提出了一个与股票投资无直接关系的复杂问题，请制定分析计划。

输出格式（JSON）：
```json
{
  "reasoning": "为什么选择这个计划",
  "steps": [
    {"id": 1, "description": "步骤描述", "tool": "auto", "args": {}}
  ]
}
```

规则：
- 步骤不超过5步
- 不要使用任何金融数据、新闻或联网搜索工具（tool 请填 auto）
- 基于逻辑推理与常识分析"""

_PLAN_SYSTEM = """你是「StockResearch」的研究规划 Agent。用户提出了一个复杂的金融研究问题，请制定研究计划。

输出格式（JSON）：
```json
{
  "reasoning": "为什么选择这个计划",
  "steps": [
    {"id": 1, "description": "步骤描述", "tool": "工具名", "args": {"参数": "值"}},
    {"id": 2, "description": "步骤描述", "tool": "工具名", "args": {"参数": "值"}}
  ]
}
```

可用工具：
- get_market_data: 获取大盘指数、北向资金等市场整体数据
- get_stock_quote: 获取个股实时行情（参数: symbol）
- get_stock_research: 获取个股四维投研分析（参数: symbol）
- debate_stock: 个股 Multi-Agent 多空辩论投研（参数: symbol, 可选 name）
- get_financial_ratios: 获取个股财报比率（参数: symbol）
- get_news: 获取最新财经新闻
- get_sector_holdings: 获取用户持仓中某板块的股票（参数: sector）
- get_sector_news: 获取与某板块相关的快讯（参数: sector）

规则：
- 步骤不超过5步
- 先获取数据，再分析
- 如果涉及个股，优先使用 debate_stock
- 不要建议买卖"""

_EXECUTE_SYSTEM = """你是「StockResearch」的执行 Agent。根据计划步骤执行研究任务。

当前计划：{plan}
已完成的步骤：{completed}

请执行下一步：{current_step}

如果需要调用工具，使用格式：
```tool
{{"tool": "工具名", "args": {{"参数": "值"}}}}
```

如果当前步骤已完成，输出该步骤的结果摘要。"""

_SYNTHESIS_SYSTEM = """你是「StockResearch」的综合分析 Agent。根据以下研究步骤的结果，生成最终报告。

研究问题：{query}

步骤结果：
{results}

请输出：
1. 核心结论（先结论后分析）
2. 关键发现（分点列出）
3. 风险因素
4. 建议关注点

不要建议买卖。末尾加上：以上内容由 AI 生成，仅供参考，不构成投资建议。"""

_MAX_PLAN_STEPS = 5


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract JSON from LLM response."""
    # Try to find JSON block
    for marker in ("```json", "```"):
        if marker in text:
            parts = text.split(marker)
            for part in parts[1:]:
                end = part.find("```")
                if end != -1:
                    json_str = part[:end].strip()
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        continue
    # Try parsing the whole text
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def _extract_tool_calls(text: str) -> list[dict[str, Any]]:
    """Extract tool calls from LLM response."""
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


class PlanExecuteAgent:
    """Plan-and-Execute workflow for complex queries."""

    def __init__(
        self,
        llm: LLMClient,
        tool_executor: Any = None,
        *,
        finance_tools: bool = True,
    ) -> None:
        self._llm = llm
        self._tool_executor = tool_executor  # function(name, args) -> str
        self._finance_tools = finance_tools
        self._plan_steps: list[dict[str, Any]] = []
        self._completed: list[dict[str, str]] = []
        self._on_progress: Any = None

    def set_progress_callback(self, cb: Any) -> None:
        """Set an async callback(msg: str) called at each step."""
        self._on_progress = cb

    async def _progress(self, msg: str) -> None:
        if self._on_progress:
            await self._on_progress(msg)

    async def run(self, query: str) -> tuple[str, list[dict[str, Any]]]:
        """Run Plan-and-Execute workflow.

        Returns:
            (reply, cards) tuple
        """
        cards: list[dict[str, Any]] = []

        # Phase 1: Planning
        await self._progress("正在制定研究计划…")
        plan_prompt = _PLAN_SYSTEM if self._finance_tools else _PLAN_GENERAL_SYSTEM
        plan_response = await self._llm.complete(plan_prompt, query)
        plan_data = _extract_json(plan_response)

        if plan_data and "steps" in plan_data:
            self._plan_steps = plan_data["steps"][:_MAX_PLAN_STEPS]
            reasoning = plan_data.get("reasoning", "")
        else:
            # Fallback: treat as single-step
            self._plan_steps = [{"id": 1, "description": query, "tool": "auto", "args": {}}]
            reasoning = "自动规划"

        # Plan card
        cards.append({
            "type": "plan",
            "data": {
                "phase": "plan",
                "reasoning": reasoning,
                "steps": [
                    {"id": s.get("id", i + 1), "description": s.get("description", "")}
                    for i, s in enumerate(self._plan_steps)
                ],
            },
        })

        # Phase 2: Execute each step
        for step in self._plan_steps:
            step_id = step.get("id", 0)
            step_desc = step.get("description", "")
            await self._progress(f"执行步骤 {step_id}/{len(self._plan_steps)}: {step_desc}")
            step_result = await self._execute_step(query, step)
            self._completed.append({"step": step_desc, "result": step_result})

            # Add progress card
            cards.append({
                "type": "plan",
                "data": {
                    "phase": "execute",
                    "step_id": step_id,
                    "step": step_desc,
                    "result_preview": step_result[:200] if step_result else "",
                },
            })

        # Phase 3: Synthesis
        await self._progress("正在综合分析…")
        results_text = "\n\n".join(
            f"步骤{c['step']}：\n{c['result']}" for c in self._completed
        )
        synthesis = await self._llm.complete(
            _SYNTHESIS_SYSTEM.format(query=query, results=results_text),
            "请生成最终综合报告。",
        )
        reply = synthesis.strip()

        if not reply:
            reply = "综合分析完成，但无法生成报告摘要。"

        return reply, cards

    async def _execute_step(self, query: str, step: dict[str, Any]) -> str:
        """Execute a single plan step."""
        tool_name = step.get("tool", "")
        tool_args = step.get("args", {})

        if (
            not self._finance_tools
            and tool_name in FINANCE_TOOLS
        ):
            return f"工具 {tool_name} 已禁用：当前问题与股票投资无关。"

        # If tool_executor is available and tool is known, use it directly
        if self._tool_executor and tool_name != "auto":
            try:
                return await self._tool_executor(tool_name, tool_args)
            except Exception as exc:
                logger.warning("Tool %s failed: %s", tool_name, exc)
                return f"工具 {tool_name} 执行失败: {exc}"

        # Otherwise, let LLM decide how to execute
        completed_desc = "\n".join(
            f"- {c['step']}: {c['result'][:100]}" for c in self._completed
        )
        current_desc = f"步骤{step.get('id')}: {step.get('description')}"

        response = await self._llm.complete(
            _EXECUTE_SYSTEM.format(
                plan=str(self._plan_steps),
                completed=completed_desc or "无",
                current_step=current_desc,
            ),
            query,
        )

        # Check for tool calls
        tool_calls = _extract_tool_calls(response)
        if tool_calls and self._tool_executor:
            results = []
            for tc in tool_calls:
                tc_name = tc["tool"]
                if not self._finance_tools and tc_name in FINANCE_TOOLS:
                    results.append(f"工具 {tc_name} 已禁用：当前问题与股票投资无关。")
                    continue
                try:
                    r = await self._tool_executor(tc_name, tc.get("args", {}))
                    results.append(r)
                except Exception as exc:
                    results.append(f"工具 {tc['tool']} 失败: {exc}")
            return "\n".join(results)

        return response.strip()
