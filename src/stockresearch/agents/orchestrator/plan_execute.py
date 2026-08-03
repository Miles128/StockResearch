"""Plan-and-Execute workflow for complex financial research queries.

The LLM first creates a plan (list of steps), then executes each step
using available tools, and finally synthesizes the results.
"""

import json
import logging
from typing import Any

from stockresearch.agents.orchestrator.tools_registry import FINANCE_TOOLS, format_tools_for_prompt
from stockresearch.i18n.status_events import status_event
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
{tools_block}

规则：
- **禁止只规划 1 个数据步骤**；金融问题至少 3 步，最后一步用 tool:auto 做归纳分析
- 步骤不超过 5 步；顺序：先行情/数据 → 再新闻或持仓/板块 → 最后解读研判
- 大盘/市场走势类至少：get_market_data → get_news → auto 综合解读
- 个股类至少：get_stock_quote 或 get_stock_research → get_news → auto 解读
- 对比多只标的：分别拉数据/投研 → get_news → auto 对比结论
- 如果涉及个股深度投研，可用 debate_stock
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
_MIN_FINANCE_PLAN_STEPS = 3

_MARKET_PLAN_TEMPLATE: list[dict[str, Any]] = [
    {
        "id": 1,
        "description": "获取主要指数、北向资金与涨跌家数",
        "tool": "get_market_data",
        "args": {},
    },
    {
        "id": 2,
        "description": "获取今日市场财经快讯与要闻",
        "tool": "get_news",
        "args": {},
    },
    {
        "id": 3,
        "description": "结合行情与新闻，归纳多空因素、板块轮动与短线节奏",
        "tool": "auto",
        "args": {},
    },
]


def _reindex_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, step in enumerate(steps[:_MAX_PLAN_STEPS], start=1):
        merged = dict(step)
        merged["id"] = i
        out.append(merged)
    return out


def _extract_symbol(query: str) -> str | None:
    import re

    match = re.search(r"(?<!\d)(\d{6})(?!\d)", query)
    return match.group(1) if match else None


