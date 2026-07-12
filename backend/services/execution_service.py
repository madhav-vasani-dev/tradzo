"""Execution Engine — orchestrates all daily trading jobs.

Job sequence (weekdays, IST):
  08:00  reset_daily_statuses     — set all userStrategy.status back to "enabled"
  11:55  pre_entry_check          — validate tokens, set status="ready"
  12:00  execute_entry            — place SELL + SL-M orders, set status="trade_active"
  15:29  execute_exit             — cancel SL orders, square off, set status="trade_closed"
  15:31  eod_cleanup              — compute PnL, log day summary

Design principles:
  - One user's failure must never block another user's execution.
  - Paper mode is checked at the start of each job and propagated to order_service.
  - Idempotency: entry skips deployments that already have open positions today.
  - All meaningful events are written to activityLogs with date + userId.
"""
import logging
from datetime import datetime, date
from typing import Any

import pytz

from services import firebase_service, market_data_service, order_service, position_service
from strategies import get_strategy
from utils import logger as activity, token_store

log = logging.getLogger("tradzo.execution")
IST = pytz.timezone("Asia/Kolkata")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


def _now_ist() -> datetime:
    return datetime.now(IST)


def _to_dt(value: Any) -> datetime:
    """Coerce a Firestore timestamp / ISO string / datetime to an aware datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo else IST.localize(value)
    if hasattr(value, "timestamp"):
        return datetime.fromtimestamp(value.timestamp(), IST)
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return _now_ist()


def _get_token(account: dict | None) -> str | None:
    if not account or not account.get("isConnected"):
        return None
    tokens = token_store.get_tokens(account["id"])
    return (tokens or {}).get("access_token")


def _is_token_valid(account: dict | None) -> bool:
    """True only if the account is connected and has a non-expired token."""
    if not account or not account.get("isConnected"):
        return False
    tokens = token_store.get_tokens(account["id"])
    if not tokens or not tokens.get("access_token"):
        return False
    expiry_raw = account.get("expiresAt")
    if expiry_raw is None:
        return True
    expiry = _to_dt(expiry_raw)
    return expiry > _now_ist()


def _accounts_by_id() -> dict[str, dict]:
    return {a["id"]: a for a in firebase_service.list_broker_accounts()}


def _log(
    event_type: str,
    message: str,
    severity: str = "info",
    date_str: str | None = None,
    user_id: str | None = None,
    strategy_id: str | None = None,
    position_id: str | None = None,
    paper: bool = False,
    metadata: dict | None = None,
) -> None:
    activity.log_activity(
        type=event_type,
        message=message,
        severity=severity,
        date=date_str or _today(),
        userId=user_id,
        strategyId=strategy_id,
        positionId=position_id,
        isPaper=paper,
        metadata=metadata or {},
    )


# ── 08:00 — Reset daily statuses ──────────────────────────────────────────────

def reset_daily_statuses() -> dict:
    """Reset all non-paused userStrategy documents to status='enabled'.

    Called once at 08:00 AM each trading day so the status badges refresh.
    """
    count = firebase_service.reset_all_strategy_statuses_to_enabled()
    log.info("Daily status reset: %d deployment(s) set to 'enabled'.", count)
    _log("daily_reset", f"Daily reset complete — {count} deployment(s) set to enabled.", "info")
    return {"reset": count}


# ── 11:55 — Pre-entry check ───────────────────────────────────────────────────

def pre_entry_check() -> dict:
    """Validate broker tokens for all 'enabled' deployments.

    Sets status='ready' for those with valid tokens.
    Logs a warning for those that will be skipped.
    Returns a readiness summary.
    """
    today = _today()
    paper = firebase_service.is_paper_trading()
    deployments = firebase_service.list_deployments_by_status("enabled")
    accounts = _accounts_by_id()

    ready = skipped = 0
    for dep in deployments:
        if dep.get("pausedByAdmin"):
            skipped += 1
            continue

        account = accounts.get(dep.get("brokerAccountId", ""))

        if paper or _is_token_valid(account):
            firebase_service.update_user_strategy_status(dep["id"], "ready")
            ready += 1
        else:
            skipped += 1
            _log(
                "token_invalid",
                f"Skipped {dep.get('strategyName')} for user {dep.get('userId')}: "
                "broker token missing or expired — user must reconnect.",
                severity="warning",
                date_str=today,
                user_id=dep.get("userId"),
                strategy_id=dep.get("strategyId"),
            )

    summary = {"ready": ready, "skipped": skipped, "paper": paper}
    log.info("Pre-entry check: %s/%s ready (paper=%s).", ready, ready + skipped, paper)
    _log("pre_entry_check", f"Pre-entry check: {ready} ready, {skipped} skipped.", "info",
         date_str=today, metadata=summary)
    return summary


# ── 12:00 — Execute entry ─────────────────────────────────────────────────────

async def execute_entry() -> dict:
    """Place entry orders for all 'ready' deployments.

    For each deployment:
      1. Resolve strategy → get ATM data.
      2. For each leg (CE + PE):
         a. Place SELL MARKET → get fill price.
         b. Place BUY SL-M at fill_price × 1.30 immediately.
         c. Write position doc to Firestore.
      3. Set userStrategy.status = 'trade_active'.

    Uses paper mode from Firestore settings.
    """
    today = _today()
    paper = firebase_service.is_paper_trading()
    deployments = firebase_service.list_deployments_by_status("ready")
    accounts = _accounts_by_id()

    if not deployments:
        log.info("No ready deployments found at entry time.")
        _log("entry_skipped", "No ready deployments at 12:00 PM.", "info", date_str=today, paper=paper)
        return {"placed": 0, "failed": 0, "skipped": 0}

    # ── Fetch market data once for all deployments ──────────────────────────
    try:
        atm_data = await market_data_service.get_atm_data()
    except Exception as exc:
        log.error("Market data fetch failed at entry: %s", exc)
        _log("entry_error", f"Market data fetch failed: {exc}", "error",
             date_str=today, paper=paper)
        return {"placed": 0, "failed": len(deployments), "skipped": 0}

    log.info(
        "Entry: Nifty spot=%.2f ATM=%d expiry=%s CE=%s PE=%s [paper=%s]",
        atm_data["spot"], atm_data["atm_strike"], atm_data["expiry"],
        atm_data["ce_key"], atm_data["pe_key"], paper,
    )
    _log(
        "entry_started",
        f"12:00 entry — Nifty {atm_data['atm_strike']} "
        f"CE+PE | expiry {atm_data['expiry']} | paper={paper}",
        "info",
        date_str=today,
        paper=paper,
        metadata={
            "atmStrike": atm_data["atm_strike"],
            "expiry": atm_data["expiry"],
            "spot": atm_data["spot"],
        },
    )

    placed = failed = skipped = 0

    for dep in deployments:
        # ── Idempotency: skip if positions already exist today ──────────────
        existing = position_service.get_open_positions_for_user_strategy(dep["id"], today)
        if existing:
            log.warning("Deployment %s already has positions today — skipping.", dep["id"])
            skipped += 1
            continue

        account = accounts.get(dep.get("brokerAccountId", ""))
        access_token = _get_token(account) if not paper else "paper_token"
        lots = dep.get("multiplier", 1)

        try:
            strategy = get_strategy(dep.get("strategyCode", dep.get("strategyId", "")))
        except ValueError as exc:
            log.error("Unknown strategy for deployment %s: %s", dep["id"], exc)
            failed += 1
            continue

        legs = strategy.get_entry_legs(dep, atm_data["atm_strike"], atm_data["expiry"], lots)

        # Map optionType → (instrument_key, ltp)
        leg_map = {
            "CE": (atm_data["ce_key"], atm_data["ce_ltp"]),
            "PE": (atm_data["pe_key"], atm_data["pe_ltp"]),
        }

        dep_placed = dep_failed = 0

        for leg in legs:
            option_type = leg["optionType"]
            instrument_key, ltp = leg_map.get(option_type, ("", 0.0))
            qty = leg["quantity"]
            tag_prefix = f"NS_{dep['id'][:6].upper()}_{option_type}"

            try:
                # Step 1: Place SELL MARKET (entry)
                sell_result = await order_service.place_sell_market(
                    access_token=access_token,
                    instrument_key=instrument_key,
                    quantity=qty,
                    tag=f"{tag_prefix}_E",
                    paper=paper,
                    ltp=ltp,
                )
                fill_price = sell_result["fill_price"] or ltp

                # Step 2: Calculate SL price and place BUY SL-M immediately
                sl_price = strategy.calculate_sl_price(fill_price)
                sl_result = await order_service.place_sl_market(
                    access_token=access_token,
                    instrument_key=instrument_key,
                    quantity=qty,
                    trigger_price=sl_price,
                    tag=f"{tag_prefix}_SL",
                    paper=paper,
                )

                # Step 3: Write position to Firestore
                symbol = f"NIFTY{atm_data['expiry'].replace('-', '')[-4:]}{leg['strike']}{option_type}"
                pos_id = position_service.create_position({
                    "date": today,
                    "userId": dep.get("userId"),
                    "strategyId": dep.get("strategyId", "nifty-straddle"),
                    "strategyCode": dep.get("strategyCode", "NIFTY_STRADDLE"),
                    "userStrategyId": dep["id"],
                    "brokerAccountId": dep.get("brokerAccountId"),
                    "broker": dep.get("brokerName", "upstox"),
                    "instrumentKey": instrument_key,
                    "symbol": symbol,
                    "optionType": option_type,
                    "strike": leg["strike"],
                    "expiry": leg["expiry"],
                    "quantity": qty,
                    "lots": lots,
                    "entryOrderId": sell_result["order_id"],
                    "slOrderId": sl_result["order_id"],
                    "entryPrice": fill_price,
                    "slPrice": sl_price,
                    "status": "open",
                    "isPaper": paper,
                    "entryAt": _now_ist(),
                    "exitAt": None,
                    "exitPrice": None,
                    "exitOrderId": None,
                    "exitReason": None,
                    "pnl": None,
                })

                _log(
                    "order_placed",
                    f"[{'PAPER ' if paper else ''}ENTRY] {symbol} | "
                    f"SELL {qty}@₹{fill_price:.1f} | SL ₹{sl_price:.1f}",
                    severity="success",
                    date_str=today,
                    user_id=dep.get("userId"),
                    strategy_id=dep.get("strategyId"),
                    position_id=pos_id,
                    paper=paper,
                    metadata={
                        "symbol": symbol,
                        "optionType": option_type,
                        "entryPrice": fill_price,
                        "slPrice": sl_price,
                        "quantity": qty,
                        "entryOrderId": sell_result["order_id"],
                        "slOrderId": sl_result["order_id"],
                    },
                )
                dep_placed += 1

            except Exception as exc:  # noqa: BLE001
                log.error("Entry failed for %s %s: %s", dep["id"], option_type, exc)
                dep_failed += 1
                _log(
                    "order_failed",
                    f"Entry failed for {option_type} leg — {exc}",
                    severity="error",
                    date_str=today,
                    user_id=dep.get("userId"),
                    strategy_id=dep.get("strategyId"),
                    paper=paper,
                    metadata={"error": str(exc), "optionType": option_type},
                )

        placed += dep_placed
        failed += dep_failed

        # Mark deployment status based on outcome
        if dep_placed > 0:
            firebase_service.update_user_strategy_status(dep["id"], "trade_active")
        elif dep_failed > 0:
            firebase_service.update_user_strategy_status(dep["id"], "enabled")  # will retry nothing

    summary = {"placed": placed, "failed": failed, "skipped": skipped, "paper": paper}
    log.info("Entry complete: %s", summary)
    return summary


# ── 15:29 — Execute exit ──────────────────────────────────────────────────────

async def execute_exit() -> dict:
    """Square off all remaining open positions at 15:29 PM.

    Steps per open position:
      1. Cancel the SL-M order (it's no longer needed).
      2. Place BUY MARKET to square off the short.
      3. Record exit price and PnL.
      4. Update position.status = 'squared_off'.
    After all positions for a deployment are closed, set status='trade_closed'.
    """
    today = _today()
    paper = firebase_service.is_paper_trading()
    open_positions = position_service.get_open_positions_for_date(today)
    accounts = _accounts_by_id()

    if not open_positions:
        log.info("No open positions at exit time.")
        _log("exit_skipped", "15:29 exit — no open positions found.", "info",
             date_str=today, paper=paper)
        return {"closed": 0, "failed": 0}

    closed = failed = 0
    closed_deployment_ids: set[str] = set()

    for pos in open_positions:
        # Get access token for this position's account
        account = accounts.get(pos.get("brokerAccountId", ""))
        access_token = _get_token(account) if not paper else "paper_token"

        try:
            # Step 1: Cancel SL-M order
            sl_order_id = pos.get("slOrderId", "")
            if sl_order_id:
                await order_service.cancel_order(
                    access_token=access_token,
                    order_id=sl_order_id,
                    paper=paper,
                )

            # Step 2: Get current LTP for PnL calculation
            current_ltp = await market_data_service.get_option_ltp(pos["instrumentKey"])

            # Step 3: Place BUY MARKET to square off
            tag = f"SQ_{pos['id'][:8].upper()}"
            buy_result = await order_service.place_buy_market(
                access_token=access_token,
                instrument_key=pos["instrumentKey"],
                quantity=pos["quantity"],
                tag=tag,
                paper=paper,
                ltp=current_ltp,
            )
            exit_price = buy_result["fill_price"] or current_ltp

            # Step 4: Calculate PnL (we SOLD entry, BUY to close → profit if exit < entry)
            pnl = (pos["entryPrice"] - exit_price) * pos["quantity"]

            position_service.update_position(pos["id"], {
                "status": "squared_off",
                "exitReason": "eod_exit",
                "exitOrderId": buy_result["order_id"],
                "exitPrice": exit_price,
                "exitAt": _now_ist(),
                "pnl": round(pnl, 2),
            })

            _log(
                "square_off",
                f"[{'PAPER ' if paper else ''}EXIT] {pos['symbol']} | "
                f"BUY {pos['quantity']}@₹{exit_price:.1f} | PnL ₹{pnl:+.2f}",
                severity="success" if pnl >= 0 else "warning",
                date_str=today,
                user_id=pos.get("userId"),
                strategy_id=pos.get("strategyId"),
                position_id=pos["id"],
                paper=paper,
                metadata={
                    "symbol": pos["symbol"],
                    "entryPrice": pos["entryPrice"],
                    "exitPrice": exit_price,
                    "quantity": pos["quantity"],
                    "pnl": round(pnl, 2),
                },
            )
            closed += 1
            closed_deployment_ids.add(pos.get("userStrategyId", ""))

        except Exception as exc:  # noqa: BLE001
            log.error("Exit failed for position %s: %s", pos["id"], exc)
            failed += 1
            _log(
                "exit_error",
                f"Exit failed for {pos.get('symbol')} — {exc}",
                severity="error",
                date_str=today,
                user_id=pos.get("userId"),
                strategy_id=pos.get("strategyId"),
                position_id=pos["id"],
                paper=paper,
                metadata={"error": str(exc)},
            )

    # Mark all closed deployments as trade_closed
    for dep_id in closed_deployment_ids:
        if dep_id:
            firebase_service.update_user_strategy_status(dep_id, "trade_closed")

    summary = {"closed": closed, "failed": failed, "paper": paper}
    log.info("Exit complete: %s", summary)
    return summary


# ── 15:31 — EOD cleanup ───────────────────────────────────────────────────────

def eod_cleanup() -> dict:
    """Compute per-deployment day PnL and write a day summary to activityLogs.

    Called at 15:31 PM after execute_exit has run.
    """
    today = _today()
    paper = firebase_service.is_paper_trading()
    positions = position_service.get_positions_for_date(today)

    # Group by userId + strategyId
    user_pnl: dict[str, float] = {}
    for pos in positions:
        key = f"{pos.get('userId')}_{pos.get('strategyId')}"
        user_pnl[key] = user_pnl.get(key, 0.0) + (pos.get("pnl") or 0.0)

    total_pnl = sum(user_pnl.values())

    _log(
        "day_summary",
        f"[{'PAPER ' if paper else ''}EOD] {today} — "
        f"{len(positions)} legs | {len(user_pnl)} users | total PnL ₹{total_pnl:+.2f}",
        severity="info",
        date_str=today,
        paper=paper,
        metadata={
            "totalPositions": len(positions),
            "uniqueUsers": len(user_pnl),
            "totalPnl": round(total_pnl, 2),
        },
    )

    log.info("EOD cleanup complete. Total PnL: ₹%.2f across %d user(s).", total_pnl, len(user_pnl))
    return {"positions": len(positions), "users": len(user_pnl), "totalPnl": round(total_pnl, 2)}


# ── Legacy stubs (kept for backward compat / readiness endpoint) ──────────────

def get_cached_readiness() -> dict:
    """Return a simple readiness snapshot (used by /execution/readiness)."""
    deployments = firebase_service.list_deployments_by_status("ready")
    enabled = firebase_service.list_deployments_by_status("enabled")
    return {
        "computedAt": _now_ist().isoformat(),
        "totalDeployments": len(deployments) + len(enabled),
        "readyDeployments": len(deployments),
        "paperTrading": firebase_service.is_paper_trading(),
    }


def compute_readiness() -> dict:
    return pre_entry_check()


def refresh_broker_tokens() -> dict:
    """Flag expired broker tokens as needing re-authentication."""
    flagged = 0
    for account in firebase_service.list_broker_accounts():
        if not account.get("isConnected"):
            continue
        tokens = token_store.get_tokens(account["id"])
        if not tokens:
            continue
        expiry_raw = account.get("expiresAt")
        if expiry_raw is None:
            continue
        if _to_dt(expiry_raw) <= _now_ist():
            firebase_service.update_broker_account(
                account["id"], {"needsReauth": True}
            )
            token_store.delete_tokens(account["id"])
            flagged += 1
            _log(
                "token_expired",
                "Broker token expired — user must reconnect.",
                severity="warning",
                user_id=account.get("userId"),
                metadata={"accountId": account["id"]},
            )
    log.info("Token sweep: %d account(s) flagged.", flagged)
    return {"flagged": flagged}
