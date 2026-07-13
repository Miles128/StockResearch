"""组合风险度量计算模块

提供夏普比率、索提诺比率、最大回撤、波动率、集中度、VaR 等风险指标的计算。
仅依赖标准库，不使用 numpy / pandas。
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any

# ── 常量 ──────────────────────────────────────────────
RISK_FREE_RATE: float = 0.02  # 无风险利率（年化 2%）

# 行业默认年化波动率（当无法从日收益计算时使用）
SECTOR_DEFAULT_VOLATILITY: dict[str, float] = {
    "tech": 0.25,
    "technology": 0.25,
    "科技": 0.25,
    "finance": 0.20,
    "financial": 0.20,
    "金融": 0.20,
    "银行": 0.18,
    "保险": 0.22,
    "证券": 0.28,
    "新能源": 0.35,
    "光伏": 0.38,
    "电池": 0.36,
    "医药": 0.28,
    "生物医药": 0.32,
    "消费": 0.22,
    "白酒": 0.24,
    "食品饮料": 0.22,
    "地产": 0.30,
    "房地产": 0.30,
    "周期": 0.32,
    "有色": 0.35,
    "钢铁": 0.30,
    "煤炭": 0.32,
    "军工": 0.34,
    "电子": 0.30,
    "半导体": 0.38,
    "传媒": 0.32,
    "互联网": 0.30,
}

DEFAULT_ANNUAL_VOLATILITY: float = 0.30  # 未知行业的默认年化波动率
SINGLE_NAME_CONCENTRATION_LIMIT: float = 0.30
SECTOR_CONCENTRATION_LIMIT: float = 0.40

# 情景压力预设（相对现价冲击，小数）
STRESS_PRESETS: list[dict[str, object]] = [
    {"id": "sector_down_10", "name": "最大行业 -10%", "kind": "max_sector", "shock_pct": -0.10},
    {"id": "book_down_15", "name": "全组合 -15%", "kind": "all", "shock_pct": -0.15},
    {"id": "crash_2015_style", "name": "急跌情景 -20%", "kind": "all", "shock_pct": -0.20},
]

# VaR 正态分位数
Z_SCORES: dict[float, float] = {
    0.90: 1.282,
    0.95: 1.645,
    0.975: 1.960,
    0.99: 2.326,
}

TRADING_DAYS_PER_YEAR: int = 252
_ASSUMED_HOLDING_DAYS: int = 120  # 无买入日期时默认持有 120 个交易日


def _parse_holding_days(buy_date: str | None) -> float:
    """从买入日期字符串计算持有交易日天数。"""
    if not buy_date:
        return _ASSUMED_HOLDING_DAYS
    try:
        from datetime import date

        bd = date.fromisoformat(buy_date)
        today = date.today()
        calendar_days = (today - bd).days
        # 粗略转换为交易日：日历天数 * 252/365
        trading_days = calendar_days * TRADING_DAYS_PER_YEAR / 365
        return max(trading_days, 1)
    except (ValueError, TypeError):
        return _ASSUMED_HOLDING_DAYS


# ── 数据模型 ──────────────────────────────────────────
@dataclass
class HoldingQuote:
    """持仓行情数据"""

    symbol: str
    name: str
    cost_price: float  # 成本价
    current_price: float  # 当前价
    quantity: float  # 持仓数量
    sector: str  # 所属行业
    daily_returns: list[float] = field(default_factory=list)  # 近期日收益率（小数形式）
    buy_date: str | None = None  # 买入日期 (YYYY-MM-DD)


@dataclass
class PortfolioMetrics:
    """组合风险指标"""

    sharpe_ratio: float  # 夏普比率
    sortino_ratio: float  # 索提诺比率
    max_drawdown: float  # 最大回撤（小数，如 -0.15 表示 -15%）
    volatility: float  # 年化波动率（小数）
    concentration_ratio: float  # 行业集中度（0-1，最大行业权重）
    concentration_sector: str | None  # 最大权重行业名称
    individual_drawdowns: list[dict[str, Any]]  # 个股回撤列表
    calmar_ratio: float = 0.0  # Calmar 比率（年化收益/最大回撤）
    information_ratio: float = 0.0  # 信息比率（超额收益/跟踪误差）
    max_loss_1d: float = 0.0  # 单日最大可能损失（元）
    max_loss_1d_pct: float = 0.0  # 单日最大可能损失占比
    expected_loss: float = 0.0  # 期望损失 EL（元）
    expected_loss_pct: float = 0.0  # 期望损失占比
    sector_weights: list[dict[str, Any]] = field(default_factory=list)
    top_holding_weight: float = 0.0
    top_holding_symbol: str | None = None
    top_holding_name: str | None = None


@dataclass
class VaRResult:
    """在险价值（VaR）计算结果"""

    confidence_level: float  # 置信水平（如 0.95、0.99）
    time_horizon_days: int  # 时间跨度（天）
    var_value: float  # 绝对 VaR（元）
    var_pct: float  # VaR 占组合市值百分比（小数）
    method: str  # 计算方法
    holdings_var: list[dict[str, Any]]  # 个股 VaR 贡献
    cvar_value: float = 0.0  # CVaR / Expected Shortfall 绝对值（元）
    cvar_pct: float = 0.0  # CVaR 占组合市值百分比（小数）


# ── 工具函数 ──────────────────────────────────────────
def _sector_volatility(sector: str) -> float:
    """根据行业名称获取默认年化波动率"""
    sector_lower = sector.lower().strip()
    return SECTOR_DEFAULT_VOLATILITY.get(sector_lower, DEFAULT_ANNUAL_VOLATILITY)


def _holding_value(h: HoldingQuote) -> float:
    """持仓市值"""
    return h.current_price * h.quantity


def _portfolio_value(holdings: list[HoldingQuote]) -> float:
    """组合总市值"""
    return sum(_holding_value(h) for h in holdings)


def _holding_weight(h: HoldingQuote, total_value: float) -> float:
    """个股权重"""
    if total_value <= 0:
        return 0.0
    return _holding_value(h) / total_value


def _estimate_annual_volatility(h: HoldingQuote) -> float:
    """估算年化波动率：优先从日收益计算，否则使用行业默认值"""
    if len(h.daily_returns) >= 2:
        daily_vol = statistics.stdev(h.daily_returns)
        return daily_vol * math.sqrt(TRADING_DAYS_PER_YEAR)
    return _sector_volatility(h.sector)


def _z_score(confidence_level: float) -> float:
    """获取正态分布分位数，支持插值"""
    if confidence_level in Z_SCORES:
        return Z_SCORES[confidence_level]
    # 线性插值
    levels = sorted(Z_SCORES.keys())
    if confidence_level <= levels[0]:
        return Z_SCORES[levels[0]]
    if confidence_level >= levels[-1]:
        return Z_SCORES[levels[-1]]
    for i in range(len(levels) - 1):
        if levels[i] <= confidence_level <= levels[i + 1]:
            ratio = (confidence_level - levels[i]) / (levels[i + 1] - levels[i])
            return Z_SCORES[levels[i]] + ratio * (
                Z_SCORES[levels[i + 1]] - Z_SCORES[levels[i]]
            )
    return Z_SCORES[0.95]


# ── 主计算函数 ────────────────────────────────────────
def calculate_portfolio_metrics(
    holding_quotes: list[HoldingQuote],
) -> PortfolioMetrics:
    """计算组合风险指标

    Args:
        holding_quotes: 持仓行情列表

    Returns:
        PortfolioMetrics 包含夏普比率、索提诺比率、最大回撤、波动率、集中度等
    """

    # ── 空组合 ──
    if not holding_quotes:
        return PortfolioMetrics(
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            max_drawdown=0.0,
            volatility=0.0,
            concentration_ratio=0.0,
            concentration_sector=None,
            individual_drawdowns=[],
        )

    total_value = _portfolio_value(holding_quotes)

    # ── 个股回撤 ──
    individual_drawdowns: list[dict[str, Any]] = []
    for h in holding_quotes:
        if h.cost_price > 0:
            dd = (h.current_price - h.cost_price) / h.cost_price
        else:
            dd = 0.0
        individual_drawdowns.append(
            {
                "symbol": h.symbol,
                "name": h.name,
                "cost_price": h.cost_price,
                "current_price": h.current_price,
                "drawdown_pct": dd,
            }
        )

    # ── 最大回撤（基于成本价） ──
    max_drawdown = 0.0
    if total_value > 0:
        weighted_dd = 0.0
        for h in holding_quotes:
            w = _holding_weight(h, total_value)
            if h.cost_price > 0:
                dd = (h.current_price - h.cost_price) / h.cost_price
            else:
                dd = 0.0
            weighted_dd += w * dd
        max_drawdown = weighted_dd

    # ── 组合日收益率序列（加权） ──
    # 找到最长日收益序列长度，不足的用 0 填充
    max_len = max((len(h.daily_returns) for h in holding_quotes), default=0)
    portfolio_daily_returns: list[float] = []

    if max_len >= 2 and total_value > 0:
        # 对齐日收益：假设各持仓日收益同期，不足的尾部补 0
        aligned: list[list[float]] = []
        for h in holding_quotes:
            rets = h.daily_returns[:]
            # 前端对齐：如果长度不足，在前面补 0
            if len(rets) < max_len:
                rets = [0.0] * (max_len - len(rets)) + rets
            aligned.append(rets)

        weights = [_holding_weight(h, total_value) for h in holding_quotes]

        for day_idx in range(max_len):
            day_ret = sum(
                weights[i] * aligned[i][day_idx] for i in range(len(holding_quotes))
            )
            portfolio_daily_returns.append(day_ret)

    # ── 年化波动率 ──
    if len(portfolio_daily_returns) >= 2:
        daily_vol = statistics.stdev(portfolio_daily_returns)
        volatility = daily_vol * math.sqrt(TRADING_DAYS_PER_YEAR)
    else:
        # 无日收益数据，用加权行业默认波动率估算
        if total_value > 0:
            volatility = sum(
                _holding_weight(h, total_value) * _estimate_annual_volatility(h)
                for h in holding_quotes
            )
        else:
            volatility = DEFAULT_ANNUAL_VOLATILITY

    # ── 组合收益率（年化） ──
    # 基于成本价到现价的涨幅，按实际持有天数年化
    portfolio_return = 0.0
    if total_value > 0:
        for h in holding_quotes:
            w = _holding_weight(h, total_value)
            if h.cost_price > 0:
                total_ret = (h.current_price - h.cost_price) / h.cost_price
            else:
                total_ret = 0.0
            portfolio_return += w * total_ret

    # 年化：用实际持有天数
    # 计算加权平均持有天数
    avg_holding_days = _ASSUMED_HOLDING_DAYS  # 默认 120 个交易日
    if total_value > 0:
        total_weighted_days = 0.0
        for h in holding_quotes:
            w = _holding_weight(h, total_value)
            days = _parse_holding_days(h.buy_date)
            total_weighted_days += w * days
        avg_holding_days = max(total_weighted_days, 1)

    annualized_return = (
        (1 + portfolio_return) ** (TRADING_DAYS_PER_YEAR / avg_holding_days) - 1
        if portfolio_return > -1
        else portfolio_return
    )

    # ── 夏普比率 ──
    if volatility > 0:
        sharpe_ratio = (annualized_return - RISK_FREE_RATE) / volatility
    else:
        sharpe_ratio = 0.0

    # ── 索提诺比率 ──
    downside_returns: list[float] = []
    if len(portfolio_daily_returns) >= 2:
        # 下偏离差：只考虑低于目标收益（无风险利率日化）的收益
        daily_rf = RISK_FREE_RATE / TRADING_DAYS_PER_YEAR
        for r in portfolio_daily_returns:
            if r < daily_rf:
                downside_returns.append((r - daily_rf) ** 2)

        if downside_returns:
            downside_vol = math.sqrt(
                sum(downside_returns) / len(portfolio_daily_returns)
            ) * math.sqrt(TRADING_DAYS_PER_YEAR)
        else:
            downside_vol = 0.0
    else:
        # 无日收益时，假设下行波动率为总波动率的 70%（经验近似）
        downside_vol = volatility * 0.7

    if downside_vol > 0:
        sortino_ratio = (annualized_return - RISK_FREE_RATE) / downside_vol
    else:
        sortino_ratio = 0.0 if portfolio_return <= RISK_FREE_RATE else float("inf")

    # ── 行业集中度 ──
    sector_weight_map: dict[str, float] = {}
    if total_value > 0:
        for h in holding_quotes:
            sector_weight_map[h.sector] = (
                sector_weight_map.get(h.sector, 0.0) + _holding_weight(h, total_value)
            )

    concentration_ratio = max(sector_weight_map.values()) if sector_weight_map else 0.0
    concentration_sector = (
        max(sector_weight_map, key=sector_weight_map.get) if sector_weight_map else None
    )
    sector_weights = [
        {
            "sector": sector,
            "weight": round(weight, 4),
            "value": round(weight * total_value, 2),
        }
        for sector, weight in sorted(
            sector_weight_map.items(), key=lambda item: item[1], reverse=True
        )
    ]

    top_holding_weight = 0.0
    top_holding_symbol: str | None = None
    top_holding_name: str | None = None
    if total_value > 0:
        top = max(holding_quotes, key=lambda h: _holding_value(h))
        top_holding_weight = _holding_weight(top, total_value)
        top_holding_symbol = top.symbol
        top_holding_name = top.name

    # ── Calmar 比率（年化收益 / |最大回撤|） ──
    abs_dd = abs(max_drawdown)
    if abs_dd > 0.001:
        calmar_ratio = annualized_return / abs_dd
    else:
        calmar_ratio = 0.0

    # ── 信息比率（超额收益 / 跟踪误差） ──
    # 跟踪误差 = 组合波动率（简化假设基准为无风险利率）
    if volatility > 0:
        information_ratio = (annualized_return - RISK_FREE_RATE) / volatility
    else:
        information_ratio = 0.0

    # ── 单日最大可能损失（3σ 原则） ──
    daily_vol = volatility / math.sqrt(TRADING_DAYS_PER_YEAR)
    max_loss_1d_pct = 3 * daily_vol  # 3 倍日标准差
    max_loss_1d = total_value * max_loss_1d_pct

    # ── 期望损失 (Expected Loss = PD × LGD × EAD) ──
    # PD: 违约概率，用日波动率 × 2 近似（极端下跌概率）
    # LGD: 违约损失率，假设 60%（股票流动性折价）
    # EAD: 风险敞口 = 组合市值
    pd_approx = daily_vol * 2  # 近似违约概率
    lgd = 0.60  # 违约损失率
    expected_loss_pct = pd_approx * lgd
    expected_loss = total_value * expected_loss_pct

    return PortfolioMetrics(
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        max_drawdown=max_drawdown,
        volatility=volatility,
        concentration_ratio=concentration_ratio,
        concentration_sector=concentration_sector,
        individual_drawdowns=individual_drawdowns,
        calmar_ratio=calmar_ratio,
        information_ratio=information_ratio,
        max_loss_1d=max_loss_1d,
        max_loss_1d_pct=max_loss_1d_pct,
        expected_loss=expected_loss,
        expected_loss_pct=expected_loss_pct,
        sector_weights=sector_weights,
        top_holding_weight=top_holding_weight,
        top_holding_symbol=top_holding_symbol,
        top_holding_name=top_holding_name,
    )


def apply_price_shocks(
    holding_quotes: list[HoldingQuote],
    shocks: dict[str, float],
    *,
    by: str = "symbol",
) -> dict[str, float]:
    """Apply relative price shocks and return portfolio PnL.

    Args:
        holding_quotes: current holdings with prices
        shocks: map of symbol or sector -> shock fraction (e.g. -0.1)
        by: "symbol" or "sector"
    """
    total_value = _portfolio_value(holding_quotes)
    if total_value <= 0:
        return {"portfolio_value": 0.0, "shocked_value": 0.0, "pnl": 0.0, "pnl_pct": 0.0}

    shocked_value = 0.0
    for h in holding_quotes:
        key = h.symbol if by == "symbol" else h.sector
        shock = shocks.get(key, shocks.get("*", 0.0))
        shocked_price = h.current_price * (1.0 + shock)
        shocked_value += shocked_price * h.quantity
    pnl = shocked_value - total_value
    return {
        "portfolio_value": total_value,
        "shocked_value": shocked_value,
        "pnl": pnl,
        "pnl_pct": pnl / total_value,
    }


def run_stress_presets(holding_quotes: list[HoldingQuote]) -> list[dict[str, Any]]:
    """Run built-in research stress presets (no broker / no Greeks)."""
    if not holding_quotes:
        return []
    results: list[dict[str, Any]] = []
    pm = calculate_portfolio_metrics(holding_quotes)
    max_sector = pm.concentration_sector
    for preset in STRESS_PRESETS:
        kind = str(preset["kind"])
        shock_pct = float(preset["shock_pct"])  # type: ignore[arg-type]
        if kind == "max_sector" and max_sector:
            shock_result = apply_price_shocks(
                holding_quotes, {max_sector: shock_pct}, by="sector"
            )
            label = f"{preset['name']}（{max_sector}）"
        elif kind == "all":
            shock_result = apply_price_shocks(holding_quotes, {"*": shock_pct}, by="symbol")
            label = str(preset["name"])
        else:
            continue
        results.append(
            {
                "id": preset["id"],
                "name": label,
                "pnl": round(shock_result["pnl"], 2),
                "pnl_pct": round(shock_result["pnl_pct"], 4),
                "shocked_value": round(shock_result["shocked_value"], 2),
            }
        )
    return results


def closes_to_daily_returns(closes: list[float]) -> list[float]:
    """Convert close series to simple daily returns (decimal)."""
    if len(closes) < 2:
        return []
    out: list[float] = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        if prev <= 0:
            continue
        out.append((closes[i] - prev) / prev)
    return out


def calculate_var(
    holding_quotes: list[HoldingQuote],
    confidence_level: float = 0.95,
    time_horizon_days: int = 1,
) -> VaRResult:
    """计算组合在险价值（VaR）——参数法

    公式：VaR = 组合市值 × z_score × 年化波动率 × √时间跨度(天) / √252

    Args:
        holding_quotes: 持仓行情列表
        confidence_level: 置信水平，默认 0.95
        time_horizon_days: 时间跨度（天），默认 1

    Returns:
        VaRResult 包含绝对 VaR、百分比 VaR 及个股贡献
    """

    # ── 空组合 ──
    if not holding_quotes:
        return VaRResult(
            confidence_level=confidence_level,
            time_horizon_days=time_horizon_days,
            var_value=0.0,
            var_pct=0.0,
            method="parametric",
            holdings_var=[],
        )

    total_value = _portfolio_value(holding_quotes)
    z = _z_score(confidence_level)

    # ── 组合加权波动率 ──
    if total_value > 0:
        portfolio_vol = sum(
            _holding_weight(h, total_value) * _estimate_annual_volatility(h)
            for h in holding_quotes
        )
    else:
        portfolio_vol = DEFAULT_ANNUAL_VOLATILITY

    # ── VaR 计算 ──
    # 将年化波动率转换为 time_horizon 天的波动率
    period_vol = portfolio_vol * math.sqrt(time_horizon_days / TRADING_DAYS_PER_YEAR)

    var_pct = z * period_vol
    var_value = total_value * var_pct

    # ── 个股 VaR 贡献 ──
    holdings_var: list[dict[str, Any]] = []
    for h in holding_quotes:
        h_value = _holding_value(h)
        h_vol = _estimate_annual_volatility(h)
        h_period_vol = h_vol * math.sqrt(time_horizon_days / TRADING_DAYS_PER_YEAR)
        h_var_pct = z * h_period_vol
        h_var_value = h_value * h_var_pct
        h_weight = _holding_weight(h, total_value) if total_value > 0 else 0.0

        holdings_var.append(
            {
                "symbol": h.symbol,
                "name": h.name,
                "var_value": h_var_value,
                "weight": h_weight,
            }
        )

    # ── CVaR (Conditional VaR / Expected Shortfall) ──
    # 参数法：CVaR = VaR × φ(z) / (1-α)
    # 其中 φ(z) 是标准正态分布的 PDF，α 是置信水平
    # φ(z) = exp(-z²/2) / √(2π)
    phi_z = math.exp(-(z**2) / 2) / math.sqrt(2 * math.pi)
    cvar_multiplier = phi_z / (1 - confidence_level)
    cvar_pct = period_vol * cvar_multiplier
    cvar_value = total_value * cvar_pct

    return VaRResult(
        confidence_level=confidence_level,
        time_horizon_days=time_horizon_days,
        var_value=var_value,
        var_pct=var_pct,
        method="parametric",
        holdings_var=holdings_var,
        cvar_value=cvar_value,
        cvar_pct=cvar_pct,
    )
