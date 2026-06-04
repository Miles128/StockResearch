"""User-facing LLM settings metadata (keys stay on client)."""

from fastapi import APIRouter, Depends, Header, HTTPException

from stockresearch.api.llm_deps import merge_llm_settings, resolve_llm_client
from stockresearch.core.config import get_settings
from stockresearch.core.llm_config import LlmOverrides
from stockresearch.core.schemas import LlmSettingsOut, LlmTestOut, LlmUserSettings
from stockresearch.utils.llm import MockLLMClient
from stockresearch.utils.llm_test import verify_llm_connection

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/llm", response_model=LlmSettingsOut)
def get_llm_settings() -> LlmSettingsOut:
    settings = get_settings()
    return LlmSettingsOut(
        default_base_url=settings.llm_base_url,
        default_model=settings.llm_model,
        default_temperature=0.3,
        server_use_mock=settings.use_mock_llm,
    )


async def _run_llm_test(overrides: LlmOverrides) -> LlmTestOut:
    if overrides.effective_use_mock():
        client = resolve_llm_client(
            LlmUserSettings(use_mock=True),
        )
        if isinstance(client, MockLLMClient):
            return LlmTestOut(ok=True, message="Mock 模式已启用，无需连接真实 API")
        return LlmTestOut(ok=True, message="Mock 模式已启用")

    err = await verify_llm_connection(overrides)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return LlmTestOut(ok=True, message="连接成功，模型可用")


@router.post("/llm/test", response_model=LlmTestOut)
async def test_llm_settings(
    payload: LlmUserSettings,
    x_llm_api_key: str | None = Header(default=None, alias="X-LLM-Api-Key"),
    x_llm_base_url: str | None = Header(default=None, alias="X-LLM-Base-Url"),
    x_llm_model: str | None = Header(default=None, alias="X-LLM-Model"),
    x_llm_temperature: str | None = Header(default=None, alias="X-LLM-Temperature"),
    x_llm_use_mock: str | None = Header(default=None, alias="X-LLM-Use-Mock"),
) -> LlmTestOut:
    overrides = merge_llm_settings(
        payload,
        x_llm_api_key=x_llm_api_key,
        x_llm_base_url=x_llm_base_url,
        x_llm_model=x_llm_model,
        x_llm_temperature=x_llm_temperature,
        x_llm_use_mock=x_llm_use_mock,
    )
    return await _run_llm_test(overrides)
