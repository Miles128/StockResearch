"""Numeric research factors computed from bars / valuation snapshots."""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from stockresearch.agents.research.budget import BASE_FACTOR_KEYS
from stockresearch.core.schemas import BarsProvenanceOut, NumericFactorOut
from stockresearch.data.providers.market import FinancialDataProvider
from stockresearch.services.daily_bars import get_bars_meta_for_symbol

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

logger = logging.getLogger(__name__)


def _std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    var = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(var)


def _want(keys: set[str] | None, key: str) -> bool:
    return keys is None or key in keys


def _bars_ok(closes: list[float]) -> bool:
    """至少 21 根且最近第 21 根为正（动量分母有效）。"""
    return len(closes) >= 21 and closes[-21] > 0


def _volatility_pct(closes: list[float]) -> float | None:
    """20 日年化波动率（%）。"""
    rets: list[float] = []
    for i in range(1, min(len(closes), 21)):
        prev = closes[-i - 1]
        cur = closes[-i]
        if prev > 0:
            rets.append(cur / prev - 1.0)
    vol = _std(rets)
    return round(vol * math.sqrt(252) * 100.0, 2) if vol is not None else None


def _percentile_display(value: float | None) -> float | None:
    """估值分位展示：≤1 视为小数分位转百分数，否则视为已是百分数原样保留。"""
    if value is None:
        return None
    return round(value * 100.0, 1) if value <= 1.0 else round(value, 1)


def factor_alignment_note(
    bias: str,
    factors: Iterable[NumericFactorOut],
) -> str | None:
    """One-line check: whether key factors lean with report bias."""
    by_key = {f.key: f for f in factors}
    mom = by_key.get("momentum_20d")
    pe = by_key.get("pe_percentile")
    signals: list[str] = []
    bullish_votes = 0
    bearish_votes = 0
    if mom is not None and mom.value is not None and not mom.partial:
        if mom.value > 0:
            bullish_votes += 1
            signals.append("动量为正")
        elif mom.value < 0:
            bearish_votes += 1
            signals.append("动量为负")
    if pe is not None and pe.percentile is not None and not pe.partial:
        # High PE percentile = expensive → lean bearish on valuation.
        if pe.percentile > 0.7:
            bearish_votes += 1
            signals.append("估值分位偏高")
        elif pe.percentile < 0.3:
            bullish_votes += 1
            signals.append("估值分位偏低")
    if not signals:
        return None
    if bias == "bullish":
        aligned = bullish_votes >= bearish_votes
    elif bias == "bearish":
        aligned = bearish_votes >= bullish_votes
    else:
        return "因子与结论：" + "、".join(signals) + "（结论中性，仅供对照）"
    tag = "大致同向" if aligned else "存在背离"
    return f"因子与结论{tag}：" + "、".join(signals)


async def compute_numeric_factors(
    symbol: str,
    *,
    factor_keys: tuple[str, ...] | list[str] | None = None,
) -> tuple[list[NumericFactorOut], BarsProvenanceOut]:
    """Compute momentum / volatility / valuation factors.

    Prefer qfq bars; when only unadjusted bars are available, still compute
    short-window factors and mark them partial.
    """
    wanted = set(factor_keys) if factor_keys is not None else set(BASE_FACTOR_KEYS)
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
    bars_ok = _bars_ok(closes)
    bar_note = meta.note
    if not bars_ok:
        bar_note = bar_note or "日线不足 21 根"
    elif non_qfq:
        bar_note = bar_note or "未复权日线：短窗口可用，变异/送转附近会偏"

    _append_bars_factors(
        factors, wanted, closes, bars_ok, non_qfq, meta.partial, provenance, bar_note
    )

    provider = FinancialDataProvider()
    valuation = await provider.get_valuation(symbol)
    pe_percentile = _append_valuation_factors(factors, wanted, valuation, as_of, provenance)

    await _append_financial_factors(factors, wanted, provider, symbol, as_of)
    await _append_peer_factors(
        factors, wanted, provider, symbol, pe_percentile, as_of, provenance, valuation
    )
    await _append_chips_factors(factors, wanted, symbol, as_of)

    return factors, provenance


