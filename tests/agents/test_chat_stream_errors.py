"""Chat stream 错误路径:面向用户的报错必须带可诊断细节。"""

import httpx

from stockresearch.agents.orchestrator.stream import _describe_request_error


def test_describe_request_error_includes_type_and_host() -> None:
    request = httpx.Request("POST", "https://apihub.agnes-ai.com/v1/chat/completions")
    exc = httpx.ConnectTimeout("timed out", request=request)
    assert _describe_request_error(exc) == "ConnectTimeout(apihub.agnes-ai.com)"


def test_describe_request_error_without_request_falls_back_to_type() -> None:
    exc = httpx.ConnectTimeout("timed out")
    assert _describe_request_error(exc) == "ConnectTimeout"


def test_describe_request_error_never_leaks_key_or_path() -> None:
    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions?api_key=sk-secret")
    exc = httpx.ConnectError("boom", request=request)
    detail = _describe_request_error(exc)
    assert "sk-secret" not in detail
    assert "/v1/chat" not in detail
    assert "api.example.com" in detail
