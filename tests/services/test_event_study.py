"""Event study classification helpers."""

from stockresearch.services.event_study import _event_kind


def test_event_kind_earnings() -> None:
    assert _event_kind("2024年年度报告", "年报") == "earnings"
    assert _event_kind("业绩预告", "其他") == "earnings"


def test_event_kind_risk() -> None:
    assert _event_kind("股东减持计划", "减持") == "risk"


def test_event_kind_other() -> None:
    assert _event_kind("日常关联交易", "其他") == "other"
