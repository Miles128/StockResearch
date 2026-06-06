"""Sector data provider tests."""

import pytest

from stockresearch.data.providers.sector import SectorDataProvider


@pytest.mark.asyncio
async def test_resolve_board_mock_semiconductor() -> None:
    provider = SectorDataProvider()
    board = await provider.resolve_board("半导体")
    assert board is not None
    assert "半导体" in board.name


@pytest.mark.asyncio
async def test_get_sector_leaders_mock() -> None:
    provider = SectorDataProvider()
    leaders = await provider.get_sector_leaders("白酒", limit=3)
    assert len(leaders) >= 1
    assert leaders[0].symbol
    assert leaders[0].name
