"""Phase 10 L2 Pricing bridge — PE/earnings decomposition of recent return.

Pure helpers (`_price_change_pct`, `_earnings_growth`, `_contribs`) are
network-free and unit-tested directly. `compute_pricing_bridge` wires them to
the daily-bar warehouse (`get_bars_meta_for_symbol`, qfq preferred)
and the financial provider (`FinancialDataProvider.get_valuation` for current
PE TTM).

Policy: **honest partial over fake DCF**.

- `price_change_pct` is computed from qfq closes over a ~60 trading-day
  window (falls back to 20d when 60d bars are unavailable, stamped in
  `window_label`).
- `pe_end` is the current PE(TTM) from the provider. `pe_start` (60d ago) is
  **not** exposed by the provider's public valuation surface, so it is left
  `None` with a gap rather than reverse-engineered from price/earnings
  (which would be circular and speculative).
- `multiple_contrib_pct` / `earnings_contrib_pct` only run when `pe_start`,
  `pe_end`, and earnings growth `g` are all available; otherwise the missing
  piece is recorded as a gap and the result is marked partial.
- `implied_growth_pct` is **always** `None` with a gap — a Gordon-style
  reverse DCF from a single PE endpoint is too strong an assumption for an
  MVP point-in-time bridge; we prefer to leave the gap than fabricate it.
- No target price is produced (out of scope).
"""

from __future__ import annotations

import logging

from stockresearch.core.schemas import NumericFactorOut, PricingBridgeOut
from stockresearch.data.providers.market import FinancialDataProvider
from stockresearch.services.daily_bars import get_bars_meta_for_symbol

logger = logging.getLogger(__name__)

_WINDOW = 60
_FALLBACK_WINDOW = 20
_IDENTITY_TOLERANCE_PP = 15.0


def _price_change_pct(
    closes: list[float],
    *,
    window: int = _WINDOW,
    fallback: int = _FALLBACK_WINDOW,
) -> tuple[float | None, str, str | None]:
    """Return (pct, window_label, gap) from qfq closes.

    Prefers `window` trading days; falls back to `fallback` when fewer bars
    are available. Returns (None, label, gap) when even the fallback is too
    short or the start close is non-positive.
    """
    n = len(closes)
    if n >= window + 1 and closes[-(window + 1)] > 0:
        pct = round((closes[-1] / closes[-(window + 1)] - 1.0) * 100.0, 2)
        return pct, f"{window}d qfq", None
    if n >= fallback + 1 and closes[-(fallback + 1)] > 0:
        pct = round((closes[-1] / closes[-(fallback + 1)] - 1.0) * 100.0, 2)
        return (
            pct,
            f"{fallback}d qfq（{window}d 日线不足）",
            f"{window}d 日线不足 {n} 根，回退 {fallback}d",
        )
    return None, "", f"日线不足 {fallback}d，price_change_pct 不可算"


def _earnings_growth(
    factors: list[NumericFactorOut],
) -> tuple[float | None, str | None, str | None]:
    """Pick earnings growth `g` (already in %) from the factors list.

    Prefers `np_yoy` (net profit YoY); falls back to `revenue_yoy` and
    records a gap noting the approximation. Returns (g, source_key, gap).
    """
    by_key = {f.key: f for f in factors}
    npf = by_key.get("np_yoy")
    if npf is not None and npf.value is not None and not npf.partial:
        return float(npf.value), "np_yoy", None
    revf = by_key.get("revenue_yoy")
    if revf is not None and revf.value is not None and not revf.partial:
        return (
            float(revf.value),
            "revenue_yoy",
            "np_yoy 不可用，earnings_contrib 用 revenue_yoy 近似",
        )
    return None, None, "np_yoy / revenue_yoy 均不可用，earnings 增长不可算"


