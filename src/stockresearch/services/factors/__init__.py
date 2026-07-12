"""Numeric research factors computed from bars / valuation snapshots."""

from __future__ import annotations

import math
from datetime import UTC, datetime

from stockresearch.core.schemas import NumericFactorOut
from stockresearch.data.providers.market import FinancialDataProvider
from stockresearch.services.daily_bars import get_bars_for_symbol


def _std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    var = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(var)


async def compute_numeric_factors(symbol: str) -> list[NumericFactorOut]:
    """Compute at least momentum / volatility / valuation factors."""
    as_of = datetime.now(UTC).date().isoformat()
    factors: list[NumericFactorOut] = []

    bars = await get_bars_for_symbol(symbol, days=60)
    closes = [float(b["close"]) for b in bars if b.get("close") is not None]

    momentum: float | None = None
    momentum_partial = True
    if len(closes) >= 21 and closes[-21] > 0:
        momentum = round((closes[-1] / closes[-21] - 1.0) * 100.0, 2)
        momentum_partial = False
    factors.append(
        NumericFactorOut(
            key="momentum_20d",
            label="20日动量",
            value=momentum,
            as_of=as_of,
            unit="%",
            partial=momentum_partial,
            note=None if not momentum_partial else "日线不足 21 根",
        )
    )

    rets: list[float] = []
    for i in range(1, min(len(closes), 21)):
        prev = closes[-i - 1]
        cur = closes[-i]
        if prev > 0:
            rets.append(cur / prev - 1.0)
    vol = _std(rets)
    vol_pct = round(vol * math.sqrt(252) * 100.0, 2) if vol is not None else None
    factors.append(
        NumericFactorOut(
            key="volatility_20d",
            label="20日年化波动",
            value=vol_pct,
            as_of=as_of,
            unit="%",
            partial=vol_pct is None,
            note=None if vol_pct is not None else "收益序列不足",
        )
    )

    valuation = await FinancialDataProvider().get_valuation(symbol)
    pe = valuation.get("pe_ttm")
    pe_pct = valuation.get("pe_percentile")
    pe_val = float(pe) if isinstance(pe, (int, float)) else None
    pe_percentile = float(pe_pct) if isinstance(pe_pct, (int, float)) else None
    factors.append(
        NumericFactorOut(
            key="pe_percentile",
            label="PE历史分位",
            value=pe_val,
            percentile=pe_percentile,
            as_of=as_of,
            unit="PE",
            partial=bool(valuation.get("partial")) or pe_percentile is None,
            note="；".join(str(g) for g in (valuation.get("gaps") or []) if g) or None,
        )
    )

    return factors
