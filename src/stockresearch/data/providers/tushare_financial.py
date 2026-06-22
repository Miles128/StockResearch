"""Optional Tushare Pro enrichment when user supplies a token."""

import logging
import threading

from stockresearch.core.data_source_config import get_tushare_token

logger = logging.getLogger(__name__)

# Tushare 库的 set_token() 修改进程级全局状态，且 pro_api() 不接受 token 参数。
# 多个并发请求若使用不同 token 会相互覆盖。用全局锁串行化 set_token + pro_api 调用，
# 确保每次调用使用正确的 token。本机单用户 MVP 下并发量低，锁竞争可忽略。
_tushare_lock = threading.Lock()


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
        # 串行化：set_token 和 pro_api 必须在同一个临界区内完成，
        # 避免并发请求覆盖彼此的 token。
        with _tushare_lock:
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
