"""Verify LLM API connectivity."""

import json
import logging

import httpx

from stockresearch.core.config import get_settings
from stockresearch.core.llm_config import LlmOverrides, resolve_chat_completions_url

logger = logging.getLogger(__name__)


def _validation_error(overrides: LlmOverrides, *, client_only: bool) -> str | None:
    if overrides.effective_use_mock():
        return None
    if client_only:
        if not overrides.api_key or not overrides.api_key.strip():
            return "请填写 API Key"
        if not overrides.base_url or not overrides.base_url.strip():
            return "请填写 API URL"
        if not overrides.model or not overrides.model.strip():
            return "请填写模型名称"
        return None
    if not overrides.effective_api_key():
        return "请填写 API Key"
    if not overrides.effective_base_url():
        return "请填写 API URL"
    if not overrides.effective_model():
        return "请填写模型名称"
    return None


def _http_error_message(exc: httpx.HTTPStatusError, *, submitted_url: str = "") -> str:
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
    url = submitted_url or (str(exc.request.url) if exc.request else "")
    url_part = f" @ {url}" if url else ""
    suffix = f"：{detail}" if detail else ""
    msg = f"连接失败（HTTP {exc.response.status_code}）{url_part}{suffix}"
    return msg


def _request_error_message(exc: httpx.RequestError) -> str:
    target = str(exc.request.url) if exc.request else "上游 API"
    hint = (
        "连接测试由本机后端发起（非浏览器）。请确认："
        "① Base URL 与服务商文档一致、本机可访问；"
        "② 终端/VPN/代理能访问该地址；"
        "③ 本地网关（如 Ollama）已启动。"
    )
    if get_settings().llm_http_proxy:
        hint += f" 当前代理：{get_settings().llm_http_proxy}"
    else:
        hint += " 可在 .env 设置 LLM_HTTP_PROXY=http://127.0.0.1:7890"
    return f"连接失败：无法访问 {target}（{exc}）。{hint}"


def _httpx_client() -> httpx.AsyncClient:
    settings = get_settings()
    proxy = settings.llm_http_proxy.strip() if settings.llm_http_proxy else None
    return httpx.AsyncClient(timeout=20.0, proxy=proxy or None)


async def verify_llm_connection(
    overrides: LlmOverrides,
    *,
    client_only: bool = False,
) -> str:
    """Return empty string if OK, otherwise a user-facing error message."""
    if overrides.effective_use_mock():
        return ""

    missing = _validation_error(overrides, client_only=client_only)
    if missing:
        return missing

    if client_only:
        api_key = overrides.api_key.strip()  # type: ignore[union-attr]
        api_url = resolve_chat_completions_url(overrides.base_url.strip())  # type: ignore[union-attr]
        model = overrides.model.strip()  # type: ignore[union-attr]
    else:
        api_key = overrides.effective_api_key()
        api_url = resolve_chat_completions_url(overrides.effective_base_url())
        model = overrides.effective_model()
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

    logger.info("LLM test POST %s model=%s", api_url, model)

    try:
        async with _httpx_client() as client:
            resp = await client.post(
                api_url,
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("LLM test HTTP error: %s", exc)
        return _http_error_message(exc, submitted_url=api_url)
    except httpx.RequestError as exc:
        logger.warning("LLM test request error: %s", exc)
        return _request_error_message(exc)
    except Exception as exc:
        logger.warning("LLM test unexpected error: %s", exc)
        return f"连接失败：{exc}"

    return ""
