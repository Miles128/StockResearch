"""Unified chat context scope — holdings injection, subject resolution, risk routing."""

from __future__ import annotations

from dataclasses import dataclass

from stockresearch.agents.orchestrator.complexity import (
    is_holdings_intent,
    is_risk_intent,
)
from stockresearch.core.schemas import ChatUserContext, ModeSettingsOut
from stockresearch.db.models import Holding
from stockresearch.services.chat_context import (
    build_long_term_context,
    format_user_context_block,
    should_include_holdings_context,
)
from stockresearch.utils.symbols import extract_symbols, has_stock_reference, resolve_name

PORTFOLIO_TOOL_NAMES: frozenset[str] = frozenset(
    {"get_sector_holdings", "skill_risk_checkup"},
)


@dataclass(frozen=True)
class ChatContextScope:
    """Single source of truth for portfolio vs subject scoping in one chat turn."""

    message: str
    include_holdings: bool
    holdings: list[Holding]
    portfolio_tools: bool
    run_portfolio_risk_shortcut: bool
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
        sym = confirmed_symbol.zfill(6)[-6:]
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


def build_chat_context_scope(
    message: str,
    holdings: list[Holding],
    user_context: ChatUserContext | None,
    *,
    confirmed_symbol: str | None = None,
    confirmed_name: str | None = None,
) -> ChatContextScope:
    msg = message.strip()
    include_holdings = should_include_holdings_context(msg, user_context)
    scoped = list(holdings) if include_holdings else []
    subject_symbol, subject_name = resolve_subject_symbol(
        msg,
        user_context=user_context,
        confirmed_symbol=confirmed_symbol,
        confirmed_name=confirmed_name,
    )
    return ChatContextScope(
        message=msg,
        include_holdings=include_holdings,
        holdings=scoped,
        portfolio_tools=include_holdings,
        run_portfolio_risk_shortcut=should_run_portfolio_risk_shortcut(
            msg,
            user_context,
            include_holdings=include_holdings,
        ),
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
    confirmed_symbol: str | None = None,
    confirmed_name: str | None = None,
) -> PreparedChatTurn:
    """Build scope + prompt blocks once per turn (stream and sync paths)."""
    scope = build_chat_context_scope(
        message,
        holdings,
        user_context,
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
