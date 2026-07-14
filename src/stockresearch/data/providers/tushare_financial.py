"""Optional Tushare Pro enrichment when user supplies a token."""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from stockresearch.core.data_source_config import get_tushare_token

logger = logging.getLogger(__name__)

# Tushare 库的 set_token() 修改进程级全局状态，且 pro_api() 不接受 token 参数。
# 多个并发请求若使用不同 token 会相互覆盖。用全局锁串行化 set_token + pro_api 调用，
# 确保每次调用使用正确的 token。本机单用户 MVP 下并发量低，锁竞争可忽略。
_tushare_lock = threading.Lock()

TushareProbeStatus = Literal["no_token", "unavailable", "invalid", "ok", "quota"]


def _ts_code(symbol: str) -> str:
    """Map 6-digit A-share code to Tushare ts_code (SH/SZ/BJ)."""
    code = (symbol or "").strip()
    # 北交所：4xxxxx / 8xxxxx 传统码，以及 9xxxxx（如 920xxx）新码。
    if code.startswith(("4", "8", "9")):
        return f"{code}.BJ"
    if code.startswith("6"):
        return f"{code}.SH"
    return f"{code}.SZ"


def _with_pro(token: str, fn: Any) -> Any:
    import tushare as ts

    with _tushare_lock:
        ts.set_token(token)
        pro = ts.pro_api()
        return fn(pro)


def fetch_daily_basic_sync(symbol: str, token: str | None = None) -> dict[str, float | str] | None:
    """Fetch PE/PB/turnover from Tushare daily_basic. Returns None if unavailable."""
    resolved = (token or get_tushare_token() or "").strip()
    if not resolved:
        return None
    try:
        import tushare as ts  # noqa: F401
    except ImportError:
        logger.debug("tushare package not installed")
        return None
    try:

        def _call(pro: Any) -> Any:
            return pro.daily_basic(
                ts_code=_ts_code(symbol),
                fields="ts_code,pe_ttm,pb,total_mv,turnover_rate",
            )

        df = _with_pro(resolved, _call)
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


def fetch_qfq_bars_sync(
    symbol: str,
    *,
    days: int = 90,
    end_date: str | None = None,
    token: str | None = None,
) -> list[dict[str, float | str]] | None:
    """Fetch qfq daily bars via Tushare pro_bar / daily. None on skip or failure."""
    resolved = (token or get_tushare_token() or "").strip()
    if not resolved:
        return None
    try:
        import tushare as ts
    except ImportError:
        return None

    end = (end_date or datetime.now(UTC).strftime("%Y%m%d"))[:8]
    try:
        end_dt = datetime.strptime(end, "%Y%m%d").replace(tzinfo=UTC)
    except ValueError:
        end_dt = datetime.now(UTC)
        end = end_dt.strftime("%Y%m%d")
    start = (end_dt - timedelta(days=max(days * 2, 120))).strftime("%Y%m%d")
    ts_code = _ts_code(symbol)

    try:
        with _tushare_lock:
            ts.set_token(resolved)
            # Prefer adj-factor aware pro_bar when available.
            try:
                df = ts.pro_bar(ts_code=ts_code, adj="qfq", start_date=start, end_date=end)
            except Exception as exc:
                msg = str(exc).lower()
                if "积分" in str(exc) or "point" in msg or "permission" in msg:
                    logger.info("Tushare qfq skipped for %s (quota/permission): %s", symbol, exc)
                    return None
                pro = ts.pro_api()
                df = pro.daily(ts_code=ts_code, start_date=start, end_date=end)
        if df is None or getattr(df, "empty", True):
            return None

        # Normalize column names across pro_bar / daily.
        date_col = "trade_date" if "trade_date" in df.columns else None
        if date_col is None:
            return None
        df = df.sort_values(date_col)
        recent = df.tail(days)
        bars: list[dict[str, float | str]] = []
        for _, row in recent.iterrows():
            raw_date = str(row[date_col])
            if len(raw_date) == 8 and raw_date.isdigit():
                date_str = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
            else:
                date_str = raw_date[:10]
            bars.append(
                {
                    "date": date_str,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("vol", row.get("volume", 0)) or 0),
                }
            )
        return bars or None
    except Exception as exc:
        msg = str(exc).lower()
        if "积分" in str(exc) or "point" in msg or "permission" in msg:
            logger.info("Tushare qfq skipped for %s (quota/permission): %s", symbol, exc)
        else:
            logger.warning("Tushare qfq bars failed for %s: %s", symbol, exc)
        return None


def probe_tushare_token(token: str | None = None) -> TushareProbeStatus:
    """Lightweight probe: package + token + one trade_cal / daily_basic call."""
    resolved = (token or get_tushare_token() or "").strip()
    if not resolved:
        return "no_token"
    try:
        import tushare as ts
    except ImportError:
        return "unavailable"
    try:
        with _tushare_lock:
            ts.set_token(resolved)
            pro = ts.pro_api()
            # trade_cal is cheap and widely available even on low-point accounts.
            df = pro.trade_cal(exchange="SSE", start_date="20240102", end_date="20240105")
        if df is None:
            return "invalid"
        return "ok"
    except Exception as exc:
        text = str(exc)
        lower = text.lower()
        if "积分" in text or "point" in lower or "权限" in text:
            return "quota"
        if "token" in lower or "无效" in text or "invalid" in lower or "权限" in text:
            return "invalid"
        logger.warning("Tushare probe failed: %s", exc)
        return "invalid"
