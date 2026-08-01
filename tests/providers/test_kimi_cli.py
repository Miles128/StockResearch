import asyncio
import json

import pytest

from stockresearch.data.providers.kimi_cli import (
    KimiCliClient,
    KimiCliNotAvailableError,
    KimiCliParseError,
    KimiCliTimeoutError,
    _extract_json_object,
)


async def _no_sleep(_seconds):
    return None


def _stream_json_line(text: str) -> bytes:
    obj = {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }
    return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")


class FakeProc:
    def __init__(self, stdout: bytes, returncode: int = 0, sleep: float = 0.0):
        self._stdout = stdout
        self.returncode = returncode
        self._sleep = sleep
        self.killed = False

    async def communicate(self):
        if self._sleep:
            await asyncio.sleep(self._sleep)
        return self._stdout, b""

    def kill(self):
        self.killed = True
        self.returncode = -9

    async def wait(self):
        return self.returncode


def _patch_proc(monkeypatch, proc):
    async def fake_exec(*args, **kwargs):
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)


def test_extract_json_object_plain() -> None:
    assert _extract_json_object('{"a": 1}') == {"a": 1}


def test_extract_json_object_fenced_and_noisy() -> None:
    text = '好的,结果如下:\n```json\n{"a": 1, "b": [2]}\n```\n完毕'
    assert _extract_json_object(text) == {"a": 1, "b": [2]}


def test_extract_json_object_invalid() -> None:
    with pytest.raises(KimiCliParseError):
        _extract_json_object("没有任何 JSON")


def test_available_false_for_missing_binary() -> None:
    client = KimiCliClient(cli_path="/nonexistent/kimi-binary")
    assert client.available() is False


async def test_query_json_success(monkeypatch) -> None:
    _patch_proc(monkeypatch, FakeProc(_stream_json_line('{"cpi_yoy": 0.3}')))
    client = KimiCliClient(cli_path="/bin/echo", timeout=5)
    result = await client.query_json("查 CPI")
    assert result.payload == {"cpi_yoy": 0.3}
    assert "cpi_yoy" in result.raw_text


async def test_query_json_not_available() -> None:
    client = KimiCliClient(cli_path="/nonexistent/kimi-binary")
    with pytest.raises(KimiCliNotAvailableError):
        await client.query_json("查 CPI")


async def test_query_json_timeout_kills_process(monkeypatch) -> None:
    proc = FakeProc(b"", sleep=1.0)
    _patch_proc(monkeypatch, proc)
    client = KimiCliClient(cli_path="/bin/echo", timeout=0.05)
    with pytest.raises(KimiCliTimeoutError):
        await client.query_json("查 CPI", max_retries=0)
    assert proc.killed is True


async def test_query_json_retries_then_succeeds(monkeypatch) -> None:
    calls = {"n": 0}

    async def fake_exec(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            return FakeProc(b"garbage\n", returncode=0)
        return FakeProc(_stream_json_line('{"ok": true}'))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    client = KimiCliClient(cli_path="/bin/echo", timeout=5)
    result = await client.query_json("查 CPI", max_retries=2)
    assert result.payload == {"ok": True}
    assert calls["n"] == 3
