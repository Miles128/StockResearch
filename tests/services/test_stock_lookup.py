"""Stock lookup service tests."""

import time

import pytest

from invesbao.core.exceptions import ValidationError
from invesbao.services.stock_lookup import clean_stock_query, lookup_stock


def test_clean_stock_query_strips_punctuation() -> None:
    assert clean_stock_query("贵州茅台，") == "贵州茅台"
    assert clean_stock_query("600519。") == "600519"


@pytest.mark.asyncio
async def test_lookup_confirmed_by_code() -> None:
    result = await lookup_stock("600519")
    assert result.status == "confirmed"
    assert result.symbol == "600519"
    assert "茅台" in (result.name or "")


@pytest.mark.asyncio
async def test_lookup_confirmed_by_alias() -> None:
    result = await lookup_stock("茅台")
    assert result.status == "confirmed"
    assert result.symbol == "600519"


@pytest.mark.asyncio
async def test_lookup_zhaoshang_securities() -> None:
    result = await lookup_stock("招商证券")
    assert result.status == "confirmed"
    assert result.symbol == "600999"


@pytest.mark.asyncio
async def test_lookup_xugong() -> None:
    result = await lookup_stock("徐工机械")
    assert result.status == "confirmed"
    assert result.symbol == "000425"


@pytest.mark.asyncio
async def test_lookup_confirmed_unknown_code_without_catalog() -> None:
    result = await lookup_stock("123456")
    assert result.status == "confirmed"
    assert result.symbol == "123456"
    assert result.name == "123456"


@pytest.mark.asyncio
async def test_lookup_is_fast() -> None:
    started = time.monotonic()
    await lookup_stock("不存在的企业集团")
    assert time.monotonic() - started < 0.05


@pytest.mark.asyncio
async def test_lookup_empty_raises() -> None:
    with pytest.raises(ValidationError):
        await lookup_stock("  ")


@pytest.mark.asyncio
async def test_lookup_not_found() -> None:
    result = await lookup_stock("不存在的企业集团")
    assert result.status == "not_found"
