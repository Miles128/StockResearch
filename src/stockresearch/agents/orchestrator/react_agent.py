"""Orchestrator Agent — ReAct pattern, LLM decides which tools to call.

Like Claude Code: the LLM is the orchestrator, tools are sub-agent capabilities.
The LLM decides what data to fetch, when to analyze, and when to reply.
"""

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from stockresearch.agents.news.agent import get_news_for_user
from stockresearch.agents.orchestrator.skills import SKILL_IDS, SkillRunner
from stockresearch.agents.orchestrator.tools_registry import (
    FINANCE_TOOLS,
    format_tools_for_prompt,
    research_skills_prompt_note,
)
from stockresearch.core.constants import DISCLAIMER
from stockresearch.core.schemas import ModeSettingsOut
from stockresearch.data.providers.market import QuoteProvider
from stockresearch.data.providers.market_overview import MarketOverviewProvider
from stockresearch.db.models import Holding, NewsItem
from stockresearch.i18n.status_events import status_event
from stockresearch.prompts import load_prompt
from stockresearch.services.chat.scope import PORTFOLIO_TOOL_NAMES, ChatContextScope
from stockresearch.services.provider_cache_policy import quote_cache_ttl_seconds
from stockresearch.utils.llm import LLMClient
from stockresearch.utils.symbols import resolve_name

logger = logging.getLogger(__name__)

ORCHESTRATOR_GENERAL_SYSTEM = f"""你是「StockResearch」的对话助手。用户的问题与股票投资无直接关系。

规则：
- 基于已有知识直接回答，不要编造实时行情或新闻
- 不要调用任何金融数据、新闻或联网搜索类工具
- 当你准备给出最终回答时，调用 reply 工具
- 简明扼要，先结论后分析
- 末尾加上：{DISCLAIMER}

调用格式（仅 reply 可用）：
```tool
{{"tool": "reply", "args": {{"message": "你的回答"}}}}
```"""

ORCHESTRATOR_SYSTEM = """你是「StockResearch」的编排 Agent。由你决定调用哪些轻量工具或打包 Skill，无需用户选手动模式。

工作流程：
1. 理解用户问题与对话上下文
2. 简单问题：轻量工具（行情/新闻/财报）即可
3. 深度问题：调用对应 Skill（四维投研、多空辩论、大师点评；仅当用户明确要求持仓风控时才用风控）
4. 复合问题：可串联多个 Skill，后序 Skill 的 context 参数引用前序结果摘要
5. 先在心里形成总体结论，调用 reply 输出给用户（各 Skill 过程已自动展开）

简单新闻/快讯：get_news + get_stock_quote，不要启动 Skill。
走势/涨跌/原因类（用户未要求深度投研）：先 get_stock_quote + get_news(symbol=...) 或 get_market_data + get_news，结合相关新闻解读可能驱动因素，不要启动 Skill。
个股/市场分析：不要调用 skill_risk_checkup / get_risk_summary；个股「有什么风险」属于投研，用 skill_stock_research 或报价/新闻即可。
用户说「只补缺口再跑 / 补充数据并重新投研 / 补充数据：…」时：必须调用 skill_stock_research（勿只口头回答）；analysis_depth 至少 comprehensive，并在 context 列出待补缺口。
仅当用户明确说持仓风控、组合体检、止损、回撤、我的持仓风险时，才做风控体检。

{context_rules}

轻量工具：
{tools_list}
{skills_note}

调用格式：
```tool
{"tool": "工具或Skill名", "args": {...}}
```

规则：
- Skill 过程会自动流式展开，reply 中写总体结论即可
- skill_master_commentary 的 context 应传入前文投研/风控/新闻的摘要
- 多大师点评后若需互辩，设 debate_masters: true
- 不给出买入、卖出、加仓、减仓等操作建议
- 末尾加上：{disclaimer}"""


def _build_orchestrator_system(tools_list: str, skills_note: str) -> str:
    """Assemble system prompt without str.format — skills JSON contains braces."""
    context_rules = load_prompt("context_rules.md")
    return (
        ORCHESTRATOR_SYSTEM.replace("{context_rules}", context_rules)
        .replace("{tools_list}", tools_list)
        .replace("{skills_note}", skills_note)
        .replace("{disclaimer}", DISCLAIMER)
    )


