"""Sector target vs actual holding weights (display only — not an optimizer)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from stockresearch.core.constants import DISCLAIMER
from stockresearch.core.schemas import AllocationDeviationOut, AllocationDeviationRow

if TYPE_CHECKING:
    from stockresearch.db.models import Holding


def sector_weights(holdings: list[Holding]) -> dict[str, float]:
    """Market-value proxy: cost_price × quantity by sector (sums to 1)."""
    totals: dict[str, float] = {}
    for h in holdings:
        sector = (h.sector or "未知").strip() or "未知"
        totals[sector] = totals.get(sector, 0.0) + float(h.cost_price) * int(h.quantity)
    grand = sum(totals.values())
    if grand <= 0:
        return {}
    return {k: round(v / grand, 4) for k, v in sorted(totals.items(), key=lambda kv: -kv[1])}


def normalize_targets(targets: dict[str, float]) -> dict[str, float]:
    cleaned = {
        str(k).strip() or "未知": float(v)
        for k, v in targets.items()
        if isinstance(v, int | float) and float(v) > 0
    }
    total = sum(cleaned.values())
    if total <= 0:
        return {}
    # Allow either 0–1 fractions or 0–100 percents.
    if total > 1.5:
        cleaned = {k: v / 100.0 for k, v in cleaned.items()}
        total = sum(cleaned.values())
    return {k: round(v / total, 4) for k, v in cleaned.items()}


def build_allocation_deviation(
    holdings: list[Holding],
    targets: dict[str, float] | None = None,
) -> AllocationDeviationOut:
    actual = sector_weights(holdings)
    norm_targets = normalize_targets(targets or {})
    sectors = sorted(set(actual) | set(norm_targets))
    rows: list[AllocationDeviationRow] = []
    for sector in sectors:
        a = actual.get(sector, 0.0)
        t = norm_targets.get(sector, 0.0)
        rows.append(
            AllocationDeviationRow(
                sector=sector,
                actual=a,
                target=t,
                delta=round(a - t, 4),
            )
        )
    rows.sort(key=lambda r: abs(r.delta), reverse=True)
    notes = [
        "配置偏差：仅展示目标权重与当前持仓（成本市值代理）的差异。",
        "不做组合优化，也不生成再平衡买卖指令。",
    ]
    if not actual:
        notes.append("暂无持仓，无法计算实际权重。")
    if not norm_targets:
        notes.append("未设置目标权重时只展示实际板块分布。")
    return AllocationDeviationOut(
        actual=actual,
        targets=norm_targets,
        rows=rows,
        notes=notes,
        disclaimer=DISCLAIMER,
    )
