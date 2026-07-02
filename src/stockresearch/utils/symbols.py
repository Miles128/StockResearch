"""Symbol extraction and stock reference detection."""

from __future__ import annotations

import re

from stockresearch.core.constants import NAME_TO_SYMBOL, SYMBOL_NAMES

STOCK_CODE_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")

STOCK_NAME_ALTERNATION = (
    r"茅台|宁德时代|宁德|比亚迪|招商银行|招行|平安银行|中国平安|平安|中芯国际|中芯"
    r"|腾讯|阿里|阿里巴巴|五粮液|泸州老窖|恒瑞医药|美的|格力"
    r"|工商银行|建行|农行|中行|交行|兴业|浦发|民生"
    r"|海康威视|药明康德|隆基绿能|隆基|通威|紫金矿业|长江电力"
    r"|中国移动|中国石油|中国石化|神华|中远海控|徐工机械|徐工|招商证券|中信证券|中信"
)

STOCK_NAME_RE = re.compile(STOCK_NAME_ALTERNATION)

_SYMBOL_PATTERN = re.compile(r"\b([036]\d{5})\b")


def extract_symbols(text: str) -> list[str]:
    found: set[str] = set()
    for match in _SYMBOL_PATTERN.findall(text):
        found.add(match)
    for match in STOCK_CODE_RE.findall(text):
        found.add(match)
    for name, symbol in NAME_TO_SYMBOL.items():
        if name in text:
            found.add(symbol)
    return sorted(found)


def has_stock_reference(message: str) -> bool:
    if STOCK_CODE_RE.search(message):
        return True
    return bool(STOCK_NAME_RE.search(message))


def resolve_name(symbol: str) -> str:
    if symbol in SYMBOL_NAMES:
        return SYMBOL_NAMES[symbol]
    return symbol
