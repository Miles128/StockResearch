"""Verify LLM API connectivity."""

import json
import logging

import httpx

from stockresearch.core.llm_config import LlmOverrides

logger = logging.getLogger(__name__)


def _validation_error(overrides: LlmOverrides) -> str | None:
    if overrides.effective_use_mock():
        return None
    if not overrides.api_key or not overrides.api_key.strip():
        return "请填写 API Key"
    if not overrides.base_url or not overrides.base_url.strip():
        return "请填写 API Base URL"
    if not overrides.model or not overrides.model.strip():
        return "请填写模型名称"
    return None


def _http_error_message(exc: httpx.HTTPStatusError) -> str:
    detail = ""
    try:
        body = exc.response.json()
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict) and err.get("message"):
                detail = str(err["message"])
            elif body.get("message"):
                detail = str(body["message"])
            elif body.get("detail"):
                detail = str(body["detail"])
    except (json.JSONDecodeError, ValueError):
        detail = exc.response.text[:200] if exc.response.text else ""
    suffix = f"：{detail}" if detail else ""
    return f"连接失败（HTTP {exc.response.status_code}）{suffix}"


async def verify_llm_connection(overrides: LlmOverrides) -> str:
    """Return empty string if OK, otherwise a user-facing error message."""
    if overrides.effective_use_mock():
        return ""

    missing = _validation_error(overrides)
    if missing:
        return missing

    api_key = overrides.api_key.strip()  # type: ignore[union-attr]
    base_url = overrides.base_url.strip().rstrip("/")  # type: ignore[union-attr]
    model = overrides.model.strip()  # type: ignore[union-attr]
    temperature = overrides.effective_temperature()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "ping"},
        ],
        "max_tokens": 8,
        "temperature": temperature,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("LLM test HTTP error: %s", exc)
        return _http_error_message(exc)
    except httpx.RequestError as exc:
        logger.warning("LLM test request error: %s", exc)
        return f"连接失败：{exc}"
    except Exception as exc:
        logger.warning("LLM test unexpected error: %s", exc)
        return f"连接失败：{exc}"

    return ""
