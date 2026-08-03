"""Same-symbol research report timeline (replay + optional post-hoc)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from stockresearch.core.constants import DISCLAIMER
from stockresearch.core.schemas import (
    ReportPostHocHorizon,
    ResearchTimelineEntryOut,
    ResearchTimelineFactorSnap,
    ResearchTimelineOut,
)
from stockresearch.db.models import ResearchReport
from stockresearch.services.daily_bars import get_bars_meta_for_symbol
from stockresearch.services.signal_backtest import _forward_return_pct, _start_idx_for_day
from stockresearch.utils.symbols import resolve_name

_SNAP_KEYS: tuple[str, ...] = (
    "momentum_20d",
    "volatility_20d",
    "pe_percentile",
    "roe_ttm",
    "revenue_yoy",
    "main_net_inflow_5d",
)


def snapshot_factors(payload: dict[str, object]) -> list[ResearchTimelineFactorSnap]:
    """Pull a small factor strip from a saved report JSON."""
    raw = payload.get("factors")
    if not isinstance(raw, list):
        return []
    by_key: dict[str, dict[str, object]] = {}
    for item in raw:
        if isinstance(item, dict) and item.get("key"):
            by_key[str(item["key"])] = item
    out: list[ResearchTimelineFactorSnap] = []
    for key in _SNAP_KEYS:
        item = by_key.get(key)
        if item is None:
            continue
        value = item.get("value")
        percentile = item.get("percentile")
        out.append(
            ResearchTimelineFactorSnap(
                key=key,
                label=str(item.get("label") or key),
                value=float(value) if isinstance(value, int | float) else None,
                percentile=float(percentile) if isinstance(percentile, int | float) else None,
                partial=bool(item.get("partial")),
            )
        )
    return out


def annotate_deltas(entries_oldest_first: list[ResearchTimelineEntryOut]) -> None:
    """Mutate entries: bias_changed / score_delta vs previous (older) report."""
    prev: ResearchTimelineEntryOut | None = None
    for entry in entries_oldest_first:
        if prev is None:
            entry.bias_changed = False
            entry.score_delta = None
        else:
            entry.bias_changed = entry.bias != prev.bias
            entry.score_delta = round(entry.composite_score - prev.composite_score, 2)
        prev = entry


def entry_from_payload(
    *,
    report_id: int,
    created_at: datetime,
    payload: dict[str, object],
) -> ResearchTimelineEntryOut:
    summary = str(payload.get("summary") or payload.get("brief_summary") or "")
    return ResearchTimelineEntryOut(
        report_id=report_id,
        created_at=created_at,
        bias=str(payload.get("bias") or "neutral"),
        composite_score=float(payload.get("composite_score") or 0),
        analysis_depth=str(payload.get("analysis_depth") or "standard"),
        summary=summary[:160],
        factor_alignment_note=(
            str(payload["factor_alignment_note"]) if payload.get("factor_alignment_note") else None
        ),
        factors=snapshot_factors(payload),
        thesis_claim=_thesis_claim(payload),
    )


def _thesis_claim(payload: dict[str, object]) -> str | None:
    """Copy thesis.claim from report_json deep_analysis if present."""
    deep = payload.get("deep_analysis")
    if not isinstance(deep, dict):
        return None
    thesis = deep.get("thesis")
    if not isinstance(thesis, dict):
        return None
    claim = thesis.get("claim")
    if isinstance(claim, str) and claim.strip():
        return claim.strip()
    return None


def _post_hoc_for_day(
    bars: list[dict[str, float | str]] | None,
    report_day,
    *,
    horizons: tuple[int, ...],
    bars_source: str,
    note_if_missing: str,
) -> list[ReportPostHocHorizon]:
    if not bars:
        return [
            ReportPostHocHorizon(
                days=h,
                return_pct=None,
                partial=True,
                note=note_if_missing,
            )
            for h in horizons
        ]
    start_idx = _start_idx_for_day(bars, report_day)
    if start_idx < 0:
        return [
            ReportPostHocHorizon(days=h, return_pct=None, partial=True, note="尚无后续交易日")
            for h in horizons
        ]
    out: list[ReportPostHocHorizon] = []
    for h in horizons:
        ret = _forward_return_pct(bars, start_idx, h)
        out.append(
            ReportPostHocHorizon(
                days=h,
                return_pct=round(ret, 2) if ret is not None else None,
                partial=ret is None,
                note=None if ret is not None else "窗口未满",
                bars_adjust="qfq",
                bars_source=bars_source,
            )
        )
    return out


async def compute_research_timeline(
    db: Session,
    user_id: int,
    symbol: str,
    *,
    include_post_hoc: bool = True,
    limit: int = 20,
    horizons: tuple[int, ...] = (5, 10, 20),
) -> ResearchTimelineOut:
    """Chronological research replay for one symbol (newest listed first)."""
    name = resolve_name(symbol)
    rows = (
        db.query(ResearchReport)
        .filter(ResearchReport.user_id == user_id, ResearchReport.symbol == symbol)
        .order_by(ResearchReport.created_at.asc())
        .limit(limit)
        .all()
    )
    notes = [
        "研究复盘：同一标的多份报告的结论与因子快照对照；非策略回测。",
        "点-in-time：事后收益仅用报告创建日及之后的前复权收盘价。",
    ]
    if not rows:
        return ResearchTimelineOut(
            symbol=symbol,
            name=name,
            entries=[],
            notes=notes + ["暂无该标的历史研报；请先在对话中生成报告。"],
            disclaimer=DISCLAIMER,
        )

    oldest_first: list[ResearchTimelineEntryOut] = []
    for row in rows:
        payload = row.report_json if isinstance(row.report_json, dict) else {}
        oldest_first.append(
            entry_from_payload(report_id=row.id, created_at=row.created_at, payload=payload)
        )
    annotate_deltas(oldest_first)

    if include_post_hoc:
        meta = await get_bars_meta_for_symbol(symbol, days=240)
        bars = meta.bars if meta.adjust == "qfq" and meta.bars else None
        miss = meta.note or "前复权日线不可用"
        for entry, row in zip(oldest_first, rows, strict=True):
            entry.post_hoc = _post_hoc_for_day(
                bars,
                row.created_at.date(),
                horizons=horizons,
                bars_source=meta.source,
                note_if_missing=miss,
            )
    else:
        notes.append("未请求事后核对（include_post_hoc=false）。")

    # API returns newest first for reading habit.
    newest_first = list(reversed(oldest_first))
    return ResearchTimelineOut(
        symbol=symbol,
        name=name,
        entries=newest_first,
        notes=notes,
        disclaimer=DISCLAIMER,
    )