def _append_bars_factors(
    factors: list[NumericFactorOut],
    wanted: set[str],
    closes: list[float],
    bars_ok: bool,
    non_qfq: bool,
    meta_partial: bool,
    provenance: BarsProvenanceOut,
    bar_note: str | None,
) -> None:
    """动量与波动因子（基于日线）。"""
    if _want(wanted, "momentum_20d"):
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
                partial=momentum is None or non_qfq or meta_partial,
                note=None
                if (momentum is not None and not non_qfq and not meta_partial)
                else bar_note,
                bars_source=provenance.source,
                bars_adjust=provenance.adjust,
            )
        )

    if _want(wanted, "volatility_20d"):
        vol_pct = _volatility_pct(closes) if bars_ok else None
        factors.append(
            NumericFactorOut(
                key="volatility_20d",
                label="20日年化波动",
                value=vol_pct,
                as_of=provenance.as_of,
                unit="%",
                partial=vol_pct is None or non_qfq or meta_partial,
                note=None
                if (vol_pct is not None and not non_qfq and not meta_partial)
                else (bar_note or "收益序列不足"),
                bars_source=provenance.source,
                bars_adjust=provenance.adjust,
            )
        )


def _append_valuation_factors(
    factors: list[NumericFactorOut],
    wanted: set[str],
    valuation: dict[str, object],
    as_of: str,
    provenance: BarsProvenanceOut,
) -> float | None:
    """PE/PB 历史分位因子；返回自身 PE 分位供同业比较。"""
    pe = valuation.get("pe_ttm")
    pe_pct = valuation.get("pe_percentile")
    pe_val = float(pe) if isinstance(pe, int | float) else None
    pe_percentile = float(pe_pct) if isinstance(pe_pct, int | float) else None
    pe_display = _percentile_display(pe_percentile)
    gaps = valuation.get("gaps")
    pe_note_bits = [str(g) for g in (gaps if isinstance(gaps, list) else []) if g]
    if pe_val is not None:
        pe_note_bits.append(f"PE={pe_val:.2f}")
    if _want(wanted, "pe_percentile"):
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

    if _want(wanted, "pb_percentile"):
        pb = valuation.get("pb")
        pb_pct = valuation.get("pb_percentile")
        pb_val = float(pb) if isinstance(pb, int | float) else None
        pb_percentile = float(pb_pct) if isinstance(pb_pct, int | float) else None
        pb_display = _percentile_display(pb_percentile) or (
            round(pb_val, 2) if pb_val is not None else None
        )
        gaps = valuation.get("gaps")
        pb_notes = [
            str(g) for g in (gaps if isinstance(gaps, list) else []) if g and "PB" in str(g)
        ]
        if pb_val is not None:
            pb_notes.append(f"PB={pb_val:.2f}")
        if pb_percentile is None:
            pb_notes.append("无 PB 历史分位" if pb_val is not None else "PB 不可用")
        factors.append(
            NumericFactorOut(
                key="pb_percentile",
                label="PB历史分位" if pb_percentile is not None else "PB",
                value=pb_display,
                percentile=pb_percentile,
                as_of=as_of,
                unit="%" if pb_percentile is not None else "",
                partial=pb_percentile is None,
                note="；".join(pb_notes) or None,
                bars_source=str(valuation.get("source") or ""),
                bars_adjust=None,
            )
        )

    return pe_percentile


