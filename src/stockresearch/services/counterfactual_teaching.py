"""Phase 13b Counterfactual 教学 — 用用户真实持仓演示概念（回撤/波动/估值）。

"假设你当时……"：把用户自己的持仓金额（成本价 × 手数 × 100）绑定到真实
历史价格情景上，规则生成三段白话教学（教机制，不给结论）。不调用 LLM，
只使用 qfq 日线仓 + 估值分位源。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from statistics import pstdev

from stockresearch.core.constants import DISCLAIMER
from stockresearch.core.schemas import (
    CounterfactualSegmentOut,
    CounterfactualTeachingOut,
)
from stockresearch.data.providers.market.financial import FinancialDataProvider
from stockresearch.services.daily_bars import get_bars_meta_for_symbol
from stockresearch.utils.symbols import resolve_name

logger = logging.getLogger(__name__)

_LOOKBACK_DAYS = 250  # 约一年交易日，保证回撤/波动样本
_WORST_DAY_FLOOR_PCT = -50.0  # 单日跌幅护栏（除权/数据异常时不过度惊吓）
_TRADING_DAYS_YEAR = 252.0


def _bars_closes(bars: list[dict]) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    for b in bars:
        close = float(b.get("close") or 0)
        if close <= 0:
            continue
        out.append((str(b.get("date", ""))[:10], close))
    return out


def _max_drawdown(series: list[tuple[str, float]]) -> tuple[float | None, str, str]:
    """最大回撤（峰值→谷值）。返回 (回撤 %, 峰日期, 谷日期)。"""
    if len(series) < 2:
        return None, "", ""
    peak_date, peak_price = series[0]
    max_dd = 0.0
    dd_peak_date, dd_trough_date = "", ""
    for day, price in series:
        if price >= peak_price:
            peak_date, peak_price = day, price
            continue
        dd = (price - peak_price) / peak_price
        if dd < max_dd:
            max_dd = dd
            dd_peak_date, dd_trough_date = peak_date, day
    if max_dd == 0.0:
        return None, "", ""
    return max_dd * 100.0, dd_peak_date, dd_trough_date


def _annualized_vol_pct(series: list[tuple[str, float]]) -> float | None:
    """日收益率年化波动率（%）。"""
    if len(series) < 3:
        return None
    returns = [b / a - 1.0 for (_, a), (_, b) in zip(series, series[1:])]
    if len(returns) < 2:
        return None
    vol = pstdev(returns) * (_TRADING_DAYS_YEAR**0.5)
    return vol * 100.0


def _worst_day_pct(series: list[tuple[str, float]]) -> tuple[float | None, str]:
    if len(series) < 2:
        return None, ""
    worst = 0.0
    worst_date = ""
    for (day_a, a), (day_b, b) in zip(series, series[1:]):
        if a <= 0:
            continue
        ret = b / a - 1.0
        if ret < worst:
            worst = ret
            worst_date = day_b
    if not worst_date:
        return None, ""
    worst = max(worst, _WORST_DAY_FLOOR_PCT / 100.0)
    return worst * 100.0, worst_date


def _fmt_money(value: float) -> str:
    """金额转「万元」表述：>=1 万用 X.X 万元，否则元。"""
    if abs(value) >= 10000:
        return f"{value / 10000:.1f} 万元"
    return f"{value:.0f} 元"


def _drawdown_segment(
    series: list[tuple[str, float]], position_value: float
) -> CounterfactualSegmentOut:
    max_dd, peak_date, trough_date = _max_drawdown(series)
    if max_dd is None or max_dd > -1:
        return CounterfactualSegmentOut(
            concept="drawdown",
            title="回撤",
            story=("过去一年这只股票没有出现明显的从高点回落，暂无值得演示的回撤情景。"),
            partial=True,
            note="日线样本内未发现显著回撤",
        )
    loss_amount = position_value * abs(max_dd) / 100.0
    story = (
        f"假设你在 {peak_date} 附近的最高价买入你现在的持仓金额（约 {_fmt_money(position_value)}），"
        f"之后股价一路跌到 {trough_date} 附近的最低点，账面最多浮亏 {abs(max_dd):.1f}%"
        f"（约 {_fmt_money(loss_amount)}）。"
        f"这就是「最大回撤」——从最高点到最低点最多跌掉多少。"
        f"它衡量的是你拿着不放时，最难受的那段日子账面要承受多少压力。"
    )
    return CounterfactualSegmentOut(
        concept="drawdown",
        title="回撤",
        story=story,
    )


def _volatility_segment(
    series: list[tuple[str, float]], position_value: float
) -> CounterfactualSegmentOut:
    vol = _annualized_vol_pct(series)
    worst, worst_date = _worst_day_pct(series)
    if vol is None:
        return CounterfactualSegmentOut(
            concept="volatility",
            title="波动",
            story="日线样本不足，暂时无法演示波动情景。",
            partial=True,
            note="日线不足 3 根",
        )
    daily_move = vol / (_TRADING_DAYS_YEAR**0.5)
    parts = [
        f"假设你持有约 {_fmt_money(position_value)} 的这只股票，"
        f"它的年化波动率约 {vol:.0f}%，"
        f"换算成日常感受就是：大部分交易日涨跌在 ±{daily_move:.1f}% 之间。"
    ]
    if worst is not None and worst_date:
        worst_amount = position_value * abs(worst) / 100.0
        parts.append(
            f"过去一年最惨的一天（{worst_date}）跌了 {abs(worst):.1f}%，"
            f"如果那天你正好持仓 {_fmt_money(position_value)}，一天账面就会少 {_fmt_money(worst_amount)}。"
        )
    parts.append(
        "波动率衡量的是价格跳动的剧烈程度——波动越大，账面起伏越刺激，"
        "但长期回报和短期波动并不总是成正比。"
    )
    return CounterfactualSegmentOut(
        concept="volatility",
        title="波动",
        story="".join(parts),
    )


def _valuation_segment(
    position_value: float, valuation: dict[str, object]
) -> CounterfactualSegmentOut:
    pe = valuation.get("pe_ttm")
    pe_min = valuation.get("pe_min")
    pe_max = valuation.get("pe_max")
    pe_pct = valuation.get("pe_percentile")
    pe_cur = float(pe) if isinstance(pe, int | float) else None
    pe_lo = float(pe_min) if isinstance(pe_min, int | float) else None
    pe_hi = float(pe_max) if isinstance(pe_max, int | float) else None
    pct = float(pe_pct) if isinstance(pe_pct, int | float) else None
    if pe_cur is None or pe_lo is None or pe_hi is None or pe_lo <= 0 or pe_hi <= pe_lo:
        return CounterfactualSegmentOut(
            concept="valuation",
            title="估值",
            story="这只股票的 PE 历史极值暂不可用，无法演示估值情景。",
            partial=True,
            note="估值源未提供 PE 历史极值",
        )
    pct_text = f"{pct * 100:.0f}%" if pct is not None else "不可得"
    parts = [
        f"假设你现在买入 {_fmt_money(position_value)}，"
        f"当前 PE 约 {pe_cur:.1f} 倍，处于过去一年 {pe_lo:.1f}~{pe_hi:.1f} 倍区间的"
        f"{pct_text} 分位（越低越便宜，越高越贵）。"
    ]
    # 反事实：若分位回到中位（50%）对应的 PE，市值（盈利不变）会怎么变。
    mid_pe = (pe_lo + pe_hi) / 2.0
    if pct is not None and pct > 0.51 and mid_pe > 0:
        shrink = (mid_pe - pe_cur) / pe_cur * 100.0
        if shrink < 0:
            parts.append(
                f"假设估值只是回落到过去一年的中位数（PE≈{mid_pe:.1f}），"
                f"盈利不变的情况下，估值这一项就会让账面缩水 {abs(shrink):.0f}%"
                f"（约 {_fmt_money(position_value * abs(shrink) / 100.0)}）。"
            )
        else:
            parts.append(
                f"你的 PE 分位还不算极端（{pct * 100:.0f}%），"
                f"即使估值回到中位数，估值项的影响也有限。"
            )
    elif pct is not None and pct < 0.49 and mid_pe > 0:
        gain = (mid_pe - pe_cur) / pe_cur * 100.0
        parts.append(
            f"假设估值回升到过去一年的中位数（PE≈{mid_pe:.1f}），"
            f"盈利不变的情况下，估值这一项会带来约 {gain:.0f}% 的账面空间"
            f"（约 {_fmt_money(position_value * gain / 100.0)}）。"
        )
    parts.append(
        "PE 分位告诉你当前价格贵不贵——买在便宜的分位，估值本身可能帮你；"
        "买在贵的分位，估值也可能反过来拖累账面。"
    )
    return CounterfactualSegmentOut(
        concept="valuation",
        title="估值",
        story="".join(parts),
    )


async def compute_counterfactual_teaching(
    symbol: str,
    *,
    position_value: float | None = None,
) -> CounterfactualTeachingOut:
    """为单个标的生成三段情景教学。position_value 为用户持仓金额。"""
    name = resolve_name(symbol)
    meta = await get_bars_meta_for_symbol(symbol, days=_LOOKBACK_DAYS)
    series = _bars_closes(meta.bars) if meta.adjust == "qfq" else []
    notes: list[str] = []
    segments: list[CounterfactualSegmentOut] = []

    if meta.adjust != "qfq":
        notes.append(meta.note or "日线非 qfq，回撤/波动教学未计算")
    if not series:
        segments.append(
            CounterfactualSegmentOut(
                concept="drawdown",
                title="回撤",
                story="日线仓暂无该标的的可教学样本。",
                partial=True,
                note="无日线",
            )
        )
        segments.append(
            CounterfactualSegmentOut(
                concept="volatility",
                title="波动",
                story="日线仓暂无该标的的可教学样本。",
                partial=True,
                note="无日线",
            )
        )
    else:
        segments.append(_drawdown_segment(series, position_value or 10000.0))
        segments.append(_volatility_segment(series, position_value or 10000.0))

    try:
        provider = FinancialDataProvider()
        valuation = await provider.get_valuation(symbol)
        segments.append(_valuation_segment(position_value or 10000.0, valuation))
        raw_gaps = valuation.get("gaps")
        if isinstance(raw_gaps, list):
            gaps = [str(g) for g in raw_gaps if g]
            if gaps:
                notes.append("估值数据：" + "；".join(gaps))
    except Exception as exc:  # noqa: BLE001 — 估值失败不应让整段教学挂掉
        logger.warning("counterfactual valuation failed for %s: %s", symbol, exc)
        segments.append(
            CounterfactualSegmentOut(
                concept="valuation",
                title="估值",
                story="估值源暂时不可用，估值情景稍后再看。",
                partial=True,
                note="估值源失败",
            )
        )

    return CounterfactualTeachingOut(
        symbol=symbol,
        name=name,
        position_value=position_value,
        segments=segments,
        bars_adjust=meta.adjust,
        bars_source=meta.source,
        notes=notes,
        disclaimer=f"情景教学用真实历史数据演示概念，非预测。{DISCLAIMER}",
        as_of=datetime.now(UTC).date().isoformat(),
    )
