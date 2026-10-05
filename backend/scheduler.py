"""APScheduler setup — all jobs in IST.

Nifty straddle (Mon–Fri):
  08:00     reset_daily_statuses  — reset userStrategy.status to "enabled"
  11:55     pre_entry_check       — validate tokens, set status="ready" (Nifty only)
  11:59:45  execute_entry         — pre-stage, then place straddle orders + SL at 12:00:00
  15:29     execute_exit          — cancel SL orders, square off remaining
  15:29:30  execute_exit (retry)  — re-run ONLY legs the first pass tried and failed to close
  15:31     eod_cleanup           — compute PnL, log day summary

Crude Oil Mini — MCX CRUDEOILM straddle (Mon–Fri):
  15:25     pre_entry_check_crude — Kotak logins, warm MCX instruments, status="ready"
  15:29:45  execute_crude_entry   — pre-stage, then sell ATM CE + PE at 15:30:00 + 20% SL
  23:24     execute_crude_exit    — cancel SL orders, square off remaining
  23:24:30  execute_crude_exit (retry)
  23:27     execute_crude_exit (last retry, before the 23:30 close)
  23:28     eod_cleanup_crude

Kotak Neo (Mon–Fri):
  08:45     kotak_daily_login     — fresh TOTP + MPIN session for every connected account

BTC option selling (every day):
  16:56     pre_entry_check_btc   — validate Delta accounts, set status="ready"
  17:00:45  execute_btc_entry     — pre-stage, then sell ATM BTC CE + PE at 17:01:00
  17:29     execute_btc_exit      — cancel SL orders, square off BTC positions

Continuous:
  every minute  sync_order_statuses — poll open positions for SL/target hits

Entry jobs are scheduled `settings.entry_prestage_lead_seconds` EARLY. The job spends
that lead window on Firestore reads, token decryption, instrument resolution and the
market snapshot, then sleeps to the exact entry second before sending any order — so
the fill lands at 12:00:00 rather than drifting out to 12:00:12.
"""
import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import IST, settings
from services import crude_execution, execution_service, kotak_service

log = logging.getLogger("tradzo.scheduler")

_scheduler: AsyncIOScheduler | None = None
_WEEKDAYS = "mon-fri"


def _prestage_trigger(entry_time: str, day_of_week: str) -> CronTrigger:
    """CronTrigger that fires `entry_prestage_lead_seconds` before `entry_time` ("HH:MM")."""
    hour, minute = (int(part) for part in entry_time.split(":", 1))
    lead = max(0, int(settings.entry_prestage_lead_seconds))
    fire_at = datetime(2000, 1, 1, hour, minute) - timedelta(seconds=lead)
    log.info("Entry %s will pre-stage at %s (lead %ds).",
             entry_time, fire_at.strftime("%H:%M:%S"), lead)
    return CronTrigger(
        day_of_week=day_of_week,
        hour=fire_at.hour,
        minute=fire_at.minute,
        second=fire_at.second,
        timezone=IST,
    )


def _hm(value: str) -> tuple[int, int]:
    hour, minute = (int(part) for part in str(value).split(":", 1))
    return hour, minute


def _run_async(coro_fn):
    """Wrap an async coroutine so APScheduler can schedule it as a sync callable."""
    def _job():
        asyncio.run(coro_fn())
    return _job


def _run_sync(fn):
    """Wrap a sync function for APScheduler (no-op wrapper for clarity)."""
    return fn


