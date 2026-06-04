"""Resolve A-share industry/sector for a symbol — local map + East Money API."""

import asyncio
import logging
import re

import httpx

from stockresearch.core.config import get_settings
from stockresearch.core.constants import AVAILABLE_SECTORS, SYMBOL_SECTORS
from stockresearch.db.models import Holding

logger = logging.getLogger(__name__)

_EASTMONEY_TIMEOUT_SEC = 3.0
_ROMAN_SUFFIX = re.compile(r"[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+")

_SECTOR_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("白酒", ("白酒", "酿酒", "啤酒", "饮料")),
    ("新能源", ("锂电", "电池", "光伏", "风电", "新能源", "储能")),
    ("半导体", ("半导体", "芯片", "集成电路", "电子元件")),
    ("医药", ("医药", "生物", "医疗", "制药")),
    ("银行", ("银行",)),
    ("地产", ("房地产", "地产", "园区")),
    ("军工", ("军工", "航天", "国防")),
    ("消费", ("消费", "零售", "商贸", "食品")),
    ("计算机", ("计算机", "软件", "互联网", "IT")),
    ("汽车", ("汽车", "整车", "零部件")),
    ("电力", ("电力", "水电", "火电")),
    ("煤炭", ("煤炭", "采掘")),
    ("钢铁", ("钢铁", "金属制品")),
    ("券商", ("证券", "券商", "保险", "非银", "多元金融")),
    ("机械", ("机械", "工程机械", "专用设备", "重工", "装备")),
    ("有色金属", ("有色", "黄金", "铜", "铝", "稀土")),
    ("传媒", ("传媒", "游戏", "影视", "广告")),
)

_NAME_HINTS: dict[str, str] = {
    "茅台": "白酒",
    "五粮": "白酒",
    "宁德": "新能源",
    "比亚迪": "汽车",
    "中芯": "半导体",
    "招行": "银行",
    "平安": "券商",
    "徐工": "机械",
    "招商": "券商",
}


def normalize_sector(raw: str) -> str:
    text = _ROMAN_SUFFIX.sub("", raw.strip())
    if not text:
        return "未知"
    if text in AVAILABLE_SECTORS:
        return text
    for sector, keywords in _SECTOR_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return sector
    return text[:20]


def sector_from_name(name: str) -> str | None:
    if "银行" in name:
        return "银行"
    if "证券" in name:
        return "券商"
    if any(keyword in name for keyword in ("徐工", "机械", "重工", "装备")):
        return "机械"
    for hint, sector in sorted(_NAME_HINTS.items(), key=lambda item: len(item[0]), reverse=True):
        if hint in name:
            return sector
    return None


def _eastmoney_secid(symbol: str) -> str:
    market = "1" if symbol.startswith("6") else "0"
    return f"{market}.{symbol}"


def fetch_eastmoney_sector(symbol: str) -> str | None:
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "secid": _eastmoney_secid(symbol),
        "fields": "f127",
        "ut": "fa5fd1943c7b386f172d6893dbfba9b",
    }
    headers = {
        "Referer": "https://quote.eastmoney.com/",
        "User-Agent": "Mozilla/5.0",
    }
    with httpx.Client(timeout=_EASTMONEY_TIMEOUT_SEC) as client:
        resp = client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        raw = data.get("f127")
        if not raw:
            return None
        return normalize_sector(str(raw))


async def resolve_stock_sector(symbol: str, name: str = "") -> str:
    if symbol in SYMBOL_SECTORS:
        return SYMBOL_SECTORS[symbol]
    if get_settings().use_mock_market_data:
        hinted = sector_from_name(name)
        return hinted or SYMBOL_SECTORS.get(symbol, "未知")
    try:
        raw = await asyncio.wait_for(
            asyncio.to_thread(fetch_eastmoney_sector, symbol),
            timeout=_EASTMONEY_TIMEOUT_SEC,
        )
        if raw:
            return raw
    except Exception as exc:
        logger.warning("East Money sector lookup failed for %s: %s", symbol, exc)
    hinted = sector_from_name(name)
    return hinted or "未知"


async def backfill_holding_sectors(holdings: list[Holding]) -> tuple[int, int]:
    """Fill sector for holdings marked 未知. Returns (updated, skipped)."""
    targets = [h for h in holdings if not h.sector or h.sector == "未知"]
    skipped = len(holdings) - len(targets)
    if not targets:
        return 0, skipped

    sectors = await asyncio.gather(
        *[resolve_stock_sector(h.symbol, h.name) for h in targets]
    )
    updated = 0
    for holding, sector in zip(targets, sectors, strict=True):
        if sector != "未知" and holding.sector != sector:
            holding.sector = sector
            updated += 1
    return updated, skipped
