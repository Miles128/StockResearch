"""Unified chat context scope — intent-routed holdings injection, subject resolution, risk routing."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from stockresearch.agents.orchestrator.complexity import (
    is_holdings_intent,
    is_risk_intent,
)
from stockresearch.core.schemas import ChatUserContext, ModeSettingsOut
from stockresearch.db.models import Holding
from stockresearch.services.chat.context import (
    build_long_term_context,
    format_user_context_block,
    should_include_holdings_context,
)
from stockresearch.services.chat.intent import ChatIntent, classify_chat_intent
from stockresearch.utils.llm import LLMClient
from stockresearch.utils.symbols import (
    extract_symbols,
    has_stock_reference,
    normalize_symbol,
    resolve_name,
)

logger = logging.getLogger(__name__)

PORTFOLIO_TOOL_NAMES: frozenset[str] = frozenset(
    {"get_sector_holdings", "get_portfolio_summary", "get_risk_summary", "skill_risk_checkup"},
)

NewsScope = Literal["market", "industry", "personalized", "symbol"]

# 主意图 → 新闻域(spec §2 推导表)
_NEWS_SCOPE_BY_INTENT: dict[str, NewsScope] = {
    "market": "market",
    "industry": "industry",
    "portfolio": "personalized",
    "stock": "symbol",
    "general": "personalized",
}


@dataclass(frozen=True)
class ChatContextScope:
    """Single source of truth for portfolio vs subject scoping in one chat turn."""

    message: str
    intent: ChatIntent
    include_holdings: bool
    holdings: list[Holding]
    skill_holdings: list[Holding]
    portfolio_tools: bool
    run_portfolio_risk_shortcut: bool
    news_scope: NewsScope
    secondary_block: str
    subject_symbol: str | None
    subject_name: str | None


def resolve_subject_symbol(
    message: str,
    *,
    user_context: ChatUserContext | None = None,
    confirmed_symbol: str | None = None,
    confirmed_name: str | None = None,
) -> tuple[str | None, str | None]:
    """Resolve discussion subject: confirmed > message > UI context."""
    if confirmed_symbol:
        sym = normalize_symbol(confirmed_symbol)
        return sym, confirmed_name or resolve_name(sym)

    codes = extract_symbols(message)
    if codes:
        sym = codes[0]
        return sym, resolve_name(sym)

    if user_context and user_context.symbol:
        sym = user_context.symbol.strip()
        if sym:
            label = user_context.label or ""
            name_match = label.split()[0] if label else resolve_name(sym)
            return sym, name_match

    return None, None


def should_run_portfolio_risk_shortcut(
    message: str,
    user_context: ChatUserContext | None,
    *,
    include_holdings: bool,
) -> bool:
    """Full portfolio risk checkup only when scope includes holdings and intent is portfolio-level."""
    msg = message.strip()
    if not msg or not include_holdings or not is_risk_intent(msg):
        return False
    if has_stock_reference(msg) and not is_holdings_intent(msg):
        return False
    return True


def _derive_include_holdings(
    intent: ChatIntent,
    msg: str,
    user_context: ChatUserContext | None,
) -> bool:
    """按意图推导是否注入持仓:market/industry 完全隔离,stock/general 维持现有判定。"""
    if intent.primary == "portfolio":
        return True
    if intent.primary in ("market", "industry"):
        return False
    return should_include_holdings_context(msg, user_context)


_SECONDARY_TITLES: dict[str, str] = {
    "market": "【附：大盘概况】",
    "portfolio": "【附：你的持仓概况】",
    "industry": "【附：板块概况】",
}

# 次要域附录长度上限(不含标题行):market ≤6 行指数摘要;portfolio ≤6 行持仓摘要;industry ≤4 行板块摘要
_SECONDARY_MAX_LINES: dict[str, int] = {"market": 6, "portfolio": 6, "industry": 4}


async def _market_secondary_block(*, mode_settings: ModeSettingsOut | None) -> str:
    from stockresearch.data.providers.market_overview import MarketOverviewProvider
    from stockresearch.services.provider_cache_policy import quote_cache_ttl_seconds

    provider = MarketOverviewProvider()
    overview = await provider.get_overview(cache_ttl_seconds=quote_cache_ttl_seconds(mode_settings))
    limit = _SECONDARY_MAX_LINES["market"]
    lines: list[str] = []
    for idx in overview.indices[: limit - 1]:
        arrow = "↑" if idx.change_pct > 0 else "↓" if idx.change_pct < 0 else "→"
        lines.append(f"{idx.name}: {idx.price:.2f} {arrow} {idx.change_pct:+.2f}%")
    if overview.northbound_net_yi is not None:
        direction = "净流入" if overview.northbound_net_yi > 0 else "净流出"
        lines.append(f"北向资金: {abs(overview.northbound_net_yi):.1f}亿{direction}")
    if not lines:
        return ""
    return _SECONDARY_TITLES["market"] + "\n" + "\n".join(lines[:limit])


def _portfolio_secondary_block(holdings: list[Holding]) -> str:
    if not holdings:
        return ""
    limit = _SECONDARY_MAX_LINES["portfolio"]
    lines = [f"- {h.name}({h.symbol}) {h.quantity}股 · {h.sector}" for h in holdings[: limit - 1]]
    if len(holdings) > len(lines):
        lines.append(f"…等共 {len(holdings)} 只")
    return _SECONDARY_TITLES["portfolio"] + "\n" + "\n".join(lines)


def _industry_secondary_block(intent: ChatIntent, holdings: list[Holding]) -> str:
    sector = intent.subject_industry
    if not sector:
        return ""
    rows = [h for h in holdings if sector in (h.sector or "")]
    if not rows:
        return ""
    limit = _SECONDARY_MAX_LINES["industry"]
    lines = [f"- {h.name}({h.symbol}) {h.quantity}股" for h in rows[:limit]]
    return f"{_SECONDARY_TITLES['industry']}（{sector}）\n" + "\n".join(lines)


async def _build_secondary_block(
    intent: ChatIntent,
    holdings: list[Holding],
    *,
    mode_settings: ModeSettingsOut | None,
) -> str:
    """组装次要域附录块(每轮至多 1 个次要域;任何失败降级为空串,绝不影响主流程)。"""
    if not intent.secondary:
        return ""
    domain = intent.secondary[0]
    try:
        if domain == "market":
            return await _market_secondary_block(mode_settings=mode_settings)
        if domain == "portfolio":
            return _portfolio_secondary_block(holdings)
        if domain == "industry":
            return _industry_secondary_block(intent, holdings)
    except Exception:
        logger.warning("secondary context block failed domain=%s", domain, exc_info=True)
    return ""


async def build_chat_context_scope(
    message: str,
    holdings: list[Holding],
    user_context: ChatUserContext | None,
    *,
    llm: LLMClient,
    mode_settings: ModeSettingsOut | None = None,
    confirmed_symbol: str | None = None,
    confirmed_name: str | None = None,
) -> ChatContextScope:
    """唯一决策点:意图分类 → 按域推导持仓注入/新闻域/SkillRunner 持仓/次要域附录。"""
    msg = message.strip()
    intent = await classify_chat_intent(msg, llm)
    include_holdings = _derive_include_holdings(intent, msg, user_context)
    scoped = list(holdings) if include_holdings else []
    subject_symbol, subject_name = resolve_subject_symbol(
        msg,
        user_context=user_context,
        confirmed_symbol=confirmed_symbol,
        confirmed_name=confirmed_name,
    )
    secondary_block = await _build_secondary_block(intent, holdings, mode_settings=mode_settings)
    return ChatContextScope(
        message=msg,
        intent=intent,
        include_holdings=include_holdings,
        holdings=scoped,
        skill_holdings=list(holdings) if intent.primary in ("portfolio", "stock") else [],
        portfolio_tools=include_holdings,
        run_portfolio_risk_shortcut=should_run_portfolio_risk_shortcut(
            msg,
            user_context,
            include_holdings=include_holdings,
        ),
        news_scope=_NEWS_SCOPE_BY_INTENT[intent.primary],
        secondary_block=secondary_block,
        subject_symbol=subject_symbol,
        subject_name=subject_name,
    )


@dataclass(frozen=True)
class PreparedChatTurn:
    message: str
    scope: ChatContextScope
    long_term_context: str
    user_context_text: str
    holdings: list[Holding]


async def prepare_chat_turn(
    *,
    mode_settings: ModeSettingsOut,
    holdings: list[Holding],
    message: str,
    user_context: ChatUserContext | None,
    llm: LLMClient,
    confirmed_symbol: str | None = None,
    confirmed_name: str | None = None,
) -> PreparedChatTurn:
    """Build scope + prompt blocks once per turn (stream and sync paths)."""
    scope = await build_chat_context_scope(
        message,
        holdings,
        user_context,
        llm=llm,
        mode_settings=mode_settings,
        confirmed_symbol=confirmed_symbol,
        confirmed_name=confirmed_name,
    )
    long_term_context = await build_long_term_context(
        mode_settings=mode_settings,
        holdings=holdings,
        message=scope.message,
        user_context=user_context,
        scope=scope,
    )
    return PreparedChatTurn(
        message=scope.message,
        scope=scope,
        long_term_context=long_term_context,
        user_context_text=format_user_context_block(user_context),
        holdings=holdings,
    )