def start_scheduler() -> AsyncIOScheduler | None:
    global _scheduler
    if not settings.enable_scheduler:
        log.info("Scheduler disabled via ENABLE_SCHEDULER=false.")
        return None
    if _scheduler is not None:
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone=IST)

    # ── 08:00 — Reset all userStrategy statuses to "enabled" ──────────────
    _scheduler.add_job(
        _run_sync(execution_service.reset_daily_statuses),
        CronTrigger(day_of_week=_WEEKDAYS, hour=8, minute=0, timezone=IST),
        id="reset_daily_statuses",
        replace_existing=True,
    )

    # ── 11:55 — Pre-entry token validation + set status="ready" ───────────
    _scheduler.add_job(
        _run_sync(execution_service.pre_entry_check),
        CronTrigger(day_of_week=_WEEKDAYS, hour=11, minute=55, timezone=IST),
        id="pre_entry_check",
        replace_existing=True,
    )

    # ── 11:59:45 — Pre-stage, then fire SELL + SL orders at 12:00:00 sharp ─
    _scheduler.add_job(
        _run_async(execution_service.execute_entry),
        _prestage_trigger(execution_service.NIFTY_ENTRY_TIME, _WEEKDAYS),
        id="execute_entry",
        replace_existing=True,
        misfire_grace_time=10,
    )

    # ── Active Order Polling (every 1 minute 24/7 for crypto + equity) ──────
    _scheduler.add_job(
        _run_async(execution_service.sync_order_statuses),
        CronTrigger(day_of_week="*", hour="*", minute="*", timezone=IST),
        id="sync_order_statuses",
        replace_existing=True,
    )

    # ── 15:29 — Nifty Exit: cancel SL orders, square off remaining positions ─
    _scheduler.add_job(
        _run_async(execution_service.execute_exit),
        CronTrigger(day_of_week=_WEEKDAYS, hour=15, minute=29, timezone=IST),
        id="execute_exit",
        replace_existing=True,
        misfire_grace_time=45,    # default is 1s: a brief stall would silently skip the exit
    )

    # ── 15:29:30 — Exit retry: only touches legs still open/closing after the first pass
    #    (e.g. an exit order that didn't fill). Position claims make it safe to overlap. ─
    _scheduler.add_job(
        _run_async(lambda: execution_service.execute_exit(retry=True)),
        CronTrigger(day_of_week=_WEEKDAYS, hour=15, minute=29, second=30, timezone=IST),
        id="execute_exit_retry",
        replace_existing=True,
        misfire_grace_time=20,
    )

    # ── 15:31 — EOD: compute PnL, log daily summary ───────────────────────
    _scheduler.add_job(
        _run_sync(execution_service.eod_cleanup),
        CronTrigger(day_of_week=_WEEKDAYS, hour=15, minute=31, timezone=IST),
        id="eod_cleanup",
        replace_existing=True,
    )

    # ── Kotak Neo — daily automatic login (TOTP + MPIN) ──────────────────
    k_h, k_m = _hm(getattr(settings, "kotak_daily_login_time", "08:45"))
    _scheduler.add_job(
        _run_async(kotak_service.daily_login_all),
        CronTrigger(day_of_week=_WEEKDAYS, hour=k_h, minute=k_m, timezone=IST),
        id="kotak_daily_login",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # ── Crude Oil Mini (MCX) — 15:30 entry, 23:24 exit ────────────────────
    ce_h, ce_m = _hm(crude_execution.entry_time())
    pre_at = datetime(2000, 1, 1, ce_h, ce_m) - timedelta(minutes=5)
    _scheduler.add_job(
        _run_sync(crude_execution.pre_entry_check_crude),
        CronTrigger(day_of_week=_WEEKDAYS, hour=pre_at.hour, minute=pre_at.minute, timezone=IST),
        id="pre_entry_check_crude",
        replace_existing=True,
        misfire_grace_time=120,
    )
    _scheduler.add_job(
        _run_async(crude_execution.execute_crude_entry),
        _prestage_trigger(crude_execution.entry_time(), _WEEKDAYS),
        id="execute_crude_entry",
        replace_existing=True,
        misfire_grace_time=10,
    )
    cx_h, cx_m = _hm(crude_execution.exit_time())
    _scheduler.add_job(
        _run_async(crude_execution.execute_crude_exit),
        CronTrigger(day_of_week=_WEEKDAYS, hour=cx_h, minute=cx_m, timezone=IST),
        id="execute_crude_exit",
        replace_existing=True,
        misfire_grace_time=45,
    )
    _scheduler.add_job(
        _run_async(lambda: crude_execution.execute_crude_exit(retry=True)),
        CronTrigger(day_of_week=_WEEKDAYS, hour=cx_h, minute=cx_m, second=30, timezone=IST),
        id="execute_crude_exit_retry",
        replace_existing=True,
        misfire_grace_time=20,
    )
    # Last-chance pass ~3 min later — still before the 23:30 MCX close (US summer time) —
    # for any leg whose exit failed twice; an MCX leg left open carries overnight (NRML).
    late = datetime(2000, 1, 1, cx_h, cx_m) + timedelta(minutes=3)
    _scheduler.add_job(
        _run_async(lambda: crude_execution.execute_crude_exit(retry=True)),
        CronTrigger(day_of_week=_WEEKDAYS, hour=late.hour, minute=late.minute, timezone=IST),
        id="execute_crude_exit_last_retry",
        replace_existing=True,
        misfire_grace_time=30,
    )
    eod_at = datetime(2000, 1, 1, cx_h, cx_m) + timedelta(minutes=4)
    _scheduler.add_job(
        _run_sync(crude_execution.eod_cleanup_crude),
        CronTrigger(day_of_week=_WEEKDAYS, hour=eod_at.hour, minute=eod_at.minute, timezone=IST),
        id="eod_cleanup_crude",
        replace_existing=True,
    )

    # ── 16:56 — BTC pre-entry check (5 min before the 17:01 BTC entry) ────────
    _scheduler.add_job(
        _run_sync(execution_service.pre_entry_check_btc),
        CronTrigger(day_of_week="*", hour=16, minute=56, timezone=IST),
        id="pre_entry_check_btc",
        replace_existing=True,
    )

    # ── 17:00:45 — Pre-stage, then sell ATM BTC CE + PE at 17:01:00 sharp ─────
    _scheduler.add_job(
        _run_async(execution_service.execute_btc_entry),
        _prestage_trigger(execution_service.BTC_ENTRY_TIME, "*"),
        id="execute_btc_entry",
        replace_existing=True,
        misfire_grace_time=10,
    )

    # ── 17:29 — BTC exit: cancel SL orders, square off BTC positions (365 days) 
    _scheduler.add_job(
        _run_async(execution_service.execute_btc_exit),
        CronTrigger(day_of_week="*", hour=17, minute=29, timezone=IST),
        id="execute_btc_exit",
        replace_existing=True,
    )

    _scheduler.start()
    log.info("Scheduler started (IST) with %d jobs.", len(_scheduler.get_jobs()))
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
