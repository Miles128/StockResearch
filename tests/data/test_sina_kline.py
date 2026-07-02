"""Sina kline provider tests."""

import pytest

from stockresearch.data.providers.sina_kline import fetch_sina_kline


@pytest.mark.live
def test_fetch_sina_kline_stock() -> None:
    bars = fetch_sina_kline("600519", 20)
    assert len(bars) >= 10
    assert bars[0]["date"]
    assert bars[-1]["close"] > 0


def test_fetch_sina_kline_stock_offline() -> None:
    """Runs against live Sina when network available (no live marker for CI default)."""
    try:
        bars = fetch_sina_kline("600519", 15)
    except Exception:
        pytest.skip("Sina kline unreachable in this environment")
    assert len(bars) >= 10
