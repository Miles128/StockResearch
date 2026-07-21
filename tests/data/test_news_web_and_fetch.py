"""Tests for URL excerpt helper and news thin-trigger helpers."""

from stockresearch.data.providers.web_fetch import _strip_html, fetch_url_excerpt_sync
from stockresearch.data.providers.news import RawNewsItem, _dedupe_items, _is_thin
from datetime import UTC, datetime


def test_strip_html_prefers_meta_description() -> None:
    html = """
    <html><head>
    <meta name="description" content="这是一段足够长的新闻摘要内容用于测试摘录。"/>
    </head><body><p>正文被忽略</p></body></html>
    """
    text = _strip_html(html)
    assert "新闻摘要" in text


def test_fetch_url_excerpt_rejects_non_http() -> None:
    assert fetch_url_excerpt_sync("ftp://example.com/a") == ""
    assert fetch_url_excerpt_sync("") == ""


def test_dedupe_prefers_cls_over_em() -> None:
    now = datetime.now(UTC)
    items = [
        RawNewsItem("同一标题", "a", "东方财富全球", now, ""),
        RawNewsItem("同一标题", "b", "财联社", now, ""),
        RawNewsItem("另一条", "c", "新浪", now, ""),
    ]
    out = _dedupe_items(items)
    assert len(out) == 2
    same = next(i for i in out if i.title == "同一标题")
    assert same.source == "财联社"


def test_is_thin_threshold() -> None:
    now = datetime.now(UTC)
    few = [RawNewsItem("t", "c", "s", now) for _ in range(2)]
    assert _is_thin(few, 20) is True
    many = [RawNewsItem(f"t{i}", "c", "s", now) for i in range(10)]
    assert _is_thin(many, 20) is False
