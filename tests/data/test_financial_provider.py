"""FinancialDataProvider honesty — no fabricated zeros / goodwill."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from stockresearch.data.providers.market import FinancialDataProvider


@pytest.mark.asyncio
async def test_get_financials_fail_without_fabricating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both THS and indicator failing must return None metrics + gaps, not 0.0."""
    provider = FinancialDataProvider()
    monkeypatch.setattr(
        "stockresearch.data.providers.market._use_mock_market_data",
        lambda: False,
    )

    async def fake_run_sync_fetch(name: str, fn, *, timeout: float, fallback=None):  # type: ignore[no-untyped-def]
        return fallback if fallback is not None else None

    monkeypatch.setattr(
        "stockresearch.data.providers.market.run_sync_fetch",
        fake_run_sync_fetch,
    )

    async def no_cache(key: str, ttl: int, factory, *, should_cache=None):  # type: ignore[no-untyped-def]
        return await factory()

    monkeypatch.setattr(
        "stockresearch.data.providers.market.get_or_set_cached_dict",
        no_cache,
    )

    result = await provider.get_financials("600519")
    assert result["revenue_yoy"] is None
    assert result["net_margin"] is None
    assert result["roe"] is None
    assert result["debt_ratio"] is None
    assert result["goodwill_ratio"] is None
    assert result["partial"] is True
    assert result["series"] == []
    assert any("不可用" in str(g) for g in result["gaps"])  # type: ignore[index]
    # Explicitly: never the old fabricated defaults
    assert result["roe"] != 0.0
    assert result["goodwill_ratio"] != 0.03


@pytest.mark.asyncio
async def test_get_financials_prefers_ths_over_indicator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FinancialDataProvider()
    monkeypatch.setattr(
        "stockresearch.data.providers.market._use_mock_market_data",
        lambda: False,
    )

    ths = pd.DataFrame(
        [
            {
                "报告期": "2023",
                "营业总收入同比增长率": "10%",
                "销售净利率": "20%",
                "净资产收益率": "15%",
                "资产负债率": "40%",
            },
            {
                "报告期": "2024",
                "营业总收入同比增长率": "12%",
                "销售净利率": "22%",
                "净资产收益率": "18%",
                "资产负债率": "38%",
            },
        ]
    )

    async def fake_run_sync_fetch(name: str, fn, *, timeout: float, fallback=None):  # type: ignore[no-untyped-def]
        if "ths" in name:
            return ths
        raise AssertionError("indicator should not be called when THS succeeds")

    monkeypatch.setattr(
        "stockresearch.data.providers.market.run_sync_fetch",
        fake_run_sync_fetch,
    )

    async def no_cache(key: str, ttl: int, factory, *, should_cache=None):  # type: ignore[no-untyped-def]
        return await factory()

    monkeypatch.setattr(
        "stockresearch.data.providers.market.get_or_set_cached_dict",
        no_cache,
    )

    result = await provider.get_financials("600519")
    assert result["source"] == "ths_abstract"
    assert result["roe"] == pytest.approx(0.18)
    assert result["revenue_yoy"] == pytest.approx(0.12)
    assert result["goodwill_ratio"] is None
    assert len(result["series"]) >= 2  # type: ignore[arg-type]


def test_optional_pct_returns_none_on_missing() -> None:
    assert FinancialDataProvider._optional_pct(None) is None
    assert FinancialDataProvider._optional_pct("") is None
    assert FinancialDataProvider._optional_pct("18.5%") == pytest.approx(0.185)
    assert FinancialDataProvider._optional_pct(12) == pytest.approx(0.12)


@pytest.mark.asyncio
async def test_get_valuation_no_default_pe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FinancialDataProvider()
    monkeypatch.setattr(
        "stockresearch.data.providers.market._use_mock_market_data",
        lambda: False,
    )

    async def fake_run_sync_fetch(name: str, fn, *, timeout: float, fallback=None):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(
        "stockresearch.data.providers.market.run_sync_fetch",
        fake_run_sync_fetch,
    )

    async def no_cache(key: str, ttl: int, factory, *, should_cache=None):  # type: ignore[no-untyped-def]
        return await factory()

    monkeypatch.setattr(
        "stockresearch.data.providers.market.get_or_set_cached_dict",
        no_cache,
    )

    result = await provider.get_valuation("600519")
    assert result["pe_ttm"] is None
    assert result["pe_percentile"] is None
    assert result["partial"] is True
    assert result["source"] == "none"


