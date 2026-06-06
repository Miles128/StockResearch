"""Resolve stock references inside natural-language chat messages."""

import re
from dataclasses import dataclass

from stockresearch.core.constants import NAME_TO_SYMBOL
from stockresearch.services.stock_lookup import STOCK_ALIASES, StockLookupResult, lookup_stock
from stockresearch.utils.llm import LLMClient
from stockresearch.utils.symbols import resolve_name

_STOCK_CODE_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")
_STOCK_NAME_RE = re.compile(
    r"(茅台|宁德时代|宁德|比亚迪|招商银行|招行|平安银行|中国平安|平安|中芯国际|中芯"
    r"|腾讯|阿里|阿里巴巴|五粮液|泸州老窖|恒瑞医药|美的|格力"
    r"|工商银行|建行|农行|中行|交行|兴业|浦发|民生"
    r"|海康威视|药明康德|隆基绿能|隆基|通威|紫金矿业|长江电力"
    r"|中国移动|中国石油|中国石化|神华|中远海控|徐工机械|徐工|招商证券|中信证券|中信)"
)


@dataclass(frozen=True)
class ResolvedStock:
    symbol: str
    name: str


def match_holding_in_message(message: str, holdings: list[object]) -> ResolvedStock | None:
    """Match a user holding name/symbol mentioned in the message."""
    text = message.strip()
    if not text or not holdings:
        return None
    for holding in holdings:
        symbol = str(getattr(holding, "symbol", "") or "")
        name = str(getattr(holding, "name", "") or "")
        if symbol and symbol in text:
            return ResolvedStock(symbol=symbol, name=name or resolve_name(symbol))
        if name and name in text:
            return ResolvedStock(symbol=symbol, name=name)
    return None


def extract_stock_query(message: str) -> str | None:
    """Pull the most likely stock token from a chat message."""
    text = message.strip()
    if not text:
        return None

    code_match = _STOCK_CODE_RE.search(text)
    if code_match:
        return code_match.group(1)

    for name in sorted(NAME_TO_SYMBOL.keys(), key=len, reverse=True):
        if name in text:
            return name

    for alias in sorted(STOCK_ALIASES.keys(), key=len, reverse=True):
        if alias in text:
            return alias

    name_match = _STOCK_NAME_RE.search(text)
    if name_match:
        return name_match.group(1)

    return None


def stock_choice_card(original_message: str, result: StockLookupResult) -> dict[str, object]:
    return {
        "type": "stock_choice",
        "data": {
            "message": result.message,
            "status": result.status,
            "candidates": [
                {"symbol": c.symbol, "name": c.name} for c in result.candidates
            ],
            "original_message": original_message,
        },
    }


async def resolve_message_stock(
    message: str,
    llm: LLMClient | None = None,
    *,
    confirmed_symbol: str | None = None,
    confirmed_name: str | None = None,
) -> ResolvedStock | StockLookupResult:
    if confirmed_symbol:
        symbol = confirmed_symbol.zfill(6)[-6:]
        name = confirmed_name or resolve_name(symbol)
        return ResolvedStock(symbol=symbol, name=name)

    query = extract_stock_query(message) or message.strip()
    result = await lookup_stock(query, llm=llm)
    if result.status == "confirmed" and result.symbol and result.name:
        return ResolvedStock(symbol=result.symbol, name=result.name)
    return result
