"""Orchestrator ReAct tool registry tests."""

import pytest
from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.react_agent import OrchestratorAgent
from stockresearch.agents.orchestrator.skills import SkillRunResult
from stockresearch.db.models import User
from stockresearch.utils.llm import MockLLMClient


@pytest.mark.asyncio
async def test_debate_stock_skill_alias(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = User(username="react-tool", password_hash="")
    db_session.add(user)
    db_session.commit()

    async def fake_skill_run(
        self: object,
        skill_id: str,
        args: dict[str, object],
    ) -> SkillRunResult:
        assert skill_id == "skill_bull_bear_debate"
        assert args.get("symbol") == "600519"
        return SkillRunResult(
            summary="裁判结论: 观望；多空分歧中等",
            cards=[{"type": "research", "data": {"summary": "测试摘要", "symbol": "600519"}}],
            intent="research",
        )

    monkeypatch.setattr(
        "stockresearch.agents.orchestrator.skills.SkillRunner.run",
        fake_skill_run,
    )

    agent = OrchestratorAgent(db_session, MockLLMClient(), user_id=user.id)
    result = await agent._execute_tool(
        "debate_stock",
        {"symbol": "600519", "name": "贵州茅台"},
    )
    assert "未知工具" not in result
    assert "裁判结论" in result
    assert "观望" in result
