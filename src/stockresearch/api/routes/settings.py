"""User-facing LLM settings metadata; keys default to project root .env locally."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from stockresearch.api.deps import get_current_user
from stockresearch.api.llm_deps import resolve_llm_client
from stockresearch.core.config import get_settings
from stockresearch.core.llm_config import LlmOverrides
from stockresearch.core.schemas import (
    LlmSettingsOut,
    LlmTestOut,
    LlmUserSettings,
    ModeSettingsOut,
    ModeSettingsUpdate,
)
from stockresearch.db.models import User
from stockresearch.db.session import get_db
from stockresearch.services.env_file import save_llm_env
from stockresearch.services.glossary import get_glossary
from stockresearch.services.mock_llm import MockLLMClient
from stockresearch.services.user_preferences import get_mode_settings, save_mode_settings
from stockresearch.utils.llm_test import verify_llm_connection

router = APIRouter(prefix="/settings", tags=["settings"])


def _mask_api_key(key: str) -> str:
    """Return a masked version of the API key for display."""
    key = key.strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


@router.get("/llm", response_model=LlmSettingsOut)
def get_llm_settings() -> LlmSettingsOut:
    settings = get_settings()
    has_key = bool(settings.llm_api_key.strip())
    configured = settings.use_mock_llm or (
        has_key and bool(settings.llm_base_url.strip()) and bool(settings.llm_model.strip())
    )
    return LlmSettingsOut(
        default_base_url=settings.llm_base_url.strip(),
        default_model=settings.llm_model.strip(),
        default_api_key=_mask_api_key(settings.llm_api_key),
        default_temperature=0.3,
        server_use_mock=settings.use_mock_llm,
        server_configured=configured,
        server_has_api_key=has_key,
    )


@router.get("/mode", response_model=ModeSettingsOut)
def get_user_mode_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ModeSettingsOut:
    """Return persisted local user mode/risk questionnaire settings."""
    return get_mode_settings(db, user.id)


@router.get("/glossary")
def get_glossary_terms() -> dict[str, dict[str, str]]:
    """Return static glossary terms for professional-mode term popovers."""
    return {
        term_id: {
            "id": term_id,
            "short": term.short,
            "en": term.en,
            "def": term.def_,
            "analogy": term.analogy,
        }
        for term_id, term in get_glossary().items()
    }


@router.put("/mode", response_model=ModeSettingsOut)
def save_user_mode_settings(
    payload: ModeSettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ModeSettingsOut:
    """Persist local user mode/risk questionnaire settings to SQLite."""
    return save_mode_settings(db, user.id, payload)


@router.put("/llm", response_model=LlmSettingsOut)
async def save_llm_settings(payload: LlmUserSettings) -> LlmSettingsOut:
    """Test connection, then persist LLM settings to project root .env."""
    overrides = LlmOverrides(
        api_key=payload.api_key,
        base_url=payload.base_url,
        model=payload.model,
        temperature=payload.temperature,
        use_mock=payload.use_mock,
    )
    await _run_llm_test(overrides)
    save_llm_env(
        api_key=payload.api_key,
        base_url=payload.base_url,
        model=payload.model,
        use_mock=payload.use_mock,
        keep_api_key_if_empty=True,
    )
    return get_llm_settings()


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
    # 表单留空时回退到项目根目录 .env（本机自用）
    overrides = LlmOverrides(
        api_key=payload.api_key,
        base_url=payload.base_url,
        model=payload.model,
        temperature=payload.temperature,
        use_mock=payload.use_mock,
    )
    return await _run_llm_test(overrides)
