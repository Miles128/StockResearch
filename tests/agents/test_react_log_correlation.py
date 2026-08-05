"""ReAct 核心循环与流式路径日志的会话/请求关联 ID 测试。

验证:连续会话运行时日志可按 [sid=...] 关联 ID 分离,且失败降级行为
(工具异常回喂、超迭代降级)保持不变。
"""

import logging

import pytest
from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.react_agent import OrchestratorAgent
from stockresearch.agents.orchestrator.stream import run_chat_stream
from stockresearch.db.models import User
from stockresearch.services.mock_llm import MockLLMClient

_REACT_LOGGER = "stockresearch.agents.orchestrator.react_agent"


@pytest.mark.asyncio
async def test_two_stream_sessions_logs_separable_by_sid(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """连续两个会话的流式运行,ReAct 日志行各自携带且互不混入对方 sid。"""
    user = User(username="sid-separable", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    caplog.set_level(logging.INFO)

    async for _ in run_chat_stream(
        db_session,
        user.id,
        "帮我分析一下600519",
        session_id="sess-aaa",
        enable_debate=False,
    ):
        pass

    async for _ in run_chat_stream(
        db_session,
        user.id,
        "帮我分析一下600519",
        session_id="sess-bbb",
        enable_debate=False,
    ):
        pass

    react_records = [r for r in caplog.records if r.name == _REACT_LOGGER]
    react_messages = [r.getMessage() for r in react_records]
    assert any("ReAct iter" in m for m in react_messages), "expected ReAct loop logs"

    sid_aaa = [m for m in react_messages if "[sid=sess-aaa]" in m]
    sid_bbb = [m for m in react_messages if "[sid=sess-bbb]" in m]
    assert sid_aaa, "first session logs must carry its own sid"
    assert sid_bbb, "second session logs must carry its own sid"

    assert all("[sid=sess-bbb]" not in m for m in sid_aaa)
    assert all("[sid=sess-aaa]" not in m for m in sid_bbb)


@pytest.mark.asyncio
async def test_tool_exception_fed_back_with_sid_log(
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """工具异常仍回喂错误字符串(降级行为),且 warning 日志带关联 ID。"""

    async def boom(self: object, args: dict[str, object]) -> str:
        raise RuntimeError("boom-detail")

    monkeypatch.setattr(
        "stockresearch.agents.orchestrator.react_agent.OrchestratorAgent._tool_news",
        boom,
    )
    caplog.set_level(logging.WARNING)

    agent = OrchestratorAgent(db_session, MockLLMClient(), user_id=1, trace_id="sess-x")
    result = await agent._execute_tool("get_news", {})
    assert "执行失败" in result
    assert "boom-detail" in result

    messages = [r.getMessage() for r in caplog.records if r.name == _REACT_LOGGER]
    assert any("[sid=sess-x] Tool get_news failed" in m and "boom-detail" in m for m in messages)


class _NeverReplyLLM(MockLLMClient):
    """永远返回工具调用(且不含 reply)的 LLM,用于触发超迭代降级。"""

    async def complete_messages(self, messages: list[dict[str, str]]) -> str:
        return '```tool\n{"tool": "unknown_tool_xyz", "args": {}}\n```'


@pytest.mark.asyncio
async def test_max_iteration_degradation_kept_with_sid_log(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """超迭代仍降级为固定兜底回复,且新增 warning 日志带关联 ID。"""
    caplog.set_level(logging.WARNING)

    agent = OrchestratorAgent(db_session, _NeverReplyLLM(), user_id=1, trace_id="sess-max")
    reply, cards = await agent.run("测试问题")
    assert "超出最大步骤数" in reply
    assert cards == []

    messages = [r.getMessage() for r in caplog.records if r.name == _REACT_LOGGER]
    assert any("[sid=sess-max] ReAct exceeded max iterations" in m for m in messages)


def test_log_ctx_prefix_optional(db_session: Session) -> None:
    """无 trace_id 时日志不加前缀(向后兼容直接构造的调用方)。"""
    agent = OrchestratorAgent(db_session, MockLLMClient(), user_id=1)
    assert agent._log_ctx("ReAct iter") == "ReAct iter"

    agent2 = OrchestratorAgent(db_session, MockLLMClient(), user_id=1, trace_id="sess-z")
    assert agent2._log_ctx("ReAct iter") == "[sid=sess-z] ReAct iter"
