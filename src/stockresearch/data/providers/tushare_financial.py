"""Optional Tushare Pro enrichment when user supplies a token."""

import logging

from stockresearch.core.data_source_config import get_tushare_token

logger = logging.getLogger(__name__)


def _ts_code(symbol: str) -> str:
    suffix = "SH" if symbol.startswith("6") else "SZ"
    return f"{symbol}.{suffix}"


def fetch_daily_basic_sync(symbol: str, token: str | None = None) -> dict[str, float | str] | None:
    """Fetch PE/PB/turnover from Tushare daily_basic. Returns None if unavailable."""
    resolved = (token or get_tushare_token() or "").strip()
    if not resolved:
        return None
    try:
        import tushare as ts
    except ImportError:
        logger.debug("tushare package not installed")
        return None
    try:
        ts.set_token(resolved)
        pro = ts.pro_api()
        df = pro.daily_basic(
            ts_code=_ts_code(symbol),
            fields="ts_code,pe_ttm,pb,total_mv,turnover_rate",
        )
        if df is None or df.empty:
            return None
        row = df.iloc[0]
        return {
            "pe_ttm": float(row.get("pe_ttm") or 0),
            "pb": float(row.get("pb") or 0),
            "total_mv": float(row.get("total_mv") or 0),
            "turnover_rate": float(row.get("turnover_rate") or 0),
            "source": "tushare_daily_basic",
        }
    except Exception as exc:
        logger.warning("Tushare daily_basic failed for %s: %s", symbol, exc)
        return None
