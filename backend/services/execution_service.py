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
    if not tokens:
        return None
    if tokens.get("broker") == "jainam":
        return tokens.get("interactive_token")
    return tokens.get("access_token")


def _get_jainam_market_data_token(account: dict | None) -> str | None:
    if account:
        tokens = token_store.get_tokens(account["id"])
        if tokens and tokens.get("marketdata_token"):
            return tokens["marketdata_token"]
            
    md_account = firebase_service.get_market_data_account()
    if md_account and md_account.get("broker") == "jainam":
        tokens = token_store.get_tokens(md_account["id"])
        if tokens and tokens.get("marketdata_token"):
            return tokens["marketdata_token"]
            
    for acc in firebase_service.list_broker_accounts():
        if acc.get("broker") == "jainam" and acc.get("isConnected"):
            tokens = token_store.get_tokens(acc["id"])
            if tokens and tokens.get("marketdata_token"):
                return tokens["marketdata_token"]
    return None


def _is_token_valid(account: dict | None) -> bool:
    """True only if the account is connected and has a non-expired token."""
    if not account or not account.get("isConnected"):
        return False
    tokens = token_store.get_tokens(account["id"])
    if not tokens:
        log.warning("Token decryption failed for account %s. Marking disconnected.", account["id"])
        firebase_service.mark_broker_account_disconnected(account["id"])
        return False
    token_key = "interactive_token" if tokens.get("broker") == "jainam" else "access_token"
    if not tokens.get(token_key):
        log.warning("Token key missing for account %s. Marking disconnected.", account["id"])
        firebase_service.mark_broker_account_disconnected(account["id"])
        return False
    expiry_raw = account.get("expiresAt")
    if expiry_raw is None:
        return True
    expiry = _to_dt(expiry_raw)
    if expiry <= _now_ist():
        log.warning("Token expired for account %s. Marking disconnected.", account["id"])
        firebase_service.mark_broker_account_disconnected(account["id"])
        return False
    return True


def _accounts_by_id() -> dict[str, dict]:
    return {a["id"]: a for a in firebase_service.list_broker_accounts()}


def _users_by_id() -> dict[str, dict]:
    db = firebase_service.get_db()
    docs = db.collection("users").stream()
    return {d.id: d.to_dict() for d in docs}


