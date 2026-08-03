"""Chat intent classifier tests — rule layer, LLM fallback layer, entry priority."""

import pytest

from stockresearch.services.chat.intent import (
    classify_by_llm,
    classify_by_rule,
    classify_chat_intent,
)
from stockresearch.utils.llm import LLMClient


class _StubLLM(LLMClient):
    """LLM stub returning a fixed reply, recording calls."""

    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.calls = 0

    async def complete(self, system: str, user: str) -> str:
        self.calls += 1
        return self._reply

    async def complete_messages(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        return self._reply


class _RaisingLLM(LLMClient):
    async def complete(self, system: str, user: str) -> str:
        raise RuntimeError("llm unavailable")

    async def complete_messages(self, messages: list[dict[str, str]]) -> str:
        raise RuntimeError("llm unavailable")


# --- rule layer: market ---


def test_rule_market_intent() -> None:
    intent = classify_by_rule("大盘走势如何")
    assert intent is not None
    assert intent.primary == "market"
    assert intent.source == "rule"


def test_rule_market_today_market() -> None:
    intent = classify_by_rule("今天市场怎么样")
    assert intent is not None
    assert intent.primary == "market"


def test_rule_market_a_share_rise() -> None:
    intent = classify_by_rule("A股会涨吗")
    assert intent is not None
    assert intent.primary == "market"


def test_rule_market_generic_hangqing() -> None:
    intent = classify_by_rule("行情如何")
    assert intent is not None
    assert intent.primary == "market"


# --- rule layer: industry ---


def test_rule_industry_intent() -> None:
    intent = classify_by_rule("半导体行业怎么看")
    assert intent is not None
    assert intent.primary == "industry"
    assert intent.subject_industry == "半导体"


# --- rule layer: portfolio ---


def test_rule_portfolio_intent() -> None:
    intent = classify_by_rule("我的持仓最近怎么样")
    assert intent is not None
    assert intent.primary == "portfolio"


def test_rule_mixed_portfolio_market() -> None:
    intent = classify_by_rule("大盘对持仓影响")
    assert intent is not None
    assert intent.primary == "portfolio"
    assert intent.secondary == ("market",)


# --- rule layer: stock ---


def test_rule_stock_intent_by_code() -> None:
    intent = classify_by_rule("600519怎么样")
    assert intent is not None
    assert intent.primary == "stock"
    assert intent.subject_symbol == "600519"
    assert intent.subject_name == "贵州茅台"


def test_rule_stock_intent_by_name() -> None:
    intent = classify_by_rule("茅台还能持有吗")
    assert intent is not None
    assert intent.primary == "stock"
    assert intent.subject_symbol == "600519"


# --- rule layer: ambiguous / empty ---


def test_rule_ambiguous_returns_none() -> None:
    assert classify_by_rule("央行降准意味着什么") is None


def test_rule_empty_returns_none() -> None:
    assert classify_by_rule("   ") is None


# --- LLM layer ---


@pytest.mark.asyncio
async def test_llm_parses_valid_json() -> None:
    llm = _StubLLM('{"primary": "market", "secondary": [], "subject_symbol": null}')
    intent = await classify_by_llm("央妈放水怎么看", llm)
    assert intent is not None
    assert intent.primary == "market"
    assert intent.source == "llm"


@pytest.mark.asyncio
async def test_llm_parses_secondary_and_industry() -> None:
    llm = _StubLLM(
        '{"primary": "industry", "secondary": ["market"], '
        '"subject_symbol": null, "subject_industry": "半导体"}'
    )
    intent = await classify_by_llm("这个行业和大盘比怎么样", llm)
    assert intent is not None
    assert intent.primary == "industry"
    assert intent.secondary == ("market",)
    assert intent.subject_industry == "半导体"


@pytest.mark.asyncio
async def test_llm_drops_invalid_secondary() -> None:
    llm = _StubLLM('{"primary": "market", "secondary": ["market", "weird"]}')
    intent = await classify_by_llm("随便问一句", llm)
    assert intent is not None
    assert intent.secondary == ()


@pytest.mark.asyncio
async def test_llm_invalid_json_returns_none() -> None:
    llm = _StubLLM("无法分类，这是一段散文")
    assert await classify_by_llm("随便问一句", llm) is None


@pytest.mark.asyncio
async def test_llm_invalid_primary_returns_none() -> None:
    llm = _StubLLM('{"primary": "weird"}')
    assert await classify_by_llm("随便问一句", llm) is None


@pytest.mark.asyncio
async def test_llm_exception_returns_none() -> None:
    assert await classify_by_llm("随便问一句", _RaisingLLM()) is None


# --- entry: priority and fallback ---


@pytest.mark.asyncio
async def test_entry_rule_wins_and_skips_llm() -> None:
    llm = _StubLLM('{"primary": "portfolio"}')
    intent = await classify_chat_intent("大盘走势如何", llm)
    assert intent.primary == "market"
    assert intent.source == "rule"
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_entry_uses_llm_when_rule_misses() -> None:
    llm = _StubLLM('{"primary": "market", "secondary": []}')
    intent = await classify_chat_intent("央行降准意味着什么", llm)
    assert intent.primary == "market"
    assert intent.source == "llm"


@pytest.mark.asyncio
async def test_entry_fallback_when_llm_fails() -> None:
    intent = await classify_chat_intent("央行降准意味着什么", _RaisingLLM())
    assert intent.primary == "portfolio"
    assert intent.source == "fallback"


@pytest.mark.asyncio
async def test_entry_fallback_without_llm() -> None:
    intent = await classify_chat_intent("央行降准意味着什么", None)
    assert intent.primary == "portfolio"
    assert intent.source == "fallback"
