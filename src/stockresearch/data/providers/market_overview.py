"""Market overview — Sina only on hot path, AkShare fallback with hard timeout."""

import asyncio
import logging
from datetime import UTC, datetime

import akshare as ak

from stockresearch.core.schemas import IndexQuoteOut, MarketOverviewOut, StockQuoteOut
from stockresearch.data.providers.market import QuoteProvider
from stockresearch.data.providers.sina_index import fetch_sina_indices
from stockresearch.data.registry import get_symbol_source, record_overview_fetch
from stockresearch.services.stock_sector import resolve_stock_sector
from stockresearch.utils.symbols import resolve_name

logger = logging.getLogger(__name__)

_INDEX_NAMES = ("上证指数", "深证成指", "创业板指", "沪深300")
_AKSHARE_FALLBACK_TIMEOUT_SEC = 3.0
_OVERVIEW_TIMEOUT_SEC = 8.0


class MarketOverviewProvider:
    async def get_overview(self) -> MarketOverviewOut:
        try:
            overview = await asyncio.wait_for(
                asyncio.to_thread(self._fetch_sina_overview),
                timeout=_OVERVIEW_TIMEOUT_SEC,
            )
            record_overview_fetch(source="sina", degraded=False)
            return overview
        except TimeoutError:
            logger.warning("Sina market overview timed out")
        except Exception as exc:
            logger.warning("Sina market overview failed: %s", exc)

        try:
            overview = await asyncio.wait_for(
                asyncio.to_thread(self._fetch_akshare_indices_only),
                timeout=_AKSHARE_FALLBACK_TIMEOUT_SEC,
            )
            if overview.indices:
                record_overview_fetch(
                    source="akshare",
                    degraded=True,
                    message="新浪不可用，已切换 AkShare 指数",
                )
                return overview.model_copy(update={
                    "message": "新浪不可用，已切换 AkShare 指数",
                })
        except TimeoutError:
            logger.warning("AkShare market overview timed out")
        except Exception as exc:
            logger.warning("AkShare market overview failed: %s", exc)

        record_overview_fetch(
            source="unavailable",
            degraded=True,
            message="行情源暂时不可用，请稍后刷新",
        )
        return MarketOverviewOut(
            indices=[],
            northbound_net_yi=None,
            advancers=None,
            decliners=None,
            source="unavailable",
            data_status="unavailable",
            message="行情源暂时不可用，请稍后刷新",
            updated_at=datetime.now(UTC),
        )

    def _fetch_akshare_indices_only(self) -> MarketOverviewOut:
        indices: list[IndexQuoteOut] = []
        df = ak.stock_zh_index_spot_em()
        for index_name in _INDEX_NAMES:
            row = df[df["名称"] == index_name]
            if row.empty:
                continue
            r = row.iloc[0]
            indices.append(
                IndexQuoteOut(
                    name=index_name,
                    symbol=str(r.get("代码", "")),
                    price=float(r["最新价"]),
                    change_pct=float(r.get("涨跌幅", 0.0)),
                )
            )
        northbound_net_yi: float | None = None
        try:
            nb_df = ak.stock_hsgt_north_net_flow_in_em(symbol="北向")
            if not nb_df.empty:
                latest = nb_df.iloc[-1]
                northbound_net_yi = float(latest.get("当日净流入", 0)) / 1e8
        except Exception as exc:
            logger.warning("AkShare northbound data failed: %s", exc)
        return MarketOverviewOut(
            indices=indices,
            northbound_net_yi=northbound_net_yi,
            advancers=None,
            decliners=None,
            source="akshare",
            data_status="live",
            message=None,
            updated_at=datetime.now(UTC),
        )

    def _fetch_sina_overview(self) -> MarketOverviewOut:
        quotes = fetch_sina_indices()
        indices = [
            IndexQuoteOut(
                name=q.name,
                symbol=q.symbol,
                price=q.price,
                change_pct=q.change_pct,
            )
            for q in quotes
        ]
        northbound_net_yi: float | None = None
        try:
            nb_df = ak.stock_hsgt_north_net_flow_in_em(symbol="北向")
            if not nb_df.empty:
                latest = nb_df.iloc[-1]
                northbound_net_yi = float(latest.get("当日净流入", 0)) / 1e8
        except Exception as exc:
            logger.warning("AkShare northbound data failed: %s", exc)
        return MarketOverviewOut(
            indices=indices,
            northbound_net_yi=northbound_net_yi,
            advancers=None,
            decliners=None,
            source="sina",
            data_status="live",
            message=None,
            updated_at=datetime.now(UTC),
        )


class BatchQuoteProvider:
    def __init__(self) -> None:
        self._quote = QuoteProvider()

    async def get_quotes(self, symbols: list[str]) -> list[StockQuoteOut]:
        unique = list(dict.fromkeys(symbols))
        if not unique:
            return []
        try:
            quote_map = await self._quote.get_quotes(unique)
        except Exception as exc:
            logger.warning("Batch quotes failed: %s", exc)
            quote_map = {}

        results: list[StockQuoteOut] = []
        sector_symbols = [symbol for symbol in unique if symbol in quote_map]
        sector_values = await asyncio.gather(
            *[
                resolve_stock_sector(symbol, quote_map[symbol].name)
                for symbol in sector_symbols
            ]
        )
        sectors = dict(zip(sector_symbols, sector_values, strict=True))
        for symbol in unique:
            q = quote_map.get(symbol)
            if q is None:
                continue
            sym_source = get_symbol_source(symbol) or "sina"
            results.append(
                StockQuoteOut(
                    symbol=q.symbol,
                    name=q.name or resolve_name(q.symbol),
                    price=q.price,
                    change_pct=q.change_pct,
                    high=q.high,
                    low=q.low,
                    volume=q.volume,
                    sector=sectors.get(symbol, "未知"),
                    source=sym_source,
                )
            )
        return results
