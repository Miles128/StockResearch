"""Quote provider — Sina primary with akshare/efinance fallback chain."""

import asyncio
import logging
from typing import cast

from stockresearch.core.exceptions import DataProviderError
from stockresearch.data.providers.akshare_quote import fetch_akshare_hist_quotes
from stockresearch.data.providers.base import run_sync_fetch
from stockresearch.data.providers.efinance_quote import fetch_efinance_quotes
from stockresearch.data.providers.market.common import (
    _QUOTE_TIMEOUT_SEC,
    Quote,
    _as_datetime,
    _as_float,
    _mock_quote,
    _quote_from_cache,
    _quote_to_cache,
    _use_mock_market_data,
)
from stockresearch.data.providers.sina_quote import QuoteRow, fetch_sina_quotes
from stockresearch.data.registry import (
    QuotePriceConflict,
    record_quote_conflicts,
    record_quote_fetch,
    record_symbol_sources,
)
from stockresearch.services.provider_cache_policy import DEFAULT_QUOTE_CACHE_TTL_SECONDS
from stockresearch.services.sqlite_cache import get_sqlite_cached, set_sqlite_cached

logger = logging.getLogger(__name__)


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
            cache_ttl_seconds if cache_ttl_seconds is not None else DEFAULT_QUOTE_CACHE_TTL_SECONDS
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
                asyncio.create_task(self._background_fill_missing_quotes(missing, background_ttl))
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
                asyncio.create_task(self._background_fill_missing_quotes(missing, background_ttl))

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
