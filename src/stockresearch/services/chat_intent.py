"""聊天意图分类 — 规则优先 + LLM 兜底的双通道分类器。

意图域:market / industry / portfolio / stock / general。
入口 `classify_chat_intent` 按「规则 → LLM → fallback」三级判定,
任何一级失败都绝不影响聊天主流程。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from stockresearch.agents.orchestrator.complexity import (
    extract_industry_sector,
    is_holdings_intent,
    is_market_scope,
    is_risk_intent,
    is_vague_query,
)
from stockresearch.agents.structured_output import extract_json_dict
from stockresearch.core.constants import NAME_TO_SYMBOL
from stockresearch.utils.symbols import extract_symbols, has_stock_reference, resolve_name

if TYPE_CHECKING:
    from stockresearch.utils.llm import LLMClient

logger = logging.getLogger(__name__)

ChatIntentKind = Literal["market", "industry", "portfolio", "stock", "general"]


@dataclass(frozen=True)
class ChatIntent:
    """单轮聊天的意图判定结果(主域 + 至多 1 个次要域)。"""

    primary: ChatIntentKind
    secondary: tuple[ChatIntentKind, ...] = ()
    subject_symbol: str | None = None
    subject_name: str | None = None
    subject_industry: str | None = None
    source: Literal["rule", "llm", "fallback"] = "rule"


# complexity.is_market_scope 未覆盖的口语化大盘问法(「今天市场」「行情如何」「A股会涨吗」)
_MARKET_EXTRA_RE = re.compile(
    r"(今天|今日|最近|近期|这周|本周).{0,4}(市场|大盘|行情|股市)"
    r"|(市场|大盘|行情|股市).{0,4}(如何|怎么样|咋样)"
    r"|a股.{0,6}(会|能|要).{0,4}(涨|跌)"
)

# 与 chat_context.should_include_holdings_context 中「持仓+影响/关系/怎么办」口径一致
_HOLDINGS_IMPACT_KEYWORDS: tuple[str, ...] = ("影响", "关系", "怎么办")

# 常用股票简称/别名 → 代码(extract_symbols 只认全名,简称在此补充解析)
_ALIAS_SYMBOLS: dict[str, str] = {
    "茅台": "600519",
    "宁德": "300750",
    "招行": "600036",
    "平安": "601318",
    "中芯": "688981",
    "隆基": "601012",
}


def _has_holdings_mention(msg: str) -> bool:
    """显式持仓提及(含「X 对持仓的影响」这类未带「我的」的说法)。"""
    if is_holdings_intent(msg):
        return True
    return "持仓" in msg and any(kw in msg for kw in _HOLDINGS_IMPACT_KEYWORDS)


def _is_market_question(msg: str) -> bool:
    return is_market_scope(msg) or bool(_MARKET_EXTRA_RE.search(msg.lower()))


def classify_by_rule(message: str) -> ChatIntent | None:
    """高置信规则分类;返回 None 表示置信不足,交 LLM 兜底。

    优先级:显式个股 > 显式持仓 > 行业 > 大盘。
    命中两个域时,高优先级为 primary,次高为 secondary(至多 1 个)。
    泛指风险提问按 portfolio 处理(保持风控体检现状路由);模糊短句判 general。
    """
    msg = message.strip()
    if not msg:
        return None

    stock = has_stock_reference(msg)
    holdings = _has_holdings_mention(msg)
    industry = extract_industry_sector(msg) if not stock else None
    market = _is_market_question(msg)

    if not stock and not holdings and industry is None and not market:
        if is_risk_intent(msg):
            return ChatIntent(primary="portfolio", source="rule")
        if is_vague_query(msg):
            return ChatIntent(primary="general", source="rule")
        return None

    primary: ChatIntentKind
    if stock:
        primary = "stock"
    elif holdings:
        primary = "portfolio"
    elif industry is not None:
        primary = "industry"
    else:
        primary = "market"

    # 次要域:主域之外再命中一个域时记录(如「大盘对持仓影响」→ portfolio + market)
    secondary: tuple[ChatIntentKind, ...] = ()
    if primary != "market" and market:
        secondary = ("market",)
    elif primary != "portfolio" and holdings:
        secondary = ("portfolio",)
    elif primary != "industry" and industry is not None:
        secondary = ("industry",)

    symbol: str | None = None
    name: str | None = None
    if stock:
        codes = extract_symbols(msg)
        if not codes:
            alias = next((sym for key, sym in _ALIAS_SYMBOLS.items() if key in msg), None)
            if alias and alias in NAME_TO_SYMBOL.values():
                codes = [alias]
        if codes:
            symbol = codes[0]
            name = resolve_name(symbol)

    return ChatIntent(
        primary=primary,
        secondary=secondary,
        subject_symbol=symbol,
        subject_name=name,
        subject_industry=industry,
        source="rule",
    )


_CLASSIFY_SYSTEM = """你是聊天意图分类器。将用户问题分类到以下主意图之一:
- market:大盘/指数/整体市场走势
- industry:某个行业或板块
- portfolio:用户自己的持仓、仓位、组合
- stock:某只具体个股
- general:闲聊或与上述均无关

只输出 JSON,不要输出任何其他内容:
{"primary": "market|industry|portfolio|stock|general", "secondary": [], "subject_symbol": null, "subject_industry": null}
其中 secondary 至多包含 1 个次要意图;subject_symbol 为 6 位股票代码(无为 null);subject_industry 为行业名(无为 null)。"""

_INTENT_KINDS: frozenset[str] = frozenset(
    {"market", "industry", "portfolio", "stock", "general"}
)


def _intent_from_dict(
    data: dict[str, object], *, source: Literal["llm"]
) -> ChatIntent | None:
    """把 LLM 返回的 JSON 校验并转成 ChatIntent;字段非法返回 None。"""
    primary = str(data.get("primary", "") or "").strip()
    if primary not in _INTENT_KINDS:
        return None
    raw_secondary = data.get("secondary") or []
    secondary: list[str] = []
    if isinstance(raw_secondary, list):
        for item in raw_secondary:
            kind = str(item).strip()
            if kind in _INTENT_KINDS and kind != primary:
                secondary.append(kind)
    symbol = data.get("subject_symbol")
    industry = data.get("subject_industry")
    return ChatIntent(
        primary=primary,  # type: ignore[arg-type]
        secondary=tuple(secondary[:1]),  # type: ignore[arg-type]
        subject_symbol=str(symbol) if symbol else None,
        subject_industry=str(industry) if industry else None,
        source=source,
    )


async def classify_by_llm(message: str, llm: "LLMClient | None") -> ChatIntent | None:
    """LLM 兜底分类;Mock 模式、llm 缺失或任何异常均返回 None。"""
    from stockresearch.utils.llm import MockLLMClient

    if llm is None or isinstance(llm, MockLLMClient):
        return None
    try:
        raw = await llm.complete(_CLASSIFY_SYSTEM, message.strip())
    except Exception:
        logger.warning("chat intent LLM classification failed", exc_info=True)
        return None
    data = extract_json_dict(raw)
    if not data:
        return None
    return _intent_from_dict(data, source="llm")


async def classify_chat_intent(
    message: str, llm: "LLMClient | None" = None
) -> ChatIntent:
    """分类入口:规则 → LLM → fallback(portfolio,保持现状行为)。"""
    intent = classify_by_rule(message)
    if intent is not None:
        return intent
    intent = await classify_by_llm(message, llm)
    if intent is not None:
        return intent
    return ChatIntent(primary="portfolio", source="fallback")