def _log(
    event_type: str,
    message: str,
    severity: str = "info",
    date_str: str | None = None,
    user_id: str | None = None,
    user_name: str | None = None,
    strategy_id: str | None = None,
    position_id: str | None = None,
    paper: bool = False,
    metadata: dict | None = None,
) -> None:
    if user_id == "system":
        return
    activity.log_activity(
        type=event_type,
        message=message,
        severity=severity,
        date=date_str or _today(),
        userId=user_id,
        userName=user_name,
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
    deployments = firebase_service.list_deployments_by_status("enabled")
    accounts = _accounts_by_id()
    users = _users_by_id()

    ready = skipped = 0
    for dep in deployments:
        if dep.get("pausedByAdmin"):
            skipped += 1
            continue

        account = accounts.get(dep.get("brokerAccountId", ""))
        user_id = dep.get("userId")
        user_doc = users.get(user_id, {})
        paper = user_doc.get("paperTrading", True)

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

    summary = {"ready": ready, "skipped": skipped}
    log.info("Pre-entry check: %s/%s ready.", ready, ready + skipped)
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
    deployments = firebase_service.list_deployments_by_status("ready")
    accounts = _accounts_by_id()
    users = _users_by_id()
    paper = firebase_service.is_paper_trading()

    placed = failed = skipped = 0

    # ── 1. Fetch market data once ──────────────────────────────────────────
    try:
        atm_data = await market_data_service.get_atm_data()
    except Exception as exc:
        log.error("Market data fetch failed at entry: %s", exc)
        _log("entry_error", f"Market data fetch failed: {exc}", "error",
             date_str=today, paper=paper)
        return {"placed": 0, "failed": 1, "skipped": 0}

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

    # ── 2. Always Execute System Benchmark Simulation Trade (userId="system") ─
    try:
        sys_existing = position_service.get_open_positions_for_user_strategy("system_nifty_benchmark", today)
        if not sys_existing:
            sys_strategy = get_strategy("NIFTY_STRADDLE")
            sys_dep = {
                "id": "system_nifty_benchmark",
                "userId": "system",
                "strategyId": "nifty-straddle",
                "strategyCode": "NIFTY_STRADDLE",
                "multiplier": 1,
            }
            sys_legs = sys_strategy.get_entry_legs(sys_dep, atm_data["atm_strike"], atm_data["expiry"], 1)
            leg_map_sys = {
                "CE": (atm_data["ce_key"], atm_data["ce_symbol"], atm_data["ce_ltp"]),
                "PE": (atm_data["pe_key"], atm_data["pe_symbol"], atm_data["pe_ltp"]),
            }
            for leg in sys_legs:
                option_type = leg["optionType"]
                qty = leg["quantity"]
                key, symbol, ltp = leg_map_sys[option_type]
                sl_price = sys_strategy.calculate_sl_price(ltp)

                pos_doc = {
                    "userId": "system",
                    "userStrategyId": "system_nifty_benchmark",
                    "strategyId": "nifty-straddle",
                    "strategyCode": "NIFTY_STRADDLE",
                    "symbol": symbol,
                    "instrumentKey": key,
                    "optionType": option_type,
                    "strike": leg["strike"],
                    "expiry": leg["expiry"],
                    "quantity": qty,
                    "entryPrice": ltp,
                    "slPrice": sl_price,
                    "slOrderId": f"SYS_SL_{int(__import__('time').time()*1000)}",
                    "status": "open",
                    "isPaper": True,
                    "broker": "upstox",
                    "date": today,
                    "createdAt": _now_ist(),
                }
                position_service.create_position(pos_doc)

            log.info("System benchmark Nifty simulation trade created for %s.", today)
            _log(
                "entry_executed",
                f"[SYSTEM BENCHMARK] Nifty {atm_data['atm_strike']} CE+PE sold @ ₹{atm_data['ce_ltp']:.1f} & ₹{atm_data['pe_ltp']:.1f}",
                severity="success",
                date_str=today,
                user_id="system",
                strategy_id="nifty-straddle",
                paper=True,
            )
            placed += 1
    except Exception as sys_exc:
        log.error("Failed to create system benchmark Nifty trade: %s", sys_exc)

    # ── 3. Execute User Deployments ───────────────────────────────────────────
    all_ready = firebase_service.list_deployments_by_status("ready")
    all_enabled = firebase_service.list_deployments_by_status("enabled")
    deployments = [
        d for d in (all_ready + all_enabled)
        if d.get("strategyCode") == "NIFTY_STRADDLE" and not d.get("pausedByAdmin")
    ]

    for dep in deployments:
        # ── Idempotency: skip if positions already exist today ──────────────
        existing = position_service.get_open_positions_for_user_strategy(dep["id"], today)
        if existing:
            log.warning("Deployment %s already has positions today — skipping.", dep["id"])
            skipped += 1
            continue

        account = accounts.get(dep.get("brokerAccountId", ""))
        user_id = dep.get("userId")
        user_doc = users.get(user_id, {})
        paper = user_doc.get("paperTrading", True)
        access_token = _get_token(account) if not paper else "paper_token"
        lots = dep.get("multiplier", 1)
        broker = dep.get("brokerName", "upstox")

        user_name = "User"
        try:
            user_doc = firebase_service.get_db().collection("users").document(dep.get("userId")).get()
            if user_doc.exists:
                user_name = user_doc.to_dict().get("username") or user_doc.to_dict().get("email") or "User"
        except Exception:
            pass

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
            qty = leg["quantity"]
            tag_prefix = f"NS_{dep['id'][:6].upper()}_{option_type}"

            try:
                # Resolve instrument key and ltp
                if not paper and broker == "jainam":
                    from services import jainam_service
                    md_token = _get_jainam_market_data_token(account)
                    if not md_token:
                        raise RuntimeError("No valid Jainam market data token found. Please connect your Jainam account.")
                    
                    res = await jainam_service.get_option_instrument(
                        token=md_token,
                        symbol="NIFTY",
                        expiry_date_str=leg["expiry"],
                        option_type=option_type,
                        strike_price=leg["strike"]
                    )
                    instrument_key = str(res["exchangeInstrumentID"])
                    ltp = atm_data["ce_ltp"] if option_type == "CE" else atm_data["pe_ltp"]
                else:
                    instrument_key, ltp = leg_map.get(option_type, ("", 0.0))

                # Step 1: Place SELL MARKET (entry)
                sell_result = await order_service.place_sell_market(
                    access_token=access_token,
                    instrument_key=instrument_key,
                    quantity=qty,
                    tag=f"{tag_prefix}_E",
                    paper=paper,
                    ltp=ltp,
                    broker=broker,
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
                    broker=broker,
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
                    "broker": broker,
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
                    user_name=user_name,
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
                    user_name=user_name,
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

    # ── Strategy Simulations ──────────────────────────────────────────────────
    try:
        strategies_ref = firebase_service.get_db().collection("strategies").stream()
        for strat_doc in strategies_ref:
            strat_data = strat_doc.to_dict()
            strat_id = strat_doc.id
            if not strat_data.get("isVisible", True):
                continue
            strat_code = strat_data.get("code") or strat_data.get("strategyCode") or strat_id.upper()

            # Idempotency check: skip if system positions already exist today
            existing_sys = (
                firebase_service.get_db()
                .collection("positions")
                .where("userId", "==", "system")
                .where("userStrategyId", "==", f"system_{strat_id}")
                .where("date", "==", today)
                .get()
            )
            if existing_sys:
                continue

            try:
                strategy_instance = get_strategy(strat_code)
            except ValueError:
                strategy_instance = get_strategy("NIFTY_STRADDLE")

            legs = strategy_instance.get_entry_legs({}, atm_data["atm_strike"], atm_data["expiry"], 1)

            leg_map = {
                "CE": (atm_data["ce_key"], atm_data["ce_ltp"]),
                "PE": (atm_data["pe_key"], atm_data["pe_ltp"]),
            }

            for leg in legs:
                option_type = leg["optionType"]
                instrument_key, ltp = leg_map.get(option_type, ("", 0.0))
                qty = leg["quantity"]
                tag_prefix = f"SYS_{strat_id[:6].upper()}_{option_type}"

                fill_price = ltp
                sl_price = strategy_instance.calculate_sl_price(fill_price)

                symbol = f"NIFTY{atm_data['expiry'].replace('-', '')[-4:]}{leg['strike']}{option_type}"
                position_service.create_position({
                    "date": today,
                    "userId": "system",
                    "strategyId": strat_id,
                    "strategyCode": strat_code,
                    "userStrategyId": f"system_{strat_id}",
                    "brokerAccountId": "system_broker",
                    "broker": "upstox",
                    "instrumentKey": instrument_key,
                    "symbol": symbol,
                    "optionType": option_type,
                    "strike": leg["strike"],
                    "expiry": leg["expiry"],
                    "quantity": qty,
                    "lots": 1,
                    "entryOrderId": f"sys_sell_{tag_prefix}",
                    "slOrderId": f"sys_sl_{tag_prefix}",
                    "entryPrice": fill_price,
                    "slPrice": sl_price,
                    "status": "open",
                    "isPaper": True,
                    "entryAt": _now_ist(),
                    "exitAt": None,
                    "exitPrice": None,
                    "exitOrderId": None,
                    "exitReason": None,
                    "pnl": None,
                })
    except Exception as exc:
        log.error("Failed to execute global strategy simulation: %s", exc)

    summary = {"placed": placed, "failed": failed, "skipped": skipped}
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
        if pos.get("status") != "open":
            continue

        # Get access token for this position's account
        account = accounts.get(pos.get("brokerAccountId", ""))
        access_token = _get_token(account) if not paper else "paper_token"
        broker = pos.get("broker", "upstox")

        user_name = "User"
        try:
            user_doc = firebase_service.get_db().collection("users").document(pos.get("userId")).get()
            if user_doc.exists:
                user_name = user_doc.to_dict().get("username") or user_doc.to_dict().get("email") or "User"
        except Exception:
            pass

        try:
            # Step 1: Cancel SL-M order
            sl_order_id = pos.get("slOrderId", "")
            if sl_order_id:
                try:
                    await order_service.cancel_order(
                        access_token=access_token,
                        order_id=sl_order_id,
                        paper=paper,
                        broker=broker,
                    )
                except Exception as e:
                    log.warning("Exit: Could not cancel SL order %s: %s", sl_order_id, e)

            # Step 2: Get current LTP for PnL calculation
            current_ltp = 0.0
            if paper:
                current_ltp = await market_data_service.get_option_ltp(pos["instrumentKey"])
            elif broker == "upstox":
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
                broker=broker,
            )
            exit_price = buy_result["fill_price"] or current_ltp or pos["entryPrice"]

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
                user_name=user_name,
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
                user_name=user_name,
                strategy_id=pos.get("strategyId"),
                position_id=pos["id"],
                paper=paper,
                metadata={"error": str(exc)},
            )

    # Mark all closed user deployments as trade_closed
    for dep_id in closed_deployment_ids:
        if dep_id and not dep_id.startswith("system"):
            try:
                firebase_service.update_user_strategy_status(dep_id, "trade_closed")
            except Exception as e:
                log.warning("Could not update userStrategy status for %s: %s", dep_id, e)

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
        if pos.get("userId") == "system":
            continue
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


