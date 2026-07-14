"""Market data providers — Sina quotes on hot path, AkShare for historical."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import akshare as ak  # type: ignore[import-untyped]

from stockresearch.core.config import get_settings
from stockresearch.core.exceptions import DataProviderError
from stockresearch.data.providers.akshare_quote import fetch_akshare_hist_quotes
from stockresearch.data.providers.base import run_sync_fetch
from stockresearch.data.providers.efinance_quote import fetch_efinance_kline, fetch_efinance_quotes
from stockresearch.data.providers.sina_kline import fetch_sina_kline
from stockresearch.data.providers.sina_quote import QuoteRow, fetch_sina_quotes
from stockresearch.data.providers.tushare_financial import fetch_daily_basic_sync
from stockresearch.data.registry import record_quote_fetch, record_quote_conflicts, record_symbol_sources
from stockresearch.data.registry import QuotePriceConflict
from stockresearch.data.provider_meta import get_provider_meta
from stockresearch.services.cache import peek_cached
from stockresearch.services.provider_cache_policy import (
    DEFAULT_QUOTE_CACHE_TTL_SECONDS,
    get_or_set_cached_dict,
    provider_ttl,
)
from stockresearch.services.sqlite_cache import get_sqlite_cached, set_sqlite_cached
from stockresearch.utils.symbols import resolve_name

logger = logging.getLogger(__name__)

_QUOTE_TIMEOUT_SEC = 6.0
_DATA_TIMEOUT_SEC = 8.0

_POSITIVE_NEWS = ("增长", "利好", "超预期", "分红", "回购", "上涨", "突破", "中标")
_NEGATIVE_NEWS = ("下滑", "亏损", "减持", "问询", "立案", "下调", "警示", "违规", "解禁")


def _as_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, datetime):
        return default
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _as_datetime(value: object) -> datetime:
    return value if isinstance(value, datetime) else datetime.now(UTC)


def _market_code(symbol: str) -> str:
    if symbol.startswith("6"):
        return "sh"
    if symbol.startswith(("4", "8")):
        return "bj"
    return "sz"


@dataclass(frozen=True)
class Quote:
    symbol: str
    name: str
    price: float
    change_pct: float
    open: float
    high: float
    low: float
    volume: float
    updated_at: datetime


_MOCK_QUOTE_DEFAULTS: dict[str, tuple[float, str]] = {
    "600519": (1800.0, "贵州茅台"),
    "300750": (250.0, "宁德时代"),
    "601318": (50.0, "中国平安"),
}


def _use_mock_market_data() -> bool:
    return get_settings().use_mock_market_data


def _mock_quote(symbol: str) -> Quote:
    price, name = _MOCK_QUOTE_DEFAULTS.get(symbol, (100.0, resolve_name(symbol)))
    now = datetime.now(UTC)
    return Quote(
        symbol=symbol,
        name=name,
        price=price,
        change_pct=1.2,
        open=round(price * 0.99, 4),
        high=round(price * 1.02, 4),
        low=round(price * 0.98, 4),
        volume=1_000_000.0,
        updated_at=now,
    )


def _quote_to_cache(quote: Quote) -> dict[str, object]:
    return {
        "symbol": quote.symbol,
        "name": quote.name,
        "price": quote.price,
        "change_pct": quote.change_pct,
        "open": quote.open,
        "high": quote.high,
        "low": quote.low,
        "volume": quote.volume,
        "updated_at": quote.updated_at.isoformat(),
        "source": "cache",
    }


def _quote_from_cache(payload: dict[str, object]) -> Quote | None:
    try:
        updated_raw = payload.get("updated_at")
        updated_at = (
            datetime.fromisoformat(str(updated_raw))
            if updated_raw
            else datetime.now(UTC)
        )
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        return Quote(
            symbol=str(payload["symbol"]),
            name=str(payload.get("name", "")),
            price=_as_float(payload.get("price")),
            change_pct=_as_float(payload.get("change_pct")),
            open=_as_float(payload.get("open")),
            high=_as_float(payload.get("high")),
            low=_as_float(payload.get("low")),
            volume=_as_float(payload.get("volume")),
            updated_at=updated_at,
        )
    except (KeyError, TypeError, ValueError):
        return None


class QuoteProvider:
    async def get_quote(
        self,
        symbol: str,
        *,
        cache_ttl_seconds: int | None = None,
    ) -> Quote:
        quotes = await self.get_quotes([symbol], cache_ttl_seconds=cache_ttl_seconds)
        if symbol not in quotes:
            raise DataProviderError(f"无法获取 {symbol} 行情")
        return quotes[symbol]

    async def get_quotes(
        self,
        symbols: list[str],
        *,
        cache_ttl_seconds: int | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Quote]:
        unique = list(dict.fromkeys(symbols))
        if not unique:
            return {}

        if _use_mock_market_data():
            return {sym: _mock_quote(sym) for sym in unique}

        ttl = (
            cache_ttl_seconds
            if cache_ttl_seconds is not None
            else DEFAULT_QUOTE_CACHE_TTL_SECONDS
        )
        out: dict[str, Quote] = {}
        to_fetch: list[str] = []
        if force_refresh:
            to_fetch = unique
        else:
            for sym in unique:
                cached = get_sqlite_cached(f"quote:{sym}")
                if cached is not None:
                    quote = _quote_from_cache(cached)
                    if quote is not None:
                        out[sym] = quote
                        continue
                to_fetch.append(sym)

        if to_fetch:
            raw = await self._fetch_quote_rows(to_fetch, background_ttl=ttl)
            fetched = self._rows_to_quotes(raw)
            for sym in to_fetch:
                if sym in fetched:
                    quote = fetched[sym]
                    set_sqlite_cached(f"quote:{sym}", _quote_to_cache(quote), ttl)
                    out[sym] = quote
                    continue
                if force_refresh:
                    cached = get_sqlite_cached(f"quote:{sym}")
                    if cached is not None:
                        quote = _quote_from_cache(cached)
                        if quote is not None:
                            out[sym] = quote

        return {sym: out[sym] for sym in unique if sym in out}

    async def _verify_cross_source_quotes(
        self,
        symbols: list[str],
        sina_rows: dict[str, QuoteRow],
    ) -> None:
        """PRD §6.1 — Sina vs AkShare price diff; runs off the request hot path."""
        try:
            verify_rows = await run_sync_fetch(
                "akshare cross-check quotes",
                lambda: fetch_akshare_hist_quotes(symbols),
                timeout=max(_QUOTE_TIMEOUT_SEC, 12.0),
                fallback=None,
            )
            if not verify_rows:
                return
            conflicts: list[QuotePriceConflict] = []
            for sym in symbols:
                sina_row = sina_rows.get(sym)
                ak_row = verify_rows.get(sym)
                if not sina_row or not ak_row:
                    continue
                primary_price = _as_float(sina_row.get("price"))
                compare_price = _as_float(ak_row.get("price"))
                if primary_price <= 0 or compare_price <= 0:
                    continue
                diff_pct = abs(primary_price - compare_price) / primary_price * 100.0
                if diff_pct > 1.0:
                    conflicts.append(
                        QuotePriceConflict(
                            symbol=sym,
                            name=str(sina_row.get("name") or ak_row.get("name") or sym),
                            primary_source="sina",
                            primary_price=primary_price,
                            compare_source="akshare",
                            compare_price=compare_price,
                            diff_pct=round(diff_pct, 2),
                        )
                    )
            record_quote_conflicts(conflicts)
        except Exception as exc:
            logger.debug("Background quote cross-check skipped: %s", exc)

    async def _background_fill_missing_quotes(
        self,
        symbols: list[str],
        cache_ttl_seconds: int,
    ) -> None:
        """Fill missing symbols off the request hot path."""
        if not symbols:
            return
        try:
            fallback_rows = await self._fetch_fallback_rows(symbols)
            if not fallback_rows:
                return
            fetched = self._rows_to_quotes(fallback_rows)
            for sym, quote in fetched.items():
                set_sqlite_cached(f"quote:{sym}", _quote_to_cache(quote), cache_ttl_seconds)
            record_symbol_sources(
                {
                    sym: str(fallback_rows[sym].get("_source", "efinance"))
                    for sym in symbols
                    if sym in fallback_rows
                }
            )
        except Exception as exc:
            logger.debug("Background quote fill failed: %s", exc)

    async def _fetch_fallback_rows(self, symbols: list[str]) -> dict[str, QuoteRow]:
        """Secondary sources for missing symbols (efinance, then akshare)."""
        raw: dict[str, QuoteRow] = {}

        ef_rows = await run_sync_fetch(
            "efinance quote fallback",
            lambda: fetch_efinance_quotes(symbols),
            timeout=max(_QUOTE_TIMEOUT_SEC, 8.0),
            fallback=None,
        )
        if ef_rows:
            for sym, ef_row in ef_rows.items():
                raw[sym] = cast(QuoteRow, {**ef_row, "_source": "efinance"})

        missing = [sym for sym in symbols if sym not in raw]
        if missing:
            ak_rows = await run_sync_fetch(
                "akshare hist quote fallback",
                lambda: fetch_akshare_hist_quotes(missing),
                timeout=max(_QUOTE_TIMEOUT_SEC, 8.0),
                fallback=None,
            )
            if ak_rows:
                for sym, ak_row in ak_rows.items():
                    raw[sym] = cast(QuoteRow, {**ak_row, "_source": "akshare"})

        return raw

    async def _fetch_quote_rows(
        self,
        symbols: list[str],
        *,
        background_ttl: int = DEFAULT_QUOTE_CACHE_TTL_SECONDS,
    ) -> dict[str, QuoteRow]:
        raw: dict[str, QuoteRow] = {}
        sina_error: str | None = None
        ak_count = 0
        ef_count = 0

        sina_rows = await run_sync_fetch(
            "sina batch quotes",
            lambda: fetch_sina_quotes(symbols),
            timeout=_QUOTE_TIMEOUT_SEC,
            fallback=None,
        )
        if sina_rows is None:
            sina_error = "新浪行情不可用或超时"
        else:
            for sym, row in sina_rows.items():
                raw[sym] = {**row, "_source": "sina"}
            asyncio.create_task(self._verify_cross_source_quotes(symbols, sina_rows))

        missing = [sym for sym in symbols if sym not in raw]

        # Partial Sina success: sync-fill gaps so holdings/risk see a complete book,
        # then keep background retry for any still-missing symbols.
        if missing and raw:
            fallback_rows = await self._fetch_fallback_rows(missing)
            for sym, row in fallback_rows.items():
                raw[sym] = row
            ak_count = sum(
                1 for sym in symbols if sym in raw and raw[sym].get("_source") == "akshare"
            )
            ef_count = sum(
                1 for sym in symbols if sym in raw and raw[sym].get("_source") == "efinance"
            )
            missing = [sym for sym in symbols if sym not in raw]
            if missing:
                asyncio.create_task(
                    self._background_fill_missing_quotes(missing, background_ttl)
                )
            sina_count = sum(
                1 for sym in symbols if sym in raw and raw[sym].get("_source") == "sina"
            )
            record_quote_fetch(
                requested=len(symbols),
                sina_count=sina_count,
                akshare_count=ak_count,
                efinance_count=ef_count,
                message=sina_error,
            )
            record_symbol_sources(
                {sym: str(raw[sym].get("_source", "sina")) for sym in symbols if sym in raw}
            )
            return raw

        if missing:
            fallback_rows = await self._fetch_fallback_rows(missing)
            for sym, row in fallback_rows.items():
                raw[sym] = row
            ak_count = sum(
                1 for sym in symbols if sym in raw and raw[sym].get("_source") == "akshare"
            )
            ef_count = sum(
                1 for sym in symbols if sym in raw and raw[sym].get("_source") == "efinance"
            )
            missing = [sym for sym in symbols if sym not in raw]
            if missing:
                asyncio.create_task(
                    self._background_fill_missing_quotes(missing, background_ttl)
                )

        if not raw:
            raise DataProviderError(sina_error or "行情数据不可用（sina/akshare/efinance 均失败）")

        sina_count = sum(1 for sym in symbols if sym in raw and raw[sym].get("_source") == "sina")
        record_quote_fetch(
            requested=len(symbols),
            sina_count=sina_count,
            akshare_count=ak_count,
            efinance_count=ef_count,
            message=sina_error,
        )
        record_symbol_sources(
            {sym: str(raw[sym].get("_source", "sina")) for sym in symbols if sym in raw}
        )
        return raw

    @staticmethod
    def _rows_to_quotes(
        raw: dict[str, QuoteRow],
    ) -> dict[str, Quote]:
        return {
            sym: Quote(
                symbol=str(row["symbol"]),
                name=str(row["name"]),
                price=_as_float(row["price"]),
                change_pct=_as_float(row["change_pct"]),
                open=_as_float(row.get("open")),
                high=_as_float(row["high"]),
                low=_as_float(row["low"]),
                volume=_as_float(row["volume"]),
                updated_at=_as_datetime(row["updated_at"]),
            )
            for sym, row in raw.items()
        }


class MarketRuleProvider:
    async def get_trading_rules(self, symbol: str) -> dict[str, object]:
        if _use_mock_market_data():
            return {
                "source": "mock",
                "verified": True,
                "status": "normal",
                "is_st": False,
                "is_suspended": False,
                "is_limit_up": False,
                "is_limit_down": False,
                "limit_pct": self._limit_pct(symbol, resolve_name(symbol)),
                "missing": [],
            }
        rows = await run_sync_fetch(
            f"sina trading rules {symbol}",
            lambda: fetch_sina_quotes([symbol]),
            timeout=_QUOTE_TIMEOUT_SEC,
            fallback={},
        )
        row = rows.get(symbol) if rows else None
        if not row:
            return {
                "source": "sina_quote",
                "verified": False,
                "status": "unknown",
                "is_st": False,
                "is_suspended": False,
                "is_limit_up": False,
                "is_limit_down": False,
                "limit_pct": self._limit_pct(symbol, ""),
                "missing": ["无法获取涨跌停、ST、停复牌状态"],
            }
        return self._row_to_trading_rules(symbol, row, source="sina_quote")

    def _row_to_trading_rules(
        self,
        symbol: str,
        row: QuoteRow,
        *,
        source: str,
    ) -> dict[str, object]:
        name = str(row.get("name", resolve_name(symbol)))
        price = _as_float(row.get("price"))
        prev_close = _as_float(row.get("prev_close"))
        open_price = _as_float(row.get("open"))
        volume = _as_float(row.get("volume"))
        is_st = "ST" in name.upper() or "退" in name
        is_suspended = price <= 0 or (open_price <= 0 and volume <= 0)
        limit_pct = self._limit_pct(symbol, name)
        upper = prev_close * (1 + limit_pct / 100) if prev_close else 0
        lower = prev_close * (1 - limit_pct / 100) if prev_close else 0
        tolerance = max(0.01, prev_close * 0.001)
        is_limit_up = bool(prev_close and price and price >= upper - tolerance)
        is_limit_down = bool(prev_close and price and price <= lower + tolerance)
        status = "suspended" if is_suspended else "limit_up" if is_limit_up else "limit_down" if is_limit_down else "normal"
        return {
            "source": source,
            "verified": True,
            "status": status,
            "name": name,
            "is_st": is_st,
            "is_suspended": is_suspended,
            "is_limit_up": is_limit_up,
            "is_limit_down": is_limit_down,
            "limit_pct": limit_pct,
            "prev_close": prev_close,
            "price": price,
            "upper_limit": round(upper, 2) if upper else None,
            "lower_limit": round(lower, 2) if lower else None,
            "missing": [],
        }

    @staticmethod
    def _limit_pct(symbol: str, name: str) -> float:
        upper_name = name.upper()
        if "ST" in upper_name or "退" in name:
            return 5.0
        if symbol.startswith(("300", "301", "688", "689")):
            return 20.0
        if symbol.startswith(("4", "8")):
            return 30.0
        return 10.0


class FinancialDataProvider:
    """Financial / valuation / peers — never fabricate zeros as real metrics."""

    _EMPTY_FINANCIALS: dict[str, object] = {
        "revenue_yoy": None,
        "net_margin": None,
        "roe": None,
        "debt_ratio": None,
        "goodwill_ratio": None,
        "series": [],
        "partial": True,
        "gaps": ["财务指标不可用"],
        "source": "none",
    }

    @staticmethod
    def _optional_pct(value: object) -> float | None:
        """Parse a percent-like value into a decimal ratio; missing → None."""
        if value is None or value == "":
            return None
        try:
            text = str(value).strip().replace(",", "")
            if text in ("False", "True", "-", "nan", "None"):
                return None
            if text.endswith("%"):
                text = text[:-1]
            return float(text) / 100.0
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None or value == "":
            return None
        try:
            fval = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        if fval != fval:  # NaN
            return None
        return fval

    @staticmethod
    def _percentile_rank(series: list[float], current: float) -> float | None:
        cleaned = [v for v in series if v is not None and v > 0]
        if not cleaned or current <= 0:
            return None
        below = sum(1 for v in cleaned if v <= current)
        return round(below / len(cleaned), 4)

    @staticmethod
    def _empty_financials(*, gaps: list[str], source: str = "none") -> dict[str, object]:
        return {
            **FinancialDataProvider._EMPTY_FINANCIALS,
            "gaps": gaps,
            "source": source,
        }

    def _from_indicator_df(self, df: Any) -> dict[str, object] | None:
        if df is None or getattr(df, "empty", True):
            return None
        series: list[dict[str, object]] = []
        for _, row in df.head(8).iterrows():
            period = str(row.get("日期", row.get("报告期", row.get("年份", ""))))[:10]
            series.append(
                {
                    "period": period,
                    "revenue_yoy": self._optional_pct(row.get("营业收入同比增长率")),
                    "net_margin": self._optional_pct(row.get("销售净利率")),
                    "roe": self._optional_pct(row.get("净资产收益率")),
                    "debt_ratio": self._optional_pct(row.get("资产负债率")),
                }
            )
        row = df.iloc[0]
        gaps: list[str] = []
        if len(series) < 2:
            gaps.append("财务序列不足 2 期")
        core = {
            "revenue_yoy": self._optional_pct(row.get("营业收入同比增长率")),
            "net_margin": self._optional_pct(row.get("销售净利率")),
            "roe": self._optional_pct(row.get("净资产收益率")),
            "debt_ratio": self._optional_pct(row.get("资产负债率")),
        }
        if all(v is None for v in core.values()):
            return None
        missing = [k for k, v in core.items() if v is None]
        if missing:
            gaps.append(f"缺失字段: {','.join(missing)}")
        return {
            **core,
            "goodwill_ratio": None,
            "series": series,
            "partial": bool(gaps) or len(series) < 2,
            "gaps": gaps + ["商誉占比不可用"],
            "source": "akshare_indicator",
        }

    def _from_ths_df(self, df: Any) -> dict[str, object] | None:
        if df is None or getattr(df, "empty", True):
            return None
        # THS abstract is chronological; latest year is last row.
        series: list[dict[str, object]] = []
        for _, row in df.tail(8).iterrows():
            period = str(row.get("报告期", row.get("日期", "")))[:10]
            series.append(
                {
                    "period": period,
                    "revenue_yoy": self._optional_pct(
                        row.get("营业总收入同比增长率", row.get("营业收入同比增长率"))
                    ),
                    "net_margin": self._optional_pct(row.get("销售净利率")),
                    "roe": self._optional_pct(row.get("净资产收益率")),
                    "debt_ratio": self._optional_pct(row.get("资产负债率")),
                }
            )
        latest = df.iloc[-1]
        core = {
            "revenue_yoy": self._optional_pct(
                latest.get("营业总收入同比增长率", latest.get("营业收入同比增长率"))
            ),
            "net_margin": self._optional_pct(latest.get("销售净利率")),
            "roe": self._optional_pct(latest.get("净资产收益率")),
            "debt_ratio": self._optional_pct(latest.get("资产负债率")),
        }
        if all(v is None for v in core.values()):
            return None
        gaps: list[str] = []
        if len(series) < 2:
            gaps.append("财务序列不足 2 期")
        missing = [k for k, v in core.items() if v is None]
        if missing:
            gaps.append(f"缺失字段: {','.join(missing)}")
        # Goodwill is never available from THS abstract — note but don't force partial alone.
        info_gaps = ["商誉占比不可用"]
        return {
            **core,
            "goodwill_ratio": None,
            "series": list(reversed(series)),  # newest-first to match indicator
            "partial": bool(gaps),
            "gaps": gaps + info_gaps,
            "source": "ths_abstract",
        }

    async def get_financials(self, symbol: str) -> dict[str, float | str | object]:
        if _use_mock_market_data():
            return {
                "revenue_yoy": 0.12,
                "net_margin": 0.25,
                "roe": 0.18,
                "pe_percentile": 0.50,
                "debt_ratio": 0.35,
                "goodwill_ratio": 0.03,
                "series": [
                    {"period": "2023", "roe": 0.16, "revenue_yoy": 0.10, "net_margin": 0.24, "debt_ratio": 0.36},
                    {"period": "2024", "roe": 0.18, "revenue_yoy": 0.12, "net_margin": 0.25, "debt_ratio": 0.35},
                ],
                "partial": False,
                "gaps": [],
                "source": "mock",
            }
        cache_key = f"financials:unified:v3:{symbol}"
        ttl = provider_ttl("akshare_financials")

        async def _fetch() -> dict[str, object]:
            # Primary: THS annual abstract (same source FinancialRatioAgent uses).
            ths_df = await run_sync_fetch(
                f"akshare ths financials {symbol}",
                lambda: ak.stock_financial_abstract_ths(symbol=symbol, indicator="按年度"),
                timeout=10.0,
                fallback=None,
            )
            parsed = self._from_ths_df(ths_df)
            if parsed is not None:
                return parsed

            # Fallback: Sina financial analysis indicator.
            ind_df = await run_sync_fetch(
                f"akshare indicator financials {symbol}",
                lambda: ak.stock_financial_analysis_indicator(symbol=symbol),
                timeout=8.0,
                fallback=None,
            )
            parsed = self._from_indicator_df(ind_df)
            if parsed is not None:
                return parsed

            return self._empty_financials(gaps=["财务指标序列不可用（THS/指标均失败）"])

        def _cacheable(payload: dict[str, object]) -> bool:
            return payload.get("source") not in (None, "", "none") and (
                payload.get("roe") is not None
                or payload.get("revenue_yoy") is not None
                or payload.get("net_margin") is not None
            )

        cached = await get_or_set_cached_dict(
            cache_key, ttl, _fetch, should_cache=_cacheable
        )
        return {k: v for k, v in cached.items()}  # type: ignore[misc]

    def _valuation_from_series(
        self,
        *,
        pe_ttm: float | None,
        pb: float | None,
        pe_series: list[float],
        source: str,
    ) -> dict[str, object]:
        pe_pct = (
            self._percentile_rank(pe_series, pe_ttm) if pe_ttm is not None else None
        )
        gaps: list[str] = []
        if pe_ttm is None:
            gaps.append("PE 不可用")
        if pb is None:
            gaps.append("PB 不可用")
        if pe_pct is None:
            gaps.append("估值历史分位不可算")
        return {
            "pe_ttm": pe_ttm,
            "pb": pb,
            "pe_percentile": pe_pct,
            "pe_history_count": len(pe_series),
            "source": source,
            "partial": bool(gaps),
            "gaps": gaps,
        }

    def _from_value_em_df(self, df: Any) -> dict[str, object] | None:
        """Parse East Money stock_value_em history (PE TTM + PB)."""
        if df is None or getattr(df, "empty", True):
            return None
        pe_col = "PE(TTM)" if "PE(TTM)" in df.columns else None
        pb_col = "市净率" if "市净率" in df.columns else None
        if not pe_col and not pb_col:
            return None
        row = df.iloc[-1]
        pe_ttm = self._optional_float(row.get(pe_col)) if pe_col else None
        pb = self._optional_float(row.get(pb_col)) if pb_col else None
        pe_series: list[float] = []
        if pe_col:
            for val in df[pe_col].tolist():
                fval = self._optional_float(val)
                if fval is not None and fval > 0:
                    pe_series.append(fval)
        if pe_ttm is None and pb is None:
            return None
        return self._valuation_from_series(
            pe_ttm=pe_ttm, pb=pb, pe_series=pe_series, source="akshare_value_em"
        )

    def _from_baidu_valuation(
        self, pe_df: Any, pb_df: Any
    ) -> dict[str, object] | None:
        """Parse Baidu stock_zh_valuation_baidu PE/PB series."""
        pe_series: list[float] = []
        pe_ttm: float | None = None
        pb: float | None = None
        if pe_df is not None and not getattr(pe_df, "empty", True) and "value" in pe_df.columns:
            for val in pe_df["value"].tolist():
                fval = self._optional_float(val)
                if fval is not None and fval > 0:
                    pe_series.append(fval)
            if pe_series:
                pe_ttm = pe_series[-1]
        if pb_df is not None and not getattr(pb_df, "empty", True) and "value" in pb_df.columns:
            pb = self._optional_float(pb_df["value"].iloc[-1])
        if pe_ttm is None and pb is None:
            return None
        return self._valuation_from_series(
            pe_ttm=pe_ttm, pb=pb, pe_series=pe_series, source="akshare_baidu"
        )

    async def get_valuation(self, symbol: str) -> dict[str, float | str | object]:
        if _use_mock_market_data():
            return {
                "pe_ttm": 28.0,
                "pe_percentile": 0.42,
                "pb": 8.0,
                "source": "mock",
                "partial": False,
                "gaps": [],
            }
        # v4: stock_a_indicator_lg removed in newer akshare; use value_em / baidu.
        cache_key = f"financials:valuation:v4:{symbol}"
        ttl = provider_ttl("akshare_financials")

        async def _fetch() -> dict[str, object]:
            # Primary: East Money valuation history (still available in akshare 1.18+).
            em_df = await run_sync_fetch(
                f"akshare value_em {symbol}",
                lambda: ak.stock_value_em(symbol=symbol),
                timeout=12.0,
                fallback=None,
            )
            parsed = self._from_value_em_df(em_df)
            if parsed is not None:
                return parsed

            # Optional L3: Tushare daily_basic when token is configured (before Baidu).
            from stockresearch.core.data_source_config import get_tushare_token

            if get_tushare_token():
                tushare = await run_sync_fetch(
                    f"tushare valuation {symbol}",
                    lambda: fetch_daily_basic_sync(symbol),
                    timeout=_DATA_TIMEOUT_SEC,
                    fallback=None,
                )
                if tushare:
                    pe = self._optional_float(tushare.get("pe_ttm"))
                    pb = self._optional_float(tushare.get("pb"))
                    if pe is not None or pb is not None:
                        return {
                            "pe_ttm": pe,
                            "pb": pb,
                            "pe_percentile": None,
                            "source": str(tushare.get("source", "tushare_daily_basic")),
                            "partial": True,
                            "gaps": ["Tushare 仅提供当日估值，无历史分位"],
                        }

            # Fallback: Baidu PE/PB series.
            pe_df = await run_sync_fetch(
                f"akshare baidu pe {symbol}",
                lambda: ak.stock_zh_valuation_baidu(
                    symbol=symbol, indicator="市盈率(TTM)", period="近一年"
                ),
                timeout=10.0,
                fallback=None,
            )
            pb_df = await run_sync_fetch(
                f"akshare baidu pb {symbol}",
                lambda: ak.stock_zh_valuation_baidu(
                    symbol=symbol, indicator="市净率", period="近一年"
                ),
                timeout=10.0,
                fallback=None,
            )
            parsed = self._from_baidu_valuation(pe_df, pb_df)
            if parsed is not None:
                return parsed

            return {
                "pe_ttm": None,
                "pb": None,
                "pe_percentile": None,
                "source": "none",
                "partial": True,
                "gaps": ["估值数据不可用"],
            }

        def _cacheable(payload: dict[str, object]) -> bool:
            if payload.get("pe_ttm") is None and payload.get("pb") is None:
                return False
            src = str(payload.get("source") or "")
            # Tushare/none shells without percentile poison the day-long cache.
            if payload.get("pe_percentile") is None and (
                "tushare" in src or src in ("", "none")
            ):
                return False
            return True

        cached = await get_or_set_cached_dict(
            cache_key, ttl, _fetch, should_cache=_cacheable
        )
        return {k: v for k, v in cached.items()}  # type: ignore[misc]

    async def get_industry_peers(self, symbol: str) -> list[dict[str, object]]:
        """Dynamic peers with relative metrics; seed fallback is marked source=seed."""
        if _use_mock_market_data():
            seeded = {"600519": ["000858", "000568"], "300750": ["002594", "300014"]}
            return [{"symbol": p, "name": "", "source": "mock"} for p in seeded.get(symbol, [])]

        cache_key = f"financials:peers:v3:{symbol}"
        ttl = provider_ttl("akshare_financials")

        async def _fetch() -> dict[str, object]:
            peers = await self._resolve_dynamic_peers(symbol)
            return {"peers": peers, "source": peers[0].get("source", "none") if peers else "none"}

        def _cacheable(payload: dict[str, object]) -> bool:
            peers = payload.get("peers")
            if not isinstance(peers, list) or not peers:
                return False
            # Seed-only / none: allow retry next request instead of locking a thin set for a day.
            sources = {str(p.get("source", "")) for p in peers if isinstance(p, dict)}
            if sources <= {"seed", "none", ""}:
                return False
            return True

        cached = await get_or_set_cached_dict(cache_key, ttl, _fetch, should_cache=_cacheable)
        raw = cached.get("peers", [])
        if isinstance(raw, list):
            return [p for p in raw if isinstance(p, dict)]
        return []

    async def _resolve_dynamic_peers(self, symbol: str) -> list[dict[str, object]]:
        seeded: dict[str, list[str]] = {
            "600519": ["000858", "000568"],
            "300750": ["002594", "300014"],
        }
        industry = await run_sync_fetch(
            f"akshare individual info {symbol}",
            lambda: self._industry_name_sync(symbol),
            timeout=8.0,
            fallback="",
        )
        peer_symbols: list[str] = []
        source = "seed"
        if industry:
            cons = await run_sync_fetch(
                f"akshare industry cons {industry}",
                lambda: self._industry_cons_sync(str(industry)),
                timeout=10.0,
                fallback=[],
            )
            if isinstance(cons, list) and cons:
                peer_symbols = [s for s in cons if s != symbol][:6]
                source = "akshare_industry"
        if not peer_symbols:
            peer_symbols = seeded.get(symbol, [])
            source = "seed" if peer_symbols else "none"
            if source == "seed":
                logger.info("industry peers falling back to seed for %s", symbol)

        peers: list[dict[str, object]] = []
        for peer in peer_symbols[:6]:
            peers.append(
                {
                    "symbol": peer,
                    "name": resolve_name(peer),
                    "source": source,
                    "industry": industry or "",
                }
            )
        # Attach relative valuation for up to 3 peers (best-effort).
        for entry in peers[:3]:
            peer = str(entry["symbol"])
            try:
                val = await self.get_valuation(peer)
                entry["pe_ttm"] = val.get("pe_ttm")
                entry["pb"] = val.get("pb")
                entry["pe_percentile"] = val.get("pe_percentile")
            except Exception:
                continue
        return peers

    @staticmethod
    def _industry_name_sync(symbol: str) -> str:
        try:
            df = ak.stock_individual_info_em(symbol=symbol)
        except Exception as exc:
            logger.warning("individual info failed for %s: %s", symbol, exc)
            return ""
        if df is None or df.empty:
            return ""
        for _, row in df.iterrows():
            key = str(row.iloc[0]) if len(row) else ""
            if "行业" in key:
                return str(row.iloc[1]).strip()
        return ""

    @staticmethod
    def _industry_cons_sync(industry: str) -> list[str]:
        try:
            df = ak.stock_board_industry_cons_em(symbol=industry)
        except Exception as exc:
            logger.warning("industry cons failed for %s: %s", industry, exc)
            return []
        if df is None or df.empty:
            return []
        col = "代码" if "代码" in df.columns else df.columns[0]
        symbols: list[str] = []
        for raw in df[col].tolist():
            digits = "".join(ch for ch in str(raw) if ch.isdigit())
            if len(digits) >= 6:
                symbols.append(digits[-6:])
        return symbols


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
                end_dt = datetime.strptime(before[:10], "%Y-%m-%d").replace(tzinfo=UTC) - timedelta(days=1)
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

        # Chart path prefers AkShare qfq for stable indicators; quote/UI hot path keeps Sina first.
        try_sina_first = before is None and not prefer_qfq
        if try_sina_first:
            sina_bars = await run_sync_fetch(
                f"sina kline {symbol}",
                lambda: fetch_sina_kline(symbol, days),
                timeout=8.0,
                fallback=None,
            )
            if sina_bars:
                bars = sina_bars
                source = "sina"

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

        if not prefer_qfq:
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

            if not bars:
                ef_bars = await run_sync_fetch(
                    f"efinance kline {symbol}",
                    lambda: fetch_efinance_kline(symbol, days, fqt=1),
                    timeout=12.0,
                    fallback=None,
                )
                if ef_bars:
                    bars = ef_bars
                    source = "efinance"

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
            "akshare/efinance (prefer_qfq)" if prefer_qfq else "akshare/sina/efinance",
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


def _xueqiu_market_code(symbol: str) -> str:
    if symbol.startswith(("4", "8")):
        return f"BJ{symbol}"
    if symbol.startswith("6"):
        return f"SH{symbol}"
    return f"SZ{symbol}"


def _lookup_xueqiu_row(df: Any, code: str, name: str) -> Any | None:
    if df is None or df.empty or "股票代码" not in df.columns:
        return None
    matches = df[df["股票代码"].astype(str) == code]
    if matches.empty and name:
        matches = df[df["股票简称"].astype(str) == name]
    if matches.empty:
        return None
    return matches.iloc[0]


def _fetch_xueqiu_hot_sync(symbol: str, name: str) -> dict[str, float | int | str | bool]:
    """Eastmoney stock-comment APIs first; Xueqiu hot lists only from warm cache.

    Full-market scrapes (stock_comment_em / stock_hot_*_xq) take 20–60s and would
    trip the async timeout, so they are never fetched on the hot path.
    """
    result: dict[str, float | int | str | bool] = {
        "heat_score": 0,
        "post_count": 0,
        "bull_ratio": 0.5,
        "follow_count": 0,
        "attention_index": 0.0,
        "source": "unavailable",
        "available": False,
    }
    sources: list[str] = []
    code = _xueqiu_market_code(symbol)

    try:
        score_df = ak.stock_comment_detail_zhpj_lspf_em(symbol=symbol)
        if not score_df.empty:
            latest_score = float(score_df.iloc[-1]["评分"])
            result["heat_score"] = min(100, max(1, round(latest_score)))
            sources.append("em_score")
    except Exception as exc:
        logger.warning("EM sentiment score failed for %s: %s", symbol, exc)

    try:
        desire_df = ak.stock_comment_detail_scrd_desire_em(symbol=symbol)
        if not desire_df.empty:
            desire = float(desire_df.iloc[-1]["参与意愿"])
            result["bull_ratio"] = round(max(0.15, min(0.85, desire / 100)), 2)
            sources.append("em_desire")
    except Exception as exc:
        logger.warning("EM participation desire failed for %s: %s", symbol, exc)

    # Warm-cache enrichments only — never block on full-market scrapes.
    df_deal = peek_cached("xq_hot_deal", 900.0)
    if df_deal is not None:
        try:
            deal_row = _lookup_xueqiu_row(df_deal, code, name)
            if deal_row is not None:
                result["post_count"] = int(float(deal_row["关注"]))
                rank = int(deal_row.name) + 1
                xq_heat = min(100, max(5, round(100 - (rank / max(len(df_deal), 1)) * 95)))
                if int(result["heat_score"]) == 0:
                    result["heat_score"] = xq_heat
                sources.append("xueqiu_deal")
        except Exception as exc:
            logger.warning("Xueqiu deal hot (cache) failed for %s: %s", symbol, exc)

    df_tweet = peek_cached("xq_hot_tweet", 900.0)
    if df_tweet is not None:
        try:
            tweet_row = _lookup_xueqiu_row(df_tweet, code, name)
            if tweet_row is not None:
                result["tweet_heat"] = int(float(tweet_row["关注"]))
                sources.append("xueqiu_tweet")
        except Exception as exc:
            logger.warning("Xueqiu tweet hot (cache) failed for %s: %s", symbol, exc)

    df_follow = peek_cached("xq_hot_follow", 900.0)
    if df_follow is not None:
        try:
            follow_row = _lookup_xueqiu_row(df_follow, code, name)
            if follow_row is not None:
                result["follow_count"] = int(float(follow_row["关注"]))
                sources.append("xueqiu_follow")
        except Exception as exc:
            logger.warning("Xueqiu follow hot (cache) failed for %s: %s", symbol, exc)

    if sources:
        result["source"] = "+".join(sources)
        result["available"] = True
        # Honest labeling when Xueqiu warm cache is cold — EM stock-comment only.
        has_xq = any(s.startswith("xueqiu_") for s in sources)
        if not has_xq and any(s.startswith("em_") for s in sources):
            result["coverage_note"] = "仅东财个股情绪（雪球热榜暖缓存未命中）"
            result["partial"] = True
    return result


class SentimentDataProvider:
    async def get_symbol_news(self, symbol: str, name: str, limit: int = 8) -> list[dict[str, str]]:
        if _use_mock_market_data():
            return [{"title": f"{name or symbol} 行业政策讨论", "source": "mock"}]
        from stockresearch.data.providers.news import NewsProvider

        provider = NewsProvider()
        queries: list[str] = []
        for query in (name, symbol):
            if query and query not in queries:
                queries.append(query)
        items = []
        for query in queries:
            batch = await provider.fetch_symbol_news(
                query, symbol=symbol, limit=limit, enrich=True
            )
            if batch:
                items = batch
                break
        return [
            {
                "title": item.title,
                "source": item.source,
                "url": item.url,
                "content": item.content[:200],
            }
            for item in items[:limit]
        ]

    def score_titles(self, titles: list[str]) -> float:
        if not titles:
            return 0.0
        score = 0.0
        for title in titles:
            if any(kw in title for kw in _POSITIVE_NEWS):
                score += 1.0
            if any(kw in title for kw in _NEGATIVE_NEWS):
                score -= 1.0
        return max(-1.0, min(1.0, score / max(len(titles), 1)))

    async def get_xueqiu_hot(self, symbol: str, name: str = "") -> dict[str, float | int | str | bool]:
        if _use_mock_market_data():
            return {
                "bull_ratio": 0.55,
                "heat_score": 42,
                "post_count": 120,
                "available": True,
                "source": "mock",
            }
        return await run_sync_fetch(
            f"xueqiu hot {symbol}",
            lambda: _fetch_xueqiu_hot_sync(symbol, name or resolve_name(symbol)),
            timeout=_DATA_TIMEOUT_SEC * 3,
            fallback={
                "heat_score": 0,
                "post_count": 0,
                "bull_ratio": 0.5,
                "follow_count": 0,
                "attention_index": 0.0,
                "source": "unavailable",
                "available": False,
            },
        )

    async def get_news_sentiment_score(self, symbol: str, name: str = "") -> float:
        news = await self.get_symbol_news(symbol, name)
        return self.score_titles([item["title"] for item in news])


class ChipsDataProvider:
    @staticmethod
    def _cache_chips_result(cache_key: str, ttl: int | None, result: dict[str, object]) -> None:
        """Persist only usable chips payloads — never poison TTL with empty shells."""
        if not ttl:
            return
        if result.get("signal") == "暂无数据":
            return
        if result.get("available") is False or result.get("partial") is True:
            return
        set_sqlite_cached(cache_key, dict(result), ttl)

    async def get_dragon_tiger(self, symbol: str) -> dict[str, str | float | int]:
        if _use_mock_market_data():
            return {
                "appearances": 0,
                "net_buy": 0.0,
                "institution_ratio": 0.0,
                "signal": "暂无数据",
                "source": "mock",
            }
        cache_key = f"dragon_tiger:{symbol}"
        ttl = provider_ttl("akshare_lhb")
        cached = get_sqlite_cached(cache_key)
        if cached is not None:
            return {**cached, "source": str(cached.get("source", "akshare_lhb"))}  # type: ignore[return-value]
        result = await run_sync_fetch(
            f"akshare lhb {symbol}",
            lambda: self._fetch_dragon_tiger_sync(symbol),
            timeout=_DATA_TIMEOUT_SEC,
            fallback={
                "appearances": 0,
                "net_buy": 0.0,
                "institution_ratio": 0.0,
                "signal": "暂无数据",
                "source": "akshare_lhb",
                "available": False,
                "partial": True,
                "gaps": ["龙虎榜不可用"],
            },
        )
        self._cache_chips_result(cache_key, ttl, dict(result))
        return result

    async def get_fund_flow(self, symbol: str) -> dict[str, float | str]:
        if _use_mock_market_data():
            return {
                "main_net_inflow": 0.0,
                "main_net_inflow_5d": 0.0,
                "main_net_pct": 0.0,
                "days_positive": 0,
                "source": "mock",
            }
        cache_key = f"fund_flow:{symbol}"
        ttl = provider_ttl("akshare_fund_flow")
        cached = get_sqlite_cached(cache_key)
        if cached is not None:
            return {**cached, "source": str(cached.get("source", "akshare_fund_flow"))}  # type: ignore[return-value]
        result = await run_sync_fetch(
            f"akshare fund flow {symbol}",
            lambda: self._fetch_fund_flow_sync(symbol),
            timeout=_DATA_TIMEOUT_SEC,
            fallback={
                "main_net_inflow": 0.0,
                "main_net_inflow_5d": 0.0,
                "main_net_pct": 0.0,
                "days_positive": 0,
                "source": "akshare_fund_flow",
                "available": False,
                "partial": True,
                "gaps": ["主力资金流向不可用"],
            },
        )
        self._cache_chips_result(cache_key, ttl, dict(result))
        return result

    async def get_northbound_flow(self, symbol: str) -> dict[str, float | str]:
        if getattr(get_settings(), "use_mock_market_data", False):
            return {
                "hold_pct": 6.5,
                "net_change_shares": 39399.0,
                "net_change_value": 5.63e7,
                "signal": "增持",
                "source": "mock",
            }
        cache_key = f"northbound:{symbol}"
        cached = get_sqlite_cached(cache_key)
        if cached is not None:
            return {**cached, "source": str(cached.get("source", "akshare_northbound"))}
        meta = get_provider_meta("akshare_northbound")
        ttl = meta.default_ttl_seconds if meta else 3600
        result = await run_sync_fetch(
            f"akshare northbound {symbol}",
            lambda: self._fetch_northbound_sync(symbol),
            timeout=_DATA_TIMEOUT_SEC,
            fallback={
                "hold_pct": 0.0,
                "net_change_shares": 0.0,
                "net_change_value": 0.0,
                "signal": "暂无数据",
                "source": "akshare_northbound",
                "available": False,
                "partial": True,
                "gaps": ["北向资金不可用"],
            },
        )
        self._cache_chips_result(cache_key, ttl, dict(result))
        return result

    async def get_margin_trading(self, symbol: str) -> dict[str, float | str]:
        if getattr(get_settings(), "use_mock_market_data", False):
            return {
                "financing_balance": 2.07e10,
                "securities_balance": 1.71e7,
                "total_balance": 2.07e10,
                "source": "mock",
            }
        cache_key = f"margin:{symbol}"
        cached = get_sqlite_cached(cache_key)
        if cached is not None:
            return {**cached, "source": str(cached.get("source", "akshare_margin"))}
        meta = get_provider_meta("akshare_margin")
        ttl = meta.default_ttl_seconds if meta else 86400
        result = await run_sync_fetch(
            f"akshare margin {symbol}",
            lambda: self._fetch_margin_sync(symbol),
            timeout=_DATA_TIMEOUT_SEC,
            fallback={
                "financing_balance": 0.0,
                "securities_balance": 0.0,
                "total_balance": 0.0,
                "source": "akshare_margin",
                "available": False,
                "partial": True,
                "gaps": ["融资融券不可用"],
            },
        )
        self._cache_chips_result(cache_key, ttl, dict(result))
        return result

    async def get_holder_count(self, symbol: str) -> dict[str, float | str]:
        if _use_mock_market_data():
            return {"holder_count": 0.0, "qoq_change": 0.0, "source": "mock"}
        cache_key = f"holder_count:{symbol}"
        ttl = provider_ttl("akshare_gdhs")
        cached = get_sqlite_cached(cache_key)
        if cached is not None:
            return {**cached, "source": str(cached.get("source", "akshare_gdhs"))}  # type: ignore[return-value]
        result = await run_sync_fetch(
            f"akshare holder count {symbol}",
            lambda: self._fetch_holder_count_sync(symbol),
            timeout=_DATA_TIMEOUT_SEC,
            fallback={
                "holder_count": 0.0,
                "qoq_change": 0.0,
                "source": "akshare_gdhs",
                "available": False,
                "partial": True,
                "gaps": ["股东户数不可用"],
            },
        )
        self._cache_chips_result(cache_key, ttl, dict(result))
        return result

    async def get_lockup(self, symbol: str) -> dict[str, str | float | int]:
        if _use_mock_market_data():
            return {"upcoming_count": 0, "next_date": "", "ratio_pct": 0.0, "source": "mock"}
        cache_key = f"lockup:{symbol}"
        ttl = provider_ttl("akshare_lockup")
        cached = get_sqlite_cached(cache_key)
        if cached is not None:
            return {**cached, "source": str(cached.get("source", "akshare_lockup"))}  # type: ignore[return-value]
        result = await run_sync_fetch(
            f"akshare lockup {symbol}",
            lambda: self._fetch_lockup_sync(symbol),
            timeout=_DATA_TIMEOUT_SEC,
            fallback={
                "upcoming_count": 0,
                "next_date": "",
                "ratio_pct": 0.0,
                "source": "akshare_lockup",
                "available": False,
                "partial": True,
                "gaps": ["限售解禁不可用"],
            },
        )
        self._cache_chips_result(cache_key, ttl, dict(result))
        return result

    def _fetch_dragon_tiger_sync(self, symbol: str) -> dict[str, str | float | int]:
        end = datetime.now(UTC)
        start = end - timedelta(days=30)
        df = ak.stock_lhb_detail_em(
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
        )
        stock_df = df[df["代码"] == symbol] if not df.empty else df
        appearances = len(stock_df)
        net_buy = float(stock_df["龙虎榜净买额"].sum()) if appearances else 0.0
        stats = ak.stock_lhb_stock_statistic_em(symbol="近一月")
        inst_ratio = 0.0
        if not stats.empty:
            row_df = stats[stats["代码"] == symbol]
            if not row_df.empty:
                row = row_df.iloc[0]
                buy_total = float(row.get("龙虎榜买入额", 0) or 0)
                inst_buy = float(row.get("机构买入总额", 0) or 0)
                if buy_total > 0:
                    inst_ratio = inst_buy / buy_total
                appearances = int(row.get("上榜次数", appearances) or appearances)
                net_buy = float(row.get("龙虎榜净买额", net_buy) or net_buy)
        if appearances == 0:
            signal = "近30日未上榜"
        elif net_buy > 0:
            signal = "净买入"
        elif net_buy < 0:
            signal = "净卖出"
        else:
            signal = "中性"
        return {
            "appearances": appearances,
            "net_buy": net_buy,
            "institution_ratio": round(inst_ratio, 2),
            "signal": signal,
            "source": "akshare_lhb",
        }

    def _fetch_northbound_sync(self, symbol: str) -> dict[str, float | str]:
        df = ak.stock_hsgt_individual_em(symbol=symbol)
        if df.empty:
            return {
                "hold_pct": 0.0,
                "net_change_shares": 0.0,
                "net_change_value": 0.0,
                "signal": "非陆股通标的或暂无数据",
                "source": "akshare_northbound",
            }
        row = df.iloc[-1]
        net_shares = _as_float(row.get("今日增持股数"))
        net_value = _as_float(row.get("今日增持资金"))
        hold_pct = _as_float(row.get("持股数量占A股百分比"))
        if net_shares > 0:
            signal = "增持"
        elif net_shares < 0:
            signal = "减持"
        else:
            signal = "持平"
        return {
            "hold_pct": hold_pct,
            "net_change_shares": net_shares,
            "net_change_value": net_value,
            "signal": signal,
            "source": "akshare_northbound",
        }

    def _fetch_margin_sync(self, symbol: str) -> dict[str, float | str]:
        for days_back in range(1, 11):
            date = (datetime.now(UTC) - timedelta(days=days_back)).strftime("%Y%m%d")
            try:
                if symbol.startswith("6"):
                    df = ak.stock_margin_detail_sse(date=date)
                    code_col = "标的证券代码"
                else:
                    df = ak.stock_margin_detail_szse(date=date)
                    code_col = "证券代码"
            except Exception:
                continue
            if df.empty or code_col not in df.columns:
                continue
            stock_df = df[df[code_col].astype(str) == symbol]
            if stock_df.empty:
                return {
                    "financing_balance": 0.0,
                    "securities_balance": 0.0,
                    "total_balance": 0.0,
                    "signal": "暂无融资融券数据",
                    "source": "akshare_margin",
                }
            row = stock_df.iloc[0]
            if symbol.startswith("6"):
                financing = _as_float(row.get("融资余额"))
                securities = _as_float(row.get("融券余量"))
                total = financing + securities
            else:
                financing = _as_float(row.get("融资余额"))
                securities = _as_float(row.get("融券余额"))
                total = _as_float(row.get("融资融券余额")) or financing + securities
            return {
                "financing_balance": financing,
                "securities_balance": securities,
                "total_balance": total,
                "source": "akshare_margin",
            }
        return {
            "financing_balance": 0.0,
            "securities_balance": 0.0,
            "total_balance": 0.0,
            "signal": "暂无融资融券数据",
            "source": "akshare_margin",
        }

    def _fetch_fund_flow_sync(self, symbol: str) -> dict[str, float | str]:
        df = ak.stock_individual_fund_flow(stock=symbol, market=_market_code(symbol))
        if df.empty:
            return {
                "main_net_inflow": 0.0,
                "main_net_inflow_5d": 0.0,
                "main_net_pct": 0.0,
                "days_positive": 0,
                "source": "akshare_fund_flow",
            }
        recent = df.tail(5)
        main_net = float(recent.iloc[-1]["主力净流入-净额"])
        main_pct = float(recent.iloc[-1]["主力净流入-净占比"])
        days_positive = int((recent["主力净流入-净额"] > 0).sum())
        main_5d = float(recent["主力净流入-净额"].sum())
        return {
            "main_net_inflow": main_net,
            "main_net_inflow_5d": main_5d,
            "main_net_pct": main_pct,
            "days_positive": days_positive,
            "source": "akshare_fund_flow",
        }

    def _fetch_holder_count_sync(self, symbol: str) -> dict[str, float | str]:
        df = ak.stock_zh_a_gdhs_detail_em(symbol=symbol)
        if df.empty:
            return {"holder_count": 0.0, "qoq_change": 0.0, "source": "akshare_gdhs"}
        row = df.iloc[-1]
        holder_count = float(row.get("股东户数-本次", 0) or 0)
        qoq_raw = row.get("股东户数-增减比例")
        qoq_change = float(qoq_raw) / 100 if qoq_raw not in (None, "") else 0.0
        return {
            "holder_count": holder_count,
            "qoq_change": qoq_change,
            "source": "akshare_gdhs",
        }

    def _fetch_lockup_sync(self, symbol: str) -> dict[str, str | float | int]:
        df = ak.stock_restricted_release_queue_em(symbol=symbol)
        if df is None or df.empty:
            return {"upcoming_count": 0, "next_date": "", "ratio_pct": 0.0, "source": "akshare_lockup"}
        today = datetime.now(UTC).date()
        upcoming = df[df["解禁时间"] >= today] if "解禁时间" in df.columns else df.iloc[0:0]
        if upcoming.empty:
            return {"upcoming_count": 0, "next_date": "", "ratio_pct": 0.0, "source": "akshare_lockup"}
        row = upcoming.iloc[-1]
        ratio_pct = float(row.get("占总市值比例", 0) or 0)
        return {
            "upcoming_count": len(upcoming),
            "next_date": str(row.get("解禁时间", "")),
            "ratio_pct": ratio_pct,
            "source": "akshare_lockup",
        }
