"""Eastmoney direct news fetch tests."""

import pytest

from stockresearch.data.providers.news import _clean_em_news_text, _fetch_em_symbol_news_sync


def test_clean_em_news_text_strips_markup() -> None:
    raw = "<em>茅台</em>发布年报\u3000\r\n增长"
    assert _clean_em_news_text(raw) == "茅台发布年报 增长"


def test_fetch_em_symbol_news_sync_returns_items_when_api_works() -> None:
    items = _fetch_em_symbol_news_sync("贵州茅台", limit=3)
    if not items:
        pytest.skip("Eastmoney news API unavailable in this environment")
    assert items[0].title
    assert items[0].source