async def _append_financial_factors(
    factors: list[NumericFactorOut],
    wanted: set[str],
    provider: FinancialDataProvider,
    symbol: str,
    as_of: str,
) -> None:
    """ROE/营收/净利同比因子。"""
    need_fin = any(_want(wanted, k) for k in ("roe_ttm", "revenue_yoy", "np_yoy"))
    financials: dict[str, object] = {}
    if need_fin:
        financials = await provider.get_financials(symbol)

    def _fin_pct(key: str, label: str, out_key: str) -> None:
        if not _want(wanted, out_key):
            return
        raw = financials.get(key)
        val = float(raw) if isinstance(raw, int | float) else None
        display = (
            round(val * 100.0, 1)
            if val is not None and abs(val) <= 5
            else (round(val, 1) if val is not None else None)
        )
        factors.append(
            NumericFactorOut(
                key=out_key,
                label=label,
                value=display,
                as_of=as_of,
                unit="%" if display is not None else "",
                partial=val is None or bool(financials.get("partial")),
                note=None if val is not None else f"{label}不可用",
                bars_source=str(financials.get("source") or ""),
                bars_adjust=None,
            )
        )

    _fin_pct("roe", "ROE(TTM)", "roe_ttm")
    _fin_pct("revenue_yoy", "营收同比", "revenue_yoy")
    _fin_pct("net_profit_yoy", "净利同比", "np_yoy")


