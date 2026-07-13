"""A-share sector / industry board data (Eastmoney + AkShare / THS backups)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import asdict, dataclass

import httpx

from stockresearch.data.providers.base import run_sync_fetch
from stockresearch.services.provider_cache_policy import provider_ttl
from stockresearch.services.sqlite_cache import get_sqlite_cached, set_sqlite_cached

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
_BOARDS_CACHE_KEY = "sector:industry_boards:v2"


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


def _boards_from_cache(payload: dict[str, object]) -> list[SectorBoard]:
    raw = payload.get("boards")
    if not isinstance(raw, list):
        return []
    out: list[SectorBoard] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        out.append(
            SectorBoard(
                code=str(item.get("code", "")),
                name=name,
                change_pct=_plain_pct(item.get("change_pct")),
                leader_name=str(item.get("leader_name", "") or "—"),
                leader_symbol=_normalize_symbol(item.get("leader_symbol")),
                leader_change_pct=_plain_pct(item.get("leader_change_pct")),
            )
        )
    return out


def _boards_to_cache(boards: list[SectorBoard]) -> dict[str, object]:
    return {"boards": [asdict(b) for b in boards], "source": "live"}


class SectorDataProvider:
    async def fetch_industry_boards(self) -> list[SectorBoard]:
        cached = get_sqlite_cached(_BOARDS_CACHE_KEY)
        if cached is not None:
            boards = _boards_from_cache(cached)
            if boards:
                return boards

        boards = await self._fetch_eastmoney_boards()
        source = "eastmoney"
        if not boards:
            logger.info("East Money industry boards empty; trying AkShare EM backup")
            boards = await self._fetch_akshare_boards()
            source = "akshare_em"
        if not boards:
            logger.info("AkShare EM boards empty; trying THS summary backup")
            boards = await self._fetch_ths_boards()
            source = "ths"
        if not boards:
            logger.info("THS boards empty; trying sector_spot backup")
            boards = await self._fetch_sector_spot_boards()
            source = "sector_spot"

        if boards:
            ttl = provider_ttl("akshare_financials", fallback=3600)
            # Prefer shorter board TTL so rankings refresh intraday.
            ttl = min(ttl, 3600)
            payload = _boards_to_cache(boards)
            payload["source"] = source
            set_sqlite_cached(_BOARDS_CACHE_KEY, payload, ttl)
        return boards

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

    async def _fetch_ths_boards(self) -> list[SectorBoard]:
        def _sync() -> list[SectorBoard]:
            import akshare as ak  # type: ignore[import-untyped]

            df = ak.stock_board_industry_summary_ths()
            if df is None or df.empty:
                return []
            out: list[SectorBoard] = []
            for _, row in df.iterrows():
                name = str(row.get("板块", "")).strip()
                if not name:
                    continue
                out.append(
                    SectorBoard(
                        code="",
                        name=name,
                        change_pct=_plain_pct(row.get("涨跌幅")),
                        leader_name=str(row.get("领涨股", "") or "—"),
                        leader_symbol="",
                        leader_change_pct=_plain_pct(row.get("领涨股-涨跌幅")),
                    )
                )
            return out

        result = await run_sync_fetch(
            "akshare ths industry boards",
            _sync,
            timeout=20.0,
            fallback=[],
        )
        return result if isinstance(result, list) else []

    async def _fetch_sector_spot_boards(self) -> list[SectorBoard]:
        def _sync() -> list[SectorBoard]:
            import akshare as ak  # type: ignore[import-untyped]

            df = ak.stock_sector_spot(indicator="行业")
            if df is None or df.empty:
                return []
            out: list[SectorBoard] = []
            for _, row in df.iterrows():
                name = str(row.get("板块", "")).strip()
                if not name:
                    continue
                out.append(
                    SectorBoard(
                        code=str(row.get("label", "")),
                        name=name,
                        change_pct=_plain_pct(row.get("涨跌幅")),
                        leader_name=str(row.get("股票名称", "") or "—"),
                        leader_symbol=_normalize_symbol(row.get("股票代码")),
                        leader_change_pct=_plain_pct(row.get("个股-涨跌幅")),
                    )
                )
            return out

        result = await run_sync_fetch(
            "akshare sector_spot boards",
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
