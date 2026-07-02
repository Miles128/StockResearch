"""Sina Finance daily K-line — direct HTTP, bypasses system proxy (trust_env=False)."""

import logging
from typing import TypeAlias

import httpx

from stockresearch.core.exceptions import DataProviderError

logger = logging.getLogger(__name__)

_SINA_TIMEOUT_SEC = 12.0
_KlineBar: TypeAlias = dict[str, float | str]

_SH_INDEX_SYMBOLS = frozenset({"000001", "000300"})


def _sina_kline_code(symbol: str) -> str:
    if symbol.startswith("6") or symbol in _SH_INDEX_SYMBOLS:
        return f"sh{symbol}"
    if symbol.startswith(("4", "8")):
        return f"bj{symbol}"
    return f"sz{symbol}"


def fetch_sina_kline(symbol: str, days: int) -> list[_KlineBar]:
    """Fetch daily OHLCV bars; at least ``days`` most recent rows when available."""
    if days < 1:
        return []
    sina_sym = _sina_kline_code(symbol)
    datalen = min(max(days + 5, 30), 1023)
    url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    params = {"symbol": sina_sym, "scale": "240", "ma": "no", "datalen": str(datalen)}
    headers = {"Referer": "https://finance.sina.com.cn"}

    with httpx.Client(timeout=_SINA_TIMEOUT_SEC, trust_env=False) as client:
        resp = client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        rows = resp.json()

    if not isinstance(rows, list) or not rows:
        raise DataProviderError(f"Sina kline empty for {symbol}")

    bars: list[_KlineBar] = []
    for row in rows:
        try:
            bars.append(
                {
                    "date": str(row["day"])[:10],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                }
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Sina kline parse skip for %s: %s", symbol, exc)
            continue

    if not bars:
        raise DataProviderError(f"Sina kline parse failed for {symbol}")

    trimmed = bars[-days:]
    logger.info("Fetched %d/%d kline bars from Sina for %s", len(trimmed), len(bars), symbol)
    return trimmed


def fetch_sina_intraday(symbol: str, *, scale: int = 5, datalen: int = 96) -> list[dict[str, str | float]]:
    """Fetch intraday price points (5-min bars by default) for sparkline charts."""
    sina_sym = _sina_kline_code(symbol)
    url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    params = {"symbol": sina_sym, "scale": str(scale), "ma": "no", "datalen": str(datalen)}
    headers = {"Referer": "https://finance.sina.com.cn"}

    with httpx.Client(timeout=_SINA_TIMEOUT_SEC, trust_env=False) as client:
        resp = client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        rows = resp.json()

    if not isinstance(rows, list) or not rows:
        return []

    points: list[dict[str, str | float]] = []
    for row in rows:
        try:
            day = str(row["day"])
            time_part = day[11:16] if len(day) >= 16 else day[-5:]
            points.append({"time": time_part, "price": float(row["close"])})
        except (KeyError, TypeError, ValueError) as exc:
            logger.debug("Sina intraday parse skip for %s: %s", symbol, exc)
            continue
    return points
