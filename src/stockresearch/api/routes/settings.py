"""User-facing LLM settings metadata (keys stay on client)."""

from fastapi import APIRouter, HTTPException

from stockresearch.api.llm_deps import resolve_llm_client
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
        default_base_url="",
        default_model="",
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

    err = await verify_llm_connection(overrides, client_only=True)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return LlmTestOut(ok=True, message="连接成功，模型可用")


@router.post("/llm/test", response_model=LlmTestOut)
async def test_llm_settings(payload: LlmUserSettings) -> LlmTestOut:
    # 连接测试只认本次表单 body，不合并请求头，避免旧配置干扰
    overrides = LlmOverrides(
        api_key=payload.api_key,
        base_url=payload.base_url,
        model=payload.model,
        temperature=payload.temperature,
        use_mock=payload.use_mock,
    )
    return await _run_llm_test(overrides)
