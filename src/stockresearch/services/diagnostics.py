"""Provider doctor — one-shot diagnostics snapshot for BYOK troubleshooting.

Snapshots LLM configuration (masked), probes each data-source layer with a
lightweight real call, and reports environment facts.  It never auto-fixes:
it tells the user what is broken and where to change it.
"""

from __future__ import annotations

import importlib.util
import logging
import platform
import time
from datetime import UTC, datetime
from urllib.parse import urlparse

from stockresearch.core.config import get_settings
from stockresearch.core.llm_config import LlmOverrides
from stockresearch.core.schemas import DiagnosticItemOut, DiagnosticsOut
from stockresearch.data.providers.base import run_sync_fetch
from stockresearch.utils.llm_test import verify_llm_connection

logger = logging.getLogger(__name__)

_PROBE_SYMBOL = "600519"
_PROBE_TIMEOUT_SEC = 10.0


def _host_of(url: str) -> str:
    """Mask a base URL down to scheme://host (never leak paths/keys)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    except ValueError:
        pass
    return url


def _mask_key(key: str) -> str:
    stripped = (key or "").strip()
    if len(stripped) <= 8:
        return "" if not stripped else "****"
    return f"****{stripped[-4:]}"


def _ok(key: str, label: str, detail: str, *, elapsed_ms: int | None = None) -> DiagnosticItemOut:
    return DiagnosticItemOut(key=key, label=label, ok=True, detail=detail, elapsed_ms=elapsed_ms)


def _fail(
    key: str,
    label: str,
    detail: str,
    hint: str | None = None,
    *,
    elapsed_ms: int | None = None,
) -> DiagnosticItemOut:
    return DiagnosticItemOut(
        key=key, label=label, ok=False, detail=detail, hint=hint, elapsed_ms=elapsed_ms
    )


def _llm_hint_for(error_text: str) -> str:
    lower = error_text.lower()
    if "http 401" in lower or "401" in error_text:
        return "API Key 无效或未授权：检查 .env 的 LLM_API_KEY，或设置页重新填写"
    if "http 403" in lower or "403" in error_text:
        return "权限不足或配额耗尽：检查账号余额/模型权限，或更换模型名"
    if "http 404" in lower or "404" in error_text:
        return "接口路径不对：检查 LLM_BASE_URL 是否包含 /v1 等必要路径"
    if "timeout" in lower or "timed out" in lower or "无法访问" in error_text:
        return "连接超时/不可达：检查网络、VPN/代理，或在 .env 配置 LLM_HTTP_PROXY"
    return "详见错误信息；常见排查：Key/Base URL/模型名三者之一有误"


async def _probe_llm() -> DiagnosticItemOut:
    settings = get_settings()
    if settings.use_mock_llm:
        return _ok(
            "llm",
            "大模型（LLM）",
            "Mock 模式（USE_MOCK_LLM=true）——不发起真实请求，配置未验证",
        )
    host = _host_of(settings.llm_base_url)
    detail = (
        f"模型 {settings.llm_model.strip() or '未配置'} · 服务 {host or '未配置'} · "
        f"Key {_mask_key(settings.llm_api_key)} · 超时 {settings.llm_timeout_seconds}s"
    )
    start = time.monotonic()
    overrides = LlmOverrides(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        temperature=0.3,
        use_mock=settings.use_mock_llm,
    )
    err = await verify_llm_connection(overrides)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    if err:
        return _fail(
            "llm", "大模型（LLM）", f"{detail} → {err}", _llm_hint_for(err), elapsed_ms=elapsed_ms
        )
    return _ok("llm", "大模型（LLM）", f"{detail} → 连通正常", elapsed_ms=elapsed_ms)


async def _probe_sina() -> DiagnosticItemOut:
    from stockresearch.data.providers.market.common import _use_mock_market_data
    from stockresearch.data.providers.market.quotes import QuoteProvider

    start = time.monotonic()
    quotes = await QuoteProvider().get_quotes([_PROBE_SYMBOL], force_refresh=True)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    q = quotes.get(_PROBE_SYMBOL)
    if q is None:
        return _fail(
            "sina_quote",
            "实时行情（新浪主源）",
            f"探针返回空（{_PROBE_SYMBOL} 无报价）",
            "检查网络；行情会自动走 AkShare/efinance 兜底",
            elapsed_ms=elapsed_ms,
        )
    if _use_mock_market_data():
        return _ok(
            "sina_quote",
            "实时行情（新浪主源）",
            "Mock 模式（USE_MOCK_MARKET_DATA=true）——返回模拟行情",
            elapsed_ms=elapsed_ms,
        )
    return _ok(
        "sina_quote",
        "实时行情（新浪主源）",
        f"获取 {_PROBE_SYMBOL} 报价成功",
        elapsed_ms=elapsed_ms,
    )


async def _probe_akshare_kline() -> DiagnosticItemOut:
    from stockresearch.data.providers.akshare_quote import fetch_akshare_hist_quotes

    start = time.monotonic()
    rows = await run_sync_fetch(
        "doctor akshare kline probe",
        lambda: fetch_akshare_hist_quotes([_PROBE_SYMBOL]),
        timeout=_PROBE_TIMEOUT_SEC,
        fallback=None,
    )
    elapsed_ms = int((time.monotonic() - start) * 1000)
    row = (rows or {}).get(_PROBE_SYMBOL)
    if row is None:
        return _fail(
            "akshare_kline",
            "K 线与财务（AkShare 主源）",
            "探针返回空（无历史行情）",
            "检查网络；日 K 会走 efinance/Tushare/新浪兜底",
            elapsed_ms=elapsed_ms,
        )
    return _ok(
        "akshare_kline",
        "K 线与财务（AkShare 主源）",
        f"获取 {_PROBE_SYMBOL} 历史行情成功",
        elapsed_ms=elapsed_ms,
    )


def _probe_efinance() -> DiagnosticItemOut:
    if importlib.util.find_spec("efinance") is None:
        return _fail("efinance", "行情兜底（efinance）", "包未安装", "运行 uv sync 后重试")
    return _ok("efinance", "行情兜底（efinance）", "包已安装（按需调用）")


def _probe_tushare() -> DiagnosticItemOut:
    from stockresearch.data.providers.tushare_financial import probe_tushare_token

    start = time.monotonic()
    status = probe_tushare_token()
    elapsed_ms = int((time.monotonic() - start) * 1000)
    if status == "no_token":
        return _ok(
            "tushare",
            "财务兜底（Tushare Pro，可选）",
            "未配置 Token——不影响主链路",
            elapsed_ms=elapsed_ms,
        )
    if status == "ok":
        return _ok(
            "tushare",
            "财务兜底（Tushare Pro，可选）",
            "Token 有效，接口连通",
            elapsed_ms=elapsed_ms,
        )
    hints = {
        "unavailable": "包未安装，运行 uv sync 后重试",
        "invalid": "Token 无效：检查设置页/环境变量中的 Tushare Token",
        "quota": "账号积分/权限不足：部分接口将不可用，主链路不受影响",
    }
    return _fail(
        "tushare",
        "财务兜底（Tushare Pro，可选）",
        f"探针状态：{status}",
        hints.get(status),
        elapsed_ms=elapsed_ms,
    )


def _env_items() -> list[DiagnosticItemOut]:
    settings = get_settings()
    return [
        _ok("python", "Python 版本", platform.python_version()),
        _ok("platform", "运行平台", f"{platform.system()} {platform.release()}"),
        _ok("tz", "时区", datetime.now().astimezone().tzname() or "未知"),
        _ok(
            "mock_flags",
            "Mock 开关",
            f"LLM: {'开' if settings.use_mock_llm else '关'} · "
            f"行情: {'开' if settings.use_mock_market_data else '关'}",
        ),
    ]


async def run_diagnostics() -> DiagnosticsOut:
    """Run every probe; failures never cascade into later probes."""
    llm = await _probe_llm()
    sina = await _probe_sina()
    akshare = await _probe_akshare_kline()
    providers = [sina, akshare, _probe_efinance(), _probe_tushare()]
    return DiagnosticsOut(
        llm=llm,
        providers=providers,
        env=_env_items(),
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
