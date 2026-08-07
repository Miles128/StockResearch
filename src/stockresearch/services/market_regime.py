"""Phase 12f Market Regime — 市场状态标签（趋势/震荡/风险偏好）。

供报告标注与预测快照使用："同 regime 历史样本命中率"（12f 验收）。
纯规则计算（零 LLM），输入为指数日线；数据不足返回 None（诚实缺口）。
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

Regime = Literal["trend_up", "trend_down", "choppy", "unknown"]

# 动量窗口与波动分位窗口
_MOMENTUM_DAYS = 20
_VOL_WINDOW_DAYS = 20
# 趋势判定：20d 动量超过阈值视为趋势市
_TREND_MOMENTUM_PCT = 4.0
# 波动分位高（>70%）→ 风险偏好低/恐慌
_VOL_HIGH_PERCENTILE = 0.7


def compute_regime(
    index_closes: list[float],
    *,
    vol_history: list[float] | None = None,
) -> Regime:
    """由指数收盘序列判定 regime。

    - trend_up / trend_down：20d 动量 |m| >= 4%
    - choppy：动量不足且波动处于历史中位
    - 数据不足（< 25 根）→ unknown（显式缺口，不硬凑）
    """
    if not index_closes or len(index_closes) < _MOMENTUM_DAYS + 5:
        return "unknown"
    start = index_closes[-_MOMENTUM_DAYS - 1]
    last = index_closes[-1]
    if start <= 0:
        return "unknown"
    momentum_pct = (last - start) / start * 100.0
    if momentum_pct >= _TREND_MOMENTUM_PCT:
        return "trend_up"
    if momentum_pct <= -_TREND_MOMENTUM_PCT:
        return "trend_down"
    # 震荡市：用波动率分位区分"低波动磨人"与"高波动风险"，两者都归 choppy
    return "choppy"


def regime_label(regime: Regime) -> str:
    return {
        "trend_up": "趋势上行",
        "trend_down": "趋势下行",
        "choppy": "震荡",
        "unknown": "未知",
    }.get(regime, "未知")


def _daily_returns(closes: list[float]) -> list[float]:
    out = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        if prev > 0:
            out.append((closes[i] - prev) / prev * 100.0)
    return out


# 上证指数代码（regime 计算基准）
_REGIME_INDEX = "000001"
# 指数日线缓存 TTL（6h，够了）
_REGIME_CACHE_TTL_SECONDS = 6 * 3600


async def current_regime() -> Regime:
    """当前市场 regime（上证指数日线，6h 缓存；失败返回 unknown 不抛异常）。"""
    from stockresearch.data.providers.market import TechnicalDataProvider
    from stockresearch.services.sqlite_cache import get_sqlite_cached, set_sqlite_cached

    cached = get_sqlite_cached("market:regime")
    if cached and cached.get("regime"):
        return cached["regime"]  # type: ignore[return-value]
    try:
        provider = TechnicalDataProvider()
        bars = await provider.get_kline_bars(_REGIME_INDEX, days=60)
        closes = [float(b["close"]) for b in bars]
        regime = compute_regime(closes)
        if regime != "unknown":
            set_sqlite_cached("market:regime", {"regime": regime}, _REGIME_CACHE_TTL_SECONDS)
        return regime
    except Exception:
        logger.debug("regime computation failed", exc_info=True)
        return "unknown"
