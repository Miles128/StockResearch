"""Cross-process mutex lock for scheduler processes.

Prevents briefing / price-alert / daily-bar schedulers from running in both
the API process (``RUN_SCHEDULERS_IN_API=true``) and the worker process
simultaneously, which would otherwise cause duplicate briefing generation
and duplicate price-alert evaluation (APScheduler has no cross-process lock).

Uses ``fcntl.flock`` (POSIX). On non-POSIX platforms the lock is a no-op
with a warning — callers must then ensure only one scheduler process runs.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from stockresearch.core.config import get_settings

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _lock_file_path() -> Path | None:
    """Resolve the scheduler lock file path next to the SQLite database.

    Returns ``None`` for in-memory databases (tests), where cross-process
    contention is not a concern.
    """
    url = get_settings().database_url
    if url == "sqlite://":
        return None
    if url.startswith("sqlite:///"):
        path_part = url.removeprefix("sqlite:///")
        if path_part.startswith("./"):
            db_path = _PROJECT_ROOT / path_part[2:]
        else:
            db_path = Path(path_part)
        return db_path.parent / "scheduler.lock"
    # Non-SQLite backends — fall back to the project root.
    return _PROJECT_ROOT / "scheduler.lock"


@contextmanager
def scheduler_lock() -> Iterator[bool]:
    """Try to acquire an exclusive cross-process lock for schedulers.

    Yields ``True`` if the lock was acquired (or is not applicable, e.g.
    in-memory DB / non-POSIX), ``False`` if another process holds the lock.

    On non-POSIX platforms (no ``fcntl``) yields ``True`` and logs a warning.
    """
    lock_path = _lock_file_path()
    if lock_path is None:
        # In-memory DB (tests) — no cross-process concern.
        yield True
        return

    try:
        import fcntl
    except ImportError:
        logger.warning(
            "fcntl not available (non-POSIX); scheduler lock disabled. "
            "Ensure only one scheduler process runs (worker OR API schedulers)."
        )
        yield True
        return

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "w")
    acquired = False
    try:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
            fh.write(f"{os.getpid()}\n")
            fh.flush()
            logger.info("Scheduler lock acquired at %s (pid=%s)", lock_path, os.getpid())
        except BlockingIOError:
            logger.warning(
                "Scheduler lock held by another process at %s; "
                "skipping scheduler startup in this process to avoid duplicate jobs. "
                "Run schedulers in only one process (worker OR API, not both).",
                lock_path,
            )
        yield acquired
    finally:
        if acquired:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()
