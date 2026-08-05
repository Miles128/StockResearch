"""单篇研报普通版切换（POST /reports/{id}/plain）测试。

覆盖四种形态：
- generated：首次请求，friendly 改写生成并落库
- cache：二次请求直接命中 report_plain_versions 缓存
- degraded：改写全字段失败时降级返回专业版原文 + 提示
- 404：报告不存在或不属于当前用户
"""

from __future__ import annotations

import pytest

from stockresearch.core.schemas import DimensionResult, ResearchReportOut


class FakeLLM:
    """可控的 LLM 替身：success/fail 两态，记录调用次数。"""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    async def complete(self, system: str, user: str) -> str:
        self.calls += 1
        if self.fail:
            raise RuntimeError("mock llm failure")
        return "用大白话讲：贵州茅台基本面稳健，但估值不便宜。"


def _sample_report() -> ResearchReportOut:
    return ResearchReportOut(
        symbol="600519",
        name="贵州茅台",
        dimensions={
            "fundamental": DimensionResult(
                agent="fundamental",
                score=7.5,
                confidence="high",
                highlights=["盈利稳健"],
                risks=["估值偏高"],
                data_sources=["akshare_financials"],
            )
        },
        composite_score=7.5,
        composite_confidence="high",
        bias="bullish",
        summary="贵州茅台综合偏多。",
    )


@pytest.fixture()
def fake_llm(client) -> FakeLLM:
    """把 llm_from_headers 依赖替换为 FakeLLM（作用于 client 的 app 实例）。"""
    from stockresearch.api.llm_deps import llm_from_headers

    fake = FakeLLM()
    client.app.dependency_overrides[llm_from_headers] = lambda: fake
    yield fake
    client.app.dependency_overrides.pop(llm_from_headers, None)


def _persist_report(db, user_id: int) -> int:
    from stockresearch.api.routes.research import persist_report

    return persist_report(db, user_id, _sample_report()).id


def _plain(client, report_id: int):
    return client.post(f"/api/v1/research/reports/{report_id}/plain")


def test_plain_generated_then_cached(client, db_session, fake_llm) -> None:
    """首次生成（generated），二次命中缓存（cache）且不再调用 LLM。"""
    from stockresearch.services.local_user import get_or_create_mvp_user

    user = get_or_create_mvp_user(db_session)
    report_id = _persist_report(db_session, user.id)

    first = _plain(client, report_id)
    assert first.status_code == 200
    body = first.json()
    assert body["source"] == "generated"
    assert "用大白话讲" in body["report"]["summary"]
    assert "<term" in body["report"]["summary"], "返回层应经词库标注"
    assert fake_llm.calls > 0

    calls_before = fake_llm.calls
    second = _plain(client, report_id)
    assert second.status_code == 200
    body2 = second.json()
    assert body2["source"] == "cache"
    assert "用大白话讲" in body2["report"]["summary"]
    assert fake_llm.calls == calls_before, "缓存命中时不应再调用 LLM"


def test_plain_degraded_when_llm_fails(client, db_session) -> None:
    """改写全字段失败 → 降级返回专业版原文与提示，且不落缓存。"""
    from stockresearch.api.llm_deps import llm_from_headers
    from stockresearch.services.local_user import get_or_create_mvp_user

    user = get_or_create_mvp_user(db_session)
    report_id = _persist_report(db_session, user.id)

    client.app.dependency_overrides[llm_from_headers] = lambda: FakeLLM(fail=True)
    try:
        resp = _plain(client, report_id)
    finally:
        client.app.dependency_overrides.pop(llm_from_headers, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "degraded"
    assert body["message"]
    assert body["report"]["summary"] == "贵州茅台综合偏多。"

    # 降级结果不落缓存：LLM 恢复后再次请求应重新生成
    client.app.dependency_overrides[llm_from_headers] = lambda: FakeLLM()
    try:
        retry = _plain(client, report_id)
    finally:
        client.app.dependency_overrides.pop(llm_from_headers, None)
    assert retry.status_code == 200
    assert retry.json()["source"] == "generated"


def test_plain_404_unknown_report(client, db_session) -> None:
    """不存在的报告 → 404。"""
    resp = _plain(client, 999999)
    assert resp.status_code == 404


def test_plain_404_report_of_other_user(client, db_session) -> None:
    """他人报告不可见 → 404（按用户归属过滤）。"""
    from stockresearch.db.models import User

    other = User(username="other_plain_user", password_hash="")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)
    report_id = _persist_report(db_session, other.id)

    resp = _plain(client, report_id)
    assert resp.status_code == 404
