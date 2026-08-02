import stockresearch.services.kimi_prefetch_scheduler as mod
from stockresearch.services.kimi_prefetch_scheduler import KimiPrefetchScheduler


class FakeSettings:
    kimi_cli_enabled = True


class FakeProvider:
    def __init__(self, marker: str):
        self.calls = 0
        self._marker = marker

    async def get_macro_snapshot(self, *, refresh: bool = False):
        assert refresh is True
        self.calls += 1
        return {"marker": self._marker}

    async def get_daily_digest(self, *, refresh: bool = False):
        assert refresh is True
        self.calls += 1
        return {"marker": self._marker}


class _Disabled:
    kimi_cli_enabled = False


def _patch(monkeypatch, *, enabled=True, trading_day=True):
    monkeypatch.setattr(mod, "get_settings", lambda: FakeSettings() if enabled else _Disabled())
    monkeypatch.setattr(mod, "is_a_share_trading_day", lambda d: trading_day)


async def test_prefetch_calls_both_providers(monkeypatch) -> None:
    _patch(monkeypatch)
    macro, wind = FakeProvider("m"), FakeProvider("w")
    s = KimiPrefetchScheduler(macro_provider=macro, wind_provider=wind)
    await s._prefetch()
    assert macro.calls == 1 and wind.calls == 1


async def test_prefetch_skips_when_disabled(monkeypatch) -> None:
    _patch(monkeypatch, enabled=False)
    macro, wind = FakeProvider("m"), FakeProvider("w")
    s = KimiPrefetchScheduler(macro_provider=macro, wind_provider=wind)
    await s._prefetch()
    assert macro.calls == 0 and wind.calls == 0


async def test_prefetch_skips_non_trading_day(monkeypatch) -> None:
    _patch(monkeypatch, trading_day=False)
    macro, wind = FakeProvider("m"), FakeProvider("w")
    s = KimiPrefetchScheduler(macro_provider=macro, wind_provider=wind)
    await s._prefetch()
    assert macro.calls == 0 and wind.calls == 0


async def test_prefetch_continues_when_one_provider_fails(monkeypatch) -> None:
    _patch(monkeypatch)

    class FailProvider:
        async def get_macro_snapshot(self, *, refresh: bool = False):
            raise RuntimeError("boom")

    wind = FakeProvider("w")
    s = KimiPrefetchScheduler(macro_provider=FailProvider(), wind_provider=wind)
    await s._prefetch()
    assert wind.calls == 1
