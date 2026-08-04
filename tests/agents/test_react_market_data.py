"""_tool_market_data enrichment tests — overseas indices + macro snapshot."""

import pytest
from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.react_agent import OrchestratorAgent
from stockresearch.data.providers.kimi_macro import MACRO_CACHE_KEY
from stockresearch.db.models import User
from stockresearch.services.mock_llm import MockLLMClient
from stockresearch.services.sqlite_cache import set_sqlite_cached


def _agent(db_session: Session) -> OrchestratorAgent:
    user = User(username="market-data-tool", password_hash="")
    db_session.add(user)
    db_session.commit()
    return OrchestratorAgent(db_session, MockLLMClient(), user_id=user.id)


@pytest.mark.asyncio
async def test_market_data_includes_overseas_markets(db_session: Session) -> None:
    # 测试环境 mock 模式：overview 与外围指数均为 mock 数据
    agent = _agent(db_session)
    result = await agent._tool_market_data()
    assert "上证指数" in result
    assert "外围市场:" in result
    assert "恒生指数" in result


@pytest.mark.asyncio
async def test_market_data_includes_macro_when_cached(db_session: Session) -> None:
    set_sqlite_cached(
        MACRO_CACHE_KEY,
        {
            "as_of": "2026-08-01",
            "indicators": [
                {
                    "name": "CPI 同比",
                    "value": "0.4%",
                    "period": "2026-06",
                    "trend": "up",
                    "comment": "",
                },
            ],
            "source": "kimi",
        },
        86400,
    )
    agent = _agent(db_session)
    result = await agent._tool_market_data()
    assert "【宏观数据(Kimi, 2026-08-01)】" in result
    assert "CPI 同比" in result


@pytest.mark.asyncio
async def test_market_data_enrichment_failure_degrades(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom() -> str:
        raise RuntimeError("macro formatting exploded")

    monkeypatch.setattr("stockresearch.services.macro_snapshot.format_macro_snapshot", boom)
    agent = _agent(db_session)
    result = await agent._tool_market_data()
    # 基础大盘数据不受影响
    assert "上证指数" in result
    assert "数据状态" in result


@pytest.mark.asyncio
async def test_orchestrator_system_has_attribution_discipline() -> None:
    from stockresearch.agents.orchestrator.react_agent import ORCHESTRATOR_SYSTEM

    assert "大盘归因纪律" in ORCHESTRATOR_SYSTEM
    assert "尚未落地" in ORCHESTRATOR_SYSTEM
