"""Sector provider — resolve_board honesty + leaders from constituents."""

from __future__ import annotations

import pytest

from stockresearch.data.providers import sector as sector_mod
from stockresearch.data.providers.sector import SectorBoard, SectorDataProvider, SectorLeader


@pytest.mark.asyncio
async def test_fetch_industry_boards_returns_empty_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """东方财富板块接口失败且所有备份也空时应返回空列表，不抛异常。"""

    class _DummyAsyncClient:
        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("network down")

        async def __aenter__(self) -> "_DummyAsyncClient":
            return self

        async def __aexit__(self, *args) -> None:  # type: ignore[no-untyped-def]
            return None

    monkeypatch.setattr(sector_mod.httpx, "AsyncClient", lambda *a, **k: _DummyAsyncClient())
    monkeypatch.setattr(sector_mod, "get_sqlite_cached", lambda _key: None)

    async def empty(self: SectorDataProvider) -> list[SectorBoard]:
        return []

    monkeypatch.setattr(SectorDataProvider, "_fetch_akshare_boards", empty)
    monkeypatch.setattr(SectorDataProvider, "_fetch_ths_boards", empty)
    monkeypatch.setattr(SectorDataProvider, "_fetch_sector_spot_boards", empty)

    provider = SectorDataProvider()
    boards = await provider.fetch_industry_boards()
    assert boards == []


@pytest.mark.asyncio
async def test_fetch_industry_boards_falls_back_to_ths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EM + AkShare EM fail → THS summary succeeds and is cached."""

    class _DummyAsyncClient:
        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("network down")

        async def __aenter__(self) -> "_DummyAsyncClient":
            return self

        async def __aexit__(self, *args) -> None:  # type: ignore[no-untyped-def]
            return None

    monkeypatch.setattr(sector_mod.httpx, "AsyncClient", lambda *a, **k: _DummyAsyncClient())
    monkeypatch.setattr(sector_mod, "get_sqlite_cached", lambda _key: None)
    stored: dict[str, object] = {}

    def fake_set(key: str, value: dict[str, object], ttl: int) -> None:
        stored["key"] = key
        stored["value"] = value
        stored["ttl"] = ttl

    monkeypatch.setattr(sector_mod, "set_sqlite_cached", fake_set)

    async def empty(self: SectorDataProvider) -> list[SectorBoard]:
        return []

    async def ths(self: SectorDataProvider) -> list[SectorBoard]:
        return [
            SectorBoard(
                code="",
                name="白酒",
                change_pct=3.77,
                leader_name="皇台酒业",
                leader_symbol="",
                leader_change_pct=6.86,
            )
        ]

    monkeypatch.setattr(SectorDataProvider, "_fetch_akshare_boards", empty)
    monkeypatch.setattr(SectorDataProvider, "_fetch_ths_boards", ths)
    monkeypatch.setattr(SectorDataProvider, "_fetch_sector_spot_boards", empty)

    provider = SectorDataProvider()
    boards = await provider.fetch_industry_boards()
    assert len(boards) == 1
    assert boards[0].name == "白酒"
    assert stored.get("key") == "sector:industry_boards:v2"
    assert stored.get("value", {}).get("source") == "ths"  # type: ignore[union-attr]


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
async def test_resolve_board_matches_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    boards = [
        SectorBoard(
            code="BK0475",
            name="半导体",
            change_pct=1.25,
            leader_name="中芯国际",
            leader_symbol="688981",
            leader_change_pct=2.1,
        ),
        SectorBoard(
            code="BK0481",
            name="白酒",
            change_pct=0.5,
            leader_name="贵州茅台",
            leader_symbol="600519",
            leader_change_pct=1.0,
        ),
    ]

    async def fake_boards(self: SectorDataProvider) -> list[SectorBoard]:
        return boards

    monkeypatch.setattr(SectorDataProvider, "fetch_industry_boards", fake_boards)
    provider = SectorDataProvider()
    matched = await provider.resolve_board("半导体")
    assert matched is not None
    assert matched.code == "BK0475"


@pytest.mark.asyncio
async def test_resolve_board_mismatch_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unmatched sector must NOT fall back to boards[0]."""
    boards = [
        SectorBoard(
            code="BK0475",
            name="半导体",
            change_pct=1.25,
            leader_name="中芯国际",
            leader_symbol="688981",
            leader_change_pct=2.1,
        ),
    ]

    async def fake_boards(self: SectorDataProvider) -> list[SectorBoard]:
        return boards

    monkeypatch.setattr(SectorDataProvider, "fetch_industry_boards", fake_boards)
    provider = SectorDataProvider()
    assert await provider.resolve_board("完全不存在的板块XYZ") is None


@pytest.mark.asyncio
async def test_get_sector_leaders_top_n_from_constituents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    board = SectorBoard(
        code="BK0475",
        name="半导体",
        change_pct=1.0,
        leader_name="占位",
        leader_symbol="000001",
        leader_change_pct=0.1,
    )

    async def fake_resolve(self: SectorDataProvider, sector: str) -> SectorBoard:
        return board

    async def fake_cons(
        self: SectorDataProvider, board: SectorBoard, *, limit: int
    ) -> list[SectorLeader]:
        return [
            SectorLeader(symbol="688981", name="中芯国际", change_pct=3.0, role="board_leader"),
            SectorLeader(symbol="002371", name="北方华创", change_pct=2.0, role="constituent"),
            SectorLeader(symbol="603986", name="兆易创新", change_pct=1.5, role="constituent"),
        ][:limit]

    monkeypatch.setattr(SectorDataProvider, "resolve_board", fake_resolve)
    monkeypatch.setattr(SectorDataProvider, "_leaders_from_constituents", fake_cons)

    provider = SectorDataProvider()
    leaders = await provider.get_sector_leaders("半导体", limit=3)
    assert len(leaders) == 3
    assert leaders[0].symbol == "688981"
    assert leaders[0].role == "board_leader"