def _normalize_plan_steps(query: str, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand overly shallow LLM plans into multi-step research workflows."""
    if not steps:
        steps = [{"id": 1, "description": query, "tool": "auto", "args": {}}]

    from stockresearch.agents.orchestrator.complexity import has_stock_reference, is_market_scope

    if len(steps) >= _MIN_FINANCE_PLAN_STEPS:
        return _reindex_steps(steps)

    msg = query.strip()
    if is_market_scope(msg) and not has_stock_reference(msg):
        return _reindex_steps(_MARKET_PLAN_TEMPLATE)

    from stockresearch.agents.orchestrator.complexity import (
        count_stock_mentions,
        is_stock_comparison,
    )
    from stockresearch.utils.symbols import STOCK_CODE_RE

    if is_stock_comparison(msg) and count_stock_mentions(msg) >= 2:
        codes = list(dict.fromkeys(STOCK_CODE_RE.findall(msg)))
        if len(codes) < 2:
            codes = ["600519", "000858"]
        return _reindex_steps(
            [
                {
                    "id": 1,
                    "description": f"获取 {codes[0]} 多维投研",
                    "tool": "skill_stock_research",
                    "args": {"symbol": codes[0]},
                },
                {
                    "id": 2,
                    "description": f"获取 {codes[1]} 多维投研",
                    "tool": "skill_stock_research",
                    "args": {"symbol": codes[1]},
                },
                {
                    "id": 3,
                    "description": "获取相关市场快讯与行业背景",
                    "tool": "get_news",
                    "args": {},
                },
                {
                    "id": 4,
                    "description": "对比两只标的的估值、趋势与风险差异",
                    "tool": "auto",
                    "args": {},
                },
            ]
        )

    symbol = _extract_symbol(msg)
    if has_stock_reference(msg) or symbol:
        sym = symbol or "600519"
        from stockresearch.agents.research.budget import parse_depth_from_text

        depth_cue = parse_depth_from_text(msg)
        stock_args: dict[str, object] = {"symbol": sym, "utterance": msg}
        if depth_cue:
            stock_args["analysis_depth"] = depth_cue
        return _reindex_steps(
            [
                {
                    "id": 1,
                    "description": f"获取 {sym} 实时行情",
                    "tool": "get_stock_quote",
                    "args": {"symbol": sym},
                },
                {
                    "id": 2,
                    "description": f"获取 {sym} 多维投研分析",
                    "tool": "skill_stock_research",
                    "args": stock_args,
                },
                {
                    "id": 3,
                    "description": "获取相关财经快讯与市场背景",
                    "tool": "get_news",
                    "args": {},
                },
                {
                    "id": 4,
                    "description": "综合行情、投研与新闻形成结论",
                    "tool": "auto",
                    "args": {},
                },
            ]
        )

    padded = list(steps)
    if len(padded) == 1:
        padded.append(
            {
                "id": 2,
                "description": "补充相关财经快讯与背景信息",
                "tool": "get_news",
                "args": {},
            }
        )
    while len(padded) < _MIN_FINANCE_PLAN_STEPS:
        padded.append(
            {
                "id": len(padded) + 1,
                "description": "综合已收集信息形成结构化分析结论",
                "tool": "auto",
                "args": {},
            }
        )
    return _reindex_steps(padded)


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

    async def _progress(self, event: dict[str, object]) -> None:
        if self._on_progress:
            await self._on_progress(event)

    async def run(
        self,
        query: str,
        *,
        history: list[dict[str, str]] | None = None,
        long_term_context: str = "",
        user_context_text: str = "",
    ) -> tuple[str, list[dict[str, Any]]]:
        """Run Plan-and-Execute workflow.

        Returns:
            (reply, cards) tuple
        """
        cards: list[dict[str, Any]] = []
        user_query = query.strip()
        if user_context_text.strip():
            user_query = f"{user_query}\n\n{user_context_text.strip()}"
        if history:
            hist_text = "\n".join(f"{m['role']}: {m['content']}" for m in history[-8:])
            user_query = f"【对话历史】\n{hist_text}\n\n【当前问题】\n{user_query}"

        # Phase 1: Planning
        await self._progress(status_event("status.planning"))
        plan_prompt = (
            _PLAN_SYSTEM.format(
                tools_block=format_tools_for_prompt(include_research_skills=True),
            )
            if self._finance_tools
            else _PLAN_GENERAL_SYSTEM
        )
        if long_term_context.strip():
            plan_prompt = f"{plan_prompt.rstrip()}\n\n{long_term_context.strip()}"
        plan_response = await self._llm.complete(plan_prompt, user_query)
        plan_data = _extract_json(plan_response)

        if plan_data and "steps" in plan_data:
            raw_steps = plan_data["steps"][:_MAX_PLAN_STEPS]
            reasoning = plan_data.get("reasoning", "")
        else:
            raw_steps = [{"id": 1, "description": query, "tool": "auto", "args": {}}]
            reasoning = "自动规划"

        if self._finance_tools:
            self._plan_steps = _normalize_plan_steps(user_query, raw_steps)
            if len(raw_steps) < _MIN_FINANCE_PLAN_STEPS:
                reasoning = (
                    f"{reasoning} "
                    f"（原规划仅 {len(raw_steps)} 步，已扩展为 {len(self._plan_steps)} 步多源研究流程）"
                ).strip()
        else:
            self._plan_steps = _reindex_steps(raw_steps)

        # Plan card
        cards.append(
            {
                "type": "plan",
                "data": {
                    "phase": "plan",
                    "reasoning": reasoning,
                    "steps": [
                        {"id": s.get("id", i + 1), "description": s.get("description", "")}
                        for i, s in enumerate(self._plan_steps)
                    ],
                },
            }
        )

        # Phase 2: Execute each step
        for step in self._plan_steps:
            step_id = step.get("id", 0)
            step_desc = step.get("description", "")
            await self._progress(
                status_event(
                    "status.plan.step",
                    step_id=step_id,
                    total=len(self._plan_steps),
                    desc=step_desc,
                )
            )
            step_result = await self._execute_step(query, step)
            self._completed.append({"step": step_desc, "result": step_result})

            # Add progress card
            cards.append(
                {
                    "type": "plan",
                    "data": {
                        "phase": "execute",
                        "step_id": step_id,
                        "step": step_desc,
                        "result_preview": step_result[:200] if step_result else "",
                    },
                }
            )

        # Phase 3: Synthesis
        await self._progress(status_event("status.plan.synthesizing"))
        results_text = "\n\n".join(f"步骤{c['step']}：\n{c['result']}" for c in self._completed)
        synthesis = await self._llm.complete(
            _SYNTHESIS_SYSTEM.format(query=query, results=results_text),
            "请生成最终综合报告。",
        )
        reply = synthesis.strip()

        if not reply:
            reply = "综合分析完成，但无法生成报告摘要。"

        cards.append(
            {
                "type": "plan",
                "data": {
                    "phase": "synthesis",
                    "step_count": len(self._plan_steps),
                    "summary_preview": reply[:400] if reply else "",
                },
            }
        )

        return reply, cards

    async def _execute_step(self, query: str, step: dict[str, Any]) -> str:
        """Execute a single plan step."""
        tool_name = step.get("tool", "")
        tool_args = step.get("args", {})

        if not self._finance_tools and tool_name in FINANCE_TOOLS:
            return f"工具 {tool_name} 已禁用：当前问题与股票投资无关。"

        # If tool_executor is available and tool is known, use it directly
        if self._tool_executor and tool_name != "auto":
            try:
                return await self._tool_executor(tool_name, tool_args)
            except Exception as exc:
                logger.warning("Tool %s failed: %s", tool_name, exc)
                return f"工具 {tool_name} 执行失败: {exc}"

        # Otherwise, let LLM decide how to execute
        completed_desc = "\n".join(f"- {c['step']}: {c['result'][:100]}" for c in self._completed)
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
                    logger.warning("tool %s failed: %s", tc_name, exc, exc_info=True)
                    results.append(f"工具 {tc['tool']} 失败: {exc}")
            return "\n".join(results)

        return response.strip()
