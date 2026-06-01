"""Stock sector resolution tests."""

import pytest

from invesbao.services import stock_sector as sector_mod
from invesbao.services.stock_sector import (
    backfill_holding_sectors,
    fetch_eastmoney_sector,
    normalize_sector,
    resolve_stock_sector,
    sector_from_name,
)
from invesbao.db.models import Holding


def test_normalize_sector_maps_baijiu() -> None:
    assert normalize_sector("白酒Ⅱ") == "白酒"


def test_normalize_sector_passes_known_bucket() -> None:
    assert normalize_sector("半导体") == "半导体"


def test_sector_from_name() -> None:
    assert sector_from_name("贵州茅台") == "白酒"
    assert sector_from_name("招商证券") == "券商"
    assert sector_from_name("徐工机械") == "机械"
    assert sector_from_name("平安银行") == "银行"


@pytest.mark.asyncio
async def test_resolve_stock_sector_by_name() -> None:
    assert await resolve_stock_sector("999999", "招商证券") == "券商"
    assert await resolve_stock_sector("999999", "徐工机械") == "机械"


def test_fetch_eastmoney_sector(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"data": {"f127": "白酒Ⅱ"}}

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def get(self, url: str, params: dict[str, str], headers: dict[str, str] | None = None) -> FakeResp:
            assert params["secid"] == "1.600519"
            return FakeResp()

    monkeypatch.setattr(sector_mod.httpx, "Client", FakeClient)
    assert fetch_eastmoney_sector("600519") == "白酒"


@pytest.mark.asyncio
async def test_resolve_stock_sector_local_catalog() -> None:
    sector = await resolve_stock_sector("600519", "贵州茅台")
    assert sector == "白酒"


@pytest.mark.asyncio
async def test_backfill_holding_sectors_updates_unknown() -> None:
    holdings = [
        Holding(
            id=1,
            user_id=1,
            symbol="600519",
            name="贵州茅台",
            cost_price=1800.0,
            quantity=100,
            sector="未知",
        ),
        Holding(
            id=2,
            user_id=1,
            symbol="300750",
            name="宁德时代",
            cost_price=200.0,
            quantity=100,
            sector="新能源",
        ),
    ]
    updated, skipped = await backfill_holding_sectors(holdings)
    assert updated == 1
    assert skipped == 1
    assert holdings[0].sector == "白酒"
    assert holdings[1].sector == "新能源"
