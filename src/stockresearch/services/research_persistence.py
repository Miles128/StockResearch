"""研报持久化与验证登记（从 API 路由层下沉，脱离 HTTP 可复用/可测）。"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from stockresearch.core.schemas import ResearchReportOut
from stockresearch.db.models import ResearchReport

logger = logging.getLogger(__name__)


def persist_report(db: Session, user_id: int, report: ResearchReportOut) -> ResearchReport:
    payload = report.model_dump(mode="json")
    row = ResearchReport(
        user_id=user_id,
        symbol=report.symbol,
        name=report.name,
        report_json=payload,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    payload["id"] = row.id
    row.report_json = payload
    db.add(row)
    db.commit()
    db.refresh(row)
    register_report_verifications(db, user_id, report, report_id=row.id)
    return row


def register_report_verifications(
    db: Session,
    user_id: int,
    report: ResearchReportOut,
    *,
    report_id: int | None,
) -> None:
    """登记预测日记/Thesis 验证（幂等）。缓存命中路径也须调用，避免缺样本。"""
    # Phase 12a 预测日记：研报事实层自动留存预测记录（幂等）。
    try:
        from stockresearch.services.prediction_journal import record_prediction_for_report

        record_prediction_for_report(db, user_id, report, report_id=report_id)
    except Exception:
        logger.warning("prediction record failed for %s", report.symbol, exc_info=True)
    # Phase 12e 假设自动验证：deep 档 Thesis 自动创建验证计划（幂等）。
    try:
        from stockresearch.services.thesis_verification import record_thesis_for_report

        record_thesis_for_report(db, user_id, report, report_id=report_id)
    except Exception:
        logger.warning("thesis verification record failed for %s", report.symbol, exc_info=True)


def register_cached_report(db: Session, user_id: int, report: ResearchReportOut) -> int | None:
    """缓存命中时登记预测/Thesis：复用该用户该标的最近报告行（幂等）。

    缓存 payload 不含 id（persist 时回写的是 DB 行），因此按 (user, symbol)
    找最近一份报告登记；找不到则新建一行（保证预测日记不因缓存缺样本）。
    """
    row = (
        db.query(ResearchReport)
        .filter(ResearchReport.user_id == user_id, ResearchReport.symbol == report.symbol)
        .order_by(ResearchReport.created_at.desc())
        .first()
    )
    if row is not None:
        register_report_verifications(db, user_id, report, report_id=row.id)
        return row.id
    return persist_report(db, user_id, report).id


def stamp_report_id(report: ResearchReportOut, report_id: int) -> ResearchReportOut:
    return report.model_copy(update={"id": report_id})


def attach_report_ids_to_cards(
    cards: list[dict[str, object]],
    id_by_symbol: dict[str, int],
) -> list[dict[str, object]]:
    updated: list[dict[str, object]] = []
    for card in cards:
        if card.get("type") != "research":
            updated.append(card)
            continue
        data = card.get("data")
        if not isinstance(data, dict):
            updated.append(card)
            continue
        symbol = str(data.get("symbol", ""))
        report_id = id_by_symbol.get(symbol)
        if report_id is None:
            updated.append(card)
            continue
        marked = dict(data)
        marked["id"] = report_id
        updated.append({**card, "data": marked})
    return updated


def extract_reports_from_cards(cards: list[dict[str, object]]) -> list[ResearchReportOut]:
    reports: list[ResearchReportOut] = []
    for card in cards:
        if card.get("type") != "research":
            continue
        data = card.get("data")
        if isinstance(data, dict):
            reports.append(ResearchReportOut.model_validate(data))
    return reports
