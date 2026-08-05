"""AkShare daily K-line fallback quotes when Sina is unavailable."""

import logging
import time
from datetime import UTC, datetime, timedelta

import akshare as ak

from stockresearch.core.exceptions import DataProviderError
from stockresearch.utils.symbols import resolve_name

logger = logging.getLogger(__name__)


def fetch_akshare_hist_quotes(
    symbols: list[str],
) -> dict[str, dict[str, float | str | datetime]]:
    """Last trading day OHLCV per symbol via AkShare hist (slower, more reliable)."""
    unique = list(dict.fromkeys(symbols))
    if not unique:
        return {}

    end_date = datetime.now(UTC).strftime("%Y%m%d")
    start_date = (datetime.now(UTC) - timedelta(days=20)).strftime("%Y%m%d")
    results: dict[str, dict[str, float | str | datetime]] = {}

    for symbol in unique:
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            )
        except Exception as exc:
            logger.warning("AkShare hist quote failed for %s: %s", symbol, exc)
            continue
        if df is None or df.empty:
            continue
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        price = float(last["收盘"])
        prev_close = float(prev["收盘"])
        change_pct = round(((price - prev_close) / prev_close * 100) if prev_close else 0.0, 2)
        results[symbol] = {
            "symbol": symbol,
            "name": resolve_name(symbol),
            "price": price,
            "open": float(last["开盘"]),
            "change_pct": change_pct,
            "high": float(last["最高"]),
            "low": float(last["最低"]),
            "volume": float(last["成交量"]),
            "updated_at": datetime.now(UTC),
        }
        time.sleep(0.3)

    if not results:
        raise DataProviderError("AkShare 历史行情不可用")
    logger.info("Fetched %d/%d quotes from AkShare hist", len(results), len(unique))
    return results
