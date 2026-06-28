"""LLM-driven intent router with keyword fallback."""

import json
import logging

from stockresearch.agents.orchestrator.complexity import wants_deep_research, is_simple_news_explanation
from stockresearch.core.constants import (
    INTENT_CHAT,
    INTENT_COMPOSITE,
    INTENT_MARKET,
    INTENT_NEWS,
    INTENT_RESEARCH,
    INTENT_RISK,
)
from stockresearch.utils.llm import LLMClient
from stockresearch.utils.symbols import extract_symbols

logger = logging.getLogger(__name__)

_INTENT_ROUTER_SYSTEM = (
    "你是「StockResearch」的意图识别模块，负责判断用户消息的意图。\n\n"
    "意图分类（必须严格按以下定义选择）：\n"
    "- market: 用户询问大盘走势、市场整体情况、板块轮动、指数行情等宏观/市场层面问题\n"
    "- research: 用户想分析某只具体股票的基本面、技术面、估值等\n"
    "- news: 用户要看新闻、快讯，或解释/解读某条新闻、消息含义及对持仓影响\n"
    "- risk: 用户关心持仓风险、止损、仓位、回撤等风控问题\n"
    "- composite: 用户同时需要个股投研分析和风控体检\n"
    "- chat: 非金融问题、闲聊、知识问答\n\n"
    "关键区分规则：\n"
    "- 「大盘/市场/股市/指数/行情/走势/板块/A股」→ market\n"
    "- 「某只股票+分析/研究/怎么样」→ research\n"
    "- 「新闻/快讯/消息/发生了什么/解释这条新闻/对持仓有什么影响」→ news\n"
    "- 「风险/止损/仓位/体检/安全」→ risk\n"
    "- 非金融话题 → chat\n\n"
    "请以 JSON 格式回复：\n"
    '{"intent": "意图", "symbols": ["股票代码"], "sectors": ["行业"], "confidence": "high/medium/low"}\n\n'
    "示例：\n"
    "用户：中国股市未来走势如何\n"
    '{"intent": "market", "symbols": [], "sectors": [], "confidence": "high"}\n\n'
    "用户：大盘今天怎么样\n"
    '{"intent": "market", "symbols": [], "sectors": [], "confidence": "high"}\n\n'
    "用户：半导体板块最近怎么样\n"
    '{"intent": "market", "symbols": [], "sectors": ["半导体"], "confidence": "high"}\n\n'
    "用户：帮我分析一下贵州茅台\n"
    '{"intent": "research", "symbols": ["600519"], "sectors": [], "confidence": "high"}\n\n'
    "用户：宁德时代值不值得买\n"
    '{"intent": "research", "symbols": ["300750"], "sectors": [], "confidence": "high"}\n\n'
    "用户：今天有什么新闻\n"
    '{"intent": "news", "symbols": [], "sectors": [], "confidence": "high"}\n\n'
    "用户：我的持仓风险大吗\n"
    '{"intent": "risk", "symbols": [], "sectors": [], "confidence": "high"}\n\n'
    "用户：今天天气怎么样\n"
    '{"intent": "chat", "symbols": [], "sectors": [], "confidence": "high"}\n\n'
    "只回复 JSON，不要其他内容。"
)

_VALID_INTENTS = {INTENT_MARKET, INTENT_NEWS, INTENT_RESEARCH, INTENT_RISK, INTENT_COMPOSITE, INTENT_CHAT}

_MARKET_PATTERNS = ("大盘", "市场", "股市", "指数", "行情", "走势", "板块", "A股", "牛市", "熊市", "震荡", "反弹", "回调", "上涨", "下跌", "涨跌")
_NEWS_PATTERNS = ("新闻", "快讯", "怎么了", "发生", "消息", "公告", "为什么跌", "为什么涨")
_RESEARCH_PATTERNS = ("分析", "研究", "值不值得", "怎么样", "看看", "评", "基本面", "技术面")
_RISK_PATTERNS = ("风险", "止损", "仓位", "体检", "回撤", "持仓", "危险")
_EDU_PATTERNS = ("什么是", "怎么", "解释", "含义", "MACD", "K线", "财报")


def _keyword_fallback(message: str) -> tuple[str, list[str], list[str]]:
    text = message.strip()
    symbols = extract_symbols(text)

    if any(p in text for p in _RISK_PATTERNS):
        if any(p in text for p in _RESEARCH_PATTERNS):
            return INTENT_COMPOSITE, symbols, []
        return INTENT_RISK, symbols, []

    if is_simple_news_explanation(text):
        return INTENT_NEWS, symbols, []

    if any(p in text for p in _NEWS_PATTERNS):
        return INTENT_NEWS, symbols, []

    if symbols and any(p in text for p in _RESEARCH_PATTERNS):
        return INTENT_RESEARCH, symbols, []

    if any(p in text for p in _MARKET_PATTERNS):
        if any(p in text for p in _RESEARCH_PATTERNS) or wants_deep_research(text):
            return INTENT_MARKET, symbols, []
        return INTENT_CHAT, symbols, []

    if any(p in text for p in _RESEARCH_PATTERNS):
        return INTENT_RESEARCH, symbols, []

    if any(p in text for p in _EDU_PATTERNS):
        return INTENT_CHAT, symbols, []

    if symbols:
        return INTENT_CHAT, symbols, []

    return INTENT_CHAT, symbols, []


async def route_intent(message: str, llm: LLMClient) -> tuple[str, list[str], list[str]]:
    try:
        response = await llm.complete(_INTENT_ROUTER_SYSTEM, message)
        data = json.loads(response.strip())
        intent = data.get("intent", INTENT_CHAT)
        if intent not in _VALID_INTENTS:
            logger.warning("LLM returned invalid intent '%s', defaulting to chat", intent)
            intent = INTENT_CHAT
        symbols = data.get("symbols", [])
        if not isinstance(symbols, list):
            symbols = []
        symbols = [s for s in symbols if isinstance(s, str)]
        if not symbols:
            symbols = extract_symbols(message)
        sectors = data.get("sectors", [])
        if not isinstance(sectors, list):
            sectors = []
        sectors = [s for s in sectors if isinstance(s, str)]
        return intent, symbols, sectors
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("LLM intent routing failed, falling back to keywords: %s", exc)
        return _keyword_fallback(message)
