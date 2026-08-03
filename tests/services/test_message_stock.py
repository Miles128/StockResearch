"""Message stock resolution tests."""

import pytest

from stockresearch.services.chat.message_stock import extract_stock_query, resolve_message_stock


def test_extract_stock_query_from_code() -> None:
    assert extract_stock_query("帮我分析 600519") == "600519"


def test_extract_stock_query_from_alias() -> None:
    assert extract_stock_query("看看茅台怎么样") == "茅台"


@pytest.mark.asyncio
async def test_resolve_message_stock_ambiguous() -> None:
    result = await resolve_message_stock("帮我分析一下平安")
    assert result.status == "ambiguous"
    assert len(result.candidates) >= 2


@pytest.mark.asyncio
async def test_resolve_message_stock_confirmed_override() -> None:
    resolved = await resolve_message_stock(
        "帮我分析一下平安",
        confirmed_symbol="601318",
        confirmed_name="中国平安",
    )
    assert resolved.symbol == "601318"
    assert resolved.name == "中国平安"
