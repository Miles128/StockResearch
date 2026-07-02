"""efinance 平行备源行情 — 当 Sina + AkShare 都失败时使用。

efinance 通过东方财富推送接口拉取实时行情，与 Sina/AkShare 互不依赖，
作为行情链路的第三层兜底，最大程度降低单点失败概率。
"""

import logging
from datetime import UTC, datetime
from typing import Any

from stockresearch.core.exceptions import DataProviderError
from stockresearch.utils.symbols import resolve_name

logger = logging.getLogger(__name__)

try:
    import efinance as ef  # type: ignore[import-untyped]

    _HAS_EFINANCE = True
except ImportError:
    _HAS_EFINANCE = False


def is_available() -> bool:
    """运行环境是否安装了 efinance。"""
    return _HAS_EFINANCE


def fetch_efinance_quotes(symbols: list[str]) -> dict[str, dict[str, float | str]]:
    """通过 efinance 批量拉取实时行情。

    efinance.stock_data.get_quote_history() 默认拉取历史，最新一行即为当日行情。
    为减少请求量，仅请求最近 2 个交易日数据。
    """
    if not _HAS_EFINANCE:
        raise DataProviderError("efinance 未安装")

    unique = list(dict.fromkeys(symbols))
    if not unique:
        return {}

    results: dict[str, dict[str, float | str]] = {}
    for symbol in unique:
        try:
            df: Any = ef.stock.get_quote_history(symbol, kctypes="1")  # 1=日K
        except Exception as exc:
            logger.warning("efinance quote failed for %s: %s", symbol, exc)
            continue
        if df is None or len(df) == 0:
            continue
        try:
            last = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else last
            price = float(last["收盘"])
            prev_close = float(prev["收盘"])
            change_pct = (
                round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0
            )
            results[symbol] = {
                "symbol": symbol,
                "name": str(last.get("股票名称", "") or resolve_name(symbol)),
                "price": price,
                "change_pct": change_pct,
                "high": float(last.get("最高", 0) or 0),
                "low": float(last.get("最低", 0) or 0),
                "volume": float(last.get("成交量", 0) or 0),
                "updated_at": datetime.now(UTC),
            }
        except (KeyError, ValueError, IndexError) as exc:
            logger.warning("efinance quote parse failed for %s: %s", symbol, exc)
            continue

    if not results:
        raise DataProviderError("efinance 行情返回空")
    logger.info("Fetched %d/%d quotes from efinance", len(results), len(unique))
    return results


def fetch_efinance_kline(symbol: str, days: int) -> list[dict[str, float | str]]:
    """Daily OHLCV history via efinance."""
    if not _HAS_EFINANCE:
        raise DataProviderError("efinance 未安装")
    if days < 1:
        return []

    try:
        df: Any = ef.stock.get_quote_history(symbol, klt=101)
    except TypeError:
        df = ef.stock.get_quote_history(symbol)
    except Exception as exc:
        raise DataProviderError(f"efinance kline failed for {symbol}: {exc}") from exc

    if df is None or len(df) == 0:
        raise DataProviderError(f"efinance kline empty for {symbol}")

    bars: list[dict[str, float | str]] = []
    for _, row in df.iterrows():
        try:
            day_raw = row.get("日期") or row.get("date")
            bars.append(
                {
                    "date": str(day_raw)[:10],
                    "open": float(row["开盘"]),
                    "high": float(row["最高"]),
                    "low": float(row["最低"]),
                    "close": float(row["收盘"]),
                    "volume": float(row["成交量"]),
                }
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("efinance kline parse skip for %s: %s", symbol, exc)
            continue

    if not bars:
        raise DataProviderError(f"efinance kline parse failed for {symbol}")

    trimmed = bars[-days:]
    logger.info("Fetched %d kline bars from efinance for %s", len(trimmed), symbol)
    return trimmed
