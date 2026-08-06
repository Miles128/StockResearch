"""Independent background worker for scheduled tasks.

Runs price alerts and briefing generation outside the uvicorn API process.
Start with:

    uv run python -m stockresearch worker

Or, after install:

    stockresearch worker
"""

from __future__ import annotations

import asyncio
import logging
import signal

from stockresearch.db.session import init_db
from stockresearch.services.briefing_scheduler import get_scheduler
from stockresearch.services.daily_bar_scheduler import get_daily_bar_scheduler
from stockresearch.services.kimi_prefetch_scheduler import get_kimi_prefetch_scheduler
from stockresearch.services.prediction_scheduler import get_prediction_scoring_scheduler
from stockresearch.services.price_alert_scheduler import get_price_alert_scheduler
from stockresearch.services.scheduler_lock import scheduler_lock

logger = logging.getLogger(__name__)


async def run_worker() -> int:
    """Start schedulers and block until SIGINT/SIGTERM.

    Returns 1 (without starting schedulers) if another process already
    holds the scheduler lock — e.g. the API process with
    ``RUN_SCHEDULERS_IN_API=true``. Returns 0 on normal shutdown.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    init_db()
    with scheduler_lock() as lock_acquired:
        if not lock_acquired:
            logger.error(
                "Another process holds the scheduler lock. "
                "Stop the other scheduler process (or set RUN_SCHEDULERS_IN_API=false) "
                "before starting the worker."
            )
            return 1
        get_scheduler().start()
        get_price_alert_scheduler().start()
        get_daily_bar_scheduler().start()
        get_prediction_scoring_scheduler().start()
        get_kimi_prefetch_scheduler().start()

        stop_event = asyncio.Event()

        def _on_signal(signum: int, _frame: object) -> None:
            sig_name = signal.Signals(signum).name
            logger.info("Received %s, shutting down worker...", sig_name)
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, _on_signal)

        logger.info("StockResearch worker running. Press Ctrl+C to stop.")
        try:
            await stop_event.wait()
        finally:
            get_kimi_prefetch_scheduler().shutdown()
            get_daily_bar_scheduler().shutdown()
            get_prediction_scoring_scheduler().shutdown()
            get_price_alert_scheduler().shutdown()
            get_scheduler().shutdown()
            logger.info("StockResearch worker stopped.")
    return 0
