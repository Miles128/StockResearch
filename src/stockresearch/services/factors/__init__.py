"""Numeric research factors computed from bars / valuation snapshots."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Iterable

from stockresearch.agents.research.budget import BASE_FACTOR_KEYS
from stockresearch.core.schemas import BarsProvenanceOut, NumericFactorOut
from stockresearch.data.providers.market import FinancialDataProvider
from stockresearch.services.daily_bars import get_bars_meta_for_symbol


def _std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    var = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(var)


def _want(keys: set[str] | None, key: str) -> bool:
    return keys is None or key in keys


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
    bars_ok = len(closes) >= 21 and closes[-21] > 0
    bar_note = meta.note
    if not bars_ok:
        bar_note = bar_note or "日线不足 21 根"
    elif non_qfq:
        bar_note = bar_note or "未复权日线：短窗口可用，变异/送转附近会偏"

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
                partial=momentum is None or non_qfq or meta.partial,
                note=None if (momentum is not None and not non_qfq and not meta.partial) else bar_note,
                bars_source=provenance.source,
                bars_adjust=provenance.adjust,
            )
        )

    if _want(wanted, "volatility_20d"):
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

    provider = FinancialDataProvider()
    valuation = await provider.get_valuation(symbol)
    pe = valuation.get("pe_ttm")
    pe_pct = valuation.get("pe_percentile")
    pe_val = float(pe) if isinstance(pe, (int, float)) else None
    pe_percentile = float(pe_pct) if isinstance(pe_pct, (int, float)) else None
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
        pb_val = float(pb) if isinstance(pb, (int, float)) else None
        pb_percentile = float(pb_pct) if isinstance(pb_pct, (int, float)) else None
        pb_display: float | None = None
        if pb_percentile is not None:
            pb_display = (
                round(pb_percentile * 100.0, 1)
                if pb_percentile <= 1.0
                else round(pb_percentile, 1)
            )
        elif pb_val is not None:
            pb_display = round(pb_val, 2)
        pb_notes = [str(g) for g in (valuation.get("gaps") or []) if g and "PB" in str(g)]
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

    need_fin = any(_want(wanted, k) for k in ("roe_ttm", "revenue_yoy", "np_yoy"))
    financials: dict[str, object] = {}
    if need_fin:
        financials = await provider.get_financials(symbol)

    def _fin_pct(key: str, label: str, out_key: str) -> None:
        if not _want(wanted, out_key):
            return
        raw = financials.get(key)
        val = float(raw) if isinstance(raw, (int, float)) else None
        display = round(val * 100.0, 1) if val is not None and abs(val) <= 5 else (
            round(val, 1) if val is not None else None
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

    want_peer_mom = _want(wanted, "peer_rel_momentum_20d")
    want_peer_pe = _want(wanted, "peer_rel_pe_percentile")
    if want_peer_mom or want_peer_pe:
        own_mom = next((f.value for f in factors if f.key == "momentum_20d"), None)
        own_pe_pct = pe_percentile
        peers = await provider.get_industry_peers(symbol)
        peer_moms: list[float] = []
        peer_pe_pcts: list[float] = []
        for peer in peers[:2]:
            if not isinstance(peer, dict):
                continue
            psym = str(peer.get("symbol") or "")
            if len(psym) != 6:
                continue
            if want_peer_mom:
                try:
                    pmeta = await get_bars_meta_for_symbol(psym, days=60)
                    pcloses = [
                        float(b["close"]) for b in pmeta.bars if b.get("close") is not None
                    ]
                    if len(pcloses) >= 21 and pcloses[-21] > 0 and pmeta.adjust == "qfq":
                        peer_moms.append((pcloses[-1] / pcloses[-21] - 1.0) * 100.0)
                except Exception:
                    pass
            if want_peer_pe:
                raw_pct = peer.get("pe_percentile")
                if isinstance(raw_pct, (int, float)):
                    peer_pe_pcts.append(float(raw_pct))
                else:
                    try:
                        pval = await provider.get_valuation(psym)
                        pp = pval.get("pe_percentile")
                        if isinstance(pp, (int, float)):
                            peer_pe_pcts.append(float(pp))
                    except Exception:
                        pass
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

    if _want(wanted, "main_net_inflow_5d") or _want(wanted, "northbound_hold_pct"):
        from stockresearch.data.providers.market import ChipsDataProvider

        chips = ChipsDataProvider()
        if _want(wanted, "main_net_inflow_5d"):
            fund = await chips.get_fund_flow(symbol)
            main_5d = fund.get("main_net_inflow_5d", fund.get("main_net_inflow"))
            main_val = float(main_5d) if isinstance(main_5d, (int, float)) else None
            fund_empty = (
                fund.get("available") is False
                or fund.get("partial") is True
                or main_val is None
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
            north_val = float(hold_pct) if isinstance(hold_pct, (int, float)) else None
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

    return factors, provenance
