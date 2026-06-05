"""LLM per-request overrides."""

import pytest
from httpx import ASGITransport, AsyncClient

from stockresearch.api.app import create_app
from stockresearch.api.llm_deps import merge_llm_settings
from stockresearch.core.llm_config import LlmOverrides, resolve_chat_completions_url
from stockresearch.core.schemas import LlmUserSettings
from stockresearch.utils.llm import MockLLMClient, OpenAICompatibleClient, get_llm_client
from stockresearch.utils.llm_test import verify_llm_connection


def test_merge_llm_settings_body_over_header() -> None:
    body = LlmUserSettings(api_key="body-key", model="gpt-4o", temperature=0.8)
    merged = merge_llm_settings(
        body,
        x_llm_api_key="header-key",
        x_llm_model="deepseek-chat",
        x_llm_temperature="0.1",
    )
    assert merged.api_key == "body-key"
    assert merged.model == "gpt-4o"
    assert merged.temperature == 0.8


def test_llm_overrides_clamp_temperature() -> None:
    cfg = LlmOverrides(temperature=9.0)
    assert cfg.effective_temperature() == 2.0


def test_get_llm_client_mock_override() -> None:
    client = get_llm_client(LlmOverrides(use_mock=True))
    assert isinstance(client, MockLLMClient)


@pytest.mark.asyncio
async def test_llm_test_endpoint_mock() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/settings/llm/test",
            json={"use_mock": True},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True


@pytest.mark.asyncio
async def test_llm_test_endpoint_missing_fields() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/settings/llm/test",
            json={"use_mock": False, "api_key": "k", "base_url": "", "model": ""},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_verify_llm_connection_mock() -> None:
    assert await verify_llm_connection(LlmOverrides(use_mock=True)) == ""


def test_resolve_chat_completions_url() -> None:
    base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert (
        resolve_chat_completions_url(base)
        == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    )
    full = f"{base}/chat/completions"
    assert resolve_chat_completions_url(full) == full
    assert resolve_chat_completions_url(f"{base}/") == resolve_chat_completions_url(base)


def test_openai_client_uses_override_temperature(monkeypatch) -> None:
    monkeypatch.setenv("USE_MOCK_LLM", "false")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from stockresearch.core.config import get_settings

    get_settings.cache_clear()
    client = OpenAICompatibleClient(LlmOverrides(temperature=1.2))
    assert client._temperature == 1.2
