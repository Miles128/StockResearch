"""Watchlist/holdings research radar — zero-LLM rule signals for Action Center."""

from __future__ import annotations

from sqlalchemy.orm import Session

from stockresearch.core.schemas import ActionSignal
from stockresearch.db.models import Holding, ResearchReport, WatchlistItem

_MAX_RADAR = 3
_MAX_SYMBOLS = 12


def _bias_of(payload: dict[str, object]) -> str:
    return str(payload.get("bias") or "neutral")


def _score_of(payload: dict[str, object]) -> float:
    try:
        return float(payload.get("composite_score") or 0)
    except (TypeError, ValueError):
        return 0.0


def _alignment_of(payload: dict[str, object]) -> str | None:
    note = payload.get("factor_alignment_note")
    return str(note) if note else None


def collect_research_radar_signals(
    db: Session,
    user_id: int,
    holdings: list[Holding] | None = None,
) -> list[ActionSignal]:
    """Emit research-replay signals (bias flip / factor divergence). Not trade signals."""
    universe: dict[str, str] = {}
    for h in holdings or []:
        universe[h.symbol] = h.name
    watch = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_id == user_id)
        .limit(_MAX_SYMBOLS)
        .all()
    )
    for w in watch:
        universe.setdefault(w.symbol, w.name)

    signals: list[ActionSignal] = []
    for symbol, name in list(universe.items())[:_MAX_SYMBOLS]:
        if len(signals) >= _MAX_RADAR:
            break
        rows = (
            db.query(ResearchReport)
            .filter(ResearchReport.user_id == user_id, ResearchReport.symbol == symbol)
            .order_by(ResearchReport.created_at.desc())
            .limit(2)
            .all()
        )
        if len(rows) < 2:
            continue
        latest_payload = rows[0].report_json if isinstance(rows[0].report_json, dict) else {}
        prev_payload = rows[1].report_json if isinstance(rows[1].report_json, dict) else {}
        latest_bias = _bias_of(latest_payload)
        prev_bias = _bias_of(prev_payload)
        if latest_bias != prev_bias:
            signals.append(
                ActionSignal(
                    type="research",
                    severity="warning",
                    title=f"{name}研究结论转向：{prev_bias} → {latest_bias}",
                    detail="研究雷达：同一标的最近两份研报偏向变化（非交易信号）",
                    action="查看复盘",
                    action_target="chat",
                    symbol=symbol,
                    weight=72,
                )
            )
            continue

        align = _alignment_of(latest_payload) or ""
        if "背离" in align:
            signals.append(
                ActionSignal(
                    type="research",
                    severity="info",
                    title=f"{name}因子与结论存在背离",
                    detail=align,
                    action="查看复盘",
                    action_target="chat",
                    symbol=symbol,
                    weight=55,
                )
            )
            continue

        score_delta = _score_of(latest_payload) - _score_of(prev_payload)
        if abs(score_delta) >= 1.5:
            direction = "上升" if score_delta > 0 else "下降"
            signals.append(
                ActionSignal(
                    type="research",
                    severity="info",
                    title=f"{name}综合分{direction} {score_delta:+.1f}",
                    detail="研究雷达：最近两份研报分数变化较大（非交易信号）",
                    action="查看复盘",
                    action_target="chat",
                    symbol=symbol,
                    weight=50,
                )
            )

    return signals[:_MAX_RADAR]
