"""次要域附录块注入测试：execute_chat_turn 统一拼接，覆盖 ReAct 路径（不触 LLM/网络）。"""

from dataclasses import replace

import pytest
from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.chat_execute import execute_chat_turn
from stockresearch.agents.orchestrator.react_agent import OrchestratorAgent
from stockresearch.core.schemas import ModeSettingsOut
from stockresearch.db.models import User
from stockresearch.services.chat.scope import build_chat_context_scope
from stockresearch.services.mock_llm import MockLLMClient

_MESSAGE = "介绍一下半导体和新能源的区别"


@pytest.fixture()
def _capture_run(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    captured: dict[str, object] = {}

    async def _fake_run(
        self: OrchestratorAgent,
        message: str,
        *,
        history: object = None,
        long_term_context: str = "",
        user_context_text: str = "",
    ) -> tuple[str, list[dict[str, object]]]:
        captured["message"] = message
        return ("好的", [])

    monkeypatch.setattr(OrchestratorAgent, "run", _fake_run)
    return captured


async def test_secondary_block_appended_to_user_message(
    db_session: Session, _capture_run: dict[str, object]
) -> None:
    user = User(username="sec-block", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    scope = await build_chat_context_scope(_MESSAGE, [], None, llm=MockLLMClient())
    scope = replace(scope, secondary_block="【附：你的持仓概况】\n- 贵州茅台(600519) 10股")
    result = await execute_chat_turn(
        db=db_session,
        user_id=user.id,
        message=_MESSAGE,
        llm=MockLLMClient(),
        holdings=[],
        debate_on=False,
        master_on=False,
        mode_settings=ModeSettingsOut(),
        scope=scope,
    )
    assert result.reply == "好的"
    message = str(_capture_run["message"])
    assert _MESSAGE in message
    assert "【附：你的持仓概况】" in message


async def test_empty_secondary_block_leaves_message_unchanged(
    db_session: Session, _capture_run: dict[str, object]
) -> None:
    user = User(username="sec-none", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    scope = await build_chat_context_scope(_MESSAGE, [], None, llm=MockLLMClient())
    assert scope.secondary_block == ""
    await execute_chat_turn(
        db=db_session,
        user_id=user.id,
        message=_MESSAGE,
        llm=MockLLMClient(),
        holdings=[],
        debate_on=False,
        master_on=False,
        mode_settings=ModeSettingsOut(),
        scope=scope,
    )
    assert _capture_run["message"] == _MESSAGE
