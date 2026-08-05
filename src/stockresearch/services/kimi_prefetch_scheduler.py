"""Kimi 数据源定时预取:交易日前/盘后批量拉取宏观与 Wind 深度数据写入缓存。

这是系统中唯一批量真实调用 kimi CLI 的路径(按次消耗会员配额),
任务清单固定,失败最多由 CLI 层重试,超限等下个调度窗口。
"""

from __future__ import annotations

import logging
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from stockresearch.core.config import get_settings
from stockresearch.data.providers.kimi_macro import KimiMacroProvider
from stockresearch.data.providers.kimi_wind import KimiWindProvider
from stockresearch.services.trading_calendar import is_a_share_trading_day

logger = logging.getLogger(__name__)


class KimiPrefetchScheduler:
    """交易日 8:20 / 16:20 预取 Kimi 宏观与 Wind 数据。"""

    def __init__(
        self,
        macro_provider: KimiMacroProvider | None = None,
        wind_provider: KimiWindProvider | None = None,
    ) -> None:
        self._scheduler: AsyncIOScheduler | None = None
        self._macro = macro_provider or KimiMacroProvider()
        self._wind = wind_provider or KimiWindProvider()

    @property
    def enabled(self) -> bool:
        return get_settings().kimi_cli_enabled

    def start(self) -> None:
        if self._scheduler is not None:
            return
        self._scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        for hour, minute in ((8, 20), (16, 20)):
            self._scheduler.add_job(
                self._prefetch,
                trigger=CronTrigger(hour=hour, minute=minute, day_of_week="mon-fri"),
                id=f"kimi-prefetch-{hour:02d}{minute:02d}",
                replace_existing=True,
            )
        self._scheduler.start()
        logger.info("Kimi prefetch scheduler started (enabled=%s)", self.enabled)

    def shutdown(self) -> None:
        if self._scheduler is None:
            return
        self._scheduler.shutdown(wait=False)
        self._scheduler = None
        logger.info("Kimi prefetch scheduler stopped")

    async def _prefetch(self) -> None:
        if not self.enabled:
            return
        if not is_a_share_trading_day(date.today()):
            logger.info("非交易日,跳过 Kimi 预取")
            return
        for name, fetch in (
            ("kimi_macro", self._macro.get_macro_snapshot),
            ("kimi_wind", self._wind.get_daily_digest),
        ):
            try:
                payload = await fetch(refresh=True)
                logger.info("Kimi 预取 %s: %s", name, "成功" if payload else "空结果")
            except Exception as exc:  # 单个失败不阻塞其余任务
                logger.warning("Kimi 预取 %s 失败: %s", name, exc)


_scheduler: KimiPrefetchScheduler | None = None


def get_kimi_prefetch_scheduler() -> KimiPrefetchScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = KimiPrefetchScheduler()
    return _scheduler
