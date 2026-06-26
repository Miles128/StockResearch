"""Market data providers — Sina quotes on hot path, mock for tests."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import akshare as ak  # type: ignore[import-untyped]

from stockresearch.core.config import get_settings
from stockresearch.core.exceptions import DataProviderError
from stockresearch.data.providers.akshare_quote import fetch_akshare_hist_quotes
from stockresearch.data.providers.base import run_async_fetch, run_sync_fetch
from stockresearch.data.providers.news import _fetch_em_symbol_news_sync
from stockresearch.data.providers.sina_quote import QuoteRow, fetch_sina_quotes
from stockresearch.data.providers.tushare_financial import fetch_daily_basic_sync
from stockresearch.data.registry import record_quote_fetch, record_symbol_sources
from stockresearch.services.cache import get_cached
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
    high: float
    low: float
    volume: float
    updated_at: datetime


class QuoteProvider:
    async def get_quote(self, symbol: str) -> Quote:
        quotes = await self.get_quotes([symbol])
        if symbol not in quotes:
            raise DataProviderError(f"无法获取 {symbol} 行情")
        return quotes[symbol]

    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        unique = list(dict.fromkeys(symbols))
        if not unique:
            return {}
        if get_settings().use_mock_market_data:
            return {sym: self._mock_quote(sym) for sym in unique}

        raw = await self._fetch_quote_rows(unique)
        return self._rows_to_quotes(raw)

    async def _fetch_quote_rows(
        self, symbols: list[str]
    ) -> dict[str, QuoteRow]:
        raw: dict[str, QuoteRow] = {}
        sina_error: str | None = None

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

        missing = [sym for sym in symbols if sym not in raw]
        ak_count = 0
        if missing:
            ak_rows = await run_sync_fetch(
                "akshare hist quote fallback",
                lambda: fetch_akshare_hist_quotes(missing),
                timeout=max(_QUOTE_TIMEOUT_SEC, 12.0),
                fallback=None,
            )
            if ak_rows is None:
                if not raw:
                    detail = sina_error or "行情获取失败"
                    raise DataProviderError(f"{detail}，AkShare 备用源也不可用")
            else:
                for sym, ak_row in ak_rows.items():
                    raw[sym] = cast(QuoteRow, {**ak_row, "_source": "akshare"})
                ak_count = len(ak_rows)
                logger.info("AkShare hist fallback filled %d symbols", ak_count)

        if not raw:
            raise DataProviderError(sina_error or "行情数据不可用")

        sina_count = sum(1 for sym in symbols if sym in raw and raw[sym].get("_source") == "sina")
        record_quote_fetch(
            requested=len(symbols),
            sina_count=sina_count,
            akshare_count=ak_count,
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
                high=_as_float(row["high"]),
                low=_as_float(row["low"]),
                volume=_as_float(row["volume"]),
                updated_at=_as_datetime(row["updated_at"]),
            )
            for sym, row in raw.items()
        }

    def _mock_quote(self, symbol: str) -> Quote:
        mock: dict[str, dict[str, float]] = {
            "600519": {"price": 1680.0, "change_pct": -1.2, "high": 1720.0, "low": 1660.0, "volume": 1.2e6},
            "000858": {"price": 145.0, "change_pct": 0.5, "high": 148.0, "low": 143.0, "volume": 2.1e6},
            "300750": {"price": 198.0, "change_pct": -3.5, "high": 205.0, "low": 195.0, "volume": 5.5e6},
            "601318": {"price": 48.0, "change_pct": -0.8, "high": 49.0, "low": 47.5, "volume": 3.0e6},
            "600036": {"price": 35.0, "change_pct": 0.3, "high": 35.5, "low": 34.8, "volume": 4.0e6},
        }
        data = mock.get(symbol, {"price": 10.0, "change_pct": 0.0, "high": 10.5, "low": 9.5, "volume": 1e6})
        return Quote(
            symbol=symbol,
            name=resolve_name(symbol),
            price=float(data["price"]),
            change_pct=float(data["change_pct"]),
            high=float(data["high"]),
            low=float(data["low"]),
            volume=float(data["volume"]),
            updated_at=datetime.now(UTC),
        )


class MarketRuleProvider:
    async def get_trading_rules(self, symbol: str) -> dict[str, object]:
        if get_settings().use_mock_market_data:
            return self._mock_trading_rules(symbol)
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

    def _mock_trading_rules(self, symbol: str) -> dict[str, object]:
        name = resolve_name(symbol)
        return {
            "source": "mock",
            "verified": True,
            "status": "normal",
            "name": name,
            "is_st": "ST" in name.upper(),
            "is_suspended": False,
            "is_limit_up": False,
            "is_limit_down": False,
            "limit_pct": self._limit_pct(symbol, name),
            "missing": [],
        }


class FinancialDataProvider:
    async def get_financials(self, symbol: str) -> dict[str, float | str]:
        if get_settings().use_mock_market_data:
            return self._mock_financials(symbol)
        df = await run_sync_fetch(
            f"akshare financials {symbol}",
            lambda: ak.stock_financial_analysis_indicator(symbol=symbol),
            timeout=8.0,
            fallback=self._mock_financials(symbol),
        )
        if df is None or df.empty:
            return self._mock_financials(symbol)
        row = df.iloc[0]
        return {
            "revenue_yoy": float(row.get("营业收入同比增长率", 0.0)) / 100 if row.get("营业收入同比增长率") else 0.0,
            "net_margin": float(row.get("销售净利率", 0.0)) / 100 if row.get("销售净利率") else 0.0,
            "roe": float(row.get("净资产收益率", 0.0)) / 100 if row.get("净资产收益率") else 0.0,
            "pe_percentile": 0.50,
            "debt_ratio": float(row.get("资产负债率", 0.35)) / 100 if row.get("资产负债率") else 0.35,
            "goodwill_ratio": 0.03,
        }

    def _mock_financials(self, symbol: str) -> dict[str, float | str]:
        mock: dict[str, dict[str, float | str]] = {
            "600519": {"revenue_yoy": 0.15, "net_margin": 0.52, "roe": 0.32, "pe_percentile": 0.55, "debt_ratio": 0.18, "goodwill_ratio": 0.01},
            "300750": {"revenue_yoy": 0.22, "net_margin": 0.11, "roe": 0.18, "pe_percentile": 0.42, "debt_ratio": 0.45, "goodwill_ratio": 0.05},
        }
        default: dict[str, float | str] = {
            "revenue_yoy": 0.08, "net_margin": 0.12, "roe": 0.10,
            "pe_percentile": 0.50, "debt_ratio": 0.35, "goodwill_ratio": 0.03,
        }
        return mock.get(symbol, default)

    async def get_valuation(self, symbol: str) -> dict[str, float | str]:
        if get_settings().use_mock_market_data:
            fin = await self.get_financials(symbol)
            pe = float(fin.get("pe_percentile", 0.5)) * 40
            return {"pe_ttm": pe, "pe_percentile": float(fin.get("pe_percentile", 0.5))}
        df = await run_sync_fetch(
            f"akshare valuation {symbol}",
            lambda: ak.stock_a_indicator_lg(symbol=symbol),
            timeout=8.0,
            fallback=None,
        )
        if df is not None and not df.empty:
            row = df.iloc[-1]
            pe_ttm = float(row.get("pe", 20.0))
            return {"pe_ttm": pe_ttm, "pe_percentile": 0.5}

        tushare = await run_sync_fetch(
            f"tushare valuation {symbol}",
            lambda: fetch_daily_basic_sync(symbol),
            timeout=_DATA_TIMEOUT_SEC,
            fallback=None,
        )
        if tushare:
            pe = float(tushare.get("pe_ttm", 20.0))
            return {
                "pe_ttm": pe,
                "pe_percentile": 0.5,
                "pb": float(tushare.get("pb", 0)),
                "source": str(tushare.get("source", "tushare")),
            }
        return {"pe_ttm": 20.0, "pe_percentile": 0.5}

    async def get_industry_peers(self, symbol: str) -> list[str]:
        sector_peers: dict[str, list[str]] = {
            "600519": ["000858", "000568"],
            "300750": ["002594", "300014"],
        }
        return sector_peers.get(symbol, [])


class TechnicalDataProvider:
    async def get_kline_bars(self, symbol: str, days: int = 60) -> list[dict[str, float | str]]:
        if get_settings().use_mock_market_data:
            return await self._mock_kline_bars(symbol, days)
        end_date = datetime.now(UTC).strftime("%Y%m%d")
        now = datetime.now(UTC)
        if now.month > 2:
            start = now.replace(month=now.month - 2)
        else:
            start = now.replace(year=now.year - 1, month=now.month + 10)
        start_date = start.strftime("%Y%m%d")
        df = await run_sync_fetch(
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
        if df is None or df.empty:
            return await self._mock_kline_bars(symbol, days)
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

    async def get_kline(self, symbol: str, days: int = 60) -> list[dict[str, float]]:
        bars = await self.get_kline_bars(symbol, days)
        return [{"close": float(b["close"]), "volume": float(b["volume"])} for b in bars]

    async def get_kline_chart(self, symbol: str, days: int = 60) -> dict[str, object]:
        from stockresearch.data.technical_indicators import ma_series, macd_series, rsi_series

        bars = await self.get_kline_bars(symbol, days)
        closes = [float(b["close"]) for b in bars]
        macd = macd_series(closes)
        return {
            "symbol": symbol,
            "days": days,
            "bars": bars,
            "indicators": {
                "ma20": ma_series(closes, 20),
                "rsi": rsi_series(closes),
                "macd": macd["macd"],
                "macd_signal": macd["signal"],
                "macd_histogram": macd["histogram"],
            },
        }

    async def _mock_kline_bars(self, symbol: str, days: int) -> list[dict[str, float | str]]:
        from datetime import timedelta

        quote = await QuoteProvider().get_quote(symbol)
        base = quote.price
        end = datetime.now(UTC).date()
        bars: list[dict[str, float | str]] = []
        for i in range(days):
            close = base * (1 + (i - days / 2) * 0.001)
            open_ = close * 0.998
            bars.append(
                {
                    "date": (end - timedelta(days=days - 1 - i)).isoformat(),
                    "open": open_,
                    "high": close * 1.005,
                    "low": close * 0.995,
                    "close": close,
                    "volume": quote.volume,
                }
            )
        return bars

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
    """Real Xueqiu + Eastmoney sentiment metrics (no fake minimum heat)."""
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

    try:
        comment_df = ak.stock_comment_em()
        row = comment_df[comment_df["代码"].astype(str) == symbol]
        if not row.empty:
            attention = float(row.iloc[0]["关注指数"])
            result["attention_index"] = attention
            if int(result["heat_score"]) == 0:
                result["heat_score"] = min(100, max(1, round(attention)))
            sources.append("em_attention")
    except Exception as exc:
        logger.warning("EM stock comment list failed for %s: %s", symbol, exc)

    try:
        df_deal = get_cached("xq_hot_deal", 900.0, ak.stock_hot_deal_xq)
        deal_row = _lookup_xueqiu_row(df_deal, code, name)
        if deal_row is not None:
            result["post_count"] = int(float(deal_row["关注"]))
            rank = int(deal_row.name) + 1
            xq_heat = min(100, max(5, round(100 - (rank / max(len(df_deal), 1)) * 95)))
            if int(result["heat_score"]) == 0:
                result["heat_score"] = xq_heat
            sources.append("xueqiu_deal")
    except Exception as exc:
        logger.warning("Xueqiu deal hot failed for %s: %s", symbol, exc)

    try:
        df_tweet = get_cached("xq_hot_tweet", 900.0, ak.stock_hot_tweet_xq)
        tweet_row = _lookup_xueqiu_row(df_tweet, code, name)
        if tweet_row is not None:
            result["tweet_heat"] = int(float(tweet_row["关注"]))
            sources.append("xueqiu_tweet")
    except Exception as exc:
        logger.warning("Xueqiu tweet hot failed for %s: %s", symbol, exc)

    try:
        df_follow = get_cached("xq_hot_follow", 900.0, ak.stock_hot_follow_xq)
        follow_row = _lookup_xueqiu_row(df_follow, code, name)
        if follow_row is not None:
            result["follow_count"] = int(float(follow_row["关注"]))
            sources.append("xueqiu_follow")
    except Exception as exc:
        logger.warning("Xueqiu follow hot failed for %s: %s", symbol, exc)

    if sources:
        result["source"] = "+".join(sources)
        result["available"] = True
    return result


class SentimentDataProvider:
    async def get_symbol_news(self, symbol: str, name: str, limit: int = 8) -> list[dict[str, str]]:
        if get_settings().use_mock_market_data:
            return [
                {"title": "公司发布经营数据更新", "source": "mock"},
                {"title": "行业政策关注度上升", "source": "mock"},
            ]
        from stockresearch.data.providers.news import NewsProvider

        provider = NewsProvider()
        queries: list[str] = []
        for query in (name, symbol):
            if query and query not in queries:
                queries.append(query)
        items = []
        for query in queries:
            batch = await provider._fetch_akshare_symbol(query, limit)
            if batch:
                items = batch
                break
        if not items:
            raw = await run_sync_fetch(
                f"em symbol news {symbol}",
                lambda: _fetch_em_symbol_news_sync(name or symbol, limit),
                timeout=_DATA_TIMEOUT_SEC,
                fallback=[],
            )
            items = raw or []
        return [{"title": item.title, "source": item.source} for item in items[:limit]]

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
        if get_settings().use_mock_market_data:
            return {
                "heat_score": 72,
                "post_count": 128,
                "bull_ratio": 0.58,
                "follow_count": 101463,
                "attention_index": 94.0,
                "source": "mock",
                "available": True,
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
    async def get_dragon_tiger(self, symbol: str) -> dict[str, str | float | int]:
        if get_settings().use_mock_market_data:
            return self._mock_dragon_tiger()
        return await run_sync_fetch(
            f"akshare lhb {symbol}",
            lambda: self._fetch_dragon_tiger_sync(symbol),
            timeout=_DATA_TIMEOUT_SEC,
            fallback={"appearances": 0, "net_buy": 0.0, "institution_ratio": 0.0, "signal": "暂无数据", "source": "akshare_lhb"},
        )

    async def get_fund_flow(self, symbol: str) -> dict[str, float | str]:
        if get_settings().use_mock_market_data:
            return {"main_net_inflow": 5.0e7, "main_net_pct": 2.5, "days_positive": 3, "source": "mock"}
        return await run_sync_fetch(
            f"akshare fund flow {symbol}",
            lambda: self._fetch_fund_flow_sync(symbol),
            timeout=_DATA_TIMEOUT_SEC,
            fallback={"main_net_inflow": 0.0, "main_net_pct": 0.0, "days_positive": 0, "source": "akshare_fund_flow"},
        )

    async def get_northbound_flow(self, symbol: str) -> dict[str, float | str]:
        fund = await self.get_fund_flow(symbol)
        main_net = float(fund.get("main_net_inflow", 0))
        days_pos = int(fund.get("days_positive", 0))
        return {
            "net_inflow": main_net,
            "days_positive": days_pos,
            "source": str(fund.get("source", "akshare_fund_flow")),
        }

    async def get_holder_count(self, symbol: str) -> dict[str, float | str]:
        if get_settings().use_mock_market_data:
            return {"holder_count": 125000, "qoq_change": -0.02, "source": "mock"}
        return await run_sync_fetch(
            f"akshare holder count {symbol}",
            lambda: self._fetch_holder_count_sync(symbol),
            timeout=_DATA_TIMEOUT_SEC,
            fallback={"holder_count": 0.0, "qoq_change": 0.0, "source": "akshare_gdhs"},
        )

    async def get_lockup(self, symbol: str) -> dict[str, str | float | int]:
        if get_settings().use_mock_market_data:
            return {"upcoming_count": 0, "next_date": "", "ratio_pct": 0.0, "source": "mock"}
        return await run_sync_fetch(
            f"akshare lockup {symbol}",
            lambda: self._fetch_lockup_sync(symbol),
            timeout=_DATA_TIMEOUT_SEC,
            fallback={"upcoming_count": 0, "next_date": "", "ratio_pct": 0.0, "source": "akshare_lockup"},
        )

    def _mock_dragon_tiger(self) -> dict[str, str | float | int]:
        return {
            "appearances": 1,
            "net_buy": 1.2e8,
            "institution_ratio": 0.35,
            "signal": "neutral",
            "source": "mock",
        }

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

    def _fetch_fund_flow_sync(self, symbol: str) -> dict[str, float | str]:
        df = ak.stock_individual_fund_flow(stock=symbol, market=_market_code(symbol))
        if df.empty:
            return {"main_net_inflow": 0.0, "main_net_pct": 0.0, "days_positive": 0, "source": "akshare_fund_flow"}
        recent = df.tail(5)
        main_net = float(recent.iloc[-1]["主力净流入-净额"])
        main_pct = float(recent.iloc[-1]["主力净流入-净占比"])
        days_positive = int((recent["主力净流入-净额"] > 0).sum())
        return {
            "main_net_inflow": main_net,
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
