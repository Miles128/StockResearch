"""Sina index provider tests."""

from stockresearch.data.providers.sina_index import fetch_sina_indices


def test_fetch_sina_indices_realistic_shanghai() -> None:
    quotes = fetch_sina_indices()
    sh = next(q for q in quotes if q.name == "上证指数")
    assert sh.price > 1000
    assert -20 <= sh.change_pct <= 20
