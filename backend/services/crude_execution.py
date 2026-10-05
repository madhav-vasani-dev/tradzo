"""Crude Oil Mini (MCX CRUDEOILM) straddle — daily jobs (IST, Mon–Fri).

  15:25     pre_entry_check_crude  — log in Kotak accounts, warm the MCX instrument cache,
                                     set deployments "ready"
  15:29:45  execute_crude_entry    — pre-stage, then SELL ATM CE + PE at 15:30:00 sharp and
                                     place a 20 % stop-limit on each leg
  23:24     execute_crude_exit     — cancel stop-losses, buy back open legs
  23:24:30  execute_crude_exit(retry=True)
  23:27     execute_crude_exit(retry=True) — last chance before the 23:30 close
  23:28     eod_cleanup_crude      — day summary for the crude legs

The fill / stop-loss / persistence / exit machinery is shared with the Nifty engine
(`execution_service._fire_and_protect`, `execution_service.execute_exit`); this module only
adds what is MCX-specific: contract selection, per-broker instrument resolution and sizing.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta

from config import settings
from services import execution_service as ex
from services import firebase_service, mcx_market_data, position_service
from strategies import get_strategy

log = logging.getLogger("tradzo.crude")

CRUDE_CODE = ex.CRUDE_CODE
SUPPORTED_BROKERS = ("kotak", "upstox", "jainam")


def entry_time() -> str:
    return str(getattr(settings, "crude_entry_time", "15:30"))


def exit_time() -> str:
    return str(getattr(settings, "crude_exit_time", "23:24"))


# ── 15:25 — pre-entry check ───────────────────────────────────────────────────

def pre_entry_check_crude() -> dict:
    """Validate brokers for enabled Crude deployments and mark them 'ready'.

    Kotak accounts are logged in here (TOTP + MPIN) if today's session is missing, so the
    entry itself never waits on a login. Also warms the Upstox MCX instrument cache.
    """
    today = ex._today()
    deployments = [d for d in firebase_service.list_deployments_by_status("enabled")
                   if d.get("strategyCode") == CRUDE_CODE]
    accounts = ex._accounts_by_id()
    users = ex._users_by_id()

    try:
        from services.kotak_service import run_sync
        run_sync(mcx_market_data.upstox_instruments())
    except Exception as exc:  # noqa: BLE001 — Kotak-only setups don't need it
        log.info("Upstox MCX instrument warm-up skipped: %s", exc)

    ready = skipped = 0
    for dep in deployments:
        if dep.get("pausedByAdmin"):
            skipped += 1
            continue
        user_doc = users.get(dep.get("userId"), {}) or {}
        paper = user_doc.get("paperTrading", True)
        broker = dep.get("brokerName", "upstox")
        account = accounts.get(dep.get("brokerAccountId", ""))
        if broker not in SUPPORTED_BROKERS and not paper:
            skipped += 1
            ex._log("token_invalid",
                    f"Crude Oil Mini cannot trade on '{broker}'. Redeploy it on Kotak Neo, Upstox or Jainam.",
                    severity="warning", date_str=today, user_id=dep.get("userId"),
                    strategy_id=dep.get("strategyId"))
            continue
        if paper or ex._is_token_valid(account):
            firebase_service.update_user_strategy_status(dep["id"], "ready")
            ready += 1
        else:
            skipped += 1
            ex._log("token_invalid",
                    f"Crude Oil Mini will be skipped today: {broker.title()} account is not connected or "
                    f"its login failed — reconnect it before {entry_time()}.",
                    severity="warning", date_str=today, user_id=dep.get("userId"),
                    strategy_id=dep.get("strategyId"))

    summary = {"ready": ready, "skipped": skipped}
    log.info("Crude pre-entry check: %s", summary)
    ex._log("pre_entry_check", f"Crude pre-entry check: {ready} ready, {skipped} skipped.", "info",
            date_str=today, metadata=summary)
    return summary


# ── 15:30 — entry ─────────────────────────────────────────────────────────────

def _stage(today: str) -> tuple[list[dict], int]:
    accounts = ex._accounts_by_id()
    users = ex._users_by_id()
    deployments = [
        d for d in (firebase_service.list_deployments_by_status("ready")
                    + firebase_service.list_deployments_by_status("enabled"))
        if d.get("strategyCode") == CRUDE_CODE and not d.get("pausedByAdmin")
    ]
    staged: list[dict] = []
    skipped = 0
    strategy = get_strategy(CRUDE_CODE)

    try:
        stale_deps = {p.get("userStrategyId") for p in position_service.get_stale_open_positions(today)
                      if p.get("strategyCode") == CRUDE_CODE}
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not check for earlier open crude legs: %s", exc)
        stale_deps = set()

    for dep in deployments:
        if position_service.get_open_positions_for_user_strategy(dep["id"], today):
            log.warning("Crude deployment %s already traded today — skipping.", dep["id"])
            skipped += 1
            continue
        if dep["id"] in stale_deps:
            ex._log("entry_error",
                    "Skipped Crude Oil Mini entry — a leg from an earlier day is still open. Close it "
                    "(or let the 23:24 exit close it) before a new straddle is sold.",
                    severity="error", date_str=today, user_id=dep.get("userId"),
                    strategy_id=dep.get("strategyId"))
            skipped += 1
            continue
        user_id = dep.get("userId")
        user_doc = users.get(user_id, {}) or {}
        paper = user_doc.get("paperTrading", True)
        user_name = user_doc.get("username") or user_doc.get("email") or "User"
        broker = dep.get("brokerName", "upstox")
        account = accounts.get(dep.get("brokerAccountId", ""))

        def _skip(msg: str):
            ex._log("token_invalid", msg, severity="warning", date_str=today, user_id=user_id,
                    user_name=user_name, strategy_id=dep.get("strategyId"), paper=paper)

        if not paper and broker not in SUPPORTED_BROKERS:
            _skip(f"Skipped Crude Oil Mini entry — broker '{broker}' does not support MCX in Tradzo.")
            skipped += 1
            continue

        md_token = None
        if paper:
            access_token = "paper_token"
        elif broker == "kotak":
            access_token = "kotak_pending" if (account and account.get("isConnected")) else None
        else:
            access_token = ex._get_token(account)
            if broker == "jainam" and access_token:
                md_token = ex._get_jainam_market_data_token(account)
                if not md_token:
                    _skip("Skipped Crude Oil Mini entry — Jainam market data token missing. Reconnect Jainam.")
                    skipped += 1
                    continue
        if not access_token:
            _skip("Skipped Crude Oil Mini entry — broker not connected or token expired. Please reconnect.")
            skipped += 1
            continue

        staged.append({
            "dep": dep, "strategy": strategy, "account": account, "paper": paper,
            "access_token": access_token, "user_id": user_id, "user_name": user_name,
            "broker": broker, "lots": int(dep.get("multiplier", 1) or 1), "md_token": md_token,
        })
    return staged, skipped


def _symbol(expiry: str, strike: float, opt: str) -> str:
    from datetime import datetime
    d = datetime.strptime(expiry, "%Y-%m-%d")
    k = int(strike) if float(strike).is_integer() else strike
    return f"CRUDEOILM{d.strftime('%d%b%y').upper()}{k}{opt}"


def _make_orders(item: dict, snap: dict) -> None:
    """Build the two SELL orders for one deployment from a snapshot (in place)."""
    legs = item["strategy"].get_entry_legs(item["dep"], snap["atm_strike"], snap["expiry"], item["lots"])
    item["legs"] = legs
    item["orders"] = []
    for leg in legs:
        opt = leg["optionType"]
        item["orders"].append({
            "item": item,
            "leg": leg,
            "option_type": opt,
            "qty": leg["quantity"],                     # lots — converted per broker below
            "tag_prefix": f"CR_{item['dep']['id'][:6].upper()}_{opt}",
            "instrument_key": snap["ce_key"] if opt == "CE" else snap["pe_key"],
            "ltp": float(snap["ce_ltp"] if opt == "CE" else snap["pe_ltp"]) or 0.0,
            "error": None,
            "exchange": "MCX",
            "symbol": (snap.get("ce_symbol") if opt == "CE" else snap.get("pe_symbol"))
                      or _symbol(snap["expiry"], snap["atm_strike"], opt),
            "pnl_multiplier": float(mcx_market_data.UNITS_PER_LOT),
            "extra": {"underlying": "CRUDEOILM", "futPriceAtEntry": snap.get("fut_price"),
                      "marketDataSource": snap.get("source")},
        })


def _fail_item(item: dict, err: Exception) -> None:
    for o in item.get("orders") or []:
        o["error"] = err


async def _resolve_jainam(item: dict, snap: dict) -> None:
    from services import jainam_service
    lot_sizes = set()
    for order in item["orders"]:
        res = await jainam_service.get_option_instrument(
            token=item["md_token"], symbol="CRUDEOILM", expiry_date_str=snap["expiry"],
            option_type=order["option_type"], strike_price=snap["atm_strike"],
            exchange_segment="MCXFO", series="OPTFUT",
        )
        lot = int(res.get("lotSize") or 0)
        if lot not in (1, mcx_market_data.UNITS_PER_LOT):
            raise RuntimeError(f"unexpected Jainam CRUDEOILM lot size {lot!r} — not sizing the order")
        lot_sizes.add(lot)
        order["extra"]["marketDataKey"] = order["instrument_key"]       # the Upstox key
        order["instrument_key"] = str(res["exchangeInstrumentID"])
        order["qty"] = order["qty"] * lot
        order["pnl_multiplier"] = mcx_market_data.UNITS_PER_LOT / lot


async def execute_crude_entry(entry: str | None = None) -> dict:
    """Sell the ATM CRUDEOILM straddle for every eligible deployment at 15:30:00 sharp."""
    from services import kotak_service

    entry = entry or entry_time()
    today = ex._today()
    target = ex.entry_target_dt(entry)
    t_start = time.monotonic()

    staged, skipped = _stage(today)
    n = len(staged)
    staged = await ex._ensure_kotak_sessions(staged, today)
    skipped += n - len(staged)
    if not staged:
        log.info("Crude entry: no eligible deployments (%d skipped).", skipped)
        return {"placed": 0, "failed": 0, "skipped": skipped, "elapsedSec": 0.0}

    need_upstox = any(i["broker"] in ("upstox", "jainam") or i["paper"] for i in staged)
    kotak_accounts: dict[str, str] = {}
    for i in staged:
        if i["broker"] == "kotak" and not i["paper"]:
            kotak_accounts.setdefault(i["dep"]["brokerAccountId"], i["access_token"])
    if need_upstox:
        try:
            await mcx_market_data.upstox_instruments()   # warm before the snapshot window
        except Exception as exc:  # noqa: BLE001
            log.warning("Upstox MCX instruments unavailable: %s", exc)

    # ── T-6s: market snapshot(s) ───────────────────────────────────────────────
    md_lead = max(0, int(getattr(settings, "entry_marketdata_lead_seconds", 6)))
    await ex._sleep_until(target - timedelta(seconds=md_lead), "crude:market-data")

    async def _safe(coro):
        try:
            return await coro, None
        except Exception as exc:  # noqa: BLE001
            return None, exc

    tasks = {}
    if need_upstox:
        tasks["upstox"] = _safe(mcx_market_data.upstox_snapshot())
    for acc_id, handle in kotak_accounts.items():
        tasks[f"kotak:{acc_id}"] = _safe(mcx_market_data.kotak_snapshot(handle))
    results = dict(zip(tasks, await asyncio.gather(*tasks.values())))

    up_snap, up_err = results.get("upstox", (None, None))
    if need_upstox and up_err:
        log.error("Crude Upstox snapshot failed: %s", up_err)
    ref = up_snap or next((r[0] for k, r in results.items() if k.startswith("kotak:") and r[0]), None)
    if not ref:
        errs = "; ".join(f"{k}: {v[1]}" for k, v in results.items() if v[1])
        ex._log("entry_error", f"Crude Oil Mini market data unavailable — no entry. {errs}", "error",
                date_str=today)
        for item in staged:
            firebase_service.update_user_strategy_status(item["dep"]["id"], "enabled")
        return {"placed": 0, "failed": len(staged), "skipped": skipped}

    paper_global = firebase_service.is_paper_trading()
    ex._log(
        "entry_started",
        f"{entry} entry — CRUDEOILM {ref['atm_strike']:g} CE+PE | option expiry {ref['expiry']} | "
        f"fut {ref.get('fut_symbol') or ''} {ref['fut_price']:.2f} | paper={paper_global}",
        "info", date_str=today, paper=paper_global,
        metadata={"atmStrike": ref["atm_strike"], "expiry": ref["expiry"], "futPrice": ref["fut_price"],
                  "source": ref.get("source")},
    )

    # ── Stage 3 (pre-T0): per-broker instruments and sizing ────────────────────
    lookups = []
    for item in staged:
        broker = item["broker"]
        if item["paper"]:
            _make_orders(item, up_snap or ref)      # simulated fills off whichever data we have
            continue
        if broker in ("upstox", "jainam"):
            if not up_snap:
                _make_orders(item, ref)
                _fail_item(item, RuntimeError(f"Upstox MCX market data unavailable: {up_err}"))
                continue
            _make_orders(item, up_snap)            # Upstox: quantity in lots (per Upstox docs)
            if broker == "jainam":
                async def _j(it=item, sn=up_snap):
                    try:
                        await _resolve_jainam(it, sn)
                    except Exception as exc:  # noqa: BLE001
                        _fail_item(it, RuntimeError(f"Jainam MCX instrument lookup failed: {exc}"))
                lookups.append(_j())
            continue

        # Kotak (live)
        acc_id = item["dep"]["brokerAccountId"]
        k_snap, k_err = results.get(f"kotak:{acc_id}", (None, None))
        if k_snap is None and ref is not None:
            # Own chain failed: resolve Kotak instruments for the reference strike/expiry.
            async def _k(it=item, err=k_err):
                try:
                    legs = await kotak_service.option_legs(
                        it["access_token"], exchange="mcx_fo", underlying="CRUDEOILM",
                        expiry=ref["expiry"], strike=ref["atm_strike"])
                    snap = {**ref, "source": "kotak", "ce_key": legs["CE"]["key"], "pe_key": legs["PE"]["key"],
                            "ce_symbol": legs["CE"]["symbol"], "pe_symbol": legs["PE"]["symbol"],
                            "ce_ltp": legs["CE"]["ltp"] or ref["ce_ltp"], "pe_ltp": legs["PE"]["ltp"] or ref["pe_ltp"],
                            "lot_size": legs["lot"], "multiplier": legs["multiplier"]}
                    _size_kotak(it, snap)
                except Exception as exc:  # noqa: BLE001
                    _make_orders(it, ref)
                    _fail_item(it, RuntimeError(f"Kotak MCX data failed ({err}); fallback failed: {exc}"))
            lookups.append(_k())
            continue
        try:
            _size_kotak(item, k_snap)
        except Exception as exc:  # noqa: BLE001
            _make_orders(item, k_snap)
            _fail_item(item, exc)

    if lookups:
        await asyncio.gather(*lookups, return_exceptions=True)

    all_orders = [o for item in staged for o in item.get("orders", [])]
    summary = await ex._fire_and_protect(staged, all_orders, target, today, t_start,
                                         default_strategy_id="crude-oil-mini-straddle",
                                         default_code=CRUDE_CODE)
    summary["skipped"] = skipped
    summary["atmStrike"] = ref["atm_strike"]
    summary["expiry"] = ref["expiry"]
    log.info("Crude entry complete: %s", summary)
    return summary


def _size_kotak(item: dict, snap: dict) -> None:
    _make_orders(item, snap)
    qty_per_lot_units, pnl_mult = mcx_market_data.kotak_quantity(1, snap)
    for order in item["orders"]:
        order["qty"] = order["qty"] * qty_per_lot_units        # lots → Kotak qt
        order["pnl_multiplier"] = pnl_mult
        md_key = mcx_market_data.upstox_key_for(snap["expiry"], snap["atm_strike"], order["option_type"])
        if md_key:
            order["extra"]["marketDataKey"] = md_key


# ── 23:24 — exit ──────────────────────────────────────────────────────────────

async def execute_crude_exit(retry: bool = False) -> dict:
    return await ex.execute_exit(retry=retry, strategy_codes=(CRUDE_CODE,), label=exit_time())


def eod_cleanup_crude() -> dict:
    return ex.eod_cleanup(strategy_codes=(CRUDE_CODE,), label="CRUDE EOD")
