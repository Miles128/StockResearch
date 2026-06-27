"""Follow-up question rule tests."""

from stockresearch.core.constants import INTENT_RISK
from stockresearch.core.schemas import AshareFactorOut, DimensionResult, ResearchReportOut
from stockresearch.services.follow_up import build_follow_up_questions


def test_follow_up_for_research_with_missing_factors() -> None:
    report = ResearchReportOut(
        symbol="600519",
        name="贵州茅台",
        dimensions={
            "fundamental": DimensionResult(
                agent="fundamental",
                score=7,
                confidence="high",
                highlights=["盈利质量稳定"],
                risks=[],
                data_sources=["akshare_financials"],
            )
        },
        composite_score=7.0,
        composite_confidence="high",
        bias="neutral",
        summary="测试摘要",
        ashare_factors=[
            AshareFactorOut(
                category="资金与筹码",
                name="北向资金",
                status="missing",
                impact="sentiment",
                missing=["缺少北向资金：akshare_northbound"],
            )
        ],
    )
    questions = build_follow_up_questions(
        intent="research",
        cards=[{"type": "research", "data": report.model_dump(mode="json")}],
        reading_mode="friendly",
    )
    assert 2 <= len(questions) <= 4
    assert any("数据" in q for q in questions)


def test_follow_up_for_risk_intent() -> None:
    questions = build_follow_up_questions(
        intent=INTENT_RISK,
        cards=[{"type": "risk", "data": {"portfolio_summary": "测试"}}],
        reading_mode="professional",
    )
    assert any("VaR" in q or "风险" in q for q in questions)
