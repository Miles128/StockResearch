"""Sina Finance batch stock quotes — one HTTP round-trip for many symbols."""

import logging
from datetime import UTC, datetime

import httpx

from stockresearch.core.exceptions import DataProviderError
from stockresearch.utils.symbols import resolve_name

logger = logging.getLogger(__name__)

_SINA_TIMEOUT_SEC = 5.0


def _sina_code(symbol: str) -> str:
    prefix = "sh" if symbol.startswith("6") else "sz"
    return f"{prefix}{symbol}"


def fetch_sina_quotes(symbols: list[str]) -> dict[str, dict[str, float | str]]:
    unique = list(dict.fromkeys(symbols))
    if not unique:
        return {}

    sina_codes = [_sina_code(sym) for sym in unique]
    code_to_symbol = dict(zip(sina_codes, unique, strict=True))
    url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
    headers = {"Referer": "https://finance.sina.com.cn"}

    with httpx.Client(timeout=_SINA_TIMEOUT_SEC) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        text = resp.content.decode("gbk", errors="ignore")

    results: dict[str, dict[str, float | str]] = {}
    for line in text.strip().split(";"):
        if "hq_str_" not in line:
            continue
        _, _, remainder = line.partition("hq_str_")
        sina_code, _, rest = remainder.partition("=")
        payload = rest.strip().strip('"')
        if not payload:
            continue
        symbol = code_to_symbol.get(sina_code)
        if symbol is None:
            continue
        fields = payload.split(",")
        if len(fields) < 10:
            continue
        try:
            price = float(fields[3] or 0)
            prev_close = float(fields[2] or price)
        except ValueError:
            continue
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0.0
        results[symbol] = {
            "symbol": symbol,
            "name": fields[0] or resolve_name(symbol),
            "price": price,
            "change_pct": round(change_pct, 2),
            "high": float(fields[4] or 0),
            "low": float(fields[5] or 0),
            "volume": float(fields[8] or 0),
            "updated_at": datetime.now(UTC),
        }

    if not results:
        raise DataProviderError("Sina quote response empty")
    logger.info("Fetched %d/%d quotes from Sina", len(results), len(unique))
    return results
