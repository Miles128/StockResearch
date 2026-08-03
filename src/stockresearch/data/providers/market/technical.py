"""K-line provider — AkShare primary, efinance/Tushare/Sina fallback."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import akshare as ak  # type: ignore[import-untyped]

from stockresearch.data.providers.base import run_sync_fetch
from stockresearch.data.providers.efinance_quote import fetch_efinance_kline
from stockresearch.data.providers.market.common import _mock_quote, _use_mock_market_data
from stockresearch.data.providers.sina_kline import fetch_sina_kline
from stockresearch.services.provider_cache_policy import provider_ttl
from stockresearch.services.sqlite_cache import get_sqlite_cached, set_sqlite_cached

logger = logging.getLogger(__name__)


_INDEX_KLINE_SYMBOLS = frozenset({"000001", "399001", "399006", "000300"})


class TechnicalDataProvider:
    @staticmethod
    def _calendar_start(end: datetime, days: int) -> str:
        """Approximate calendar lookback for *days* trading bars."""
        calendar_days = max(int(days * 1.55) + 15, 30)
        return (end - timedelta(days=calendar_days)).strftime("%Y%m%d")

    @staticmethod
    def _bars_from_akshare_df(df: Any, days: int) -> list[dict[str, float | str]]:
        if df is None or df.empty:
            return []
        recent = df.tail(days)
        return [
            {
                "date": str(row["日期"])[:10],
                "open": float(row["开盘"]),
                "high": float(row["最高"]),
                "low": float(row["最低"]),
                "close": float(row["收盘"]),
                "volume": float(row["成交量"]),
            }
            for _, row in recent.iterrows()
        ]

    async def _fetch_akshare_kline_df(
        self,
        symbol: str,
        *,
        start_date: str,
        end_date: str,
    ) -> Any:
        if symbol in _INDEX_KLINE_SYMBOLS:
            return await run_sync_fetch(
                f"akshare index kline {symbol}",
                lambda: ak.index_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                ),
                timeout=10.0,
                fallback=None,
            )
        return await run_sync_fetch(
            f"akshare kline {symbol}",
            lambda: ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            ),
            timeout=10.0,
            fallback=None,
        )

    @staticmethod
    def _kline_adjust(source: str) -> str:
        # AkShare hist / efinance fqt=1 / Tushare pro_bar adj="qfq".
        return "qfq" if source in ("akshare", "efinance", "tushare") else "none"

    async def get_kline_bars(
        self,
        symbol: str,
        days: int = 90,
        *,
        before: str | None = None,
        prefer_qfq: bool = False,
    ) -> list[dict[str, float | str]]:
        bars, _source, _adjust = await self.get_kline_bars_meta(
            symbol, days, before=before, prefer_qfq=prefer_qfq
        )
        return bars

    async def get_kline_bars_meta(
        self,
        symbol: str,
        days: int = 90,
        *,
        before: str | None = None,
        prefer_qfq: bool = False,
    ) -> tuple[list[dict[str, float | str]], str, str]:
        if _use_mock_market_data():
            quote = _mock_quote(symbol)
            base = quote.price
            bars = [
                {
                    "date": (datetime.now(UTC).date().isoformat()),
                    "open": round(base * 0.99, 4),
                    "high": round(base * 1.01, 4),
                    "low": round(base * 0.98, 4),
                    "close": round(base * (1 + 0.002 * i), 4),
                    "volume": 1_000_000.0 + i * 10_000,
                }
                for i in range(max(days, 20))
            ]
            return bars, "mock", "none"

        end_dt = datetime.now(UTC)
        if before:
            try:
                end_dt = datetime.strptime(before[:10], "%Y-%m-%d").replace(tzinfo=UTC) - timedelta(
                    days=1
                )
            except ValueError:
                end_dt = datetime.now(UTC)
        end_date = end_dt.strftime("%Y%m%d")
        start_date = self._calendar_start(end_dt, days)
        cache_key = f"kline:{symbol}:{days}:{before or 'latest'}:{'qfq' if prefer_qfq else 'fast'}"
        ttl = provider_ttl("akshare_kline")
        cached = get_sqlite_cached(cache_key)
        if cached is not None and isinstance(cached.get("bars"), list):
            cached_bars = cached["bars"]
            if cached_bars:
                source = str(cached.get("source") or "unknown")
                return cached_bars, source, self._kline_adjust(source)  # type: ignore[return-value]

        bars: list[dict[str, float | str]] = []
        source = "unknown"

        # PRD §5.1: 日 K 线 AkShare 优先（前复权 stock_zh_a_hist），efinance →
        # Tushare（prefer_qfq=True 路径）→ 新浪（非 qfq，最后兜底）。
        # 不再让 Sina 抢先；quote/UI hot path 与 chart path 都从 AkShare 开始。
        if not bars:
            ak_df = await self._fetch_akshare_kline_df(
                symbol, start_date=start_date, end_date=end_date
            )
            bars = self._bars_from_akshare_df(ak_df, days)
            if bars:
                source = "akshare"
            elif prefer_qfq:
                # One short retry — AkShare qfq flakes frequently under load.
                await asyncio.sleep(0.35)
                ak_df = await self._fetch_akshare_kline_df(
                    symbol, start_date=start_date, end_date=end_date
                )
                bars = self._bars_from_akshare_df(ak_df, days)
                if bars:
                    source = "akshare"

        if prefer_qfq and not bars:
            # AkShare adjust=qfq often flakes; efinance fqt=1 is the qfq fallback.
            ef_bars = await run_sync_fetch(
                f"efinance kline qfq {symbol}",
                lambda: fetch_efinance_kline(symbol, days, fqt=1),
                timeout=12.0,
                fallback=None,
            )
            if ef_bars:
                bars = ef_bars
                source = "efinance"

        if prefer_qfq and not bars:
            from stockresearch.data.providers.tushare_financial import fetch_qfq_bars_sync

            ts_bars = await run_sync_fetch(
                f"tushare kline qfq {symbol}",
                lambda: fetch_qfq_bars_sync(symbol, days=days, end_date=end_date),
                timeout=12.0,
                fallback=None,
            )
            if ts_bars:
                bars = ts_bars
                source = "tushare"

        if not prefer_qfq and not bars:
            # 默认路径兜底：efinance(qfq) → Sina(非 qfq)。Sina 是最后兜底，因其非前复权。
            ef_bars = await run_sync_fetch(
                f"efinance kline {symbol}",
                lambda: fetch_efinance_kline(symbol, days, fqt=1),
                timeout=12.0,
                fallback=None,
            )
            if ef_bars:
                bars = ef_bars
                source = "efinance"

            if not bars and before is None:
                sina_bars = await run_sync_fetch(
                    f"sina kline {symbol}",
                    lambda: fetch_sina_kline(symbol, days),
                    timeout=8.0,
                    fallback=None,
                )
                if sina_bars:
                    bars = sina_bars
                    source = "sina"

        if bars:
            if before:
                cutoff = before[:10]
                bars = [b for b in bars if str(b["date"])[:10] < cutoff]
            adjust = self._kline_adjust(source)
            if not prefer_qfq or adjust == "qfq":
                set_sqlite_cached(cache_key, {"bars": bars, "source": source}, ttl)
            logger.info("Kline for %s: %d bars via %s (%s)", symbol, len(bars), source, adjust)
            return bars, source, adjust

        logger.warning(
            "Kline unavailable for %s after %s",
            symbol,
            "akshare/efinance/tushare (prefer_qfq)" if prefer_qfq else "akshare/efinance/sina",
        )
        return bars, source, self._kline_adjust(source)

    async def get_kline(self, symbol: str, days: int = 60) -> list[dict[str, float]]:
        bars = await self.get_kline_bars(symbol, days)
        return [{"close": float(b["close"]), "volume": float(b["volume"])} for b in bars]

    async def get_kline_chart(
        self,
        symbol: str,
        days: int = 90,
        *,
        before: str | None = None,
    ) -> dict[str, object]:
        from stockresearch.data.technical_indicators import (
            atr_series,
            boll_series,
            kdj_series,
            ma_series,
            macd_series,
            rsi_series,
        )

        bars, source, adjust = await self.get_kline_bars_meta(
            symbol, days, before=before, prefer_qfq=True
        )
        if not bars:
            # Chart may still render unadjusted bars when AkShare qfq is down.
            bars, source, adjust = await self.get_kline_bars_meta(
                symbol, days, before=before, prefer_qfq=False
            )
        closes = [float(b["close"]) for b in bars]
        highs = [float(b["high"]) for b in bars]
        lows = [float(b["low"]) for b in bars]
        macd = macd_series(closes)
        boll = boll_series(closes)
        kdj = kdj_series(highs, lows, closes)
        return {
            "symbol": symbol,
            "days": days,
            "bars": bars,
            "source": source,
            "adjust": adjust,
            "indicators": {
                "ma20": ma_series(closes, 20),
                "rsi": rsi_series(closes),
                "macd": macd["macd"],
                "macd_signal": macd["signal"],
                "macd_histogram": macd["histogram"],
                "boll_mid": boll["mid"],
                "boll_upper": boll["upper"],
                "boll_lower": boll["lower"],
                "atr": atr_series(highs, lows, closes),
                "kdj_k": kdj["k"],
                "kdj_d": kdj["d"],
                "kdj_j": kdj["j"],
            },
        }

    def calc_ma(self, closes: list[float], window: int) -> float:
        if not closes:
            return 0.0
        segment = closes[-window:] if len(closes) >= window else closes
        return sum(segment) / len(segment)

    def calc_macd_rsi(self, closes: list[float]) -> dict[str, float]:
        if len(closes) < 2:
            return {"macd": 0.0, "rsi": 50.0}
        gains = [max(closes[i] - closes[i - 1], 0) for i in range(1, len(closes))]
        losses = [max(closes[i - 1] - closes[i], 0) for i in range(1, len(closes))]
        avg_gain = sum(gains[-14:]) / max(len(gains[-14:]), 1)
        avg_loss = sum(losses[-14:]) / max(len(losses[-14:]), 1)
        rs = avg_gain / avg_loss if avg_loss else 100.0
        rsi = 100 - (100 / (1 + rs))
        macd = closes[-1] - self.calc_ma(closes, 12)
        return {"macd": round(macd, 4), "rsi": round(rsi, 2)}
