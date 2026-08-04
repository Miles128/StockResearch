"""Packaged SkillRunner tests — all agent skills with mocked sub-streams."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.orm import Session

from stockresearch.agents.orchestrator.skills import PACKAGED_SKILLS, SKILL_IDS, SkillRunner
from stockresearch.core.schemas import (
    DebateResult,
    DimensionResult,
    ModeSettingsOut,
    ResearchReportOut,
)
from stockresearch.db.models import Holding, User
from stockresearch.services.mock_llm import MockLLMClient


def _research_payload(**overrides: object) -> dict[str, object]:
    base = ResearchReportOut(
        symbol="600519",
        name="贵州茅台",
        dimensions={
            "fundamental": DimensionResult(
                agent="fundamental",
                score=7.0,
                confidence="high",
                highlights=["盈利稳健"],
                risks=["估值偏高"],
                data_sources=["mock"],
            )
        },
        composite_score=7.0,
        composite_confidence="high",
        bias="neutral",
        summary="贵州茅台综合中性。",
        debate=DebateResult(
            rounds=[],
            judge_verdict="中性",
            consensus="中性",
            core_divergence="分歧小",
            final_bias="neutral",
            confidence="medium",
        ),
    ).model_dump(mode="json")
    base.update(overrides)
    return base


async def _stream_done(payload: dict[str, object]) -> AsyncIterator[dict[str, object]]:
    yield {"type": "status", "message": "mock"}
    yield {"type": "done", "result": payload}


def _runner(
    db: Session,
    user_id: int,
    *,
    holdings: list[Holding] | None = None,
    events: list[dict[str, object]] | None = None,
) -> SkillRunner:
    collected: list[dict[str, object]] = events if events is not None else []

    async def on_event(event: dict[str, object]) -> None:
        collected.append(event)

    return SkillRunner(
        db=db,
        llm=MockLLMClient(),
        user_id=user_id,
        holdings=holdings or [],
        mode_settings=ModeSettingsOut(),
        debate_default=False,
        master_default=False,
        on_event=on_event,
    )


@pytest.mark.parametrize("skill_id", sorted(SKILL_IDS))
def test_all_skills_registered(skill_id: str) -> None:
    ids = {s.skill_id for s in PACKAGED_SKILLS}
    assert skill_id in ids


@pytest.mark.asyncio
async def test_skill_risk_checkup_no_holdings(db_session: Session) -> None:
    user = User(username="skill-risk-empty", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    events: list[dict[str, object]] = []
    runner = _runner(db_session, user.id, events=events)
    result = await runner.run("skill_risk_checkup", {})

    assert result.partial is True
    assert result.error is None
    assert "暂无持仓" in result.summary
    assert events[0]["type"] == "skill_start"
    assert events[-1]["type"] == "skill_done"


@pytest.mark.asyncio
async def test_skill_risk_checkup_forwards_substream(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(username="skill-risk", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    holding = Holding(
        user_id=user.id,
        symbol="600519",
        name="贵州茅台",
        cost_price=1800.0,
        quantity=10,
        sector="白酒",
    )
    db_session.add(holding)
    db_session.commit()

    async def fake_risk_stream(
        *_args: object, **_kwargs: object
    ) -> AsyncIterator[dict[str, object]]:
        yield {
            "type": "agent_start",
            "agent_id": "risk_rule",
            "agent_name": "规则",
            "role": "analyst",
        }
        async for event in _stream_done({"alerts": [], "portfolio_summary": "组合风险可控"}):
            yield event

    monkeypatch.setattr(
        "stockresearch.agents.orchestrator.skills.run_risk_checkup_stream",
        fake_risk_stream,
    )

    events: list[dict[str, object]] = []
    runner = _runner(db_session, user.id, holdings=[holding], events=events)
    result = await runner.run("skill_risk_checkup", {})

    assert result.intent == "risk"
    assert result.cards[0]["type"] == "risk"
    assert result.summary == "组合风险可控"
    run_id = events[0]["skill_run_id"]
    nested = [
        e
        for e in events
        if e.get("skill_run_id") == run_id and e["type"] not in ("skill_start", "skill_done")
    ]
    assert any(e["type"] == "agent_start" for e in nested)


@pytest.mark.asyncio
async def test_skill_stock_research_forwards_substream(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(username="skill-stock", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    async def fake_research_stream(
        *_args: object, **_kwargs: object
    ) -> AsyncIterator[dict[str, object]]:
        yield {
            "type": "dimension_ready",
            "agent_id": "fundamental",
            "agent_name": "基本面",
            "content": "ok",
        }
        async for event in _stream_done(_research_payload()):
            yield event

    monkeypatch.setattr(
        "stockresearch.agents.orchestrator.skills.run_research_stream",
        fake_research_stream,
    )

    events: list[dict[str, object]] = []
    runner = _runner(db_session, user.id, events=events)
    result = await runner.run("skill_stock_research", {"symbol": "600519"})

    assert result.intent == "research"
    assert result.cards[0]["type"] == "research"
    run_id = str(events[0]["skill_run_id"])
    assert any(
        e.get("skill_run_id") == run_id and e.get("type") == "dimension_ready" for e in events
    )


@pytest.mark.asyncio
async def test_skill_stock_research_resolves_ambiguous_query(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(username="skill-stock-ambig", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    async def fake_resolve(*_args: object, **_kwargs: object) -> object:
        from stockresearch.services.stock_lookup import StockLookupResult

        return StockLookupResult(
            status="ambiguous",
            symbol=None,
            name=None,
            message="找到多个匹配",
            candidates=(),
            normalized_query="平安",
        )

    monkeypatch.setattr(
        "stockresearch.agents.orchestrator.skills.resolve_message_stock",
        fake_resolve,
    )

    runner = _runner(db_session, user.id)
    result = await runner.run("skill_stock_research", {"query": "帮我分析平安"})

    assert result.cards[0]["type"] == "stock_choice"
    assert result.intent == "chat"


@pytest.mark.asyncio
async def test_skill_market_research(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(username="skill-market", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    async def fake_market_stream(
        *_args: object, **_kwargs: object
    ) -> AsyncIterator[dict[str, object]]:
        async for event in _stream_done(_research_payload(symbol="000001", name="上证指数")):
            yield event

    monkeypatch.setattr(
        "stockresearch.agents.orchestrator.skills.run_market_research_stream",
        fake_market_stream,
    )

    runner = _runner(db_session, user.id)
    result = await runner.run("skill_market_research", {"query": "今天大盘走势"})

    assert result.intent == "research"
    assert result.cards[0]["type"] == "research"


@pytest.mark.asyncio
async def test_skill_industry_research(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = User(username="skill-industry", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    async def fake_industry_stream(
        *_args: object, **_kwargs: object
    ) -> AsyncIterator[dict[str, object]]:
        payload = _research_payload(symbol="688981", name="半导体板块")
        payload["sector"] = "半导体"
        async for event in _stream_done(payload):
            yield event

    monkeypatch.setattr(
        "stockresearch.agents.orchestrator.skills.run_industry_research_stream",
        fake_industry_stream,
    )

    runner = _runner(db_session, user.id)
    result = await runner.run("skill_industry_research", {"sector": "半导体"})

    assert result.intent == "research"
    assert result.cards[0]["type"] == "research"


@pytest.mark.asyncio
async def test_skill_bull_bear_debate_requires_symbol(db_session: Session) -> None:
    user = User(username="skill-debate", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    runner = _runner(db_session, user.id)
    result = await runner.run("skill_bull_bear_debate", {})

    assert result.error == "missing_symbol"


@pytest.mark.asyncio
async def test_skill_bull_bear_debate_enables_debate(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(username="skill-debate-ok", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    captured: dict[str, Any] = {}

    async def fake_research_stream(
        _symbol: str, **kwargs: object
    ) -> AsyncIterator[dict[str, object]]:
        captured["with_debate"] = kwargs.get("with_debate")
        async for event in _stream_done(_research_payload()):
            yield event

    monkeypatch.setattr(
        "stockresearch.agents.orchestrator.skills.run_research_stream",
        fake_research_stream,
    )

    runner = _runner(db_session, user.id)
    result = await runner.run("skill_bull_bear_debate", {"symbol": "600519"})

    assert captured.get("with_debate") is True
    assert result.intent == "research"


@pytest.mark.asyncio
async def test_skill_master_commentary_missing_context(db_session: Session) -> None:
    user = User(username="skill-master", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    runner = _runner(db_session, user.id)
    result = await runner.run("skill_master_commentary", {"subject": "600519"})

    assert result.error == "missing_context"


@pytest.mark.asyncio
async def test_skill_master_commentary_forwards_events(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(username="skill-master-ok", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    async def fake_commentary(
        *_args: object, **_kwargs: object
    ) -> AsyncIterator[dict[str, object]]:
        yield {
            "type": "master_commentary",
            "commentary": [
                {
                    "master": "buffett",
                    "name": "巴菲特",
                    "signal": "neutral",
                    "confidence": 0.6,
                    "reasoning": "估值合理",
                    "key_metric": "ROE",
                }
            ],
        }

    monkeypatch.setattr(
        "stockresearch.agents.orchestrator.skills.stream_master_commentary",
        fake_commentary,
    )

    events: list[dict[str, object]] = []
    runner = _runner(db_session, user.id, events=events)
    result = await runner.run(
        "skill_master_commentary",
        {"subject": "600519", "context": "基本面稳健，估值中性"},
    )

    assert result.cards[0]["type"] == "master"
    assert "估值合理" in result.summary
    assert events[0]["type"] == "skill_start"
    assert events[-1]["type"] == "skill_done"
    assert events[-1]["skill_id"] == "skill_master_commentary"


@pytest.mark.asyncio
async def test_unknown_skill(db_session: Session) -> None:
    user = User(username="skill-unknown", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    runner = _runner(db_session, user.id)
    result = await runner.run("skill_not_real", {})

    assert result.error == "unknown_skill"


@pytest.mark.asyncio
async def test_skill_chart_overlays_requires_symbol(db_session: Session) -> None:
    user = User(username="skill-overlays-nosym", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    runner = _runner(db_session, user.id)
    result = await runner.run("skill_chart_overlays", {})

    assert result.partial is True
    assert "股票代码" in result.summary


@pytest.mark.asyncio
async def test_skill_chart_overlays_returns_set(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from stockresearch.core.schemas import (
        ChartOverlay,
        ChartOverlayPoint,
        ChartOverlaySet,
    )

    user = User(username="skill-overlays-ok", password_hash="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    overlay_set = ChartOverlaySet(
        symbol="600519",
        generatedAt="2026-08-04T00:00:00+00:00",
        overlays=[
            ChartOverlay(
                id="trend-support-5-79",
                kind="trend",
                a=ChartOverlayPoint(time="2026-04-01", price=100.0),
                b=ChartOverlayPoint(time="2026-08-01", price=137.0),
                side="support",
                strength=1.0,
                touches=4,
                source="ai",
                rationale="支撑线：连接低点，共 4 次触碰。仅为图形描述，不构成交易建议。",
            )
        ],
    )

    async def fake_compute(symbol: str, days: int = 250) -> ChartOverlaySet:
        assert symbol == "600519"
        return overlay_set

    monkeypatch.setattr(
        "stockresearch.services.chart_overlays.compute_chart_overlays", fake_compute
    )

    events: list[dict[str, object]] = []
    runner = _runner(db_session, user.id, events=events)
    result = await runner.run("skill_chart_overlays", {"symbol": "600519"})

    assert result.error is None
    assert result.cards and result.cards[0]["type"] == "chart_overlays"
    assert "支撑线" in result.summary
    assert "不构成交易建议" in result.summary
    assert events[0]["type"] == "skill_start"
    assert events[-1]["type"] == "skill_done"
