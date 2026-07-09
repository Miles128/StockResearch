"""Context scoping tests — holdings injection rules."""

import pytest

from stockresearch.agents.orchestrator.complexity import is_holdings_intent, is_vague_query
from stockresearch.core.schemas import ChatUserContext
from stockresearch.services.chat_context import should_include_holdings_context


@pytest.mark.parametrize(
    "message",
    [
        "今天大盘怎么样",
        "分析一下600519",
        "帮我看看宁德时代走势",
        "半导体板块前景如何",
    ],
)
def test_market_and_stock_queries_skip_holdings(message: str) -> None:
    assert not should_include_holdings_context(message, None)


@pytest.mark.parametrize(
    "message",
    [
        "我的持仓风险大吗",
        "帮我分析一下我的持仓",
        "组合要不要调整",
        "持仓体检",
    ],
)
def test_explicit_holdings_queries_include_holdings(message: str) -> None:
    assert should_include_holdings_context(message, None)


def test_risk_tab_vague_query_includes_holdings() -> None:
    ctx = ChatUserContext(kind="risk", label="风控体检")
    assert should_include_holdings_context("分析一下", ctx)


def test_risk_tab_market_question_skips_holdings() -> None:
    ctx = ChatUserContext(kind="risk", label="风控体检")
    assert not should_include_holdings_context("今天大盘怎么样", ctx)


def test_stock_ui_context_without_holdings_intent() -> None:
    ctx = ChatUserContext(kind="stock", label="贵州茅台 600519", symbol="600519")
    assert not should_include_holdings_context("分析一下", ctx)
    assert is_vague_query("分析一下")


def test_is_holdings_intent() -> None:
    assert is_holdings_intent("我的持仓怎么样")
    assert not is_holdings_intent("茅台怎么样")
