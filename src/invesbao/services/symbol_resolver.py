"""Resolve A-share symbol or name — local maps only, no AkShare on request path."""

import re

from invesbao.core.constants import NAME_TO_SYMBOL, SYMBOL_NAMES
from invesbao.core.exceptions import ValidationError
from invesbao.services.stock_lookup import clean_stock_query, resolve_local

_SYMBOL_RE = re.compile(r"^\d{6}$")


def resolve_stock_query(query: str) -> tuple[str, str]:
    """Resolve user input (6-digit code or Chinese name) to (symbol, name)."""
    raw = query.strip()
    if not raw:
        raise ValidationError("请输入股票代码或名称")

    if _SYMBOL_RE.match(raw):
        return resolve_local(raw)

    if raw in NAME_TO_SYMBOL:
        symbol = NAME_TO_SYMBOL[raw]
        return symbol, SYMBOL_NAMES.get(symbol, raw)

    return resolve_local(raw)
