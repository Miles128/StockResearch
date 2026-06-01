"""LLM-driven intent router with keyword fallback."""

import json
import logging

from invesbao.core.constants import (
    INTENT_CHAT,
    INTENT_COMPOSITE,
    INTENT_NEWS,
    INTENT_RESEARCH,
    INTENT_RISK,
)
from invesbao.utils.llm import LLMClient
from invesbao.utils.symbols import extract_symbols

logger = logging.getLogger(__name__)

_INTENT_ROUTER_SYSTEM = (
    "你是「投小宝」的意图识别模块。"
    "根据用户消息，判断用户意图并提取相关股票代码。\n\n"
    "可能的意图：\n"
    "- news: 用户想看新闻、快讯、了解发生了什么\n"
    "- research: 用户想分析某只股票的基本面、技术面等\n"
    "- risk: 用户关心持仓风险、止损、仓位等\n"
    "- composite: 用户同时需要投研分析和风控体检\n"
    "- chat: 闲聊、知识问答、其他\n\n"
    "请以 JSON 格式回复：\n"
    '{"intent": "意图", "symbols": ["股票代码"], "confidence": "high/medium/low"}\n\n'
    "示例：\n"
    "用户：帮我分析一下贵州茅台\n"
    '{"intent": "research", "symbols": ["600519"], "confidence": "high"}\n\n'
    "用户：今天市场怎么了\n"
    '{"intent": "news", "symbols": [], "confidence": "high"}\n\n'
    "用户：我的持仓安全吗\n"
    '{"intent": "risk", "symbols": [], "confidence": "high"}\n\n'
    "用户：帮我分析持仓股票并检查风险\n"
    '{"intent": "composite", "symbols": [], "confidence": "high"}\n\n'
    "只回复 JSON，不要其他内容。"
)

_VALID_INTENTS = {INTENT_NEWS, INTENT_RESEARCH, INTENT_RISK, INTENT_COMPOSITE, INTENT_CHAT}

_NEWS_PATTERNS = ("新闻", "快讯", "怎么了", "发生", "消息", "公告", "为什么跌", "为什么涨")
_RESEARCH_PATTERNS = ("分析", "研究", "值不值得", "怎么样", "看看", "评", "基本面", "技术面")
_RISK_PATTERNS = ("风险", "止损", "仓位", "体检", "回撤", "持仓", "危险")
_EDU_PATTERNS = ("什么是", "怎么", "解释", "含义", "MACD", "K线", "财报")


def _keyword_fallback(message: str) -> tuple[str, list[str]]:
    text = message.strip()
    symbols = extract_symbols(text)

    if any(p in text for p in _RISK_PATTERNS):
        if any(p in text for p in _RESEARCH_PATTERNS):
            return INTENT_COMPOSITE, symbols
        return INTENT_RISK, symbols

    if any(p in text for p in _NEWS_PATTERNS):
        return INTENT_NEWS, symbols

    if any(p in text for p in _RESEARCH_PATTERNS):
        return INTENT_RESEARCH, symbols

    if any(p in text for p in _EDU_PATTERNS):
        return INTENT_CHAT, symbols

    if symbols:
        return INTENT_RESEARCH, symbols

    return INTENT_CHAT, symbols


async def route_intent(message: str, llm: LLMClient) -> tuple[str, list[str]]:
    try:
        response = await llm.complete(_INTENT_ROUTER_SYSTEM, message)
        data = json.loads(response.strip())
        intent = data.get("intent", INTENT_CHAT)
        if intent not in _VALID_INTENTS:
            intent = INTENT_CHAT
        symbols = data.get("symbols", [])
        if not isinstance(symbols, list):
            symbols = []
        symbols = [s for s in symbols if isinstance(s, str)]
        if not symbols:
            symbols = extract_symbols(message)
        return intent, symbols
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("LLM intent routing failed, falling back to keywords: %s", exc)
        return _keyword_fallback(message)
