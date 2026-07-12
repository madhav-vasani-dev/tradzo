"""APScheduler setup — weekday morning jobs, all in IST.

Jobs (Mon–Fri):
  08:00  refresh_broker_tokens        — flag lapsed tokens (Upstox has no refresh)
  08:05  compute_readiness_snapshot   — cache readiness for the admin panel
  09:15  execute_morning_strategies   — place orders for active deployments
  09:15  log_market_open              — write a strategy_triggered marker log
"""
import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import IST, settings
from services import execution_service
from utils import logger as activity

log = logging.getLogger("tradzo.scheduler")

_scheduler: AsyncIOScheduler | None = None
_WEEKDAYS = "mon-fri"


def _run_async(coro_fn):
    """Wrap an async job so APScheduler can schedule it as a sync callable."""
    def _job():
        asyncio.run(coro_fn())
    return _job


def _log_market_open():
    activity.log_activity(
        type="strategy_triggered",
        message="Market open — morning execution window started (09:15 IST).",
        severity="info",
    )


def start_scheduler() -> AsyncIOScheduler | None:
    global _scheduler
    if not settings.enable_scheduler:
        log.info("Scheduler disabled via ENABLE_SCHEDULER=false.")
        return None
    if _scheduler is not None:
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone=IST)

    _scheduler.add_job(
        execution_service.refresh_broker_tokens,
        CronTrigger(day_of_week=_WEEKDAYS, hour=8, minute=0, timezone=IST),
        id="refresh_broker_tokens", replace_existing=True,
    )
    _scheduler.add_job(
        execution_service.compute_readiness,
        CronTrigger(day_of_week=_WEEKDAYS, hour=8, minute=5, timezone=IST),
        id="compute_readiness_snapshot", replace_existing=True,
    )
    _scheduler.add_job(
        _run_async(execution_service.execute_morning_strategies),
        CronTrigger(day_of_week=_WEEKDAYS, hour=9, minute=15, timezone=IST),
        id="execute_morning_strategies", replace_existing=True,
    )
    _scheduler.add_job(
        _log_market_open,
        CronTrigger(day_of_week=_WEEKDAYS, hour=9, minute=15, timezone=IST),
        id="log_market_open", replace_existing=True,
    )

    _scheduler.start()
    log.info("Scheduler started (IST) with %d jobs.", len(_scheduler.get_jobs()))
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
