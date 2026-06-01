"""Symbol extraction from text."""

import re

from invesbao.core.constants import NAME_TO_SYMBOL, SYMBOL_NAMES

_SYMBOL_PATTERN = re.compile(r"\b([036]\d{5})\b")


def extract_symbols(text: str) -> list[str]:
    found: set[str] = set()
    for match in _SYMBOL_PATTERN.findall(text):
        found.add(match)
    for name, symbol in NAME_TO_SYMBOL.items():
        if name in text:
            found.add(symbol)
    return sorted(found)


def resolve_name(symbol: str) -> str:
    if symbol in SYMBOL_NAMES:
        return SYMBOL_NAMES[symbol]
    from invesbao.services.symbol_resolver import _catalog

    code_to_name, _ = _catalog()
    return code_to_name.get(symbol, symbol)
