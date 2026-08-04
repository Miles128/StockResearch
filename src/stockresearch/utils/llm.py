"""LLM client with mock fallback for tests."""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import httpx

from stockresearch.core.config import get_settings
from stockresearch.core.exceptions import LLMConfigError
from stockresearch.core.llm_config import LlmOverrides, resolve_chat_completions_url
from stockresearch.core.output_style import apply_style_to_system
from stockresearch.utils.llm_usage import estimate_tokens, record_usage

logger = logging.getLogger(__name__)


def _httpx_client_kwargs() -> dict:
    """Build httpx.AsyncClient kwargs for LLM calls.

    trust_env=False ignores shell HTTP_PROXY/HTTPS_PROXY (often breaks local dev
    when a stale proxy is set). Use LLM_HTTP_PROXY in .env when a proxy is required.
    """
    kwargs: dict = {
        "timeout": float(get_settings().llm_timeout_seconds),
        "trust_env": False,
    }
    proxy = get_settings().llm_http_proxy
    if proxy:
        kwargs["proxy"] = proxy
    return kwargs


# Transient failures worth retrying: rate limits, server errors, timeouts.
_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
_MAX_LLM_RETRIES = 2


def _is_retryable_llm_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS
    return isinstance(
        exc, httpx.ConnectError | httpx.ConnectTimeout | httpx.ReadTimeout | httpx.PoolTimeout
    )


def _styled_system(system: str) -> str:
    return apply_style_to_system(system)


class LLMClient(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str) -> str:
        pass

    async def complete_messages(self, messages: list[dict[str, str]]) -> str:
        """Complete with full message history. Default: concatenate into system+user."""
        system = messages[0]["content"] if messages and messages[0].get("role") == "system" else ""
        user_parts = []
        for m in messages:
            if m.get("role") == "system":
                continue
            role = m.get("role", "user")
            user_parts.append(f"[{role}]\n{m['content']}")
        return await self.complete(system, "\n".join(user_parts))

    async def stream_complete(self, system: str, user: str) -> AsyncIterator[str]:
        text = await self.complete(system, user)
        if text:
            yield text


class OpenAICompatibleClient(LLMClient):
    def __init__(self, overrides: LlmOverrides | None = None) -> None:
        cfg = overrides or LlmOverrides()
        self._api_key = cfg.effective_api_key()
        self._base_url = resolve_chat_completions_url(cfg.effective_base_url())
        self._model = cfg.effective_model()
        self._temperature = cfg.effective_temperature()

    async def _post_with_retry(
        self, headers: dict[str, str], payload: dict[str, object]
    ) -> dict[str, object]:
        """POST a chat-completion request, retrying on transient failures."""
        for attempt in range(_MAX_LLM_RETRIES + 1):
            try:
                async with httpx.AsyncClient(**_httpx_client_kwargs()) as client:
                    resp = await client.post(self._base_url, headers=headers, json=payload)
                    resp.raise_for_status()
                    return resp.json()  # type: ignore[no-any-return]
            except Exception as exc:
                if not _is_retryable_llm_error(exc) or attempt >= _MAX_LLM_RETRIES:
                    raise
                backoff = 0.5 * (2**attempt)
                logger.warning(
                    "LLM request failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1,
                    _MAX_LLM_RETRIES + 1,
                    backoff,
                    exc,
                )
                await asyncio.sleep(backoff)
        raise RuntimeError("unreachable")  # pragma: no cover

    async def stream_complete(self, system: str, user: str) -> AsyncIterator[str]:
        system = _styled_system(system)
        if not self._api_key:
            # 用户已显式请求真实 LLM（USE_MOCK_LLM=false）但未配置 API key，
            # 不再静默回退到 Mock，避免误以为"AI 回复质量差"。
            raise LLMConfigError(
                "LLM API key is not configured. Set USE_MOCK_LLM=true for offline "
                "development or provide a valid API key in Settings."
            )

        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self._temperature,
            "stream": True,
        }
        prompt_text = f"{system}\n{user}"
        completion_parts: list[str] = []
        usage_from_api: dict[str, int] | None = None
        async with httpx.AsyncClient(**_httpx_client_kwargs()) as client:
            async with client.stream(
                "POST",
                self._base_url,
                headers=headers,
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    raw_usage = chunk.get("usage")
                    if isinstance(raw_usage, dict) and raw_usage.get("total_tokens"):
                        usage_from_api = {
                            "prompt_tokens": int(raw_usage.get("prompt_tokens") or 0),
                            "completion_tokens": int(raw_usage.get("completion_tokens") or 0),
                        }
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        piece = str(content)
                        completion_parts.append(piece)
                        yield piece
        if usage_from_api:
            record_usage(
                prompt_tokens=usage_from_api["prompt_tokens"],
                completion_tokens=usage_from_api["completion_tokens"],
            )
        else:
            record_usage(
                prompt_tokens=estimate_tokens(prompt_text),
                completion_tokens=estimate_tokens("".join(completion_parts)),
                is_estimate=True,
            )

    async def complete(self, system: str, user: str) -> str:
        parts: list[str] = []
        async for chunk in self.stream_complete(system, user):
            parts.append(chunk)
        return "".join(parts)

    async def complete_messages(self, messages: list[dict[str, str]]) -> str:
        """Complete with full message history using the chat API natively."""
        styled_messages = list(messages)
        for idx, msg in enumerate(styled_messages):
            if msg.get("role") == "system" and msg.get("content"):
                styled_messages[idx] = {
                    **msg,
                    "content": _styled_system(str(msg["content"])),
                }
        if not self._api_key:
            raise LLMConfigError(
                "LLM API key is not configured. Set USE_MOCK_LLM=true for offline "
                "development or provide a valid API key in Settings."
            )

        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self._model,
            "messages": styled_messages,
            "temperature": self._temperature,
        }
        data = await self._post_with_retry(headers, payload)
        content = str(data["choices"][0]["message"]["content"])
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        if usage.get("total_tokens"):
            record_usage(
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
            )
        else:
            prompt_text = "\n".join(
                f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages
            )
            record_usage(
                prompt_tokens=estimate_tokens(prompt_text),
                completion_tokens=estimate_tokens(content),
                is_estimate=True,
            )
        return content


def get_llm_client(overrides: LlmOverrides | None = None) -> LLMClient:
    cfg = overrides or LlmOverrides()
    if cfg.effective_use_mock():
        # Lazy import: mock lives in services and depends on this module.
        from stockresearch.services.mock_llm import MockLLMClient

        return MockLLMClient()
    return OpenAICompatibleClient(cfg)
