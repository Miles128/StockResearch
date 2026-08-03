"""Layered provider metadata catalog — single contract for tools, factors, and diagnostics."""

from dataclasses import dataclass
from typing import Literal

Layer = Literal["L1", "L2", "L3"]


@dataclass(frozen=True)
class ProviderMeta:
    key: str
    label: str
    layer: Layer
    provider: str
    domain: str
    default_ttl_seconds: int | None = None


PROVIDER_CATALOG: dict[str, ProviderMeta] = {
    "sina_quote": ProviderMeta("sina_quote", "实时行情", "L1", "sina", "quotes", 5),
    "sina_global_indices": ProviderMeta(
        "sina_global_indices", "外围市场指数", "L1", "sina", "global", 600
    ),
    "sina_trading_rules": ProviderMeta(
        "sina_trading_rules", "涨跌停 / ST / 停复牌", "L1", "sina", "quotes", 5
    ),
    "akshare_kline": ProviderMeta(
        "akshare_kline", "K 线与技术指标", "L2", "akshare", "technical", 3600
    ),
    "akshare_lhb": ProviderMeta("akshare_lhb", "龙虎榜", "L2", "akshare", "chips", 86400),
    "akshare_fund_flow": ProviderMeta(
        "akshare_fund_flow", "主力资金流向", "L2", "akshare", "chips", 3600
    ),
    "akshare_northbound": ProviderMeta(
        "akshare_northbound", "北向资金", "L2", "akshare", "chips", 3600
    ),
    "akshare_margin": ProviderMeta("akshare_margin", "融资融券", "L2", "akshare", "chips", 86400),
    "akshare_gdhs": ProviderMeta("akshare_gdhs", "股东户数", "L2", "akshare", "chips", 86400),
    "akshare_lockup": ProviderMeta("akshare_lockup", "限售解禁", "L2", "akshare", "chips", 86400),
    "akshare_financials": ProviderMeta(
        "akshare_financials", "财务与估值", "L2", "akshare", "fundamental", 86400
    ),
    "kimi_macro": ProviderMeta("kimi_macro", "Kimi 宏观与行业数据", "L2", "kimi", "macro", 86400),
    "kimi_wind": ProviderMeta(
        "kimi_wind",
        "Kimi Wind 深度数据",
        "L2",
        "kimi",
        "fundamental",
        21600,
    ),
    "news_text_factor": ProviderMeta(
        "news_text_factor", "新闻文本因子", "L1", "news", "sentiment", 1800
    ),
    "tushare_pro": ProviderMeta(
        "tushare_pro",
        "Tushare Pro（估值 / 日线 qfq 兜底）",
        "L3",
        "tushare",
        "fundamental",
        86400,
    ),
    "tushare_daily_basic": ProviderMeta(
        "tushare_daily_basic",
        "Tushare 当日估值",
        "L3",
        "tushare",
        "valuation",
        3600,
    ),
    "tushare_kline": ProviderMeta(
        "tushare_kline",
        "Tushare 前复权日线",
        "L3",
        "tushare",
        "technical",
        3600,
    ),
}


def list_provider_catalog() -> list[ProviderMeta]:
    return list(PROVIDER_CATALOG.values())


def get_provider_meta(key: str) -> ProviderMeta | None:
    return PROVIDER_CATALOG.get(key)
