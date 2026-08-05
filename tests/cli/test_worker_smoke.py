"""worker.py 入口冒烟测试 — mock 全部外部依赖，覆盖锁冲突与正常启停。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from stockresearch import worker


class _FakeScheduler:
    """记录 start/shutdown 调用的假调度器。"""

    def __init__(self) -> None:
        self.start_calls = 0
        self.shutdown_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def shutdown(self) -> None:
        self.shutdown_calls += 1


def _patch_deps(
    monkeypatch: pytest.MonkeyPatch,
    *,
    lock_acquired: bool,
) -> dict[str, _FakeScheduler]:
    schedulers = {
        "briefing": _FakeScheduler(),
        "price_alert": _FakeScheduler(),
        "daily_bar": _FakeScheduler(),
        "kimi": _FakeScheduler(),
    }

    @contextmanager
    def fake_lock() -> Iterator[bool]:
        yield lock_acquired

    monkeypatch.setattr(worker, "init_db", lambda: None)
    monkeypatch.setattr(worker, "scheduler_lock", fake_lock)
    monkeypatch.setattr(worker, "get_scheduler", lambda: schedulers["briefing"])
    monkeypatch.setattr(worker, "get_price_alert_scheduler", lambda: schedulers["price_alert"])
    monkeypatch.setattr(worker, "get_daily_bar_scheduler", lambda: schedulers["daily_bar"])
    monkeypatch.setattr(worker, "get_kimi_prefetch_scheduler", lambda: schedulers["kimi"])

    # 注册信号处理器时立即触发 → stop_event 被 set → wait 立即返回
    def fake_signal(sig: int, handler: object) -> None:
        handler(sig, None)  # type: ignore[operator]

    monkeypatch.setattr(worker.signal, "signal", fake_signal)
    return schedulers


@pytest.mark.asyncio
async def test_worker_returns_1_when_lock_held(monkeypatch: pytest.MonkeyPatch) -> None:
    schedulers = _patch_deps(monkeypatch, lock_acquired=False)
    assert await worker.run_worker() == 1
    for s in schedulers.values():
        assert s.start_calls == 0
        assert s.shutdown_calls == 0


@pytest.mark.asyncio
async def test_worker_starts_and_stops_all_schedulers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schedulers = _patch_deps(monkeypatch, lock_acquired=True)
    assert await worker.run_worker() == 0
    for s in schedulers.values():
        assert s.start_calls == 1
        assert s.shutdown_calls == 1