def _contribs(
    *,
    pe_start: float | None,
    pe_end: float | None,
    g: float | None,
    price_change_pct: float | None,
) -> tuple[float | None, float | None, bool, list[str]]:
    """Decompose recent return into multiple + earnings contributions.

    Only runs the full identity when `pe_start`, `pe_end`, and `g` are all
    available; otherwise the missing piece is a gap and the result is
    partial. Identity residual > 15pp also marks partial.
    """
    gaps: list[str] = []
    multiple: float | None = None
    earnings: float | None = None
    partial = False

    if g is not None:
        earnings = round(float(g), 2)
    else:
        gaps.append("earnings 增长不可用")

    if pe_start is not None and pe_end is not None and pe_start > 0:
        multiple = round((pe_end / pe_start - 1.0) * 100.0, 2)
        if price_change_pct is not None and earnings is not None:
            residual = abs(price_change_pct - (multiple + earnings))
            if residual > _IDENTITY_TOLERANCE_PP:
                partial = True
                gaps.append(
                    f"价格分解残差 {residual:.1f}pp > {_IDENTITY_TOLERANCE_PP:.0f}pp"
                )
    else:
        partial = True
        if pe_start is None:
            gaps.append("pe_start 不可用（provider 未暴露 60d 前 PE 序列）")
        if pe_end is None:
            gaps.append("pe_end 不可用（PE TTM 不可用）")
        elif pe_start is None and pe_end is not None:
            # pe_end known but pe_start missing -> multiple cannot be computed.
            pass

    return multiple, earnings, partial, gaps


async def compute_pricing_bridge(
    symbol: str,
    factors: list[NumericFactorOut],
) -> PricingBridgeOut:
    """Build a point-in-time pricing bridge for `symbol`.

    Reads PE/earnings from the same `factors` list produced by
    `compute_numeric_factors` (keys: `pe_percentile`, `np_yoy`,
    `revenue_yoy`); fetches current PE(TTM) from the financial provider as
    `pe_end`. `pe_start` (60d ago) is not historically exposed -> gap.

    See module docstring for the honest-partial policy.
    """
    factor_keys_used = [f.key for f in factors]
    gaps: list[str] = []
    partial = False

    # 1) price_change_pct from qfq bars (~60d).
    meta = await get_bars_meta_for_symbol(symbol, days=_WINDOW)
    closes = [
        float(b["close"]) for b in meta.bars if b.get("close") is not None
    ]
    price_change_pct, window_label, price_gap = _price_change_pct(closes)
    if window_label:
        window_label = (
            f"{window_label}（未复权）" if meta.adjust != "qfq" else window_label
        )
    else:
        window_label = f"{_WINDOW}d qfq"
    if price_gap:
        gaps.append(price_gap)
        partial = True
    if meta.adjust != "qfq" and closes:
        gaps.append("日线非 qfq，price_change_pct 在分红/送转窗口会偏")
        partial = True

    # 2) earnings growth from factors list.
    g, g_source, g_gap = _earnings_growth(factors)
    if g_gap:
        gaps.append(g_gap)
        if g is None:
            partial = True

    # 3) pe_end from provider; pe_start not historically exposed.
    provider = FinancialDataProvider()
    pe_end: float | None = None
    try:
        valuation = await provider.get_valuation(symbol)
    except Exception:
        logger.warning("valuation fetch failed for %s", symbol, exc_info=True)
        valuation = {}
    raw_pe = valuation.get("pe_ttm")
    if isinstance(raw_pe, (int, float)) and float(raw_pe) > 0:
        pe_end = round(float(raw_pe), 2)
    pe_start: float | None = None  # never fabricated

    # 4) contrib math (only when pe_start/pe_end/g all available).
    multiple, earnings, contrib_partial, contrib_gaps = _contribs(
        pe_start=pe_start,
        pe_end=pe_end,
        g=g,
        price_change_pct=price_change_pct,
    )
    if contrib_partial:
        partial = True
    gaps.extend(contrib_gaps)

    # 5) implied growth: skip — reverse DCF too speculative for MVP.
    implied_growth_pct: float | None = None
    gaps.append("implied_growth 跳过：reverse DCF 假设过强，留空（honest partial）")

    return PricingBridgeOut(
        window_label=window_label,
        price_change_pct=price_change_pct,
        earnings_contrib_pct=earnings,
        multiple_contrib_pct=multiple,
        pe_start=pe_start,
        pe_end=pe_end,
        implied_growth_pct=implied_growth_pct,
        factor_keys_used=factor_keys_used,
        partial=partial,
        gaps=gaps,
        point_in_time=True,
    )
