"""Sina Finance index quotes — free backup when East Money/AkShare fails."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

logger = logging.getLogger(__name__)

_SINA_INDEX_LIST = (
    ("s_sh000001", "000001", "上证指数"),
    ("s_sz399001", "399001", "深证成指"),
    ("s_sz399006", "399006", "创业板指"),
    ("s_sh000300", "000300", "沪深300"),
)


@dataclass(frozen=True)
class SinaIndexQuote:
    name: str
    symbol: str
    price: float
    change_pct: float


def fetch_sina_indices() -> list[SinaIndexQuote]:
    codes = ",".join(item[0] for item in _SINA_INDEX_LIST)
    url = f"https://hq.sinajs.cn/list={codes}"
    headers = {"Referer": "https://finance.sina.com.cn"}

    with httpx.Client(timeout=5.0) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        text = resp.content.decode("gbk", errors="ignore")

    by_sina_code = {item[0]: (item[1], item[2]) for item in _SINA_INDEX_LIST}
    results: list[SinaIndexQuote] = []

    for line in text.strip().split(";"):
        if "hq_str_" not in line:
            continue
        _, _, remainder = line.partition("hq_str_")
        sina_code, _, rest = remainder.partition("=")
        payload = rest.strip().strip('"')
        if not payload:
            continue
        parts = payload.split(",")
        if len(parts) < 4:
            continue
        meta = by_sina_code.get(sina_code)
        if meta is None:
            continue
        symbol, label = meta
        try:
            price = float(parts[1])
            change_pct = float(parts[3])
        except ValueError:
            continue
        results.append(
            SinaIndexQuote(name=label, symbol=symbol, price=price, change_pct=change_pct)
        )

    if not results:
        raise ValueError("Sina index response empty")
    logger.info("Fetched %d indices from Sina", len(results))
    return results