@pytest.mark.asyncio
async def test_get_valuation_from_value_em(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FinancialDataProvider()
    monkeypatch.setattr(
        "stockresearch.data.providers.market._use_mock_market_data",
        lambda: False,
    )
    em = pd.DataFrame(
        [
            {"数据日期": "2024-01-02", "PE(TTM)": 20.0, "市净率": 6.0},
            {"数据日期": "2024-01-03", "PE(TTM)": 22.0, "市净率": 6.5},
            {"数据日期": "2024-01-04", "PE(TTM)": 18.0, "市净率": 5.5},
        ]
    )

    async def fake_run_sync_fetch(name: str, fn, *, timeout: float, fallback=None):  # type: ignore[no-untyped-def]
        if "value_em" in name:
            return em
        raise AssertionError(f"unexpected fetch: {name}")

    monkeypatch.setattr(
        "stockresearch.data.providers.market.run_sync_fetch",
        fake_run_sync_fetch,
    )

    async def no_cache(key: str, ttl: int, factory, *, should_cache=None):  # type: ignore[no-untyped-def]
        result = await factory()
        if should_cache is not None:
            assert should_cache(result) is True
        return result

    monkeypatch.setattr(
        "stockresearch.data.providers.market.get_or_set_cached_dict",
        no_cache,
    )

    result = await provider.get_valuation("600519")
    assert result["source"] == "akshare_value_em"
    assert result["pe_ttm"] == pytest.approx(18.0)
    assert result["pb"] == pytest.approx(5.5)
    assert result["pe_percentile"] is not None


@pytest.mark.asyncio
async def test_get_valuation_falls_back_to_baidu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FinancialDataProvider()
    monkeypatch.setattr(
        "stockresearch.data.providers.market._use_mock_market_data",
        lambda: False,
    )
    pe = pd.DataFrame({"date": ["2024-01-01", "2024-01-02"], "value": [25.0, 18.2]})
    pb = pd.DataFrame({"date": ["2024-01-01", "2024-01-02"], "value": [7.0, 5.56]})

    async def fake_run_sync_fetch(name: str, fn, *, timeout: float, fallback=None):  # type: ignore[no-untyped-def]
        if "value_em" in name:
            return None
        if "baidu pe" in name:
            return pe
        if "baidu pb" in name:
            return pb
        return None

    monkeypatch.setattr(
        "stockresearch.data.providers.market.run_sync_fetch",
        fake_run_sync_fetch,
    )

    async def no_cache(key: str, ttl: int, factory, *, should_cache=None):  # type: ignore[no-untyped-def]
        return await factory()

    monkeypatch.setattr(
        "stockresearch.data.providers.market.get_or_set_cached_dict",
        no_cache,
    )

    result = await provider.get_valuation("600519")
    assert result["source"] == "akshare_baidu"
    assert result["pe_ttm"] == pytest.approx(18.2)
    assert result["pb"] == pytest.approx(5.56)


@pytest.mark.asyncio
async def test_seed_peers_marked_as_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FinancialDataProvider()
    monkeypatch.setattr(
        "stockresearch.data.providers.market._use_mock_market_data",
        lambda: False,
    )

    async def fake_run_sync_fetch(name: str, fn, *, timeout: float, fallback=None):  # type: ignore[no-untyped-def]
        if "individual" in name:
            return ""
        return fallback if fallback is not None else None

    monkeypatch.setattr(
        "stockresearch.data.providers.market.run_sync_fetch",
        fake_run_sync_fetch,
    )

    async def no_cache(key: str, ttl: int, factory, *, should_cache=None):  # type: ignore[no-untyped-def]
        return await factory()

    monkeypatch.setattr(
        "stockresearch.data.providers.market.get_or_set_cached_dict",
        no_cache,
    )

    async def no_val(self: Any, symbol: str) -> dict[str, object]:
        return {"pe_ttm": None, "pb": None, "pe_percentile": None}

    monkeypatch.setattr(FinancialDataProvider, "get_valuation", no_val)

    peers = await provider.get_industry_peers("600519")
    assert peers
    assert all(p.get("source") == "seed" for p in peers)
