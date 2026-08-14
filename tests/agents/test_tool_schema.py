"""Tool-call schema validation tests (framework-free Pydantic-AI-style layer)."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.plan_execute import PlanExecuteAgent
from stockresearch.agents.orchestrator.react_agent import _VALIDATOR, OrchestratorAgent
from stockresearch.db.models import User


def test_valid_call_passthrough() -> None:
    norm, error = _VALIDATOR.validate({"tool": "get_news", "args": {"symbol": "600519"}})
    assert error is None
    assert norm == {"tool": "get_news", "args": {"symbol": "600519"}}


def test_args_optional() -> None:
    norm, error = _VALIDATOR.validate({"tool": "reply"})
    assert error is None
    assert norm == {"tool": "reply", "args": {}}


def test_unknown_tool_rejected() -> None:
    _, error = _VALIDATOR.validate({"tool": "get_stock_price", "args": {}})
    assert error is not None
    assert "不存在" in error
    assert "get_stock_quote" in error


def test_args_must_be_object() -> None:
    _, error = _VALIDATOR.validate({"tool": "get_news", "args": "600519"})
    assert error is not None
    assert "格式错误" in error


def test_non_dict_input_rejected() -> None:
    _, error = _VALIDATOR.validate("not-a-dict")
    assert error is not None


def test_numeric_symbol_coerced_to_str() -> None:
    norm, error = _VALIDATOR.validate({"tool": "get_stock_quote", "args": {"symbol": 600519}})
    assert error is None
    assert norm == {"tool": "get_stock_quote", "args": {"symbol": "600519"}}


def test_bool_arg_preserved() -> None:
    norm, error = _VALIDATOR.validate(
        {"tool": "skill_stock_research", "args": {"with_debate": False, "symbol": 1}}
    )
    assert error is None
    assert norm is not None
    assert norm["args"]["with_debate"] is False
    assert norm["args"]["symbol"] == "1"


def test_legacy_alias_normalized() -> None:
    norm, error = _VALIDATOR.validate({"tool": "get_stock_research", "args": {"symbol": "600519"}})
    assert error is None
    assert norm == {"tool": "skill_stock_research", "args": {"symbol": "600519"}}


class SequencedLLM:
    """Replies with preset responses, records every messages payload."""

    def __init__(self, *responses: str) -> None:
        self._responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []

    async def complete_messages(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(list(messages))
        if self._responses:
            return self._responses.pop(0)
        return "抱歉，我暂时无法回答，请稍后再试。"


@pytest.mark.asyncio
async def test_rejected_call_injected_back_and_retry(db_session: Session) -> None:
    user = User(username="tool-schema-retry", password_hash="")
    db_session.add(user)
    db_session.commit()

    llm = SequencedLLM(
        '```tool\n{"tool": "get_stock_price", "args": {"symbol": "600519"}}\n```',
        '```tool\n{"tool": "reply", "args": {"message": "完成"}}\n```',
    )
    agent = OrchestratorAgent(db_session, llm, user_id=user.id)  # type: ignore[arg-type]
    reply, _ = await agent.run("测试")
    assert reply == "完成"
    assert len(llm.calls) == 2
    assert "不存在" in llm.calls[1][-1]["content"]


@pytest.mark.asyncio
async def test_mixed_calls_execute_valid_only(db_session: Session) -> None:
    user = User(username="tool-schema-mixed", password_hash="")
    db_session.add(user)
    db_session.commit()

    llm = SequencedLLM(
        '```tool\n{"tool": "get_stock_price", "args": {}}\n```\n'
        '```tool\n{"tool": "reply", "args": {"message": "完成"}}\n```'
    )
    agent = OrchestratorAgent(db_session, llm, user_id=user.id)  # type: ignore[arg-type]
    reply, _ = await agent.run("测试")
    assert reply == "完成"
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_plan_step_rejects_invalid_tool_call() -> None:
    executed: list[tuple[str, dict[str, Any]]] = []

    class PlanLLM:
        async def complete(self, system: str, user: str) -> str:
            return '```tool\n{"tool": "not_a_tool", "args": {}}\n```'

    async def executor(name: str, args: dict[str, Any]) -> str:
        executed.append((name, args))
        return "ok"

    agent = PlanExecuteAgent(PlanLLM(), tool_executor=executor)  # type: ignore[arg-type]
    result = await agent._execute_step(
        "测试",
        {"id": 1, "description": "步骤", "tool": "auto", "args": {}},
    )
    assert "格式错误" in result
    assert executed == []
