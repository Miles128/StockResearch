"""Kimi Code CLI 子进程封装:经 `kimi -p` 调用 Kimi Datasource。

每次调用都是一次 LLM 往返并按次消耗 Kimi Code 会员配额,
调用方必须配合缓存使用(provider_cache)。
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass
from datetime import date

from stockresearch.core.config import get_settings

logger = logging.getLogger(__name__)


class KimiCliError(Exception):
    """Kimi CLI 调用失败基类。"""


class KimiCliNotAvailableError(KimiCliError):
    """kimi 二进制不存在。"""


class KimiCliTimeoutError(KimiCliError):
    """CLI 调用超时。"""


class KimiCliParseError(KimiCliError):
    """CLI 输出无法解析为 JSON。"""


class KimiCliQuotaExceededError(KimiCliError):
    """当日调用次数超过 kimi_live_max_calls_per_day 配额。"""


@dataclass(frozen=True)
class KimiCliResult:
    payload: dict[str, object]
    raw_text: str


_JSON_INSTRUCTION = (
    "请只输出一个 JSON 对象作为回答,不要输出任何其他文字、解释或 markdown 代码块标记。"
)

# Module-level daily quota counter shared by all KimiCliClient instances.
_quota_date: date | None = None
_quota_count = 0


def _consume_daily_quota() -> None:
    """按自然日计数;超额时拒绝调用,防止烧穿 Kimi Code 会员配额。"""
    global _quota_date, _quota_count
    limit = get_settings().kimi_live_max_calls_per_day
    today = date.today()
    if _quota_date != today:
        _quota_date = today
        _quota_count = 0
    if limit > 0 and _quota_count >= limit:
        raise KimiCliQuotaExceededError(
            f"kimi CLI 当日调用已达上限({limit} 次),请明日再试或调高配额"
        )
    _quota_count += 1


def _extract_assistant_text(stream_output: str) -> str:
    """从 stream-json(JSONL)输出中拼接全部 assistant 文本。"""
    parts: list[str] = []
    for line in stream_output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict) or obj.get("type") != "assistant":
            continue
        content = (obj.get("message") or {}).get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text") or ""))
    return "\n".join(parts)


def _extract_json_object(text: str) -> dict[str, object]:
    """从文本中提取第一个完整 JSON 对象(容忍围栏与前导文字)。"""
    start = text.find("{")
    while start != -1:
        try:
            obj, _end = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
            continue
        if isinstance(obj, dict):
            return obj
        start = text.find("{", start + 1)
    raise KimiCliParseError(f"输出中未找到 JSON 对象: {text[:200]!r}")


class KimiCliClient:
    """异步调用本地 kimi CLI 并解析严格 JSON 输出。"""

    def __init__(self, *, cli_path: str | None = None, timeout: float | None = None) -> None:
        settings = get_settings()
        self._cli_path = cli_path or settings.kimi_cli_path
        self._timeout = timeout if timeout is not None else float(settings.kimi_cli_timeout_seconds)

    def available(self) -> bool:
        return shutil.which(self._cli_path) is not None

    async def query_json(self, prompt: str, *, max_retries: int = 2) -> KimiCliResult:
        if not self.available():
            raise KimiCliNotAvailableError(f"kimi CLI 不可用: {self._cli_path}")
        _consume_daily_quota()
        full_prompt = f"{prompt}\n\n{_JSON_INSTRUCTION}"
        last_exc: KimiCliError | None = None
        for attempt in range(max_retries + 1):
            try:
                raw = await self._run_once(full_prompt)
                return KimiCliResult(payload=_extract_json_object(raw), raw_text=raw)
            except KimiCliError as exc:
                last_exc = exc
                logger.warning("kimi CLI 第 %s 次调用失败: %s", attempt + 1, exc)
                if attempt < max_retries:
                    await asyncio.sleep(2**attempt)
        assert last_exc is not None
        raise last_exc

    async def _run_once(self, prompt: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            self._cli_path,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise KimiCliTimeoutError(f"kimi CLI 超时({self._timeout}s)") from None
        if proc.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace")[:300]
            raise KimiCliError(f"kimi CLI 退出码 {proc.returncode}: {detail}")
        return _extract_assistant_text(stdout.decode("utf-8", errors="replace"))
