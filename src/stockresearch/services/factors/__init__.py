"""Numeric research factors computed from bars / valuation snapshots."""

from __future__ import annotations

import math
from datetime import UTC, datetime

from stockresearch.core.schemas import BarsProvenanceOut, NumericFactorOut
from stockresearch.data.providers.market import FinancialDataProvider
from stockresearch.services.daily_bars import get_bars_meta_for_symbol


def _std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    var = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(var)


async def compute_numeric_factors(
    symbol: str,
) -> tuple[list[NumericFactorOut], BarsProvenanceOut]:
    """Compute momentum / volatility / valuation factors.

    Prefer qfq bars; when only unadjusted bars are available, still compute
    short-window factors and mark them partial.
    """
    as_of = datetime.now(UTC).date().isoformat()
    factors: list[NumericFactorOut] = []

    meta = await get_bars_meta_for_symbol(symbol, days=60)
    non_qfq = meta.adjust != "qfq"
    provenance = BarsProvenanceOut(
        source=meta.source,
        adjust=meta.adjust,
        as_of=meta.as_of or as_of,
        partial=meta.partial or non_qfq or not meta.bars,
        note=meta.note,
    )
    closes = [float(b["close"]) for b in meta.bars if b.get("close") is not None]
    bars_ok = len(closes) >= 21 and closes[-21] > 0
    bar_note = meta.note
    if not bars_ok:
        bar_note = bar_note or "日线不足 21 根"
    elif non_qfq:
        bar_note = bar_note or "未复权日线：短窗口可用，分红/送转附近会偏"

    momentum: float | None = None
    if bars_ok:
        momentum = round((closes[-1] / closes[-21] - 1.0) * 100.0, 2)
    factors.append(
        NumericFactorOut(
            key="momentum_20d",
            label="20日动量",
            value=momentum,
            as_of=provenance.as_of,
            unit="%",
            partial=momentum is None or non_qfq or meta.partial,
            note=None if (momentum is not None and not non_qfq and not meta.partial) else bar_note,
            bars_source=provenance.source,
            bars_adjust=provenance.adjust,
        )
    )

    rets: list[float] = []
    if bars_ok:
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
            as_of=provenance.as_of,
            unit="%",
            partial=vol_pct is None or non_qfq or meta.partial,
            note=None if (vol_pct is not None and not non_qfq and not meta.partial) else (
                bar_note or "收益序列不足"
            ),
            bars_source=provenance.source,
            bars_adjust=provenance.adjust,
        )
    )

    valuation = await FinancialDataProvider().get_valuation(symbol)
    pe = valuation.get("pe_ttm")
    pe_pct = valuation.get("pe_percentile")
    pe_val = float(pe) if isinstance(pe, (int, float)) else None
    pe_percentile = float(pe_pct) if isinstance(pe_pct, (int, float)) else None
    # Store raw 0–1 percentile; display value as percent for the trust strip.
    pe_display: float | None = None
    if pe_percentile is not None:
        pe_display = (
            round(pe_percentile * 100.0, 1)
            if pe_percentile <= 1.0
            else round(pe_percentile, 1)
        )
    pe_note_bits = [str(g) for g in (valuation.get("gaps") or []) if g]
    if pe_val is not None:
        pe_note_bits.append(f"PE={pe_val:.2f}")
    factors.append(
        NumericFactorOut(
            key="pe_percentile",
            label="PE历史分位",
            value=pe_display,
            percentile=pe_percentile,
            as_of=as_of,
            unit="%",
            partial=bool(valuation.get("partial")) or pe_percentile is None,
            note="；".join(pe_note_bits) or None,
            bars_source=provenance.source,
            bars_adjust=provenance.adjust,
        )
    )

    return factors, provenance
