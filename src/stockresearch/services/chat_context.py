"""Build long-term and user-scoped chat context blocks from prompts/."""

from __future__ import annotations

import logging

from stockresearch.core.schemas import ChatUserContext, ModeSettingsOut
from stockresearch.data.providers.market import QuoteProvider
from stockresearch.db.models import Holding
from stockresearch.prompts import load_prompt
from stockresearch.services.provider_cache_policy import quote_cache_ttl_seconds

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

_READING_LABELS: dict[str, str] = {
    "friendly": "友善白话",
    "standard": "标准",
    "professional": "专业",
}


def _holdings_summary(holdings: list[Holding]) -> str:
    if not holdings:
        return "当前无持仓记录"
    parts = [f"{h.name}({h.symbol})·{h.sector}" for h in holdings[:8]]
    suffix = f" 等共 {len(holdings)} 只" if len(holdings) > 8 else f" 共 {len(holdings)} 只"
    return "；".join(parts) + suffix


def _format_quote_line(holding: Holding, price: float, change_pct: float) -> str:
    arrow = "↑" if change_pct > 0 else "↓" if change_pct < 0 else "→"
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
) -> str:
    """Render the hidden long-term system context (not shown in UI)."""
    template = load_prompt("long_term_context.md")
    mode = mode_settings.mode
    advisor_block = ""
    if mode == "advisor":
        advisor_block = load_prompt("advisor_plain_language.md").strip()
    holdings_quotes = await _holdings_quotes_block(holdings, mode_settings=mode_settings)
    return template.format(
        mode_label=_MODE_LABELS.get(mode, mode),
        mode_hint=_MODE_HINTS.get(mode, ""),
        reading_mode_label=_READING_LABELS.get(mode_settings.reading_mode, mode_settings.reading_mode),
        holdings_summary=_holdings_summary(holdings),
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
    detail_block = f"详情：{ctx.detail}" if ctx.detail else ""
    symbol_block = f"代码：{ctx.symbol}" if ctx.symbol else ""
    metadata_lines: list[str] = []
    if ctx.metadata:
        for key, value in ctx.metadata.items():
            if value:
                metadata_lines.append(f"- {key}：{value}")
    metadata_block = "补充：\n" + "\n".join(metadata_lines) if metadata_lines else ""
    return template.format(
        kind_label=_KIND_LABELS.get(ctx.kind, ctx.kind),
        label=ctx.label,
        detail_block=detail_block,
        symbol_block=symbol_block,
        metadata_block=metadata_block,
    ).strip()
