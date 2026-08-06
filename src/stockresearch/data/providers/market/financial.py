"""Financial / valuation / peers provider — never fabricate zeros as real metrics."""

import logging
from typing import Any

import akshare as ak  # type: ignore[import-untyped]

from stockresearch.data.providers.base import run_sync_fetch
from stockresearch.data.providers.market.common import _DATA_TIMEOUT_SEC, _use_mock_market_data
from stockresearch.data.providers.tushare_financial import fetch_daily_basic_sync
from stockresearch.services.provider_cache_policy import get_or_set_cached_dict, provider_ttl
from stockresearch.utils.symbols import resolve_name

logger = logging.getLogger(__name__)


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
        # AkShare indicator order is not guaranteed (oldest-first vs newest-first);
        # sort by period so "latest" is always the most recent row regardless of source order.
        frame = df.copy()
        period_col = next((c for c in ("日期", "报告期", "年份") if c in frame.columns), None)
        if period_col is not None:
            try:
                frame = frame.sort_values(period_col, ascending=True)
            except (TypeError, ValueError):
                pass
        series: list[dict[str, object]] = []
        for _, row in frame.tail(8).iterrows():
            period = str(row.get("日期", row.get("报告期", row.get("年份", ""))))[:10]
            series.append(
                {
                    "period": period,
                    "revenue_yoy": self._optional_pct(row.get("营业收入同比增长率")),
                    "net_profit_yoy": self._optional_pct(row.get("净利润同比增长率")),
                    "net_margin": self._optional_pct(row.get("销售净利率")),
                    "roe": self._optional_pct(row.get("净资产收益率")),
                    "debt_ratio": self._optional_pct(row.get("资产负债率")),
                }
            )
        row = frame.iloc[-1]
        gaps: list[str] = []
        if len(series) < 2:
            gaps.append("财务序列不足 2 期")
        core = {
            "revenue_yoy": self._optional_pct(row.get("营业收入同比增长率")),
            "net_profit_yoy": self._optional_pct(row.get("净利润同比增长率")),
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
            "series": list(reversed(series)),  # newest-first to match THS path
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
                    "net_profit_yoy": self._optional_pct(
                        row.get("净利润同比增长率", row.get("归母净利润同比增长率"))
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
            "net_profit_yoy": self._optional_pct(
                latest.get("净利润同比增长率", latest.get("归母净利润同比增长率"))
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
                "net_profit_yoy": 0.15,
                "net_margin": 0.25,
                "roe": 0.18,
                "pe_percentile": 0.50,
                "debt_ratio": 0.35,
                "goodwill_ratio": 0.03,
                "series": [
                    {
                        "period": "2023",
                        "roe": 0.16,
                        "revenue_yoy": 0.10,
                        "net_profit_yoy": 0.11,
                        "net_margin": 0.24,
                        "debt_ratio": 0.36,
                    },
                    {
                        "period": "2024",
                        "roe": 0.18,
                        "revenue_yoy": 0.12,
                        "net_profit_yoy": 0.15,
                        "net_margin": 0.25,
                        "debt_ratio": 0.35,
                    },
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

        cached = await get_or_set_cached_dict(cache_key, ttl, _fetch, should_cache=_cacheable)
        return {k: v for k, v in cached.items()}  # type: ignore[misc]

    def _valuation_from_series(
        self,
        *,
        pe_ttm: float | None,
        pb: float | None,
        pe_series: list[float],
        pb_series: list[float] | None = None,
        source: str,
    ) -> dict[str, object]:
        pe_pct = self._percentile_rank(pe_series, pe_ttm) if pe_ttm is not None else None
        pb_hist = pb_series or []
        pb_pct = self._percentile_rank(pb_hist, pb) if pb is not None else None
        gaps: list[str] = []
        if pe_ttm is None:
            gaps.append("PE 不可用")
        if pb is None:
            gaps.append("PB 不可用")
        if pe_pct is None:
            gaps.append("PE 历史分位不可算")
        if pb is not None and pb_pct is None:
            gaps.append("PB 历史分位不可算")
        return {
            "pe_ttm": pe_ttm,
            "pb": pb,
            "pe_percentile": pe_pct,
            "pb_percentile": pb_pct,
            "pe_history_count": len(pe_series),
            "pb_history_count": len(pb_hist),
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
        pb_series: list[float] = []
        if pe_col:
            for val in df[pe_col].tolist():
                fval = self._optional_float(val)
                if fval is not None and fval > 0:
                    pe_series.append(fval)
        if pb_col:
            for val in df[pb_col].tolist():
                fval = self._optional_float(val)
                if fval is not None and fval > 0:
                    pb_series.append(fval)
        if pe_ttm is None and pb is None:
            return None
        return self._valuation_from_series(
            pe_ttm=pe_ttm,
            pb=pb,
            pe_series=pe_series,
            pb_series=pb_series,
            source="akshare_value_em",
        )

    def _from_baidu_valuation(self, pe_df: Any, pb_df: Any) -> dict[str, object] | None:
        """Parse Baidu stock_zh_valuation_baidu PE/PB series."""
        pe_series: list[float] = []
        pb_series: list[float] = []
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
            for val in pb_df["value"].tolist():
                fval = self._optional_float(val)
                if fval is not None and fval > 0:
                    pb_series.append(fval)
            if pb_series:
                pb = pb_series[-1]
        if pe_ttm is None and pb is None:
            return None
        return self._valuation_from_series(
            pe_ttm=pe_ttm,
            pb=pb,
            pe_series=pe_series,
            pb_series=pb_series,
            source="akshare_baidu",
        )

    async def get_valuation(self, symbol: str) -> dict[str, float | str | object]:
        if _use_mock_market_data():
            return {
                "pe_ttm": 28.0,
                "pe_percentile": 0.42,
                "pb": 8.0,
                "pb_percentile": 0.55,
                "source": "mock",
                "partial": False,
                "gaps": [],
            }
        # v5: include PB historical percentile alongside PE.
        cache_key = f"financials:valuation:v5:{symbol}"
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
                            "pb_percentile": None,
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
                "pb_percentile": None,
                "source": "none",
                "partial": True,
                "gaps": ["估值数据不可用"],
            }

        def _cacheable(payload: dict[str, object]) -> bool:
            if payload.get("pe_ttm") is None and payload.get("pb") is None:
                return False
            src = str(payload.get("source") or "")
            # Tushare/none shells without percentile poison the day-long cache.
            if payload.get("pe_percentile") is None and ("tushare" in src or src in ("", "none")):
                return False
            return True

        cached = await get_or_set_cached_dict(cache_key, ttl, _fetch, should_cache=_cacheable)
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
                logger.debug("peer valuation attach failed for %s", peer, exc_info=True)
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
