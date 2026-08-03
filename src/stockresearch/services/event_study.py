"""Event-window forward returns after announcements (research verification)."""

from __future__ import annotations

from datetime import UTC, datetime
from statistics import mean

from stockresearch.core.constants import DISCLAIMER
from stockresearch.core.schemas import EventStudyEventOut, EventStudyOut, EventStudyWindowOut
from stockresearch.data.providers.announcements import AnnouncementProvider
from stockresearch.services.daily_bars import get_bars_meta_for_symbol
from stockresearch.services.signal_backtest import _forward_return_pct, _parse_date
from stockresearch.utils.symbols import resolve_name

_EARNINGS_KEYS = ("年报", "半年报", "季报", "业绩", "预告", "快报")
_RISK_KEYS = ("减持", "增持", "回购", "问询", "立案", "重组", "停牌")


def _event_kind(title: str, ann_type: str) -> str:
    blob = f"{title}{ann_type}"
    if any(k in blob for k in _EARNINGS_KEYS):
        return "earnings"
    if any(k in blob for k in _RISK_KEYS):
        return "risk"
    return "other"


async def compute_event_study(
    symbol: str,
    *,
    event_filter: str = "earnings",
    lookback_days: int = 365,
    horizons: tuple[int, ...] = (1, 5, 20),
    limit: int = 12,
) -> EventStudyOut:
    """Average forward returns after filtered announcement dates (qfq only)."""
    name = resolve_name(symbol)
    result = await AnnouncementProvider().fetch_announcements_result(
        symbol, name, days=lookback_days, limit=max(limit * 3, 20)
    )
    items = list(result.items)
    kind_counts: dict[str, int] = {"earnings": 0, "risk": 0, "other": 0}
    for it in items:
        kind = _event_kind(it.title, it.announcement_type)
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    if event_filter != "all":
        items = [it for it in items if _event_kind(it.title, it.announcement_type) == event_filter]
    items = items[:limit]

    meta = await get_bars_meta_for_symbol(symbol, days=max(lookback_days + 40, 120))
    bars = meta.bars if meta.adjust == "qfq" else []
    events: list[EventStudyEventOut] = []
    window_vals: dict[int, list[float]] = {h: [] for h in horizons}

    for it in items:
        event_day = it.announcement_time.date() if hasattr(it.announcement_time, "date") else None
        if event_day is None:
            raw = str(it.announcement_time)
            parsed = _parse_date(raw)
            event_day = parsed.date() if parsed else None
        if event_day is None or not bars:
            events.append(
                EventStudyEventOut(
                    title=it.title,
                    event_kind=_event_kind(it.title, it.announcement_type),
                    event_date=str(it.announcement_time)[:10],
                    returns={str(h): None for h in horizons},
                    partial=True,
                    note="事件日无法对齐或无 qfq 日线",
                )
            )
            continue

        start_idx = -1
        for i, bar in enumerate(bars):
            bar_dt = _parse_date(str(bar.get("date", "")))
            if bar_dt and bar_dt.date() >= event_day:
                start_idx = i
                break
        rets: dict[str, float | None] = {}
        partial = False
        note = None
        for h in horizons:
            ret = _forward_return_pct(bars, start_idx, h) if start_idx >= 0 else None
            rets[str(h)] = round(ret, 2) if ret is not None else None
            if ret is None:
                partial = True
                note = "窗口未满或事件日无交易"
            else:
                window_vals[h].append(ret)
        events.append(
            EventStudyEventOut(
                title=it.title,
                event_kind=_event_kind(it.title, it.announcement_type),
                event_date=event_day.isoformat(),
                returns=rets,
                partial=partial,
                note=note,
                url=it.url,
            )
        )

    windows: list[EventStudyWindowOut] = []
    for h in horizons:
        vals = window_vals[h]
        windows.append(
            EventStudyWindowOut(
                days=h,
                sample_count=len(vals),
                avg_return_pct=round(mean(vals), 2) if vals else None,
                positive_rate_pct=(
                    round(sum(1 for v in vals if v > 0) / len(vals) * 100.0, 1) if vals else None
                ),
            )
        )

    notes = [
        "事件研究：以公告日为 t0，仅用前复权日线前向收益；非策略回测。",
        "点-in-time：事件日取公告时间，不使用事后才可知的财务修订。",
        (
            "公告类型分组（过滤前）："
            f"业绩 {kind_counts.get('earnings', 0)} · "
            f"风险 {kind_counts.get('risk', 0)} · "
            f"其他 {kind_counts.get('other', 0)}"
        ),
    ]
    if meta.adjust != "qfq":
        notes.append(meta.note or "日线非 qfq，事件收益未计算")
    if result.source_failed:
        notes.append("公告源暂时失败")

    return EventStudyOut(
        symbol=symbol,
        name=name,
        event_filter=event_filter,
        events=events,
        windows=windows,
        kind_counts=kind_counts,
        bars_adjust=meta.adjust,
        bars_source=meta.source,
        notes=notes,
        disclaimer=f"事件研究仅供验证参考。{DISCLAIMER}",
        as_of=datetime.now(UTC).date().isoformat(),
        point_in_time=True,
    )


async def compute_event_study_batch(
    symbols: list[str],
    *,
    event_filter: str = "earnings",
) -> list[EventStudyOut]:
    """Run event study for up to 8 symbols (watchlist batch entry)."""
    out: list[EventStudyOut] = []
    for symbol in symbols[:8]:
        sym = symbol.strip()
        if len(sym) != 6 or not sym.isdigit():
            continue
        out.append(await compute_event_study(sym, event_filter=event_filter))
    return out
