"""Chips provider — dragon-tiger, fund flow, northbound, margin, holders, lockup."""

import logging
from datetime import UTC, datetime, timedelta

import akshare as ak  # type: ignore[import-untyped]

from stockresearch.core.config import get_settings
from stockresearch.data.provider_meta import get_provider_meta
from stockresearch.data.providers.base import run_sync_fetch
from stockresearch.data.providers.market.common import (
    _DATA_TIMEOUT_SEC,
    _as_float,
    _market_code,
    _use_mock_market_data,
)
from stockresearch.services.provider_cache_policy import provider_ttl
from stockresearch.services.sqlite_cache import get_sqlite_cached, set_sqlite_cached

logger = logging.getLogger(__name__)


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
        assert result is not None
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
        assert result is not None
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
        assert result is not None
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
        assert result is not None
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
        assert result is not None
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
        assert result is not None
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
                logger.debug(
                    "margin detail fetch failed for %s date=%s", symbol, date, exc_info=True
                )
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
                # SSE detail reports 融券余量 in shares; use the yuan-valued column
                # (融券余量金额) so the total keeps a single unit.
                securities = _as_float(row.get("融券余量金额")) or _as_float(row.get("融券余额"))
                total = _as_float(row.get("融资融券余额")) or financing + securities
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
            return {
                "upcoming_count": 0,
                "next_date": "",
                "ratio_pct": 0.0,
                "source": "akshare_lockup",
            }
        today = datetime.now(UTC).date()
        try:
            upcoming = df[df["解禁时间"] >= today] if "解禁时间" in df.columns else df.iloc[0:0]
        except TypeError:
            # Column stored as strings ("YYYY-MM-DD") — compare as strings.
            upcoming = (
                df[df["解禁时间"].astype(str) >= today.isoformat()]
                if "解禁时间" in df.columns
                else df.iloc[0:0]
            )
        if upcoming.empty:
            return {
                "upcoming_count": 0,
                "next_date": "",
                "ratio_pct": 0.0,
                "source": "akshare_lockup",
            }
        # "Next unlock" = the NEAREST future date; source row order is not
        # guaranteed, so sort ascending before taking the first row.
        upcoming = upcoming.sort_values("解禁时间", ascending=True)
        row = upcoming.iloc[0]
        ratio_pct = float(row.get("占总市值比例", 0) or 0)
        return {
            "upcoming_count": len(upcoming),
            "next_date": str(row.get("解禁时间", ""))[:10],
            "ratio_pct": ratio_pct,
            "source": "akshare_lockup",
        }
