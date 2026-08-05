"""Lifespan scheduler-lock behaviour for the API process.

Regression guard: the API must NOT grab the cross-process scheduler lock when
``run_schedulers_in_api`` is false — otherwise the worker process can never
acquire it and scheduled jobs (briefings / price alerts / daily bars) silently
never run. When the API *does* own the schedulers, it must still acquire the
lock and start/stop them.
"""

from __future__ import annotations

import pytest

from stockresearch.api import app as app_module


class FakeLock:
    """Records whether scheduler_lock() was invoked and what it yielded."""

    def __init__(self, acquired: bool) -> None:
        self.acquired = acquired
        self.entered = False
        self.exited = False

    def __enter__(self) -> bool:
        self.entered = True
        return self.acquired

    def __exit__(self, *exc: object) -> bool:
        self.exited = True
        return False


class FakeScheduler:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def shutdown(self) -> None:
        self.stopped = True


class FakeSettings:
    def __init__(self, run_schedulers_in_api: bool) -> None:
        self.run_schedulers_in_api = run_schedulers_in_api


def _patch(
    monkeypatch: pytest.MonkeyPatch, *, in_api: bool
) -> tuple[FakeLock, FakeScheduler, FakeScheduler]:
    fake_lock = FakeLock(acquired=True)
    sched = FakeScheduler()
    alerts = FakeScheduler()
    monkeypatch.setattr(app_module, "get_settings", lambda: FakeSettings(in_api))
    monkeypatch.setattr(app_module, "scheduler_lock", lambda: fake_lock)
    monkeypatch.setattr(app_module, "get_scheduler", lambda: sched)
    monkeypatch.setattr(app_module, "get_price_alert_scheduler", lambda: alerts)
    return fake_lock, sched, alerts


async def test_lifespan_does_not_grab_lock_when_schedulers_in_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_schedulers_in_api=false → lock must stay available for the worker."""
    fake_lock, _sched, _alerts = _patch(monkeypatch, in_api=False)
    async with app_module.lifespan(None):
        pass
    assert fake_lock.entered is False, "API must not acquire the scheduler lock"


async def test_lifespan_acquires_lock_and_starts_schedulers_when_in_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_schedulers_in_api=true → lock acquired, schedulers started/stopped."""
    fake_lock, sched, alerts = _patch(monkeypatch, in_api=True)
    async with app_module.lifespan(None):
        assert fake_lock.entered is True
        assert sched.started is True
        assert alerts.started is True
    assert fake_lock.exited is True
    assert sched.stopped is True
    assert alerts.stopped is True


async def test_lifespan_skips_schedulers_when_lock_held_elsewhere(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """API owns schedulers but the lock is held → start nothing, keep lock held."""
    fake_lock = FakeLock(acquired=False)
    sched = FakeScheduler()
    alerts = FakeScheduler()
    monkeypatch.setattr(app_module, "get_settings", lambda: FakeSettings(True))
    monkeypatch.setattr(app_module, "scheduler_lock", lambda: fake_lock)
    monkeypatch.setattr(app_module, "get_scheduler", lambda: sched)
    monkeypatch.setattr(app_module, "get_price_alert_scheduler", lambda: alerts)

    async with app_module.lifespan(None):
        assert fake_lock.entered is True
        assert sched.started is False
        assert alerts.started is False
    assert fake_lock.exited is True
    assert sched.stopped is False
