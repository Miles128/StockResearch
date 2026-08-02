"""Tests for the cross-process scheduler lock."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from stockresearch.services import scheduler_lock as lock_module
from stockresearch.services.scheduler_lock import scheduler_lock


def test_in_memory_db_yields_no_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    """In-memory SQLite (tests) skips the file lock entirely."""
    # conftest.py forces DATABASE_URL=sqlite://
    with scheduler_lock() as acquired:
        assert acquired is True


def test_file_db_acquires_then_blocks_second(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A file-based DB produces a real fcntl lock that blocks a second caller."""

    class FakeSettings:
        database_url = f"sqlite:///{tmp_path.as_posix()}/test.db"

    monkeypatch.setattr(lock_module, "get_settings", lambda: FakeSettings())

    lock_path = lock_module._lock_file_path()
    assert lock_path is not None
    assert lock_path.parent == tmp_path
    assert lock_path.name == "scheduler.lock"

    # First acquisition succeeds.
    with scheduler_lock() as first:
        assert first is True
        # While the first lock is held, a nested scheduler_lock on the same
        # process would re-lock the same inode — fcntl locks are per-process
        # (not per-fd) on POSIX, so the second open in the *same* process
        # succeeds. To truly simulate a second process we fork.
        pid = os.fork()
        if pid == 0:
            # Child process: should NOT acquire.
            with scheduler_lock() as child_acquired:
                os._exit(0 if child_acquired is False else 1)
        else:
            _, status = os.waitpid(pid, 0)
            exit_code = os.waitstatus_to_exitcode(status)
            assert exit_code == 0, "child should have failed to acquire the lock"


def test_lock_released_after_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """After the context exits, a forked child can acquire the lock."""

    class FakeSettings:
        database_url = f"sqlite:///{tmp_path.as_posix()}/test.db"

    monkeypatch.setattr(lock_module, "get_settings", lambda: FakeSettings())

    with scheduler_lock() as acquired:
        assert acquired is True

    # Lock should now be released; a forked child must succeed.
    pid = os.fork()
    if pid == 0:
        with scheduler_lock() as child_acquired:
            os._exit(0 if child_acquired is True else 1)
    else:
        _, status = os.waitpid(pid, 0)
        exit_code = os.waitstatus_to_exitcode(status)
        assert exit_code == 0, "child should acquire the lock after parent released"