async def square_off_single_deployment(user_strategy_id: str) -> dict:
    """Square off open positions for a single userStrategy deployment immediately."""
    today = _today()
    paper = firebase_service.is_paper_trading()
    all_positions = position_service.get_open_positions_for_user_strategy(user_strategy_id, today)
    open_positions = [p for p in all_positions if p.get("status") == "open"]
    accounts = _accounts_by_id()

    if not open_positions:
        # If no positions are open, just disable the strategy for today
        firebase_service.update_user_strategy_status(user_strategy_id, "disabled_today")
        return {"closed": 0, "status": "disabled_today"}

    closed = 0
    for pos in open_positions:
        account = accounts.get(pos.get("brokerAccountId", ""))
        access_token = _get_token(account) if not paper else "paper_token"
        broker = pos.get("broker", "upstox")

        user_name = "User"
        try:
            user_doc = firebase_service.get_db().collection("users").document(pos.get("userId")).get()
            if user_doc.exists:
                user_name = user_doc.to_dict().get("username") or user_doc.to_dict().get("email") or "User"
        except Exception:
            pass

        # 1. Cancel SL-M order
        sl_order_id = pos.get("slOrderId", "")
        if sl_order_id:
            try:
                await order_service.cancel_order(
                    access_token=access_token,
                    order_id=sl_order_id,
                    paper=paper,
                    broker=broker,
                )
            except Exception as e:
                log.warning("Could not cancel SL order %s: %s", sl_order_id, e)

        # 2. Get current LTP
        current_ltp = await market_data_service.get_option_ltp(pos["instrumentKey"])

        # 3. Place BUY MARKET to close
        tag = f"SQ_MAN_{pos['id'][:6].upper()}"
        buy_result = await order_service.place_buy_market(
            access_token=access_token,
            instrument_key=pos["instrumentKey"],
            quantity=pos["quantity"],
            tag=tag,
            paper=paper,
            ltp=current_ltp,
            broker=broker,
        )
        exit_price = buy_result["fill_price"] or current_ltp

        # 4. Calculate PnL
        pnl = (pos["entryPrice"] - exit_price) * pos["quantity"]

        position_service.update_position(pos["id"], {
            "status": "squared_off",
            "exitReason": "manual_exit",
            "exitOrderId": buy_result["order_id"],
            "exitPrice": exit_price,
            "exitAt": _now_ist(),
            "pnl": round(pnl, 2),
        })

        _log(
            "square_off",
            f"[MANUAL EXIT] {pos['symbol']} | "
            f"BUY {pos['quantity']}@₹{exit_price:.1f} | PnL {pnl:+.2f}",
            severity="success" if pnl >= 0 else "warning",
            date_str=today,
            user_id=pos.get("userId"),
            user_name=user_name,
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

    # Set status to disabled_today so that EOD job does not process it again and it does not re-enter today
    firebase_service.update_user_strategy_status(user_strategy_id, "disabled_today")
    return {"closed": closed, "status": "disabled_today"}


async def sync_order_statuses() -> dict:
    """Sync order status for active open positions to catch stop-loss triggers."""
    now = _now_ist()
    # Market hours check (12:01 PM to 15:28 PM IST)
    if not (12 <= now.hour <= 15):
        return {"status": "outside_market_hours", "hour": now.hour}
    if now.hour == 12 and now.minute == 0:
        return {"status": "skipping_exact_entry"}
    if now.hour == 15 and now.minute >= 29:
        return {"status": "skipping_exact_exit"}

    today = _today()
    paper = firebase_service.is_paper_trading()
    open_positions = position_service.get_open_positions_for_date(today)
    
    if not open_positions:
        return {"synced": 0, "hits": 0}

    accounts = _accounts_by_id()
    synced = hits = 0

    for pos in open_positions:
        if pos.get("status") != "open":
            continue

        user_id = pos.get("userId")
        user_name = "User"
        try:
            user_doc = firebase_service.get_db().collection("users").document(user_id).get()
            if user_doc.exists:
                user_name = user_doc.to_dict().get("username") or user_doc.to_dict().get("email") or "User"
        except Exception:
            pass

        # ── BTC Option Selling (Delta / Paper) ─────────────────────────────────
        if pos.get("strategyCode") == "BTC_OPTION_SELLING":
            from services import delta_service
            usd_inr_rate = getattr(__import__("config", fromlist=["settings"]).settings, "usd_to_inr_rate", 85.0)
            try:
                current_ltp = await delta_service.get_option_ltp(int(pos["instrumentKey"]))
                if current_ltp > 0:
                    # 1. Check if SL hit (LTP >= current SL price)
                    if current_ltp >= pos["slPrice"]:
                        exit_price_usd = current_ltp
                        exit_price_inr = delta_service.usd_to_inr(exit_price_usd, usd_inr_rate)
                        pnl_usd = round((pos["entryPrice"] - exit_price_usd) * pos["quantity"], 6)
                        pnl_inr = delta_service.usd_to_inr(pnl_usd, usd_inr_rate)

                        # In live mode, cancel SL order and square off
                        if not pos.get("isPaper"):
                            delta_creds = {}
                            if account:
                                tokens = token_store.get_tokens(account["id"])
                                if tokens and tokens.get("broker") == "delta":
                                    delta_creds = {"api_key": tokens.get("api_key"), "api_secret": tokens.get("api_secret")}
                            try:
                                await order_service.cancel_order(
                                    access_token="delta_token",
                                    order_id=pos.get("slOrderId", ""),
                                    paper=False,
                                    broker="delta",
                                    delta_creds=delta_creds,
                                    product_id=pos.get("instrumentKey"),
                                )
                            except Exception as e:
                                log.warning("BTC live SL cancel failed: %s", e)

                        position_service.update_position(pos["id"], {
                            "status": "sl_hit",
                            "exitReason": "sl_hit",
                            "exitPrice": exit_price_usd,
                            "exitPriceInr": exit_price_inr,
                            "exitAt": _now_ist(),
                            "pnl": pnl_usd,
                            "pnlInr": pnl_inr,
                        })
                        _log(
                            "sl_hit",
                            f"[{'PAPER ' if pos.get('isPaper') else ''}BTC SL HIT] {pos['symbol']} | "
                            f"Triggered at ${exit_price_usd:.2f} (₹{exit_price_inr:.2f}) | "
                            f"PnL ${pnl_usd:+.2f} (₹{pnl_inr:+.2f})",
                            severity="error",
                            date_str=today,
                            user_id=user_id,
                            user_name=user_name,
                            strategy_id=pos.get("strategyId"),
                            position_id=pos["id"],
                            paper=pos.get("isPaper", True),
                        )
                        hits += 1

                    # 2. Check Trailing SL update (if SL not hit)
                    else:
                        try:
                            strategy_cls = get_strategy("BTC_OPTION_SELLING")
                            new_sl_usd = strategy_cls.calculate_trailed_sl(
                                pos["entryPrice"], pos["slPrice"], current_ltp
                            )
                            if new_sl_usd is not None and new_sl_usd < pos["slPrice"]:
                                new_sl_inr = delta_service.usd_to_inr(new_sl_usd, usd_inr_rate)
                                old_sl_usd = pos["slPrice"]

                                # In live mode, replace stop-market order on Delta
                                new_order_id = pos.get("slOrderId")
                                if not pos.get("isPaper"):
                                    delta_creds = {}
                                    if account:
                                        tokens = token_store.get_tokens(account["id"])
                                        if tokens and tokens.get("broker") == "delta":
                                            delta_creds = {"api_key": tokens.get("api_key"), "api_secret": tokens.get("api_secret")}
                                    try:
                                        await order_service.cancel_order(
                                            access_token="delta_token",
                                            order_id=pos.get("slOrderId", ""),
                                            paper=False,
                                            broker="delta",
                                            delta_creds=delta_creds,
                                        )
                                        sl_res = await order_service.place_sl_market(
                                            access_token="delta_token",
                                            instrument_key=pos["instrumentKey"],
                                            quantity=pos["quantity"],
                                            trigger_price=new_sl_usd,
                                            tag=f"BTC_{pos['id'][:6].upper()}_TSL",
                                            paper=False,
                                            broker="delta",
                                            delta_creds=delta_creds,
                                        )
                                        new_order_id = sl_res.get("order_id", new_order_id)
                                    except Exception as e:
                                        log.warning("Live Delta Trailing SL order update failed: %s", e)

                                position_service.update_position(pos["id"], {
                                    "slPrice": new_sl_usd,
                                    "slPriceInr": new_sl_inr,
                                    "slOrderId": new_order_id,
                                })
                                _log(
                                    "order_modified",
                                    f"[{'PAPER ' if pos.get('isPaper') else ''}BTC TRAIL SL] {pos['symbol']} | "
                                    f"LTP ${current_ltp:.2f} | SL trailed from ${old_sl_usd:.2f} → ${new_sl_usd:.2f} (₹{new_sl_inr:.2f})",
                                    severity="info",
                                    date_str=today,
                                    user_id=user_id,
                                    user_name=user_name,
                                    strategy_id=pos.get("strategyId"),
                                    position_id=pos["id"],
                                    paper=pos.get("isPaper", True),
                                )
                        except Exception as e:
                            log.warning("BTC trailing SL calculation failed for %s: %s", pos["id"], e)

                synced += 1
            except Exception as e:
                log.error("BTC SL sync failed for position %s: %s", pos["id"], e)
            continue

        # Paper mode trigger simulation for other strategies
        if pos.get("isPaper"):
            try:
                current_ltp = await market_data_service.get_option_ltp(pos["instrumentKey"])
                if current_ltp >= pos["slPrice"]:
                    pnl = (pos["entryPrice"] - pos["slPrice"]) * pos["quantity"]
                    position_service.update_position(pos["id"], {
                        "status": "sl_hit",
                        "exitReason": "sl_hit",
                        "exitPrice": pos["slPrice"],
                        "exitAt": _now_ist(),
                        "pnl": round(pnl, 2),
                    })
                    _log(
                        "sl_hit",
                        f"[PAPER SL HIT] {pos['symbol']} | Triggered at ₹{pos['slPrice']:.1f} | PnL {pnl:+.2f}",
                        severity="error",
                        date_str=today,
                        user_id=user_id,
                        user_name=user_name,
                        strategy_id=pos.get("strategyId"),
                        position_id=pos["id"],
                        paper=True,
                    )
                    hits += 1
                synced += 1
            except Exception as e:
                log.error("Paper SL simulation failed for position %s: %s", pos["id"], e)
            continue

        # Live trading status query
        broker = pos.get("broker", "upstox")
        account = accounts.get(pos.get("brokerAccountId", ""))
        access_token = _get_token(account)
        if not access_token:
            continue

        sl_order_id = pos.get("slOrderId")
        if not sl_order_id:
            continue

        try:
            is_hit = False
            exit_price = 0.0

            if broker == "upstox":
                order_data = await order_service.get_order_details(access_token, sl_order_id)
                if order_data.get("status", "").lower() == "complete":
                    is_hit = True
                    exit_price = float(order_data.get("average_price") or order_data.get("trigger_price") or pos["slPrice"])
            
            elif broker == "jainam":
                from services import jainam_service
                history = await jainam_service.get_order_history(access_token, sl_order_id)
                if history:
                    latest = history[-1]
                    if latest.get("orderstatus", "").upper() == "FILLED":
                        is_hit = True
                        exit_price = float(latest.get("averageprice") or latest.get("stopPrice") or pos["slPrice"])

            if is_hit:
                pnl = (pos["entryPrice"] - exit_price) * pos["quantity"]
                position_service.update_position(pos["id"], {
                    "status": "sl_hit",
                    "exitReason": "sl_hit",
                    "exitPrice": exit_price,
                    "exitAt": _now_ist(),
                    "pnl": round(pnl, 2),
                })
                _log(
                    "sl_hit",
                    f"[SL HIT] {pos['symbol']} | Triggered at ₹{exit_price:.1f} | PnL {pnl:+.2f}",
                    severity="error",
                    date_str=today,
                    user_id=user_id,
                    user_name=user_name,
                    strategy_id=pos.get("strategyId"),
                    position_id=pos["id"],
                    paper=False,
                )
                hits += 1
            synced += 1
        except Exception as e:
            log.error("Failed to sync order status for position %s: %s", pos["id"], e)

    return {"synced": synced, "hits": hits}



# ── 17:01 — Execute BTC entry (Delta Exchange) ────────────────────────────────

async def execute_btc_entry() -> dict:
    """Place BTC option entry orders via Delta Exchange for all 'ready' BTC deployments.

    For each BTC_OPTION_SELLING deployment:
      1. Fetch ATM data from Delta Exchange (spot, CE/PE product IDs, LTPs).
      2. For each leg (CE + PE):
         a. Place SELL MARKET → get fill price (in USD).
         b. Place BUY Stop-Market at fill_price × 2.0 (100% SL).
         c. Write position doc to Firestore (USD + INR PnL fields).
      3. Set userStrategy.status = 'trade_active'.
    """
    from services import delta_service
    from utils import token_store

    today = _today()
    placed = failed = skipped = 0
    usd_inr_rate = getattr(__import__("config", fromlist=["settings"]).settings, "usd_to_inr_rate", 85.0)

    # 1. Fetch BTC ATM data once
    try:
        atm_data = await delta_service.get_atm_data()
    except Exception as exc:
        log.error("Delta ATM data fetch failed at 17:01 entry: %s", exc)
        _log("entry_error", f"Delta ATM data fetch failed: {exc}", "error", date_str=today)
        return {"placed": 0, "failed": 1, "skipped": 0}

    log.info(
        "BTC entry: spot=%.2f ATM=%d expiry=%s CE_id=%d PE_id=%d CE_ltp=%.4f PE_ltp=%.4f",
        atm_data["spot"], atm_data["atm_strike"], atm_data["expiry"],
        atm_data["ce_product_id"], atm_data["pe_product_id"],
        atm_data["ce_ltp"], atm_data["pe_ltp"],
    )

    # ── 2. Always Execute System Benchmark Simulation Trade (userId="system") ─
    try:
        sys_existing = position_service.get_open_positions_for_user_strategy("system_btc_benchmark", today)
        if not sys_existing:
            sys_strategy = get_strategy("BTC_OPTION_SELLING")
            sys_dep = {
                "id": "system_btc_benchmark",
                "userId": "system",
                "strategyId": "btc-option-selling",
                "strategyCode": "BTC_OPTION_SELLING",
                "multiplier": 1,
            }
            sys_legs = sys_strategy.get_entry_legs(sys_dep, atm_data["atm_strike"], atm_data["expiry"], 1)
            leg_map_sys = {
                "CE": (str(atm_data["ce_product_id"]), atm_data["ce_symbol"], atm_data["ce_ltp"]),
                "PE": (str(atm_data["pe_product_id"]), atm_data["pe_symbol"], atm_data["pe_ltp"]),
            }
            for leg in sys_legs:
                option_type = leg["optionType"]
                qty = leg["quantity"]
                prod_id, symbol, ltp = leg_map_sys[option_type]
                sl_usd = sys_strategy.calculate_sl_price(ltp)
                sl_inr = delta_service.usd_to_inr(sl_usd, usd_inr_rate)
                entry_inr = delta_service.usd_to_inr(ltp, usd_inr_rate)

                pos_doc = {
                    "userId": "system",
                    "userStrategyId": "system_btc_benchmark",
                    "strategyId": "btc-option-selling",
                    "strategyCode": "BTC_OPTION_SELLING",
                    "symbol": symbol,
                    "instrumentKey": prod_id,
                    "optionType": option_type,
                    "strike": leg["strike"],
                    "expiry": leg["expiry"],
                    "quantity": qty,
                    "entryPrice": ltp,
                    "entryPriceInr": entry_inr,
                    "currency": "USD",
                    "usdToInrRate": usd_inr_rate,
                    "slPrice": sl_usd,
                    "slPriceInr": sl_inr,
                    "slOrderId": f"SYS_SL_{int(__import__('time').time()*1000)}",
                    "status": "open",
                    "isPaper": True,
                    "broker": "delta",
                    "date": today,
                    "createdAt": _now_ist(),
                }
                position_service.create_position(pos_doc)

            log.info("System benchmark BTC simulation trade created for %s.", today)
            _log(
                "entry_executed",
                f"[SYSTEM BENCHMARK] BTC {atm_data['atm_strike']} CE+PE sold @ ${atm_data['ce_ltp']:.2f} & ${atm_data['pe_ltp']:.2f}",
                severity="success",
                date_str=today,
                user_id="system",
                strategy_id="btc-option-selling",
                paper=True,
            )
            placed += 1
    except Exception as sys_exc:
        log.error("Failed to create system benchmark BTC trade: %s", sys_exc)

    # ── 3. Process User Deployments ───────────────────────────────────────────
    all_ready = firebase_service.list_deployments_by_status("ready")
    all_enabled = firebase_service.list_deployments_by_status("enabled")
    deployments = [
        d for d in (all_ready + all_enabled)
        if d.get("strategyCode") == "BTC_OPTION_SELLING" and not d.get("pausedByAdmin")
    ]

    for dep in deployments:
        # Idempotency
        existing = position_service.get_open_positions_for_user_strategy(dep["id"], today)
        if existing:
            log.warning("BTC deployment %s already has positions today — skipping.", dep["id"])
            skipped += 1
            continue

        account = accounts.get(dep.get("brokerAccountId", ""))
        user_id = dep.get("userId")
        user_doc = users.get(user_id, {})
        paper = user_doc.get("paperTrading", True)
        lots = dep.get("multiplier", 1)

        user_name = "User"
        try:
            ud = firebase_service.get_db().collection("users").document(user_id).get()
            if ud.exists:
                user_name = ud.to_dict().get("username") or ud.to_dict().get("email") or "User"
        except Exception:
            pass

        # Get Delta API credentials
        api_key = api_secret = None
        if not paper and account:
            tokens = token_store.get_tokens(account["id"])
            if tokens and tokens.get("broker") == "delta":
                api_key = tokens.get("api_key")
                api_secret = tokens.get("api_secret")
            if not api_key or not api_secret:
                _log(
                    "token_invalid",
                    f"Delta API credentials missing for BTC deployment {dep['id']} — skipping.",
                    "error",
                    date_str=today,
                    user_id=user_id,
                    user_name=user_name,
                    strategy_id=dep.get("strategyId"),
                )
                failed += 1
                continue

        delta_creds = {"api_key": api_key, "api_secret": api_secret} if not paper else {}

        try:
            strategy = get_strategy("BTC_OPTION_SELLING")
        except ValueError as exc:
            log.error("BTC strategy not found: %s", exc)
            failed += 1
            continue

        legs = strategy.get_entry_legs(dep, atm_data["atm_strike"], atm_data["expiry"], lots)

        leg_map = {
            "CE": (str(atm_data["ce_product_id"]), atm_data["ce_symbol"], atm_data["ce_ltp"]),
            "PE": (str(atm_data["pe_product_id"]), atm_data["pe_symbol"], atm_data["pe_ltp"]),
        }

        dep_placed = dep_failed = 0

        for leg in legs:
            option_type = leg["optionType"]
            qty = leg["quantity"]
            product_id_str, symbol, ltp = leg_map[option_type]
            tag_prefix = f"BTC_{dep['id'][:6].upper()}_{option_type}"

            try:
                # Step 1: Place SELL MARKET
                sell_result = await order_service.place_sell_market(
                    access_token="delta_token",
                    instrument_key=product_id_str,
                    quantity=qty,
                    tag=f"{tag_prefix[:18]}_E",
                    paper=paper,
                    ltp=ltp,
                    broker="delta" if not paper else "upstox",
                    delta_creds=delta_creds if not paper else None,
                )
                fill_price_usd = sell_result["fill_price"] or ltp
                fill_price_inr = delta_service.usd_to_inr(fill_price_usd, usd_inr_rate)

                # Step 2: Calculate SL price and place Stop-Market
                sl_price_usd = strategy.calculate_sl_price(fill_price_usd)
                sl_price_inr = delta_service.usd_to_inr(sl_price_usd, usd_inr_rate)
                sl_result = await order_service.place_sl_market(
                    access_token="delta_token",
                    instrument_key=product_id_str,
                    quantity=qty,
                    trigger_price=sl_price_usd,
                    tag=f"{tag_prefix[:18]}_SL",
                    paper=paper,
                    broker="delta" if not paper else "upstox",
                    delta_creds=delta_creds if not paper else None,
                )

                # Step 3: Write position to Firestore
                pos_id = position_service.create_position({
                    "date": today,
                    "userId": user_id,
                    "strategyId": dep.get("strategyId", "btc-option-selling"),
                    "strategyCode": "BTC_OPTION_SELLING",
                    "userStrategyId": dep["id"],
                    "brokerAccountId": dep.get("brokerAccountId"),
                    "broker": "delta",
                    "instrumentKey": product_id_str,
                    "symbol": symbol,
                    "optionType": option_type,
                    "strike": leg["strike"],
                    "expiry": leg["expiry"],
                    "quantity": qty,
                    "lots": lots,
                    "entryOrderId": sell_result["order_id"],
                    "slOrderId": sl_result["order_id"],
                    "entryPrice": fill_price_usd,       # USD
                    "entryPriceInr": fill_price_inr,    # INR equivalent
                    "slPrice": sl_price_usd,            # USD
                    "slPriceInr": sl_price_inr,         # INR equivalent
                    "currency": "USD",
                    "usdToInrRate": usd_inr_rate,
                    "status": "open",
                    "isPaper": paper,
                    "entryAt": _now_ist(),
                    "exitAt": None,
                    "exitPrice": None,
                    "exitPriceInr": None,
                    "exitOrderId": None,
                    "exitReason": None,
                    "pnl": None,          # USD P&L on close
                    "pnlInr": None,       # INR P&L on close
                })

                _log(
                    "order_placed",
                    f"[{'PAPER ' if paper else ''}BTC ENTRY] {symbol} | "
                    f"SELL {qty}@${fill_price_usd:.4f} (₹{fill_price_inr:.2f}) | "
                    f"SL ${sl_price_usd:.4f}",
                    severity="success",
                    date_str=today,
                    user_id=user_id,
                    user_name=user_name,
                    strategy_id=dep.get("strategyId"),
                    position_id=pos_id,
                    paper=paper,
                    metadata={
                        "symbol": symbol,
                        "optionType": option_type,
                        "entryPriceUsd": fill_price_usd,
                        "entryPriceInr": fill_price_inr,
                        "slPriceUsd": sl_price_usd,
                        "quantity": qty,
                        "exchange": "delta",
                    },
                )
                dep_placed += 1

            except Exception as exc:  # noqa: BLE001
                log.error("BTC entry failed for %s %s: %s", dep["id"], option_type, exc)
                dep_failed += 1
                _log(
                    "order_failed",
                    f"BTC entry failed for {option_type} leg — {exc}",
                    severity="error",
                    date_str=today,
                    user_id=user_id,
                    user_name=user_name,
                    strategy_id=dep.get("strategyId"),
                    paper=paper,
                    metadata={"error": str(exc), "optionType": option_type, "exchange": "delta"},
                )

        placed += dep_placed
        failed += dep_failed

        if dep_placed > 0:
            firebase_service.update_user_strategy_status(dep["id"], "trade_active")
        elif dep_failed > 0:
            firebase_service.update_user_strategy_status(dep["id"], "enabled")

    summary = {"placed": placed, "failed": failed, "skipped": skipped}
    log.info("BTC entry complete: %s", summary)
    return summary


# ── 17:29 — Execute BTC exit (Delta Exchange) ─────────────────────────────────

async def execute_btc_exit() -> dict:
    """Square off all open BTC_OPTION_SELLING positions via Delta Exchange at 17:29 IST.

    Steps per open BTC position:
      1. Cancel the stop-market SL order.
      2. Place BUY MARKET to square off the short.
      3. Compute PnL in USD and INR.
      4. Update position.status = 'squared_off'.
    """
    from services import delta_service
    from utils import token_store

    today = _today()
    paper = firebase_service.is_paper_trading()
    all_open = position_service.get_open_positions_for_date(today)
    # Filter to BTC positions only
    open_positions = [p for p in all_open if p.get("strategyCode") == "BTC_OPTION_SELLING"]
    accounts = _accounts_by_id()

    if not open_positions:
        log.info("No open BTC positions at 17:29 exit time.")
        _log("exit_skipped", "17:29 BTC exit — no open BTC positions found.", "info",
             date_str=today, paper=paper)
        return {"closed": 0, "failed": 0}

    usd_inr_rate = getattr(__import__("config", fromlist=["settings"]).settings, "usd_to_inr_rate", 85.0)
    closed = failed = 0
    closed_deployment_ids: set[str] = set()

    for pos in open_positions:
        if pos.get("status") != "open":
            continue

        account = accounts.get(pos.get("brokerAccountId", ""))
        pos_paper = pos.get("isPaper", paper)

        # Get Delta API credentials
        api_key = api_secret = None
        if not pos_paper and account:
            tokens = token_store.get_tokens(account["id"])
            if tokens and tokens.get("broker") == "delta":
                api_key = tokens.get("api_key")
                api_secret = tokens.get("api_secret")

        delta_creds = {"api_key": api_key, "api_secret": api_secret} if (api_key and api_secret) else {}

        user_name = "User"
        try:
            ud = firebase_service.get_db().collection("users").document(pos.get("userId")).get()
            if ud.exists:
                user_name = ud.to_dict().get("username") or ud.to_dict().get("email") or "User"
        except Exception:
            pass

        try:
            # Step 1: Cancel SL stop-market order
            sl_order_id = pos.get("slOrderId", "")
            if sl_order_id:
                try:
                    await order_service.cancel_order(
                        access_token="delta_token",
                        order_id=sl_order_id,
                        paper=pos_paper,
                        broker="delta" if not pos_paper else "upstox",
                        delta_creds=delta_creds if not pos_paper else None,
                        product_id=pos.get("instrumentKey"),
                    )
                except Exception as e:
                    log.warning("BTC exit: Could not cancel SL order %s: %s", sl_order_id, e)

            # Step 2: Get current LTP for PnL estimate
            current_ltp_usd = 0.0
            try:
                current_ltp_usd = await delta_service.get_option_ltp(int(pos["instrumentKey"]))
            except Exception as e:
                log.warning("BTC exit: Could not fetch LTP for %s: %s", pos["instrumentKey"], e)

            # Step 3: Place BUY MARKET to square off
            tag = f"BQ_{pos['id'][:8].upper()}"
            buy_result = await order_service.place_buy_market(
                access_token="delta_token",
                instrument_key=pos["instrumentKey"],
                quantity=pos["quantity"],
                tag=tag[:20],
                paper=pos_paper,
                ltp=current_ltp_usd,
                broker="delta" if not pos_paper else "upstox",
                delta_creds=delta_creds if not pos_paper else None,
            )
            exit_price_usd = buy_result["fill_price"] or current_ltp_usd or pos["entryPrice"]
            exit_price_inr = delta_service.usd_to_inr(exit_price_usd, usd_inr_rate)

            # Step 4: Compute PnL (sold at entry, bought to close → profit if exit < entry)
            pnl_usd = round((pos["entryPrice"] - exit_price_usd) * pos["quantity"], 6)
            pnl_inr = delta_service.usd_to_inr(pnl_usd, usd_inr_rate)

            position_service.update_position(pos["id"], {
                "status": "squared_off",
                "exitReason": "eod_exit",
                "exitOrderId": buy_result["order_id"],
                "exitPrice": exit_price_usd,
                "exitPriceInr": exit_price_inr,
                "exitAt": _now_ist(),
                "pnl": pnl_usd,
                "pnlInr": pnl_inr,
            })

            _log(
                "square_off",
                f"[{'PAPER ' if pos_paper else ''}BTC EXIT] {pos['symbol']} | "
                f"BUY {pos['quantity']}@${exit_price_usd:.4f} (₹{exit_price_inr:.2f}) | "
                f"PnL ${pnl_usd:+.6f} (₹{pnl_inr:+.2f})",
                severity="success" if pnl_usd >= 0 else "warning",
                date_str=today,
                user_id=pos.get("userId"),
                user_name=user_name,
                strategy_id=pos.get("strategyId"),
                position_id=pos["id"],
                paper=pos_paper,
                metadata={
                    "symbol": pos["symbol"],
                    "entryPriceUsd": pos["entryPrice"],
                    "exitPriceUsd": exit_price_usd,
                    "pnlUsd": pnl_usd,
                    "pnlInr": pnl_inr,
                    "quantity": pos["quantity"],
                    "exchange": "delta",
                },
            )
            closed += 1
            closed_deployment_ids.add(pos.get("userStrategyId", ""))

        except Exception as exc:  # noqa: BLE001
            log.error("BTC exit failed for position %s: %s", pos["id"], exc)
            failed += 1
            _log(
                "exit_error",
                f"BTC exit failed for {pos.get('symbol')} — {exc}",
                severity="error",
                date_str=today,
                user_id=pos.get("userId"),
                user_name=user_name,
                strategy_id=pos.get("strategyId"),
                position_id=pos["id"],
                paper=pos_paper,
                metadata={"error": str(exc), "exchange": "delta"},
            )

    for dep_id in closed_deployment_ids:
        if dep_id and not dep_id.startswith("system"):
            try:
                firebase_service.update_user_strategy_status(dep_id, "trade_closed")
            except Exception as e:
                log.warning("Could not update userStrategy status for %s: %s", dep_id, e)

    summary = {"closed": closed, "failed": failed, "paper": paper}
    log.info("BTC exit complete: %s", summary)
    return summary


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