_RESEARCH_SKILL_BLOCK = frozenset(
    {
        "skill_stock_research",
        "skill_bull_bear_debate",
        "skill_market_research",
        "skill_industry_research",
    }
)

_MAX_ITERATIONS = 8
_MAX_TOOL_RESULT_CHARS = 2000

_LEGACY_SKILL_ALIASES: dict[str, str] = {
    "get_stock_research": "skill_stock_research",
    "debate_stock": "skill_bull_bear_debate",
}


def _truncate_tool_result(result: str) -> str:
    """Truncate tool results to limit context pollution in ReAct messages."""
    if len(result) <= _MAX_TOOL_RESULT_CHARS:
        return result
    return (
        result[:_MAX_TOOL_RESULT_CHARS]
        + "\n…（工具返回已截断，仅保留前半部分；如需更多细节请直接 reply 引用关键结论）"
    )


_PAGE_CONTEXT_HINTS: dict[str, str] = {
    "market": (
        "当前界面为市场视图。优先使用 get_market_data 获取大盘数据，"
        "用 get_news 获取市场快讯，用 get_sentiment 获取情绪数据；"
        "个股问题再用 get_stock_quote。不要调用 skill_risk_checkup，除非用户明确要求持仓风控。"
    ),
    "risk": (
        "当前界面为风控视图。若用户问风控相关问题，优先用 get_risk_summary 读取已有告警，"
        "需要完整风控体检再调 skill_risk_checkup；"
        "问个股风险可用 get_stock_quote / skill_stock_research，勿默认做持仓体检。"
        "问市场/大盘时不要做风控体检。"
    ),
    "news": (
        "当前界面为资讯视图。优先使用 get_news 获取新闻；"
        "个股相关新闻可传 symbol。避免启动四维投研 Skill，除非用户明确要求深度分析。"
        "不要调用 skill_risk_checkup，除非用户明确要求持仓风控。"
    ),
    "stock": (
        "当前界面为个股详情。优先使用 get_stock_quote + get_financial_ratios 获取该个股数据，"
        "用 get_news(symbol=...) 获取相关新闻，用 get_sentiment(scope=stock, symbol=...) 获取情绪。"
        "避免拉取全市场数据。不要调用 skill_risk_checkup，除非用户明确要求持仓风控。"
    ),
    "focus": (
        "当前界面为焦点视图。根据用户问题选择对应工具；"
        "仅当用户明确问持仓/组合时再用 get_portfolio_summary。"
        "分析个股或市场时不要调用 skill_risk_checkup。"
    ),
}


def _page_context_tool_hint(kind: str | None) -> str:
    """Return a tool-selection hint based on the current page context."""
    if not kind:
        return ""
    return _PAGE_CONTEXT_HINTS.get(kind, "")


