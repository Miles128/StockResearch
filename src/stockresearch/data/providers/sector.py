"""A-share sector / industry board data (Eastmoney + AkShare backup)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass

import httpx

from stockresearch.data.providers.base import run_sync_fetch

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


def _em_pct(raw: object) -> float:
    """East Money fltt=1 scales percent by 100 (e.g. 125 → 1.25)."""
    try:
        return round(float(raw) / 100.0, 2)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _plain_pct(raw: object) -> float:
    """AkShare-style percent already in display units (e.g. 1.25)."""
    try:
        return round(float(raw), 2)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _normalize_symbol(raw: object) -> str:
    text = str(raw or "").strip()
    digits = re.sub(r"\D", "", text)
    return digits[-6:].zfill(6) if digits else ""


def _board_matches(needle: str, board_name: str) -> bool:
    if not needle or not board_name:
        return False
    if needle in board_name or board_name in needle:
        return True
    parts = [p for p in re.split(r"[\s/、,，]+", needle) if len(p) >= 2]
    return any(part in board_name for part in parts)


class SectorDataProvider:
    async def fetch_industry_boards(self) -> list[SectorBoard]:
        boards = await self._fetch_eastmoney_boards()
        if boards:
            return boards
        logger.info("East Money industry boards empty; trying AkShare backup")
        return await self._fetch_akshare_boards()

    async def _fetch_eastmoney_boards(self) -> list[SectorBoard]:
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(_INDUSTRY_BOARD_URL, headers=_HEADERS)
                resp.raise_for_status()
            payload = _parse_jsonp(resp.text)
            if not payload:
                return []
            diff = payload.get("data", {})
            if isinstance(diff, dict):
                rows = diff.get("diff", [])
            else:
                rows = []
            boards: list[SectorBoard] = []
            if not isinstance(rows, list):
                return []
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
                        change_pct=_em_pct(row.get("f3")),
                        leader_name=str(row.get("f140", "") or "—"),
                        leader_symbol=_normalize_symbol(row.get("f128")),
                        leader_change_pct=_em_pct(row.get("f136")),
                    )
                )
            return boards
        except Exception as exc:
            logger.warning("Sector board fetch failed: %s", exc)
            return []

    async def _fetch_akshare_boards(self) -> list[SectorBoard]:
        def _sync() -> list[SectorBoard]:
            import akshare as ak  # type: ignore[import-untyped]

            df = ak.stock_board_industry_name_em()
            if df is None or df.empty:
                return []
            out: list[SectorBoard] = []
            for _, row in df.iterrows():
                name = str(row.get("板块名称", "")).strip()
                if not name:
                    continue
                out.append(
                    SectorBoard(
                        code=str(row.get("板块代码", "")),
                        name=name,
                        change_pct=_plain_pct(row.get("涨跌幅")),
                        leader_name=str(row.get("领涨股票", "") or "—"),
                        leader_symbol="",
                        leader_change_pct=_plain_pct(row.get("领涨股票-涨跌幅")),
                    )
                )
            return out

        result = await run_sync_fetch(
            "akshare industry boards",
            _sync,
            timeout=15.0,
            fallback=[],
        )
        return result if isinstance(result, list) else []

    async def resolve_board(self, sector: str) -> SectorBoard | None:
        """Match a sector name to a board. Never fall back to boards[0]."""
        boards = await self.fetch_industry_boards()
        if not boards:
            return None
        needle = sector.strip()
        if not needle:
            return None
        for board in boards:
            if _board_matches(needle, board.name):
                return board
        logger.info("No industry board match for sector=%r (%d boards)", needle, len(boards))
        return None

    async def get_sector_leaders(self, sector: str, *, limit: int = 3) -> list[SectorLeader]:
        board = await self.resolve_board(sector)
        if board is None:
            return []

        leaders = await self._leaders_from_constituents(board, limit=limit)
        if leaders:
            return leaders

        # Fallback: single board-reported leader if present.
        if board.leader_symbol and board.leader_name and board.leader_name != "—":
            return [
                SectorLeader(
                    symbol=board.leader_symbol,
                    name=board.leader_name,
                    change_pct=board.leader_change_pct,
                    role="board_leader",
                )
            ][:limit]
        return []

    async def _leaders_from_constituents(
        self, board: SectorBoard, *, limit: int
    ) -> list[SectorLeader]:
        def _sync() -> list[SectorLeader]:
            import akshare as ak  # type: ignore[import-untyped]

            key = board.name or board.code
            if not key:
                return []
            df = ak.stock_board_industry_cons_em(symbol=key)
            if df is None or df.empty:
                return []
            code_col = "代码" if "代码" in df.columns else None
            name_col = "名称" if "名称" in df.columns else None
            chg_col = "涨跌幅" if "涨跌幅" in df.columns else None
            if not code_col or not name_col:
                return []
            rows: list[SectorLeader] = []
            for _, row in df.iterrows():
                symbol = _normalize_symbol(row.get(code_col))
                name = str(row.get(name_col, "")).strip()
                if not symbol or not name:
                    continue
                rows.append(
                    SectorLeader(
                        symbol=symbol,
                        name=name,
                        change_pct=_plain_pct(row.get(chg_col) if chg_col else 0),
                        role="constituent",
                    )
                )
            rows.sort(key=lambda x: x.change_pct, reverse=True)
            top = rows[:limit]
            if top:
                first = top[0]
                top[0] = SectorLeader(
                    symbol=first.symbol,
                    name=first.name,
                    change_pct=first.change_pct,
                    role="board_leader",
                )
            return top

        result = await run_sync_fetch(
            f"akshare industry cons leaders {board.name}",
            _sync,
            timeout=12.0,
            fallback=[],
        )
        return result if isinstance(result, list) else []


async def fetch_sector_snapshot(sector: str) -> dict[str, object]:
    provider = SectorDataProvider()
    board, leaders = await asyncio.gather(
        provider.resolve_board(sector),
        provider.get_sector_leaders(sector, limit=3),
    )
    gaps: list[str] = []
    if board is None:
        gaps.append("行业板块未匹配")
    if not leaders:
        gaps.append("板块龙头/成份不足")
    return {
        "sector": sector,
        "board": board,
        "leaders": leaders,
        "partial": bool(gaps),
        "gaps": gaps,
    }
