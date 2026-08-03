"""ReAct 接线测试：_tool_news 与 SkillRunner 均读取 scope（不触 LLM/网络）。"""

import pytest
from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.react_agent import OrchestratorAgent
from stockresearch.db.models import User
from stockresearch.services.chat_scope import build_chat_context_scope
from stockresearch.utils.llm import MockLLMClient


class _HoldingStub:
    symbol = "600519"
    name = "贵州茅台"
    sector = "白酒"
    float_cost_price = 1800.0
    quantity = 10


def _make_user(db: Session, username: str) -> User:
    user = User(username=username, password_hash="")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _patch_skill_runner(monkeypatch: pytest.MonkeyPatch, captured: dict[str, object]) -> None:
    class _FakeSkillRunner:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(
        "stockresearch.agents.orchestrator.react_agent.SkillRunner", _FakeSkillRunner
    )


async def test_tool_news_uses_scope_news_scope(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _make_user(db_session, "scope-news")
    captured: dict[str, object] = {}

    async def _fake_feed(*args: object, **kwargs: object) -> list[object]:
        captured.update(kwargs)
        return []

    monkeypatch.setattr(
        "stockresearch.agents.orchestrator.react_agent.get_news_for_user", _fake_feed
    )
    scope = await build_chat_context_scope(
        "大盘走势如何", [_HoldingStub()], None, llm=MockLLMClient()  # type: ignore[list-item]
    )
    agent = OrchestratorAgent(db_session, MockLLMClient(), user_id=user.id, scope=scope)
    result = await agent._tool_news({})
    assert result == "暂无最新新闻"
    assert captured["news_scope"] == "market"
    assert captured["industry"] is None


async def test_skill_runner_receives_skill_holdings_for_stock_intent(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _make_user(db_session, "scope-skill-stock")
    captured: dict[str, object] = {}
    _patch_skill_runner(monkeypatch, captured)

    holdings = [_HoldingStub()]
    scope = await build_chat_context_scope(
        "600519怎么样", holdings, None, llm=MockLLMClient()  # type: ignore[list-item]
    )
    # scope.holdings 为空（不注入 prompt），但 SkillRunner 应拿到全部持仓
    agent = OrchestratorAgent(
        db_session, MockLLMClient(), user_id=user.id, holdings=[], scope=scope
    )
    agent._skills()
    assert captured["holdings"] == holdings


async def test_skill_runner_receives_empty_holdings_for_market_intent(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _make_user(db_session, "scope-skill-market")
    captured: dict[str, object] = {}
    _patch_skill_runner(monkeypatch, captured)

    holdings = [_HoldingStub()]
    scope = await build_chat_context_scope(
        "大盘走势如何", holdings, None, llm=MockLLMClient()  # type: ignore[list-item]
    )
    agent = OrchestratorAgent(
        db_session, MockLLMClient(), user_id=user.id, holdings=holdings, scope=scope  # type: ignore[list-item]
    )
    agent._skills()
    assert captured["holdings"] == []
