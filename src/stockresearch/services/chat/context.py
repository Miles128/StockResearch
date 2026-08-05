"""Build long-term and user-scoped chat context blocks from prompts/."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from stockresearch.agents.orchestrator.complexity import (
    has_stock_reference,
    is_holdings_intent,
    is_market_scope,
    is_risk_intent,
    is_vague_query,
)
from stockresearch.data.providers.market import QuoteProvider
from stockresearch.prompts import load_prompt
from stockresearch.services.provider_cache_policy import quote_cache_ttl_seconds
from stockresearch.utils.format import arrow_for_change

if TYPE_CHECKING:
    from stockresearch.core.schemas import ChatUserContext, ModeSettingsOut
    from stockresearch.db.models import Holding
    from stockresearch.services.chat.scope import ChatContextScope

logger = logging.getLogger(__name__)

_KIND_LABELS: dict[str, str] = {
    "focus": "焦点视图",
    "risk": "风控视图",
    "news": "资讯视图",
    "stock": "个股",
    "report": "研报",
}

_MODE_LABELS: dict[str, str] = {
    "advisor": "个人投顾",
    "research": "专家投研",
}

_MODE_HINTS: dict[str, str] = {
    "advisor": "侧重持仓相关解释与风险感知",
    "research": "侧重多维数据与专业口径",
}

_MODE_HINTS_NEUTRAL: dict[str, str] = {
    "advisor": "用通俗语言解读行情与新闻，勿主动展开持仓组合分析",
    "research": "侧重多维数据与专业口径，勿主动展开持仓组合分析",
}

_READING_LABELS: dict[str, str] = {
    "friendly": "友善白话",
    "standard": "标准",
    "professional": "专业",
}

_HOLDINGS_DEFERRED_SUMMARY = "（本轮未询问持仓，勿主动结合或展开持仓分析）"
_HOLDINGS_DEFERRED_QUOTES = "（未注入；用户未问持仓时不要调用持仓相关工具）"


def should_include_holdings_context(
    message: str,
    user_context: ChatUserContext | None,
) -> bool:
    """Inject portfolio holdings only when the user or UI context calls for it."""
    msg = message.strip()
    if not msg:
        return False
    if is_holdings_intent(msg):
        return True
    if user_context and user_context.kind == "risk":
        if is_market_scope(msg) or (has_stock_reference(msg) and not is_holdings_intent(msg)):
            return False
        if is_vague_query(msg) or is_risk_intent(msg):
            return True
    if user_context and user_context.kind in ("stock", "focus") and user_context.symbol:
        if (is_vague_query(msg) or is_risk_intent(msg)) and not is_holdings_intent(msg):
            return False
    if "持仓" in msg and ("影响" in msg or "关系" in msg or "怎么办" in msg):
        return True
    if is_risk_intent(msg) and not has_stock_reference(msg) and not is_market_scope(msg):
        return True
    return False


def _holdings_summary(holdings: list[Holding]) -> str:
    if not holdings:
        return "当前无持仓记录"
    parts = [f"{h.name}({h.symbol})·{h.sector}" for h in holdings[:8]]
    suffix = f" 等共 {len(holdings)} 只" if len(holdings) > 8 else f" 共 {len(holdings)} 只"
    return "；".join(parts) + suffix


def _format_quote_line(holding: Holding, price: float, change_pct: float) -> str:
    arrow = arrow_for_change(change_pct)
    return f"{holding.name}({holding.symbol}) 现价{price:.2f} {arrow}{change_pct:+.2f}%"


async def _holdings_quotes_block(
    holdings: list[Holding],
    *,
    mode_settings: ModeSettingsOut,
) -> str:
    if not holdings:
        return "无持仓"
    try:
        provider = QuoteProvider()
        ttl = quote_cache_ttl_seconds(mode_settings)
        quotes = await provider.get_quotes(
            [h.symbol for h in holdings],
            cache_ttl_seconds=ttl,
        )
    except Exception:
        logger.warning("Failed to load cached holdings quotes", exc_info=True)
        return "暂无缓存行情（前端加载持仓后会写入；收盘后不再刷新）"
    if not quotes:
        return "暂无缓存行情（前端加载持仓后会写入；收盘后不再刷新）"
    lines: list[str] = []
    for holding in holdings:
        quote = quotes.get(holding.symbol)
        if quote is None:
            continue
        lines.append(_format_quote_line(holding, quote.price, quote.change_pct))
    if not lines:
        return "暂无缓存行情（前端加载持仓后会写入；收盘后不再刷新）"
    return "；".join(lines)


async def build_long_term_context(
    *,
    mode_settings: ModeSettingsOut,
    holdings: list[Holding],
    message: str = "",
    user_context: ChatUserContext | None = None,
    scope: ChatContextScope | None = None,
) -> str:
    """Render the hidden long-term system context (not shown in UI)."""
    include_holdings = (
        scope.include_holdings
        if scope is not None
        else should_include_holdings_context(message, user_context)
    )
    template = load_prompt("long_term_context.md")
    mode = mode_settings.mode
    advisor_block = ""
    if mode == "advisor":
        advisor_block = load_prompt("advisor_plain_language.md").strip()
    if include_holdings:
        holdings_summary = _holdings_summary(holdings)
        holdings_quotes = await _holdings_quotes_block(holdings, mode_settings=mode_settings)
        mode_hint = _MODE_HINTS.get(mode, "")
    else:
        holdings_summary = _HOLDINGS_DEFERRED_SUMMARY
        holdings_quotes = _HOLDINGS_DEFERRED_QUOTES
        mode_hint = _MODE_HINTS_NEUTRAL.get(mode, _MODE_HINTS.get(mode, ""))
    return template.format(
        mode_label=_MODE_LABELS.get(mode, mode),
        mode_hint=mode_hint,
        reading_mode_label=_READING_LABELS.get(
            mode_settings.reading_mode, mode_settings.reading_mode
        ),
        holdings_summary=holdings_summary,
        holdings_quotes=holdings_quotes,
        debate_label="开启" if mode_settings.enable_debate else "关闭",
        glossary_label="开启" if mode_settings.enable_glossary else "关闭",
        advisor_style_block=advisor_block,
    )


def format_user_context_block(ctx: ChatUserContext | None) -> str:
    """Render structured user context for injection alongside the user message."""
    if ctx is None:
        return ""
    template = load_prompt("user_context.md")
    context_rules = load_prompt("context_rules.md")
    detail_block = f"详情：{ctx.detail}" if ctx.detail else ""
    symbol_block = f"代码：{ctx.symbol}" if ctx.symbol else ""
    metadata_lines: list[str] = []
    if ctx.metadata:
        for key, value in ctx.metadata.items():
            if value:
                metadata_lines.append(f"- {key}：{value}")
    metadata_block = "补充：\n" + "\n".join(metadata_lines) if metadata_lines else ""
    return template.format(
        context_rules=context_rules,
        kind_label=_KIND_LABELS.get(ctx.kind, ctx.kind),
        label=ctx.label,
        detail_block=detail_block,
        symbol_block=symbol_block,
        metadata_block=metadata_block,
    ).strip()
