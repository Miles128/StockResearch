"""Resolve LLM client from request body and/or headers."""

from fastapi import Header

from stockresearch.core.llm_config import LlmOverrides
from stockresearch.core.schemas import LlmUserSettings
from stockresearch.utils.llm import LLMClient, get_llm_client


def _parse_float_header(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


def _parse_bool_header(value: str | None) -> bool | None:
    if value is None or not value.strip():
        return None
    lowered = value.strip().lower()
    if lowered in ("1", "true", "yes", "on"):
        return True
    if lowered in ("0", "false", "no", "off"):
        return False
    return None


def merge_llm_settings(
    body: LlmUserSettings | None,
    *,
    x_llm_api_key: str | None = None,
    x_llm_base_url: str | None = None,
    x_llm_model: str | None = None,
    x_llm_temperature: str | None = None,
    x_llm_use_mock: str | None = None,
) -> LlmOverrides:
    header = LlmUserSettings(
        api_key=x_llm_api_key,
        base_url=x_llm_base_url,
        model=x_llm_model,
        temperature=_parse_float_header(x_llm_temperature),
        use_mock=_parse_bool_header(x_llm_use_mock),
    )
    return LlmOverrides(
        api_key=(body.api_key if body and body.api_key else None) or header.api_key,
        base_url=(body.base_url if body and body.base_url else None) or header.base_url,
        model=(body.model if body and body.model else None) or header.model,
        temperature=(
            body.temperature if body and body.temperature is not None else header.temperature
        ),
        use_mock=(body.use_mock if body and body.use_mock is not None else header.use_mock),
    )


def resolve_llm_client(
    body: LlmUserSettings | None,
    *,
    x_llm_api_key: str | None = None,
    x_llm_base_url: str | None = None,
    x_llm_model: str | None = None,
    x_llm_temperature: str | None = None,
    x_llm_use_mock: str | None = None,
) -> LLMClient:
    return get_llm_client(
        merge_llm_settings(
            body,
            x_llm_api_key=x_llm_api_key,
            x_llm_base_url=x_llm_base_url,
            x_llm_model=x_llm_model,
            x_llm_temperature=x_llm_temperature,
            x_llm_use_mock=x_llm_use_mock,
        )
    )


async def llm_from_headers(
    x_llm_api_key: str | None = Header(default=None, alias="X-LLM-Api-Key"),
    x_llm_base_url: str | None = Header(default=None, alias="X-LLM-Base-Url"),
    x_llm_model: str | None = Header(default=None, alias="X-LLM-Model"),
    x_llm_temperature: str | None = Header(default=None, alias="X-LLM-Temperature"),
    x_llm_use_mock: str | None = Header(default=None, alias="X-LLM-Use-Mock"),
) -> LLMClient:
    return resolve_llm_client(
        None,
        x_llm_api_key=x_llm_api_key,
        x_llm_base_url=x_llm_base_url,
        x_llm_model=x_llm_model,
        x_llm_temperature=x_llm_temperature,
        x_llm_use_mock=x_llm_use_mock,
    )