async def _append_peer_factors(
    factors: list[NumericFactorOut],
    wanted: set[str],
    provider: FinancialDataProvider,
    symbol: str,
    own_pe_pct: float | None,
    as_of: str,
    provenance: BarsProvenanceOut,
    valuation: dict[str, object],
) -> None:
    """相对同业动量 / 相对同业 PE 分位因子。"""
    want_peer_mom = _want(wanted, "peer_rel_momentum_20d")
    want_peer_pe = _want(wanted, "peer_rel_pe_percentile")
    if not (want_peer_mom or want_peer_pe):
        return
    own_mom = next((f.value for f in factors if f.key == "momentum_20d"), None)
    peers = await provider.get_industry_peers(symbol)
    peer_moms, peer_pe_pcts = await _collect_peer_stats(
        provider, peers[:2], want_peer_mom, want_peer_pe
    )
    if want_peer_mom:
        if own_mom is not None and peer_moms:
            med = sorted(peer_moms)[len(peer_moms) // 2]
            rel = round(float(own_mom) - med, 2)
            factors.append(
                NumericFactorOut(
                    key="peer_rel_momentum_20d",
                    label="相对同业动量",
                    value=rel,
                    as_of=provenance.as_of,
                    unit="pp",
                    partial=False,
                    note=f"自身−同业中位（n={len(peer_moms)}）",
                    bars_source=provenance.source,
                    bars_adjust=provenance.adjust,
                )
            )
        else:
            factors.append(
                NumericFactorOut(
                    key="peer_rel_momentum_20d",
                    label="相对同业动量",
                    value=None,
                    as_of=as_of,
                    unit="pp",
                    partial=True,
                    note="同业动量不足",
                    bars_source=provenance.source,
                    bars_adjust=provenance.adjust,
                )
            )
    if want_peer_pe:
        if own_pe_pct is not None and peer_pe_pcts:
            med_pe = sorted(peer_pe_pcts)[len(peer_pe_pcts) // 2]
            rel_pe = round((float(own_pe_pct) - med_pe) * 100.0, 1)
            factors.append(
                NumericFactorOut(
                    key="peer_rel_pe_percentile",
                    label="相对同业PE分位",
                    value=rel_pe,
                    as_of=as_of,
                    unit="pp",
                    partial=False,
                    note=f"自身分位−同业中位（n={len(peer_pe_pcts)}）",
                    bars_source=str(valuation.get("source") or ""),
                    bars_adjust=None,
                )
            )
        else:
            factors.append(
                NumericFactorOut(
                    key="peer_rel_pe_percentile",
                    label="相对同业PE分位",
                    value=None,
                    as_of=as_of,
                    unit="pp",
                    partial=True,
                    note="同业PE分位不足",
                    bars_source=str(valuation.get("source") or ""),
                    bars_adjust=None,
                )
            )


async def _collect_peer_stats(
    provider: FinancialDataProvider,
    peers: Sequence[object],
    want_peer_mom: bool,
    want_peer_pe: bool,
) -> tuple[list[float], list[float]]:
    """收集同业动量与 PE 分位（最多前 2 只同业，逐个容错）。"""
    peer_moms: list[float] = []
    peer_pe_pcts: list[float] = []
    for peer in peers:
        if not isinstance(peer, dict):
            continue
        psym = _peer_symbol(peer)
        if psym is None:
            continue
        if want_peer_mom:
            mom = await _peer_momentum(psym)
            if mom is not None:
                peer_moms.append(mom)
        if want_peer_pe:
            pct = await _peer_pe_percentile(provider, psym, peer.get("pe_percentile"))
            if pct is not None:
                peer_pe_pcts.append(pct)
    return peer_moms, peer_pe_pcts


def _peer_symbol(peer: object) -> str | None:
    """提取同业代码；非字典或非 6 位代码返回 None。"""
    if not isinstance(peer, dict):
        return None
    psym = str(peer.get("symbol") or "")
    return psym if len(psym) == 6 else None


async def _peer_momentum(psym: str) -> float | None:
    """同业 20 日动量；qfq 日线不足 21 根时返回 None。"""
    try:
        pmeta = await get_bars_meta_for_symbol(psym, days=60)
        pcloses = [float(b["close"]) for b in pmeta.bars if b.get("close") is not None]
        if len(pcloses) >= 21 and pcloses[-21] > 0 and pmeta.adjust == "qfq":
            return (pcloses[-1] / pcloses[-21] - 1.0) * 100.0
    except Exception:
        logger.debug("peer momentum skipped for %s", psym, exc_info=True)
    return None


async def _peer_pe_percentile(
    provider: FinancialDataProvider,
    psym: str,
    raw_pct: object,
) -> float | None:
    """同业 PE 分位：优先用同行列表自带值，缺失时逐个拉取。"""
    if isinstance(raw_pct, int | float):
        return float(raw_pct)
    try:
        pval = await provider.get_valuation(psym)
        pp = pval.get("pe_percentile")
        if isinstance(pp, int | float):
            return float(pp)
    except Exception:
        logger.debug("peer PE percentile skipped for %s", psym, exc_info=True)
    return None


async def _append_chips_factors(
    factors: list[NumericFactorOut],
    wanted: set[str],
    symbol: str,
    as_of: str,
) -> None:
    """主力净流入与北向持股占比因子。"""
    if not (_want(wanted, "main_net_inflow_5d") or _want(wanted, "northbound_hold_pct")):
        return
    from stockresearch.data.providers.market import ChipsDataProvider

    chips = ChipsDataProvider()
    if _want(wanted, "main_net_inflow_5d"):
        fund = await chips.get_fund_flow(symbol)
        main_5d = fund.get("main_net_inflow_5d", fund.get("main_net_inflow"))
        main_val = float(main_5d) if isinstance(main_5d, int | float) else None
        fund_empty = (
            fund.get("available") is False or fund.get("partial") is True or main_val is None
        )
        factors.append(
            NumericFactorOut(
                key="main_net_inflow_5d",
                label="主力净流入(5日)",
                value=None if fund_empty else round(main_val, 2),  # type: ignore[arg-type]
                as_of=as_of,
                unit="",
                partial=fund_empty,
                note=None if not fund_empty else "主力资金流向不可用",
                bars_source=str(fund.get("source") or ""),
                bars_adjust=None,
            )
        )
    if _want(wanted, "northbound_hold_pct"):
        north = await chips.get_northbound_flow(symbol)
        hold_pct = north.get("hold_pct")
        north_val = float(hold_pct) if isinstance(hold_pct, int | float) else None
        north_empty = (
            north.get("available") is False
            or north.get("signal") == "暂无数据"
            or north.get("partial") is True
            or north_val is None
        )
        factors.append(
            NumericFactorOut(
                key="northbound_hold_pct",
                label="北向持股占比",
                value=None if north_empty else round(north_val, 2),  # type: ignore[arg-type]
                as_of=as_of,
                unit="%",
                partial=north_empty,
                note=None if not north_empty else "北向资金不可用",
                bars_source=str(north.get("source") or ""),
                bars_adjust=None,
            )
        )
