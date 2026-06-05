"""Orchestrator ReAct tool registry tests."""

import pytest
from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.react_agent import OrchestratorAgent
from stockresearch.core.schemas import DebateResult, DimensionResult, ResearchReportOut
from stockresearch.db.models import User
from stockresearch.utils.llm import MockLLMClient


@pytest.mark.asyncio
async def test_debate_stock_tool_registered(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(username="react-tool", password_hash="")
    db_session.add(user)
    db_session.commit()

    mock_report = ResearchReportOut(
        symbol="600519",
        name="贵州茅台",
        dimensions={
            "fundamental": DimensionResult(
                agent="fundamental",
                score=7.0,
                confidence="high",
                highlights=["稳健"],
                risks=["估值"],
                data_sources=["mock"],
            ),
        },
        composite_score=7.0,
        composite_confidence="high",
        bias="bullish",
        summary="测试摘要",
        debate=DebateResult(
            consensus="多空分歧中等",
            core_divergence="估值分歧",
            final_bias="neutral",
            judge_verdict="观望",
            confidence="medium",
            rounds=[],
        ),
    )

    async def fake_research(
        symbol: str,
        llm: object | None = None,
        *,
        with_debate: bool = True,
    ) -> ResearchReportOut:
        return mock_report

    monkeypatch.setattr(
        "stockresearch.agents.orchestrator.react_agent.run_research",
        fake_research,
    )

    agent = OrchestratorAgent(db_session, MockLLMClient(), user_id=user.id)
    result = await agent._execute_tool(
        "debate_stock",
        {"symbol": "600519", "name": "贵州茅台"},
    )
    assert "未知工具" not in result
    assert "裁判结论" in result
    assert "观望" in result
