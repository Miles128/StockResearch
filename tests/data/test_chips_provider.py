"""Chips provider tests — fallback path returns safe defaults when offline."""

import pytest

from stockresearch.data.providers.market import ChipsDataProvider


@pytest.mark.asyncio
async def test_chips_provider_returns_defaults_when_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AkShare 网络不可用时，ChipsDataProvider 应返回安全默认值，不抛异常。"""
    from stockresearch.data.providers.market import chips as market_mod

    async def fake_run_sync_fetch(*args, **kwargs):  # type: ignore[no-untyped-def]
        return kwargs.get("fallback")

    monkeypatch.setattr(market_mod, "run_sync_fetch", fake_run_sync_fetch)

    provider = ChipsDataProvider()
    dragon = await provider.get_dragon_tiger("600519")
    fund = await provider.get_fund_flow("600519")
    northbound = await provider.get_northbound_flow("600519")
    margin = await provider.get_margin_trading("600519")
    holders = await provider.get_holder_count("600519")
    lockup = await provider.get_lockup("600519")

    assert dragon["source"] == "akshare_lhb"
    assert dragon["appearances"] == 0
    assert fund["source"] == "akshare_fund_flow"
    assert fund["main_net_inflow"] == 0.0
    assert northbound["source"] == "akshare_northbound"
    assert margin["source"] == "akshare_margin"
    assert holders["source"] == "akshare_gdhs"
    assert holders["holder_count"] == 0.0
    assert lockup["source"] == "akshare_lockup"
    assert lockup["upcoming_count"] == 0


def test_margin_sse_uses_yuan_column_not_share_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: SSE total must not mix 融资余额 (yuan) with 融券余量 (shares).

    Total should use 融资融券余额 when present, else 融资余额 + 融券余量金额."""
    import pandas as pd

    df = pd.DataFrame(
        [
            {
                "标的证券代码": "600519",
                "融资余额": "1000000.0",
                "融券余量": "500.0",
                "融券余量金额": "200000.0",
                "融资融券余额": "1200000.0",
            }
        ]
    )
    monkeypatch.setattr(
        "stockresearch.data.providers.market.chips.ak.stock_margin_detail_sse",
        lambda date: df,
    )
    provider = ChipsDataProvider()
    result = provider._fetch_margin_sync("600519")
    assert result["total_balance"] == 1_200_000.0
    assert result["securities_balance"] == 200_000.0
    # 500 shares must never be added to a yuan balance.
    assert result["total_balance"] != 1_000_000.0 + 500.0
