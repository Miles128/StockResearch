"""Market data providers — Sina quotes on hot path, mock for tests."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import akshare as ak

from invesbao.core.config import get_settings
from invesbao.core.exceptions import DataProviderError
from invesbao.data.providers.sina_quote import fetch_sina_quotes
from invesbao.utils.symbols import resolve_name

logger = logging.getLogger(__name__)

_QUOTE_TIMEOUT_SEC = 6.0
_DATA_TIMEOUT_SEC = 8.0

_POSITIVE_NEWS = ("增长", "利好", "超预期", "分红", "回购", "上涨", "突破", "中标")
_NEGATIVE_NEWS = ("下滑", "亏损", "减持", "问询", "立案", "下调", "警示", "违规", "解禁")


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

        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(fetch_sina_quotes, unique),
                timeout=_QUOTE_TIMEOUT_SEC,
            )
        except TimeoutError as exc:
            raise DataProviderError("新浪行情请求超时") from exc
        except Exception as exc:
            logger.warning("Sina batch quote failed: %s", exc)
            raise DataProviderError("新浪行情不可用") from exc

        return {
            sym: Quote(
                symbol=str(row["symbol"]),
                name=str(row["name"]),
                price=float(row["price"]),
                change_pct=float(row["change_pct"]),
                high=float(row["high"]),
                low=float(row["low"]),
                volume=float(row["volume"]),
                updated_at=row["updated_at"],  # type: ignore[arg-type]
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


class FinancialDataProvider:
    async def get_financials(self, symbol: str) -> dict[str, float | str]:
        if get_settings().use_mock_market_data:
            return self._mock_financials(symbol)
        try:
            df = await asyncio.wait_for(
                asyncio.to_thread(ak.stock_financial_analysis_indicator, symbol=symbol),
                timeout=8.0,
            )
            if df.empty:
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
        except Exception as exc:
            logger.warning("AkShare financials failed for %s: %s", symbol, exc)
            return self._mock_financials(symbol)

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

    async def get_valuation(self, symbol: str) -> dict[str, float]:
        if get_settings().use_mock_market_data:
            fin = await self.get_financials(symbol)
            pe = float(fin.get("pe_percentile", 0.5)) * 40
            return {"pe_ttm": pe, "pe_percentile": float(fin.get("pe_percentile", 0.5))}
        try:
            df = await asyncio.wait_for(
                asyncio.to_thread(ak.stock_a_indicator_lg, symbol=symbol),
                timeout=8.0,
            )
            if df.empty:
                return {"pe_ttm": 20.0, "pe_percentile": 0.5}
            row = df.iloc[-1]
            pe_ttm = float(row.get("pe", 20.0))
            return {"pe_ttm": pe_ttm, "pe_percentile": 0.5}
        except Exception as exc:
            logger.warning("AkShare valuation failed for %s: %s", symbol, exc)
            return {"pe_ttm": 20.0, "pe_percentile": 0.5}

    async def get_industry_peers(self, symbol: str) -> list[str]:
        sector_peers: dict[str, list[str]] = {
            "600519": ["000858", "000568"],
            "300750": ["002594", "300014"],
        }
        return sector_peers.get(symbol, [])


class TechnicalDataProvider:
    async def get_kline(self, symbol: str, days: int = 60) -> list[dict[str, float]]:
        if get_settings().use_mock_market_data:
            quote = await QuoteProvider().get_quote(symbol)
            base = quote.price
            return [{"close": base * (1 + (i - days / 2) * 0.001), "volume": quote.volume} for i in range(days)]
        try:
            end_date = datetime.now(UTC).strftime("%Y%m%d")
            now = datetime.now(UTC)
            if now.month > 2:
                start = now.replace(month=now.month - 2)
            else:
                start = now.replace(year=now.year - 1, month=now.month + 10)
            start_date = start.strftime("%Y%m%d")
            df = await asyncio.wait_for(
                asyncio.to_thread(
                    ak.stock_zh_a_hist,
                    symbol=symbol,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq",
                ),
                timeout=10.0,
            )
            if df.empty:
                return await self._mock_kline(symbol, days)
            recent = df.tail(days)
            return [
                {"close": float(row["收盘"]), "volume": float(row["成交量"])}
                for _, row in recent.iterrows()
            ]
        except Exception as exc:
            logger.warning("AkShare kline failed for %s: %s", symbol, exc)
            return await self._mock_kline(symbol, days)

    async def _mock_kline(self, symbol: str, days: int) -> list[dict[str, float]]:
        quote = await QuoteProvider().get_quote(symbol)
        base = quote.price
        return [{"close": base * (1 + (i - days / 2) * 0.001), "volume": quote.volume} for i in range(days)]

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


class SentimentDataProvider:
    async def get_symbol_news(self, symbol: str, name: str, limit: int = 8) -> list[dict[str, str]]:
        if get_settings().use_mock_market_data:
            return [
                {"title": "公司发布经营数据更新", "source": "mock"},
                {"title": "行业政策关注度上升", "source": "mock"},
            ]
        from invesbao.data.providers.news import NewsProvider

        provider = NewsProvider()
        query = name or symbol
        items = await provider._fetch_akshare_symbol(query, limit)
        if not items and name != symbol:
            items = await provider._fetch_akshare_symbol(symbol, limit)
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

    async def get_xueqiu_hot(self, symbol: str, name: str = "") -> dict[str, float | int]:
        news = await self.get_symbol_news(symbol, name)
        sentiment = self.score_titles([item["title"] for item in news])
        heat = min(100, max(10, len(news) * 12))
        bull_ratio = max(0.2, min(0.8, 0.5 + sentiment * 0.25))
        return {
            "heat_score": heat,
            "post_count": len(news),
            "bull_ratio": round(bull_ratio, 2),
        }

    async def get_news_sentiment_score(self, symbol: str, name: str = "") -> float:
        news = await self.get_symbol_news(symbol, name)
        return self.score_titles([item["title"] for item in news])


class ChipsDataProvider:
    async def get_dragon_tiger(self, symbol: str) -> dict[str, str | float | int]:
        if get_settings().use_mock_market_data:
            return self._mock_dragon_tiger()
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._fetch_dragon_tiger_sync, symbol),
                timeout=_DATA_TIMEOUT_SEC,
            )
        except Exception as exc:
            logger.warning("AkShare LHB failed for %s: %s", symbol, exc)
            return {"appearances": 0, "net_buy": 0.0, "institution_ratio": 0.0, "signal": "暂无数据", "source": "akshare_lhb"}

    async def get_fund_flow(self, symbol: str) -> dict[str, float | str]:
        if get_settings().use_mock_market_data:
            return {"main_net_inflow": 5.0e7, "main_net_pct": 2.5, "days_positive": 3, "source": "mock"}
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._fetch_fund_flow_sync, symbol),
                timeout=_DATA_TIMEOUT_SEC,
            )
        except Exception as exc:
            logger.warning("AkShare fund flow failed for %s: %s", symbol, exc)
            return {"main_net_inflow": 0.0, "main_net_pct": 0.0, "days_positive": 0, "source": "akshare_fund_flow"}

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
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._fetch_holder_count_sync, symbol),
                timeout=_DATA_TIMEOUT_SEC,
            )
        except Exception as exc:
            logger.warning("AkShare holder count failed for %s: %s", symbol, exc)
            return {"holder_count": 0.0, "qoq_change": 0.0, "source": "akshare_gdhs"}

    async def get_lockup(self, symbol: str) -> dict[str, str | float | int]:
        if get_settings().use_mock_market_data:
            return {"upcoming_count": 0, "next_date": "", "ratio_pct": 0.0, "source": "mock"}
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._fetch_lockup_sync, symbol),
                timeout=_DATA_TIMEOUT_SEC,
            )
        except Exception as exc:
            logger.warning("AkShare lockup failed for %s: %s", symbol, exc)
            return {"upcoming_count": 0, "next_date": "", "ratio_pct": 0.0, "source": "akshare_lockup"}

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
