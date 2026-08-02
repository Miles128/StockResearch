from dataclasses import dataclass

from stockresearch.data.provider_meta import get_provider_meta
from stockresearch.data.providers.kimi_cli import KimiCliError
from stockresearch.data.providers.kimi_macro import MACRO_CACHE_KEY, KimiMacroProvider
from stockresearch.data.providers.kimi_wind import WIND_CACHE_KEY, KimiWindProvider
from stockresearch.services.sqlite_cache import get_sqlite_cached


@dataclass(frozen=True)
class FakeResult:
    payload: dict[str, object]
    raw_text: str = ""


class FakeClient:
    def __init__(self, payload=None, exc: Exception | None = None):
        self._payload = payload or {}
        self._exc = exc
        self.calls = 0

    async def query_json(self, prompt: str, *, max_retries: int = 2):
        self.calls += 1
        if self._exc is not None:
            raise self._exc
        return FakeResult(payload=self._payload)


def test_provider_meta_registered() -> None:
    macro = get_provider_meta("kimi_macro")
    wind = get_provider_meta("kimi_wind")
    assert macro is not None and macro.layer == "L2" and macro.default_ttl_seconds == 86400
    assert wind is not None and wind.layer == "L2" and wind.default_ttl_seconds == 21600


async def test_macro_snapshot_caches_result() -> None:
    payload = {"as_of": "2026-08-01", "indicators": [{"name": "CPI 同比", "value": "0.3%"}]}
    client = FakeClient(payload=payload)
    provider = KimiMacroProvider(client=client)  # type: ignore[arg-type]
    result = await provider.get_macro_snapshot()
    assert result["as_of"] == "2026-08-01"
    assert get_sqlite_cached(MACRO_CACHE_KEY) is not None
    # 第二次调用命中缓存,不再调 CLI
    result2 = await provider.get_macro_snapshot()
    assert result2 == result
    assert client.calls == 1


async def test_macro_failure_returns_empty_and_not_cached() -> None:
    client = FakeClient(exc=KimiCliError("boom"))
    provider = KimiMacroProvider(client=client)  # type: ignore[arg-type]
    assert await provider.get_macro_snapshot() == {}
    assert get_sqlite_cached(MACRO_CACHE_KEY) is None


async def test_macro_refresh_bypasses_cache_read() -> None:
    client = FakeClient(payload={"as_of": "2026-08-01", "indicators": []})
    provider = KimiMacroProvider(client=client)  # type: ignore[arg-type]
    await provider.get_macro_snapshot()
    await provider.get_macro_snapshot(refresh=True)
    assert client.calls == 2


async def test_wind_digest_caches_result() -> None:
    payload = {"as_of": "2026-08-01", "announcements": [{"title": "t"}], "research_reports": []}
    client = FakeClient(payload=payload)
    provider = KimiWindProvider(client=client)  # type: ignore[arg-type]
    result = await provider.get_daily_digest()
    assert result["announcements"] == [{"title": "t"}]
    assert get_sqlite_cached(WIND_CACHE_KEY) is not None


async def test_macro_empty_shell_not_cached() -> None:
    # 空壳 payload(只有 as_of,无 indicators/industry_highlights)不应写缓存
    client = FakeClient(payload={"as_of": "2026-08-01"})
    provider = KimiMacroProvider(client=client)  # type: ignore[arg-type]
    assert await provider.get_macro_snapshot() == {}
    assert get_sqlite_cached(MACRO_CACHE_KEY) is None


async def test_wind_empty_shell_not_cached() -> None:
    # 空壳 payload(只有 as_of,无 announcements/research_reports)不应写缓存
    client = FakeClient(payload={"as_of": "2026-08-01"})
    provider = KimiWindProvider(client=client)  # type: ignore[arg-type]
    assert await provider.get_daily_digest() == {}
    assert get_sqlite_cached(WIND_CACHE_KEY) is None


async def test_wind_empty_shell_not_cached_on_refresh() -> None:
    # refresh=True 走 _fetch_and_store 路径,同样不应写空壳缓存
    client = FakeClient(payload={"as_of": "2026-08-01"})
    provider = KimiWindProvider(client=client)  # type: ignore[arg-type]
    assert await provider.get_daily_digest(refresh=True) == {}
    assert get_sqlite_cached(WIND_CACHE_KEY) is None
