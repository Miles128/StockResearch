"""A-share sector / industry board data (Eastmoney-style)."""

import asyncio
import json
import logging
import re
from dataclasses import dataclass

import httpx

from stockresearch.core.config import get_settings

logger = logging.getLogger(__name__)

_INDUSTRY_BOARD_URL = (
    "https://push2.eastmoney.com/api/qt/clist/get"
    "?np=1&fltt=1&invt=2"
    "&fs=m:90+t:2"
    "&fields=f12,f14,f3,f136,f140,f128"
    "&fid=f3&pn=1&pz=200&po=1"
    "&ut=fa5fd1943c7b386f172d6893dbfba10b"
)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}


@dataclass(frozen=True)
class SectorBoard:
    code: str
    name: str
    change_pct: float
    leader_name: str
    leader_symbol: str
    leader_change_pct: float


@dataclass(frozen=True)
class SectorLeader:
    symbol: str
    name: str
    change_pct: float
    role: str = "leader"


def _parse_jsonp(text: str) -> dict[str, object] | None:
    match = re.search(r"\((.*)\)", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _pct(raw: object) -> float:
    try:
        return round(float(raw) / 100.0, 2)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _normalize_symbol(raw: object) -> str:
    text = str(raw or "").strip()
    digits = re.sub(r"\D", "", text)
    return digits[-6:].zfill(6) if digits else ""


class SectorDataProvider:
    async def fetch_industry_boards(self) -> list[SectorBoard]:
        if get_settings().use_mock_market_data:
            return _mock_boards()
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(_INDUSTRY_BOARD_URL, headers=_HEADERS)
                resp.raise_for_status()
            payload = _parse_jsonp(resp.text)
            if not payload:
                return _mock_boards()
            diff = payload.get("data", {})
            if isinstance(diff, dict):
                rows = diff.get("diff", [])
            else:
                rows = []
            boards: list[SectorBoard] = []
            if not isinstance(rows, list):
                return _mock_boards()
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("f14", "")).strip()
                if not name:
                    continue
                boards.append(
                    SectorBoard(
                        code=str(row.get("f12", "")),
                        name=name,
                        change_pct=_pct(row.get("f3")),
                        leader_name=str(row.get("f140", "") or "—"),
                        leader_symbol=_normalize_symbol(row.get("f128")),
                        leader_change_pct=_pct(row.get("f136")),
                    )
                )
            return boards or _mock_boards()
        except Exception as exc:
            logger.warning("Sector board fetch failed: %s", exc)
            return _mock_boards()

    async def resolve_board(self, sector: str) -> SectorBoard | None:
        boards = await self.fetch_industry_boards()
        needle = sector.strip()
        for board in boards:
            if needle in board.name or board.name in needle:
                return board
        for board in boards:
            if any(part in board.name for part in needle.split() if len(part) >= 2):
                return board
        return boards[0] if boards else None

    async def get_sector_leaders(self, sector: str, *, limit: int = 3) -> list[SectorLeader]:
        board = await self.resolve_board(sector)
        if board is None:
            return _mock_leaders(sector, limit)
        leaders: list[SectorLeader] = []
        if board.leader_symbol and board.leader_name:
            leaders.append(
                SectorLeader(
                    symbol=board.leader_symbol,
                    name=board.leader_name,
                    change_pct=board.leader_change_pct,
                    role="board_leader",
                )
            )
        # Pad with sector-themed mock peers when only one leader from board API
        if len(leaders) < limit:
            for extra in _mock_leaders(sector, limit):
                if extra.symbol not in {x.symbol for x in leaders}:
                    leaders.append(extra)
                if len(leaders) >= limit:
                    break
        return leaders[:limit]


def _mock_boards() -> list[SectorBoard]:
    return [
        SectorBoard("BK0475", "半导体", 1.25, "中芯国际", "688981", 2.1),
        SectorBoard("BK0896", "白酒", -0.45, "贵州茅台", "600519", -0.3),
        SectorBoard("BK0493", "新能源", 0.88, "宁德时代", "300750", 1.2),
        SectorBoard("BK0477", "医药", 0.15, "恒瑞医药", "600276", 0.5),
    ]


def _mock_leaders(sector: str, limit: int) -> list[SectorLeader]:
    catalog: dict[str, list[tuple[str, str, float]]] = {
        "半导体": [("688981", "中芯国际", 2.1), ("002371", "北方华创", 1.8), ("603501", "韦尔股份", 1.2)],
        "白酒": [("600519", "贵州茅台", -0.3), ("000858", "五粮液", -0.5), ("000568", "泸州老窖", 0.1)],
        "新能源": [("300750", "宁德时代", 1.2), ("002594", "比亚迪", 0.9), ("601012", "隆基绿能", 0.4)],
    }
    for key, rows in catalog.items():
        if key in sector or sector in key:
            return [
                SectorLeader(symbol=s, name=n, change_pct=c, role="mock_leader")
                for s, n, c in rows[:limit]
            ]
    return [
        SectorLeader("600519", "贵州茅台", 0.0, role="mock_leader"),
        SectorLeader("300750", "宁德时代", 0.0, role="mock_leader"),
    ][:limit]


async def fetch_sector_snapshot(sector: str) -> dict[str, object]:
    provider = SectorDataProvider()
    board, leaders = await asyncio.gather(
        provider.resolve_board(sector),
        provider.get_sector_leaders(sector, limit=3),
    )
    return {
        "sector": sector,
        "board": board,
        "leaders": leaders,
    }
