"""简单组合优化 — 最小波动 / 风险平价 / 均衡（夏普加权）三预设。

面向普通投资者（不交易衍生品/固收）的教育参考，不构成投资建议：
- 仅 long-only，单票权重上限 40%；
- 输入为持仓 ∪ 自选（≤8 个），用 qfq 日线对齐后的日收益估计年化协方差；
- 无 numpy/scipy 依赖，纯 Python 实现（坐标下降 / 反波动率 / 夏普加权）；
- 输出白话解释 + 免责声明，对照「当前权重 vs 建议权重」。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from statistics import mean

from stockresearch.core.constants import DISCLAIMER
from stockresearch.core.schemas import (
    PortfolioOptimizeOut,
    PortfolioOptimizeRow,
)
from stockresearch.services.daily_bars import get_bars_meta_for_symbol
from stockresearch.utils.symbols import resolve_name

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 250
TRADING_DAYS_YEAR = 252.0
MAX_WEIGHT = 0.40  # 单票上限
MAX_ITER = 200
TOL = 1e-8


def _aligned_returns(
    series_by_symbol: dict[str, list[tuple[str, float]]],
) -> dict[str, list[float]]:
    """按日期对齐各标的的日收益（仅保留所有标的共有的日期）。"""
    dates: set[str] = set()
    for series in series_by_symbol.values():
        dates.update(day for day, _ in series)
    keep = [d for d in dates if all(any(sd == d for sd, _ in s) for s in series_by_symbol.values())]
    if len(keep) < 2:
        return {}
    keep_sorted = sorted(keep)
    out: dict[str, list[float]] = {}
    for sym, series in series_by_symbol.items():
        closes = {day: close for day, close in series}
        seq = [closes[d] for d in keep_sorted]
        out[sym] = [b / a - 1.0 for a, b in zip(seq, seq[1:])]
    return out


def _cov_matrix(returns: dict[str, list[float]]) -> list[list[float]] | None:
    symbols = list(returns)
    n = len(symbols)
    if n < 2:
        return None
    means = {s: mean(rs) for s, rs in returns.items()}
    rows: list[list[float]] = []
    for i in range(n):
        row: list[float] = []
        ri = returns[symbols[i]]
        for j in range(n):
            rj = returns[symbols[j]]
            cov = sum((a - means[symbols[i]]) * (b - means[symbols[j]]) for a, b in zip(ri, rj))
            cov /= len(ri) - 1
            cov *= TRADING_DAYS_YEAR
            row.append(cov)
        rows.append(row)
    return rows


def _min_vol_weights(cov: list[list[float]]) -> list[float]:
    """Long-only 最小波动：坐标下降（每轮在 [0, MAX_WEIGHT] 内优化单票权重）。"""
    n = len(cov)
    weights = [1.0 / n] * n
    for _ in range(MAX_ITER):
        max_delta = 0.0
        for i in range(n):
            # 固定其它权重，w_i 的最优值：-(Σ_{j≠i} w_j σ_ij) / σ_ii，clamp 到 [0, MAX_WEIGHT]
            others = sum(cov[i][j] * weights[j] for j in range(n) if j != i)
            var_i = cov[i][i]
            if var_i <= 0:
                continue
            new_w = max(0.0, min(MAX_WEIGHT, -others / var_i))
            max_delta = max(max_delta, abs(new_w - weights[i]))
            weights[i] = new_w
        total = sum(weights)
        if total <= 0:
            weights = [1.0 / n] * n
            break
        weights = [w / total for w in weights]
        if max_delta < TOL:
            break
    total = sum(weights)
    return [w / total for w in weights] if total > 0 else weights


def _risk_parity_weights(vols: list[float]) -> list[float]:
    """朴素风险平价：权重 ∝ 1/σ（忽略相关性的一阶近似），单票上限 40%。"""
    n = len(vols)
    inv = [1.0 / v if v > 0 else 0.0 for v in vols]
    total = sum(inv)
    if total <= 0:
        return [1.0 / n] * n
    weights = [x / total for x in inv]
    return _cap_weights(weights)


def _cap_weights(weights: list[float]) -> list[float]:
    """水填充投影：long-only、sum=1、单票 ≤ MAX_WEIGHT。

    迭代把超上限的票压到上限，把剩余权重按比例分给未达上限的票；
    若未达上限的票全为零权重，则平分剩余（等价于把这些票等权补足）。
    """
    n = len(weights)
    w = [max(0.0, x) for x in weights]
    total = sum(w)
    if total <= 0:
        return [1.0 / n] * n
    w = [x / total for x in w]
    for _ in range(50):
        over = [i for i in range(n) if w[i] > MAX_WEIGHT + 1e-12]
        if not over:
            return w
        for i in over:
            w[i] = MAX_WEIGHT
        rem = 1.0 - sum(w)
        under = [i for i in range(n) if i not in over and w[i] < MAX_WEIGHT]
        if not under or rem <= 1e-12:
            break
        sub = sum(w[i] for i in under)
        if sub <= 1e-12:
            for i in under:
                w[i] = rem / len(under)
            continue
        scale = (sub + rem) / sub
        for i in under:
            w[i] *= scale
    return w


def _balanced_weights(
    returns: dict[str, list[float]], vols: list[float]
) -> tuple[list[float], float]:
    """均衡（夏普加权近似）：w ∝ max(μ, 0) / σ²，负收益标的归零。

    返回 (weights, cash_weight)。正收益票受单票 40% 上限约束，
    超出部分记为「现金权重」（不硬塞给负收益票）。
    """
    symbols = list(returns)
    scores: list[float] = []
    for i, sym in enumerate(symbols):
        mu = mean(returns[sym]) * TRADING_DAYS_YEAR
        vol = vols[i]
        if vol <= 0 or mu <= 0:
            scores.append(0.0)
        else:
            scores.append(mu / (vol * vol))
    total = sum(scores)
    if total <= 0:
        # 全部历史收益为负/无正夏普 → 退化为风险平价
        return _risk_parity_weights(vols), 0.0
    weights = [s / total for s in scores]
    weights = [min(w, MAX_WEIGHT) for w in weights]
    cash = max(0.0, 1.0 - sum(weights))
    return weights, round(cash, 4)


def _portfolio_vol(weights: list[float], cov: list[list[float]]) -> float:
    var = sum(
        weights[i] * weights[j] * cov[i][j]
        for i in range(len(weights))
        for j in range(len(weights))
    )
    return max(0.0, var) ** 0.5


def _portfolio_return(weights: list[float], returns: dict[str, list[float]]) -> float:
    symbols = list(returns)
    return sum(w * mean(returns[s]) for w, s in zip(weights, symbols)) * TRADING_DAYS_YEAR


def _equal_weights(n: int) -> list[float]:
    return [1.0 / n] * n


async def _load_series(symbols: list[str]) -> tuple[dict[str, list[tuple[str, float]]], list[str]]:
    series: dict[str, list[tuple[str, float]]] = {}
    skipped: list[str] = []
    for sym in symbols:
        meta = await get_bars_meta_for_symbol(sym, days=LOOKBACK_DAYS)
        if meta.adjust != "qfq" or len(meta.bars) < 2:
            skipped.append(sym)
            continue
        seq = [
            (str(b.get("date", ""))[:10], float(b.get("close") or 0))
            for b in meta.bars
            if float(b.get("close") or 0) > 0
        ]
        if len(seq) >= 2:
            series[sym] = seq
        else:
            skipped.append(sym)
    return series, skipped


async def optimize_portfolio(
    universe: dict[str, float],
    *,
    method: str = "min_vol",
) -> PortfolioOptimizeOut:
    """universe: symbol → 当前权重（持仓市值占比；自选=0）。"""
    symbols = list(universe)[:8]
    series, skipped = await _load_series(symbols)
    notes: list[str] = []
    if skipped:
        notes.append(f"日线不足或非 qfq，已跳过：{', '.join(skipped)}")
    symbols = [s for s in symbols if s in series]
    if len(symbols) < 2:
        return PortfolioOptimizeOut(
            method=method,
            rows=[],
            current_vol=None,
            current_return=None,
            optimal_vol=None,
            optimal_return=None,
            explanation="优化至少需要 2 个有 qfq 日线的标的。",
            partial=True,
            notes=notes,
            disclaimer=f"组合优化为教育参考，不构成投资建议。{DISCLAIMER}",
            as_of=datetime.now(UTC).date().isoformat(),
        )

    returns = _aligned_returns(series)
    if len(returns) < 2 or any(len(rs) < 3 for rs in returns.values()):
        return PortfolioOptimizeOut(
            method=method,
            rows=[],
            current_vol=None,
            current_return=None,
            optimal_vol=None,
            optimal_return=None,
            explanation="共有的交易日不足，暂无法估计协方差。",
            partial=True,
            notes=notes,
            disclaimer=f"组合优化为教育参考，不构成投资建议。{DISCLAIMER}",
            as_of=datetime.now(UTC).date().isoformat(),
        )

    cov = _cov_matrix(returns)
    if cov is None:
        return PortfolioOptimizeOut(
            method=method,
            rows=[],
            current_vol=None,
            current_return=None,
            optimal_vol=None,
            optimal_return=None,
            explanation="标的不足，无法优化。",
            partial=True,
            notes=notes,
            disclaimer=f"组合优化为教育参考，不构成投资建议。{DISCLAIMER}",
            as_of=datetime.now(UTC).date().isoformat(),
        )

    vols = [(cov[i][i] ** 0.5) for i in range(len(cov))]

    cash_weight = 0.0
    if method == "risk_parity":
        optimal = _risk_parity_weights(vols)
        method_label = "风险平价"
    elif method == "balanced":
        optimal, cash_weight = _balanced_weights(returns, vols)
        method_label = "均衡"
    else:
        optimal = _min_vol_weights(cov)
        method_label = "最小波动"

    current = [universe.get(s, 0.0) for s in symbols]
    c_total = sum(current)
    if c_total > 0:
        current = [w / c_total for w in current]
    else:
        current = _equal_weights(len(symbols))

    current_vol = _portfolio_vol(current, cov)
    optimal_vol = _portfolio_vol(optimal, cov)
    current_ret = _portfolio_return(current, returns)
    optimal_ret = _portfolio_return(optimal, returns)

    rows = [
        PortfolioOptimizeRow(
            symbol=s,
            name=resolve_name(s),
            current_weight=round(current[i], 4),
            optimal_weight=round(optimal[i], 4),
        )
        for i, s in enumerate(symbols)
    ]
    if method == "min_vol":
        explanation = (
            f"按历史波动构造的最稳组合（{method_label}）："
            f"预期年化波动从 {current_vol * 100:.0f}% 降到 {optimal_vol * 100:.0f}%"
            f"（历史估计）。它把更多仓位让给历史上波动小、与其他持仓联动低的标的。"
            f"代价是放弃了部分上行弹性——稳，不等于赚更多。"
        )
    elif method == "risk_parity":
        explanation = (
            f"{method_label}思路：让每只股票贡献差不多的波动，而不是按金额均分。"
            f"结果波动小的票拿更多仓位。历史估计的年化波动从 {current_vol * 100:.0f}% "
            f"变为 {optimal_vol * 100:.0f}%。它不追求最低波动，而是让组合不'偏科'。"
        )
    else:
        explanation = (
            f"{method_label}思路：历史上单位风险收益（夏普）更高的票拿更多仓位，"
            f"历史收益为负的票归零。历史估计年化收益从 {current_ret * 100:.1f}% "
            f"变为 {optimal_ret * 100:.1f}%，波动从 {current_vol * 100:.0f}% "
            f"变为 {optimal_vol * 100:.0f}%。"
        )
        if cash_weight > 0:
            explanation += (
                f"正收益票受单票上限约束后，剩余 {cash_weight * 100:.0f}% 记为现金仓位"
                f"（不硬塞给历史收益为负的票）。"
            )
        explanation += "注意：历史收益不代表未来，这只是一个分配思路。"
    explanation += (
        f" 以上均基于约 {LOOKBACK_DAYS} 个交易日的历史数据，未计入交易成本，不构成买入/卖出建议。"
    )

    return PortfolioOptimizeOut(
        method=method,
        method_label=method_label,
        rows=rows,
        cash_weight=cash_weight,
        current_vol=round(current_vol * 100.0, 1),
        current_return=round(current_ret * 100.0, 1),
        optimal_vol=round(optimal_vol * 100.0, 1),
        optimal_return=round(optimal_ret * 100.0, 1),
        explanation=explanation,
        partial=bool(skipped),
        notes=notes,
        disclaimer=f"组合优化为教育参考，不构成投资建议。{DISCLAIMER}",
        as_of=datetime.now(UTC).date().isoformat(),
    )
