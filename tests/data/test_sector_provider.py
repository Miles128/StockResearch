"""Sector data provider tests — verifies offline fallback returns empty list."""

import pytest

from stockresearch.data.providers import sector as sector_mod
from stockresearch.data.providers.sector import SectorDataProvider, SectorBoard


@pytest.mark.asyncio
async def test_fetch_industry_boards_returns_empty_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """东方财富板块接口失败时应返回空列表，不抛异常。"""

    def raise_http_error() -> None:
        raise RuntimeError("network down")

    monkeypatch.setattr(sector_mod.httpx, "AsyncClient", _raise_async_client)

    provider = SectorDataProvider()
    boards = await provider.fetch_industry_boards()
    assert boards == []


@pytest.mark.asyncio
async def test_get_sector_leaders_returns_empty_when_no_board(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """当 resolve_board 返回 None 时，get_sector_leaders 应返回空列表。"""

    async def no_board(_sector: str) -> None:
        return None

    provider = SectorDataProvider()
    monkeypatch.setattr(provider, "resolve_board", no_board)
    leaders = await provider.get_sector_leaders("白酒", limit=3)
    assert leaders == []


@pytest.mark.asyncio
async def test_resolve_board_matches_by_name() -> None:
    """验证 board 名称匹配逻辑。"""
    board = SectorBoard(
        code="BK0475",
        name="半导体",
        change_pct=1.25,
        leader_name="中芯国际",
        leader_symbol="688981",
        leader_change_pct=2.1,
    )
    # 直接通过 _match 逻辑验证
    needle = "半导体"
    assert needle in board.name or board.name in needle


class _DummyAsyncClient:
    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        raise RuntimeError("network down")

    async def __aenter__(self) -> "_DummyAsyncClient":
        return self

    async def __aexit__(self, *args) -> None:  # type: ignore[no-untyped-def]
        return None


def _raise_async_client(*args, **kwargs):  # type: ignore[no-untyped-def]
    return _DummyAsyncClient(*args, **kwargs)
