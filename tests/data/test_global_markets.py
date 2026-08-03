"""Global/overseas market indices provider tests."""

import pytest

from stockresearch.data.providers import global_markets as mod
from stockresearch.data.providers.global_markets import (
    GlobalIndexQuote,
    GlobalMarketsProvider,
    _parse_sina_global_response,
    format_global_snapshot,
)

_SAMPLE = (
    'var hq_str_int_hangseng="恒生指数,26009.40,124.97,0.48";\n'
    'var hq_str_int_dji=" 道琼斯,46247.29,299.97,0.65";\n'
    'var hq_str_int_nasdaq="纳斯达克,22484.07,99.37,0.44%";\n'
    'var hq_str_int_sp500="标普指数,6643.70,38.98,0.59";\n'
    'var hq_str_int_nikkei="日经指数,44946.64,-408.35,-0.90";\n'
)


def test_parse_sina_global_response() -> None:
    rows = _parse_sina_global_response(_SAMPLE)
    assert len(rows) == 5
    by_name = {row.name: row for row in rows}
    # 显示名以本地映射为准（载荷名可能带空格或不同叫法）
    assert by_name["恒生指数"].price == 26009.40
    assert by_name["恒生指数"].change_pct == 0.48
    assert by_name["道琼斯"].change_pct == 0.65
    # 涨跌幅字段偶带 % — 防御性剥离
    assert by_name["纳斯达克"].change_pct == 0.44
    assert by_name["日经225"].change_pct == -0.90


def test_parse_skips_malformed_lines() -> None:
    text = (
        'var hq_str_int_hangseng="恒生指数,bad,124.97,0.48";\n'
        'var hq_str_int_dji="道琼斯,46247.29";\n'
        'var hq_str_int_nasdaq="纳斯达克,22484.07,99.37,0.44";\n'
    )
    rows = _parse_sina_global_response(text)
    assert [row.name for row in rows] == ["纳斯达克"]


@pytest.mark.asyncio
async def test_get_indices_mock_mode() -> None:
    # 测试环境 USE_MOCK_MARKET_DATA=true — 返回固定 mock 数据
    rows = await GlobalMarketsProvider().get_indices()
    assert len(rows) == 5
    assert any(row.name == "恒生指数" for row in rows)


@pytest.mark.asyncio
async def test_get_indices_failure_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "stockresearch.core.config.get_settings",
        lambda: type("S", (), {"use_mock_market_data": False})(),
    )

    def boom() -> list[GlobalIndexQuote]:
        raise RuntimeError("sina down")

    monkeypatch.setattr(mod, "fetch_sina_global_indices", boom)
    rows = await GlobalMarketsProvider().get_indices()
    assert rows == []


@pytest.mark.asyncio
async def test_get_indices_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "stockresearch.core.config.get_settings",
        lambda: type("S", (), {"use_mock_market_data": False})(),
    )
    from stockresearch.services.sqlite_cache import set_sqlite_cached

    set_sqlite_cached(
        "market:global_indices",
        {
            "rows": [
                {"name": "恒生指数", "price": 26000.0, "change_pct": 0.48},
                {"name": "道琼斯", "price": 46200.0, "change_pct": 0.65},
            ],
            "source": "sina",
        },
        600,
    )

    def fail() -> list[GlobalIndexQuote]:
        raise AssertionError("live fetch should not run when cache hit")

    monkeypatch.setattr(mod, "fetch_sina_global_indices", fail)
    rows = await GlobalMarketsProvider().get_indices()
    assert [row.name for row in rows] == ["恒生指数", "道琼斯"]


@pytest.mark.asyncio
async def test_get_indices_stores_cache_on_live_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "stockresearch.core.config.get_settings",
        lambda: type("S", (), {"use_mock_market_data": False})(),
    )
    monkeypatch.setattr(
        mod,
        "fetch_sina_global_indices",
        lambda: [GlobalIndexQuote(name="恒生指数", price=26000.0, change_pct=0.48)],
    )
    rows = await GlobalMarketsProvider().get_indices()
    assert rows and rows[0].name == "恒生指数"

    from stockresearch.services.sqlite_cache import get_sqlite_cached

    cached = get_sqlite_cached("market:global_indices")
    assert cached is not None and cached.get("source") == "sina"


def test_format_global_snapshot() -> None:
    rows = [
        GlobalIndexQuote(name="恒生指数", price=26009.40, change_pct=0.48),
        GlobalIndexQuote(name="日经225", price=44946.64, change_pct=-0.90),
    ]
    text = format_global_snapshot(rows)
    assert "恒生指数: 26009.40 ↑ +0.48%" in text
    assert "日经225: 44946.64 ↓ -0.90%" in text
    assert format_global_snapshot([]) == ""
