"""One-click hypothesis verification on qfq bars (research, not a strategy)."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from statistics import mean

from stockresearch.core.constants import DISCLAIMER
from stockresearch.core.schemas import HypothesisVerifyOut, HypothesisWindowOut
from stockresearch.services.daily_bars import get_bars_meta_for_symbol
from stockresearch.services.signal_backtest import _forward_return_pct
from stockresearch.utils.symbols import resolve_name

# Preset rules evaluated only from prices known at day t (point-in-time).
# Valuation/ROE series are not available historically here — use price proxies
# (drawdown / rally / vol×momentum) as research hypotheses.
HYPOTHESIS_PRESETS: dict[str, str] = {
    "momentum_positive": "20日动量 > 0 时，后续收益是否偏正",
    "momentum_negative": "20日动量 < 0 时，后续收益是否偏负",
    "momentum_strong_up": "20日动量 ≥ 5% 时，后续收益是否偏正",
    "momentum_strong_down": "20日动量 ≤ -5% 时，后续收益是否偏负",
    "drawdown_rebound": "20日动量 ≤ -10%（深回撤）时，后续是否易反弹",
    "rally_continuation": "20日动量 ≥ 10%（大涨）时，后续是否仍偏正",
    "calm_momentum_up": "20日动量 ≥ 3% 且年化波动 < 30%（低波顺势）时，后续是否偏正",
    "high_vol_momentum_up": "20日动量 ≥ 5% 且年化波动 ≥ 40%（高波追涨）时，后续是否偏正",
}

_BULLISH_HIT_RULES = frozenset(
    {
        "momentum_positive",
        "momentum_strong_up",
        "drawdown_rebound",
        "rally_continuation",
        "calm_momentum_up",
        "high_vol_momentum_up",
    }
)
_BEARISH_HIT_RULES = frozenset({"momentum_negative", "momentum_strong_down"})


def _momentum_at(closes: list[float], idx: int, window: int = 20) -> float | None:
    if idx < window or closes[idx - window] <= 0:
        return None
    return (closes[idx] / closes[idx - window] - 1.0) * 100.0


def _vol_ann_pct_at(closes: list[float], idx: int, window: int = 20) -> float | None:
    """Annualized volatility (%) from daily returns ending at idx (inclusive)."""
    if idx < window:
        return None
    rets: list[float] = []
    for i in range(idx - window + 1, idx + 1):
        prev = closes[i - 1]
        cur = closes[i]
        if prev > 0:
            rets.append(cur / prev - 1.0)
    if len(rets) < 2:
        return None
    avg = sum(rets) / len(rets)
    var = sum((x - avg) ** 2 for x in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252) * 100.0


def _match(rule: str, mom: float | None, vol: float | None = None) -> bool:
    if mom is None:
        return False
    if rule == "momentum_positive":
        return mom > 0
    if rule == "momentum_negative":
        return mom < 0
    if rule == "momentum_strong_up":
        return mom >= 5.0
    if rule == "momentum_strong_down":
        return mom <= -5.0
    if rule == "drawdown_rebound":
        return mom <= -10.0
    if rule == "rally_continuation":
        return mom >= 10.0
    if rule == "calm_momentum_up":
        return mom >= 3.0 and vol is not None and vol < 30.0
    if rule == "high_vol_momentum_up":
        return mom >= 5.0 and vol is not None and vol >= 40.0
    return False


def _hit_rate(rule: str, vals: list[float]) -> float | None:
    if not vals:
        return None
    if rule in _BULLISH_HIT_RULES:
        return round(sum(1 for v in vals if v > 0) / len(vals) * 100.0, 1)
    if rule in _BEARISH_HIT_RULES:
        return round(sum(1 for v in vals if v < 0) / len(vals) * 100.0, 1)
    return round(sum(1 for v in vals if v > 0) / len(vals) * 100.0, 1)


async def verify_hypothesis(
    symbol: str,
    *,
    rule: str = "momentum_positive",
    lookback_days: int = 240,
    horizons: tuple[int, ...] = (5, 10, 20),
    step: int = 5,
) -> HypothesisVerifyOut:
    """Walk history; when rule holds at t, measure forward returns (qfq only)."""
    if rule not in HYPOTHESIS_PRESETS:
        rule = "momentum_positive"
    name = resolve_name(symbol)
    meta = await get_bars_meta_for_symbol(symbol, days=lookback_days)
    notes = [
        "假设验证：仅用当日及以前的价格计算条件，再用之后的价格量收益（点-in-time）。",
        "非策略回测：未计成本、未做组合约束；样本有重叠。",
        "无历史估值/ROE 序列时，用回撤、大涨与波动×动量作为研究型代理假设。",
        HYPOTHESIS_PRESETS[rule],
    ]
    if meta.adjust != "qfq" or not meta.bars:
        return HypothesisVerifyOut(
            symbol=symbol,
            name=name,
            rule=rule,
            rule_label=HYPOTHESIS_PRESETS[rule],
            windows=[],
            sample_count=0,
            bars_adjust=meta.adjust,
            bars_source=meta.source,
            point_in_time=True,
            as_of=datetime.now(UTC).date().isoformat(),
            notes=notes + [meta.note or "前复权日线不可用"],
            partial=True,
            disclaimer=f"假设验证仅供参考。{DISCLAIMER}",
        )

    bars = meta.bars
    usable = [b for b in bars if b.get("close") is not None]
    window_vals: dict[int, list[float]] = {h: [] for h in horizons}
    hits = 0
    needs_vol = rule in ("calm_momentum_up", "high_vol_momentum_up")
    for idx in range(20, len(usable) - max(horizons) - 1, step):
        closes = [float(usable[j]["close"]) for j in range(idx + 1)]
        mom = _momentum_at(closes, idx, 20)
        vol = _vol_ann_pct_at(closes, idx, 20) if needs_vol else None
        if not _match(rule, mom, vol):
            continue
        hits += 1
        for h in horizons:
            ret = _forward_return_pct(usable, idx, h)
            if ret is not None:
                window_vals[h].append(ret)

    windows: list[HypothesisWindowOut] = []
    for h in horizons:
        vals = window_vals[h]
        windows.append(
            HypothesisWindowOut(
                days=h,
                sample_count=len(vals),
                avg_return_pct=round(mean(vals), 2) if vals else None,
                hit_rate_pct=_hit_rate(rule, vals),
            )
        )

    return HypothesisVerifyOut(
        symbol=symbol,
        name=name,
        rule=rule,
        rule_label=HYPOTHESIS_PRESETS[rule],
        windows=windows,
        sample_count=hits,
        bars_adjust=meta.adjust,
        bars_source=meta.source,
        point_in_time=True,
        as_of=datetime.now(UTC).date().isoformat(),
        notes=notes,
        partial=hits < 5,
        disclaimer=f"假设验证仅供参考。{DISCLAIMER}",
    )