class OrchestratorAgent:
    def __init__(
        self,
        db: Session,
        llm: LLMClient,
        user_id: int = 1,
        *,
        finance_tools: bool = True,
        research_tools: bool = True,
        mode_settings: ModeSettingsOut | None = None,
        holdings: list[Holding] | None = None,
        debate_default: bool = False,
        master_default: bool = False,
        portfolio_context: bool = False,
        news_explain_only: bool = False,
        confirmed_symbol: str | None = None,
        confirmed_name: str | None = None,
        page_context_kind: str | None = None,
        scope: ChatContextScope | None = None,
    ) -> None:
        self._db = db
        self._llm = llm
        self._user_id = user_id
        self._finance_tools = finance_tools
        self._research_tools = research_tools
        self._mode_settings = mode_settings
        self._holdings = holdings or []
        self._portfolio_context = portfolio_context
        self._news_explain_only = news_explain_only
        self._debate_default = debate_default
        self._master_default = master_default
        self._confirmed_symbol = confirmed_symbol
        self._confirmed_name = confirmed_name
        self._page_context_kind = page_context_kind
        self._scope = scope
        self._quote_cache_ttl = quote_cache_ttl_seconds(mode_settings)
        self._cards: list[dict[str, Any]] = []
        self._on_progress: Any = None
        self._skill_runner: SkillRunner | None = None
        self._user_message: str = ""

    def set_progress_callback(self, cb: Any) -> None:
        """Set async callback for status + skill stream events."""
        self._on_progress = cb

    def _skills(self) -> SkillRunner:
        if self._skill_runner is None:
            settings = self._mode_settings
            if settings is None:
                from stockresearch.core.schemas import ModeSettingsOut

                settings = ModeSettingsOut()
            self._skill_runner = SkillRunner(
                db=self._db,
                llm=self._llm,
                user_id=self._user_id,
                holdings=self._scope.skill_holdings if self._scope is not None else self._holdings,
                mode_settings=settings,
                debate_default=self._debate_default,
                master_default=self._master_default,
                confirmed_symbol=self._confirmed_symbol,
                confirmed_name=self._confirmed_name,
                on_event=self._progress,
            )
        return self._skill_runner

    def tool_cards(self) -> list[dict[str, Any]]:
        """Cards accumulated from tool calls (research, news, etc.)."""
        return list(self._cards)

    async def _progress(self, event: dict[str, object]) -> None:
        if self._on_progress:
            await self._on_progress(event)

    async def run(
        self,
        message: str,
        *,
        history: list[dict[str, str]] | None = None,
        long_term_context: str = "",
        user_context_text: str = "",
    ) -> tuple[str, list[dict[str, Any]]]:
        if self._finance_tools:
            tools_list = format_tools_for_prompt(
                include_research_skills=True,
                include_portfolio_tools=self._portfolio_context,
            )
            skills_note = research_skills_prompt_note(skills_available=True)
            system = _build_orchestrator_system(tools_list, skills_note)
        else:
            system = ORCHESTRATOR_GENERAL_SYSTEM
        if long_term_context.strip():
            system = f"{system.rstrip()}\n\n{long_term_context.strip()}"
        hint = _page_context_tool_hint(self._page_context_kind)
        if hint:
            system = f"{system.rstrip()}\n\n{hint}"
        user_content = message.strip()
        self._user_message = user_content
        if user_context_text.strip():
            user_content = f"{user_content}\n\n{user_context_text.strip()}"
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_content})

        for i in range(_MAX_ITERATIONS):
            await self._progress(status_event("status.react.thinking", step=i + 1))
            response = await self._llm.complete_messages(messages)
            logger.info("ReAct iter %d: response=%s", i, response[:200])

            tool_calls = _extract_tool_calls(response)
            logger.info("ReAct iter %d: tool_calls=%s", i, tool_calls)

            if not tool_calls:
                reply = _clean_reply(response)
                reply = _reply_from_cards(self._cards) or reply
                logger.info("ReAct final reply (no tool): %s", reply[:200])
                return reply, self._cards

            messages.append({"role": "assistant", "content": response})

            for tc in tool_calls:
                tool_name = tc.get("tool", "")
                tool_args = tc.get("args", {})
                # Progress hint based on tool
                tool_status_keys = {
                    "get_market_data": ("status.react.market_data", {}),
                    "get_stock_quote": (
                        "status.react.stock_quote",
                        {"symbol": str(tool_args.get("symbol", ""))},
                    ),
                    "get_news": ("status.react.news", {}),
                    "reply": ("status.react.reply", {}),
                }
                if tool_name in SKILL_IDS or tool_name in _LEGACY_SKILL_ALIASES:
                    key, params = ("status.react.skill", {"tool": tool_name})
                else:
                    key, params = tool_status_keys.get(
                        tool_name,
                        ("status.react.tool", {"tool": tool_name}),
                    )
                await self._progress(status_event(key, **params))

                result = await self._execute_tool(tool_name, tool_args)
                result = _truncate_tool_result(result)
                messages.append({"role": "user", "content": f"[工具 {tool_name} 返回]\n{result}"})

                if tool_name == "reply":
                    reply = tool_args.get("message", result)
                    logger.info("ReAct final reply (via reply tool): %s", reply[:200])
                    return reply, self._cards

        reply = _reply_from_cards(self._cards) or (
            "抱歉，分析过程超出最大步骤数，以下是目前已获取的信息摘要。"
        )
        if self._cards:
            last_card = self._cards[-1]
            if last_card.get("type") == "text":
                reply = str(last_card.get("data", {}).get("content", reply))
        return reply, self._cards

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> str:
        if not self._finance_tools and name in FINANCE_TOOLS:
            return f"工具 {name} 已禁用：当前问题与股票投资无关，请直接基于知识回答。"
        skill_name = _LEGACY_SKILL_ALIASES.get(name, name)
        if skill_name in PORTFOLIO_TOOL_NAMES and not self._portfolio_context:
            return f"工具 {name} 不可用：当前问题未涉及持仓组合，请勿调用持仓相关工具。"
        if self._news_explain_only and skill_name in _RESEARCH_SKILL_BLOCK:
            return (
                f"工具 {name} 不可用：当前为新闻解读问题，"
                "请基于已预取快讯直接 reply，勿启动投研 Skill。"
            )
        if skill_name in SKILL_IDS:
            return await self._run_skill(skill_name, args)
        try:
            if name == "get_market_data":
                return await self._tool_market_data()
            if name == "get_stock_quote":
                return await self._tool_stock_quote(args.get("symbol", ""))
            if name == "get_financial_ratios":
                return await self._tool_financial_ratios(args.get("symbol", ""))
            if name == "get_news":
                return await self._tool_news(args)
            if name == "get_sector_holdings":
                return await self._tool_sector_holdings(args)
            if name == "get_sector_news":
                return await self._tool_sector_news(args)
            if name == "get_portfolio_summary":
                return await self._tool_portfolio_summary()
            if name == "get_risk_summary":
                return await self._tool_risk_summary()
            if name == "get_sentiment":
                return await self._tool_sentiment(args)
            if name == "reply":
                return args.get("message", "")
            return f"未知工具: {name}"
        except Exception as exc:
            logger.warning("Tool %s failed: %s", name, exc)
            return f"工具 {name} 执行失败: {exc}"

    async def _run_skill(self, skill_id: str, args: dict[str, Any]) -> str:
        if skill_id == "skill_stock_research" and not args.get("with_debate"):
            args = {**args, "with_debate": self._debate_default}
        if skill_id == "skill_stock_research":
            from stockresearch.agents.research.budget import (
                is_gap_close_utterance,
                parse_depth_from_text,
            )

            gap_blob = " ".join(
                [
                    self._user_message,
                    str(args.get("context") or ""),
                    str(args.get("query") or ""),
                ]
            )
            if is_gap_close_utterance(gap_blob):
                # Gap close-the-loop: prefer thicker evidence budget; keep explicit deep.
                depth = str(args.get("analysis_depth") or "")
                if depth not in ("comprehensive", "deep"):
                    args = {**args, "analysis_depth": "comprehensive"}
                if not str(args.get("context") or "").strip():
                    args = {**args, "context": self._user_message}
            elif not args.get("analysis_depth"):
                cue = parse_depth_from_text(self._user_message) or parse_depth_from_text(
                    str(args.get("context") or args.get("query") or "")
                )
                if cue:
                    args = {**args, "analysis_depth": cue}
                elif not args.get("utterance"):
                    args = {**args, "utterance": self._user_message}
        result = await self._skills().run(skill_id, args)
        for card in result.cards:
            ctype = card.get("type")
            if ctype == "research":
                self._cards = [c for c in self._cards if c.get("type") != "research"]
            self._cards.append(card)
        return result.summary

    async def _tool_market_data(self) -> str:
        provider = MarketOverviewProvider()
        overview = await provider.get_overview(cache_ttl_seconds=self._quote_cache_ttl)
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
        quote = await provider.get_quote(symbol, cache_ttl_seconds=self._quote_cache_ttl)
        arrow = "↑" if quote.change_pct > 0 else "↓" if quote.change_pct < 0 else "→"
        return (
            f"{quote.name}({quote.symbol})\n"
            f"现价: {quote.price:.2f} {arrow} {quote.change_pct:+.2f}%\n"
            f"最高: {quote.high:.2f} 最低: {quote.low:.2f}\n"
            f"成交量: {quote.volume:.0f}"
        )

    async def _tool_financial_ratios(self, symbol: str) -> str:
        if not symbol:
            return "请提供股票代码"
        from stockresearch.agents.financial.agent import FinancialRatioAgent

        agent = FinancialRatioAgent(
            llm=None,
            quote_cache_ttl_seconds=self._quote_cache_ttl,
        )
        result = await agent.run(symbol, resolve_name(symbol))
        ratios = result.get("ratios", [])
        if not ratios:
            return f"{resolve_name(symbol)} 财报数据暂不可用"

        self._cards.append({"type": "financial", "data": result})

        lines = [f"{result.get('name', symbol)}({symbol}) 财报比率分析"]
        for r in ratios:
            lines.append(
                f"  {r['name']}: {r['value']} (参考: {r['reference']}, 评价: {r['assessment']})"
            )
        return "\n".join(lines)

    async def _tool_news(self, args: dict[str, Any] | None = None) -> str:
        from stockresearch.services.text_factor import (
            build_news_text_factor,
            fetch_symbol_news_snippets,
            news_from_out,
        )

        payload = args or {}
        symbol = str(payload.get("symbol", "") or "").strip()
        name = str(payload.get("name", "") or "").strip()
        if symbol:
            display = name or resolve_name(symbol)
            snippets = await fetch_symbol_news_snippets(symbol, display)
            if not snippets:
                return f"暂无与 {display}({symbol}) 相关的最新新闻"
            factor = build_news_text_factor(snippets, subject=f"{display}({symbol}) 相关新闻")
            self._cards.append(
                {
                    "type": "news",
                    "data": {
                        "items": [
                            {"title": s.title, "summary": s.summary, "source": s.source}
                            for s in snippets
                        ],
                    },
                }
            )
            return factor

        news_scope = self._scope.news_scope if self._scope is not None else "personalized"
        industry = self._scope.intent.subject_industry if self._scope is not None else None
        news = await get_news_for_user(
            self._db,
            self._user_id,
            related_only=False,
            limit=8,
            news_scope=news_scope,
            industry=industry,
        )
        if not news:
            return "暂无最新新闻"
        self._cards.append(
            {
                "type": "news",
                "data": {"items": [n.model_dump(mode="json") for n in news]},
            }
        )
        return build_news_text_factor(
            [news_from_out(n) for n in news],
            subject="财经快讯",
        )

    async def _tool_sector_holdings(self, args: dict[str, Any]) -> str:
        sector = str(args.get("sector", "")).strip()
        if not sector:
            return "请提供板块名称"
        if not self._holdings:
            return f"持仓中暂无「{sector}」板块标的"
        rows = [h for h in self._holdings if sector in (h.sector or "")]
        if not rows:
            return f"持仓中暂无「{sector}」板块标的"
        lines = [
            f"- {h.name}({h.symbol}) 成本{h.float_cost_price:.2f} · {h.quantity}股" for h in rows
        ]
        return f"「{sector}」板块持仓：\n" + "\n".join(lines)

    async def _tool_sector_news(self, args: dict[str, Any]) -> str:
        sector = str(args.get("sector", "")).strip()
        if not sector:
            return "请提供板块名称"
        candidates = self._db.query(NewsItem).order_by(NewsItem.published_at.desc()).limit(80).all()
        matched = [
            n
            for n in candidates
            if sector in n.title or sector in n.summary or sector in " ".join(n.entities or [])
        ][:8]
        if not matched:
            return f"暂无与「{sector}」相关的快讯"
        lines = [f"- {n.title} [{n.sentiment}]" for n in matched]
        return f"「{sector}」板块快讯：\n" + "\n".join(lines)

    async def _tool_portfolio_summary(self) -> str:
        """轻量读取持仓摘要，仅从 DB 读取，不拉实时行情。"""
        if not self._holdings:
            return "暂无持仓"
        from stockresearch.services.portfolio_summary import build_portfolio_brief

        brief = build_portfolio_brief(self._holdings)
        self._cards.append({"type": "portfolio", "data": brief})
        lines = [f"持仓 {len(self._holdings)} 只，总成本 ¥{brief['total_cost']:.0f}"]
        if brief.get("sectors"):
            sector_line = "、".join(f"{s['name']}({s['count']}只)" for s in brief["sectors"][:5])
            lines.append(f"行业分布: {sector_line}")
        for h in brief["holdings"][:6]:
            lines.append(
                f"- {h['name']}({h['symbol']}) {h['quantity']}股 成本{h['cost_price']:.2f}"
            )
        if len(brief["holdings"]) > 6:
            lines.append(f"…等共 {len(brief['holdings'])} 只")
        return "\n".join(lines)

    async def _tool_risk_summary(self) -> str:
        """读取最近风控告警记录，或提示用户运行风控体检。"""
        from stockresearch.db.models import RiskAlertRecord

        recent = (
            self._db.query(RiskAlertRecord)
            .filter(RiskAlertRecord.user_id == self._user_id)
            .order_by(RiskAlertRecord.created_at.desc())
            .limit(10)
            .all()
        )
        if not recent:
            return "暂无风控告警记录。如需风控体检，请调用 skill_risk_checkup 工具执行完整分析。"
        lines = [f"最近 {len(recent)} 条风控告警："]
        for r in recent:
            sev = r.severity
            sym = f"[{r.symbol}]" if r.symbol else ""
            lines.append(f"- [{sev}] {r.rule_id}{sym}: {r.message[:80]}")
        lines.append("如需深度风控体检，请调用 skill_risk_checkup。")
        return "\n".join(lines)

    async def _tool_sentiment(self, args: dict[str, Any]) -> str:
        """读取市场/行业/个股情绪数据。"""
        from stockresearch.services.sentiment import SentimentService

        scope = str(args.get("scope", "market")).strip().lower()
        service = SentimentService()
        if scope == "stock":
            symbol = str(args.get("symbol", "")).strip()
            if not symbol:
                return "请提供 symbol 参数（6位股票代码）"
            name = str(args.get("name", "")).strip() or resolve_name(symbol)
            result = await service.compute_stock_sentiment(symbol, name)
        elif scope == "sector":
            sector = str(args.get("sector", "")).strip()
            if not sector:
                return "请提供 sector 参数（板块名称）"
            result = await service.compute_sector_sentiment(sector)
        else:
            result = await service.compute_market_sentiment()

        self._cards.append(
            {
                "type": "sentiment",
                "data": {
                    "scope": scope,
                    "score": result.score,
                    "label": result.label,
                    "drivers": [
                        {"label": d.label, "value": d.value, "impact": d.impact}
                        for d in result.drivers
                    ],
                },
            }
        )
        lines = [f"情绪指数: {result.score:.0f} ({result.label})"]
        if result.drivers:
            lines.append("驱动因素:")
            for d in result.drivers[:5]:
                lines.append(f"  - {d.label}: {d.value} ({d.impact})")
        return "\n".join(lines)


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


def _reply_from_cards(cards: list[dict[str, Any]]) -> str | None:
    """Build a user-facing reply when the LLM returns empty but tools already produced cards."""
    for card in reversed(cards):
        ctype = card.get("type")
        data = card.get("data")
        if not isinstance(data, dict):
            continue
        if ctype == "research":
            summary = str(data.get("summary", "")).strip()
            if summary:
                return summary
            name = str(data.get("name", ""))
            symbol = str(data.get("symbol", ""))
            score = data.get("composite_score")
            if name and symbol and score is not None:
                return f"{name}({symbol}) 投研已完成，综合评分 {score}/10。"
        if ctype == "text":
            content = str(data.get("content", "")).strip()
            if content:
                return content
    return None


def _clean_reply(text: str) -> str:
    """Clean LLM response when no tool calls are found — just return the text as-is."""
    # Remove any stray ```tool blocks that weren't parsed
    import re

    text = re.sub(r"```tool\s*.*?```", "", text, flags=re.DOTALL).strip()
    return text if text else "抱歉，我暂时无法回答，请稍后再试。"
