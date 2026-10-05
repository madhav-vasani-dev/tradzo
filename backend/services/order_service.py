"""Order Service — the single gateway for ALL broker order placement.

Rules
-----
1. Every order MUST go through this module.  Never call upstox_service.place_order
   directly from the execution engine.
2. When paper=True, orders are simulated locally — no broker API is called.
3. The caller is responsible for providing the correct access_token and paper flag.
4. Each function returns a minimal dict: {"order_id": str, "fill_price": float}
   so the rest of the engine is broker-agnostic.

Paper mode fill prices
----------------------
SELL MARKET  → uses the `ltp` argument as the simulated fill price.
SL-M         → no fill_price (order stays open until triggered).
BUY MARKET   → uses the `ltp` argument as the simulated fill price.

Product type
------------
Equity/F&O legs are placed with the product code from `settings.equity_product`
("delivery" by default → Upstox "D" / Jainam "NRML"). Delivery/NRML positions are NOT
auto-squared-off by the broker at 15:15 — the strategy owns its own exit. Delta Exchange
has no product concept; crypto positions always carry forward.

"Market" orders
---------------
`settings.order_style` picks how place_sell_market / place_buy_market send an order:
  "market" (default) — a plain MARKET order, as before.
  "limit"            — a marketable IOC LIMIT priced past the LTP by `market_protection_pct`,
                       escalating on a miss. Use this if the broker/exchange starts refusing
                       API MARKET orders (Upstox announced that from 1 Oct 2025; it has not
                       been observed on this account).
Either way the fill is VERIFIED against the broker (never assumed from the LTP), and if the
order can't be filled the call RAISES `OrderNotFilled` — callers must never assume a fill.
Delta Exchange keeps its own market_order path.

Exchanges / brokers
-------------------
`exchange` is "NSE" (Nifty F&O) or "MCX" (commodity options). MCX options never take market
orders (brokers reject them) and MCX accepts DAY validity only, so every MCX entry/exit is a
DAY limit priced past the LTP that is cancelled and re-priced if it does not fill within
`mcx_order_wait_seconds`, and every MCX stop-loss is a stop-LIMIT from the start.
Kotak Neo always gets limit orders (Kotak converts API market orders into its own protected
limits anyway, and recommends sending limits); its stop-losses are always SL (stop-limit).

Stop-loss orders
----------------
Every SL is placed as a stop-MARKET. NSE discontinued SL-M in the F&O segment, so an
Indian broker may silently downgrade it to a stop-LIMIT priced AT the trigger, which
does not fill when the market gaps through. After placing, we read the order back and,
if it was downgraded, repair the limit price to `trigger × (1 + sl_limit_buffer_pct)`
so it still fills on a spike with a bounded worst price.
"""
import asyncio
import logging
import math
import time
import uuid

import httpx

from config import settings

log = logging.getLogger("tradzo.orders")

UPSTOX_BASE = "https://api.upstox.com/v2"
PLACE_ORDER_URL = f"{UPSTOX_BASE}/order/place"
CANCEL_ORDER_URL = f"{UPSTOX_BASE}/order/cancel"
MODIFY_ORDER_URL = f"{UPSTOX_BASE}/order/modify"

# NSE quotes options in 5-paise ticks; a limit price off-tick is rejected.
NSE_TICK = 0.05
# MCX crude options: prices are kept on a 10-paise grid, which is valid whether the contract's
# tick is 0.05 or 0.10.
MCX_TICK = 0.10


def tick_for(exchange: str | None) -> float:
    return MCX_TICK if str(exchange or "").upper() == "MCX" else NSE_TICK


def _is_mcx(exchange: str | None) -> bool:
    return str(exchange or "").upper() == "MCX"


# ── Product-type helpers ──────────────────────────────────────────────────────

def _is_delivery() -> bool:
    return str(getattr(settings, "equity_product", "delivery")).lower() != "intraday"


def upstox_product() -> str:
    """Upstox product code: "D" = delivery/carry-forward, "I" = intraday."""
    return "D" if _is_delivery() else "I"


def jainam_product() -> str:
    """Jainam (XTS) product code: "NRML" = carry-forward, "MIS" = intraday."""
    return "NRML" if _is_delivery() else "MIS"


def kotak_product(exchange: str | None = "NSE") -> str:
    """Kotak Neo product: NRML (carry-forward) / MIS. Kotak does not allow MIS in commodity
    options, so MCX legs are always NRML."""
    if _is_mcx(exchange):
        return "NRML"
    return "NRML" if _is_delivery() else "MIS"


def jainam_segment(exchange: str | None) -> str:
    return "MCXFO" if _is_mcx(exchange) else "NSEFO"


# ── Stop-loss price helpers ───────────────────────────────────────────────────

def _round_up_tick(price: float, tick: float = NSE_TICK) -> float:
    return round(math.ceil(round(price / tick, 6)) * tick, 2)


def sl_limit_price(trigger_price: float, tick: float = NSE_TICK) -> float:
    """Protective limit price for a BUY stop order that must fill through a spike.

    Sits `sl_limit_buffer_pct` ABOVE the trigger so the order behaves like a market
    order once triggered, while capping the worst fill.
    """
    buffer_pct = float(getattr(settings, "sl_limit_buffer_pct", 10.0))
    return _round_up_tick(trigger_price * (1 + buffer_pct / 100.0), tick)


# ── Paper-mode helpers ────────────────────────────────────────────────────────

def _paper_id() -> str:
    return f"PAPER_{uuid.uuid4().hex[:10].upper()}"


# ── Internal real-broker call ────────────────────────────────────────────────

async def _real_place(access_token: str, payload: dict) -> dict:
    """POST to Upstox place-order endpoint. Raises RuntimeError on failure."""
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(PLACE_ORDER_URL, json=payload, headers=headers)
    body = resp.json() if resp.content else {}
    if resp.status_code not in (200, 201):
        log.error("Upstox order failed %s: %s", resp.status_code, body)
        raise RuntimeError(body.get("errors", "order_placement_failed"))
    return body


async def _real_modify(access_token: str, payload: dict) -> dict:
    """PUT to Upstox modify-order endpoint. Raises RuntimeError on failure."""
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.put(MODIFY_ORDER_URL, json=payload, headers=headers)
    body = resp.json() if resp.content else {}
    if resp.status_code not in (200, 201):
        log.error("Upstox modify failed %s: %s", resp.status_code, body)
        raise RuntimeError(body.get("errors", "order_modify_failed"))
    return body


async def _real_cancel(access_token: str, order_id: str) -> dict:
    """DELETE to Upstox cancel-order endpoint. Raises RuntimeError on failure."""
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.delete(
            CANCEL_ORDER_URL,
            params={"order_id": order_id},
            headers=headers,
        )
    body = resp.json() if resp.content else {}
    if resp.status_code not in (200, 201):
        log.error("Upstox cancel failed %s: %s", resp.status_code, body)
        raise RuntimeError(body.get("errors", "order_cancel_failed"))
    return body


# ── Public API ────────────────────────────────────────────────────────────────

async def get_order_details(access_token: str, order_id: str) -> dict:
    """GET to Upstox order details endpoint. Returns the order object."""
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    url = f"{UPSTOX_BASE}/order/details"
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, params={"order_id": order_id}, headers=headers)
    body = resp.json() if resp.content else {}
    if resp.status_code not in (200, 201):
        log.error("Upstox get order details failed %s: %s", resp.status_code, body)
        raise RuntimeError(body.get("errors", "get_order_details_failed"))
    return body.get("data", {})


async def _get_upstox_fill_price(access_token: str, order_id: str, default_price: float) -> float:
    """Poll Upstox order details for the actual average fill price of a MARKET order.

    Upstox's place-order response does not include the fill price, so the SL must be
    computed from the real fill (not the pre-trade LTP). Falls back to default_price
    (the LTP) only if the fill genuinely can't be retrieved in time.
    """
    import asyncio
    if not order_id:
        return default_price
    for _ in range(10):
        try:
            details = await get_order_details(access_token, order_id)
            status = str(details.get("status", "")).lower()
            avg = float(details.get("average_price") or 0.0)
            if status == "complete" and avg > 0:
                return avg
            if status in ("rejected", "cancelled"):
                break
        except Exception as e:  # noqa: BLE001 — polling must not raise
            log.warning("Upstox fill-price poll failed for %s: %s", order_id, e)
        await asyncio.sleep(0.2)
    return default_price


async def _get_jainam_fill_price(token: str, app_order_id: str, default_price: float) -> float:
    import asyncio
    from services import jainam_service
    # Poll for up to ~4.5s — a market order often isn't reported FILLED within 0.5s,
    # and the SL must be computed off the real fill, not the fallback LTP.
    for _ in range(15):
        try:
            history = await jainam_service.get_order_history(token, app_order_id)
            if history:
                filled = [h for h in history if str(h.get("orderstatus", "")).upper() == "FILLED"]
                if filled:
                    latest = filled[-1]
                    return float(latest.get("averageprice") or latest.get("averagePrice") or default_price)
        except Exception as e:
            log.warning("Failed to get Jainam order fill price: %s", e)
        await asyncio.sleep(0.3)
    return default_price


# ── Marketable-limit ("market with protection") orders ────────────────────────

class OrderNotFilled(RuntimeError):
    """A protected-limit order could not be (fully) filled.

    Carries whatever DID fill so the caller can reconcile a partial fill instead of
    treating the whole leg as untouched.
    """

    def __init__(self, message: str, *, filled_qty: int = 0, avg_price: float = 0.0,
                 remaining: int = 0, order_id: str = "", ambiguous: bool = False):
        super().__init__(message)
        # True when we could not tell whether the order filled (timeout, unreadable status).
        # The order may well HAVE filled — callers must check the broker before acting.
        self.ambiguous = ambiguous
        self.filled_qty = filled_qty
        self.avg_price = avg_price
        self.remaining = remaining
        self.order_id = order_id


def _round_down_tick(price: float, tick: float = NSE_TICK) -> float:
    return round(math.floor(round(price / tick, 6)) * tick, 2)


def protected_limit_price(ref_price: float, side: str, buffer_pct: float, tick: float = NSE_TICK) -> float:
    """Limit price that behaves like a market order but caps the worst fill.

    BUY sits `buffer_pct` above the reference (LTP), SELL sits below it, tick-aligned.
    The pad is at least two ticks so very cheap options still get a marketable price.
    """
    pad = max(ref_price * buffer_pct / 100.0, 2 * tick)
    if side == "BUY":
        return _round_up_tick(ref_price + pad, tick)
    return max(_round_down_tick(ref_price - pad, tick), tick)


def _ci(row: dict, *keys, default=None):
    """Case-insensitive dict lookup — XTS responses vary their key casing."""
    lowered = {str(k).lower(): v for k, v in (row or {}).items()}
    for k in keys:
        v = lowered.get(k.lower())
        if v not in (None, ""):
            return v
    return default


async def _order_fill_state(access_token: str, order_id: str, broker: str) -> dict:
    """Normalised order state: {terminal, status, filled_qty, avg_price, message}.

    status is one of "complete" | "cancelled" | "rejected" | "open" | "unknown".
    """
    if broker == "kotak":
        from services import kotak_service
        st = await kotak_service.order_state(access_token, order_id)
        return {"terminal": st["terminal"], "status": st["status"], "filled_qty": st["filled_qty"],
                "avg_price": st["avg_price"], "message": st["message"]}

    if broker == "jainam":
        from services import jainam_service
        hist = await jainam_service.get_order_history(access_token, order_id)
        if not hist:
            return {"terminal": False, "status": "unknown", "filled_qty": 0, "avg_price": 0.0, "message": ""}
        raw = str(_ci(hist[-1], "orderstatus", default="")).upper().replace(" ", "")
        status = {
            "FILLED": "complete",
            "CANCELLED": "cancelled",
            "EXPIRED": "cancelled",
            "REJECTED": "rejected",
        }.get(raw, "open")
        filled = max(int(float(_ci(r, "cumulativequantity", "cumulativeqty", default=0) or 0)) for r in hist)
        avg = 0.0
        for r in reversed(hist):
            a = float(_ci(r, "orderaveragetradedprice", "averageprice", "averagetradedprice", default=0) or 0)
            if a > 0:
                avg = a
                break
        msg = str(_ci(hist[-1], "cancelrejectreason", default="") or "")
        return {"terminal": status != "open", "status": status, "filled_qty": filled,
                "avg_price": avg, "message": msg}

    details = await get_order_details(access_token, order_id)
    raw = str(details.get("status", "")).lower()
    status = raw if raw in ("complete", "cancelled", "rejected") else "open"
    return {
        "terminal": status != "open",
        "status": status,
        "filled_qty": int(float(details.get("filled_quantity") or 0)),
        "avg_price": float(details.get("average_price") or 0.0),
        "message": str(details.get("status_message") or details.get("status_message_raw") or ""),
    }


async def _submit_limit(
    access_token: str, instrument_key: str, quantity: int, side: str,
    price: float | None, tag: str, broker: str, exchange: str = "NSE",
) -> str:
    """Send one order and return the broker order id.

    price=None sends a plain MARKET/DAY order; otherwise a LIMIT at `price` — IOC on NSE,
    DAY on MCX (MCX has no IOC; `_place_protected` cancels it if it does not fill).
    """
    is_market = price is None
    mcx = _is_mcx(exchange)
    if is_market and (mcx or broker == "kotak"):
        raise RuntimeError("market orders are not used for this broker/exchange — a limit price is required")
    limit_tif = "DAY" if mcx else "IOC"

    if broker == "kotak":
        from services import kotak_service
        seg, _tok, sym = kotak_service.parse_instrument_key(instrument_key)
        return await kotak_service.place_order(
            access_token, segment=seg, trading_symbol=sym, side=side, quantity=quantity,
            order_type="L", price=price, product=kotak_product(exchange),
            validity=limit_tif, tag=tag,
        )

    if broker == "jainam":
        from services import jainam_service
        resp = await jainam_service.place_order(access_token, {
            "exchangeSegment": jainam_segment(exchange),
            "exchangeInstrumentID": int(instrument_key),
            "productType": jainam_product(),
            "orderType": "Market" if is_market else "Limit",
            "orderSide": side,
            "timeInForce": "DAY" if is_market else limit_tif,
            "disclosedQuantity": 0,
            "orderQuantity": quantity,
            "limitPrice": 0.0 if is_market else price,
            "stopPrice": 0.0,
            "orderUniqueIdentifier": tag[:20],
        })
        order_id = resp.get("result", {}).get("appOrderID")
        if not order_id:
            raise RuntimeError("Jainam order placement failed: no appOrderID returned")
        return str(order_id)

    resp = await _real_place(access_token, {
        "instrument_token": instrument_key,
        "quantity": quantity,
        "order_type": "MARKET" if is_market else "LIMIT",
        "transaction_type": side,
        "product": upstox_product(),
        "validity": "DAY" if is_market else limit_tif,
        "price": 0 if is_market else price,    # Upstox requires price=0 for MARKET (UDAPI1008)
        "disclosed_quantity": 0,
        "trigger_price": 0,
        "is_amo": False,
        "tag": tag[:40],
    })
    order_id = resp.get("data", {}).get("order_id", "")
    if not order_id:
        raise RuntimeError("Upstox order placement failed: no order_id returned")
    return str(order_id)


async def _await_terminal(access_token: str, order_id: str, broker: str, timeout: float) -> dict | None:
    """Poll until the order reaches a terminal state, or `timeout` seconds pass."""
    deadline = time.monotonic() + timeout
    state = None
    # Kotak allows ~10 requests/second across all APIs — poll it more gently.
    interval = 0.5 if broker == "kotak" else 0.25
    while True:
        try:
            state = await _order_fill_state(access_token, order_id, broker)
            if state["terminal"]:
                return state
        except Exception as exc:  # noqa: BLE001 — polling must not raise
            log.warning("Order state poll failed for %s: %s", order_id, exc)
        if time.monotonic() >= deadline:
            return state
        await asyncio.sleep(interval)


async def cancel_until_terminal(access_token: str, order_id: str, broker: str,
                                total_seconds: float = 20.0) -> dict | None:
    """Cancel a resting order and keep re-sending the cancel until the broker reports it
    terminal (or `total_seconds` pass). Returns the last known state.

    Used for DAY limits (MCX has no IOC): giving up while the order still rests would leave a
    live order that can fill later, untracked.
    """
    deadline = time.monotonic() + total_seconds
    state = None
    while True:
        try:
            await cancel_order(access_token, order_id, paper=False, broker=broker)
        except Exception as exc:  # noqa: BLE001 — "already complete/cancelled" lands here too
            log.info("Cancel of %s raised (will verify state): %s", order_id, exc)
        state = await _await_terminal(access_token, order_id, broker, min(3.0, max(0.5, deadline - time.monotonic())))
        if (state and state["terminal"]) or time.monotonic() >= deadline:
            return state
        log.warning("Order %s still not terminal after cancel — re-sending cancel.", order_id)


async def _place_protected(
    *,
    access_token: str,
    instrument_key: str,
    quantity: int,
    side: str,
    tag: str,
    ltp: float,
    broker: str,
    ltp_fn=None,
    reference_fallback: float = 0.0,
    exchange: str = "NSE",
) -> dict:
    """Fill `quantity` and verify it, retrying on a miss.

    order_style "market": plain MARKET orders. "limit": IOC limits priced past the LTP,
    with the buffer doubling each attempt.

    Returns {"order_id", "fill_price", "filled_quantity", "order_ids"} on a full fill.
    Raises OrderNotFilled otherwise (carrying any partial fill). Never places a new order
    while an earlier one's outcome is unknown — a duplicate would double the position.
    """
    start = float(getattr(settings, "market_protection_pct", 2.0))
    cap = float(getattr(settings, "market_protection_max_pct", 10.0))
    attempts = int(getattr(settings, "order_max_attempts", 4))
    timeout = float(getattr(settings, "order_status_timeout_seconds", 3.0))
    use_market = str(getattr(settings, "order_style", "market")).lower() != "limit"
    tick = tick_for(exchange)
    if _is_mcx(exchange) or broker == "kotak":
        use_market = False
    if _is_mcx(exchange):
        # A DAY limit can legitimately rest for a moment before it trades.
        timeout = max(timeout, float(getattr(settings, "mcx_order_wait_seconds", 4.0)))

    remaining = quantity
    filled_total = 0
    notional = 0.0
    order_ids: list[str] = []

    def _fail(msg: str, ambiguous: bool = False) -> OrderNotFilled:
        avg = notional / filled_total if filled_total else 0.0
        return OrderNotFilled(
            f"{side} {instrument_key}: {msg} (filled {filled_total}/{quantity})",
            filled_qty=filled_total, avg_price=avg, remaining=remaining,
            order_id=order_ids[-1] if order_ids else "", ambiguous=ambiguous,
        )

    for attempt in range(attempts):
        fresh = 0.0
        if ltp_fn is not None:
            try:
                fresh = float(await ltp_fn() or 0.0)
            except Exception as exc:  # noqa: BLE001
                log.warning("LTP refresh failed for %s: %s", instrument_key, exc)
        ref = fresh or ltp or reference_fallback
        buffer_pct = 0.0
        if use_market:
            price = None
        else:
            if ref <= 0:
                raise _fail("no reference price (LTP) available to price a protected limit order")
            buffer_pct = min(start * (2 ** attempt), cap)
            price = protected_limit_price(ref, side, buffer_pct, tick)
        attempt_tag = tag if attempt == 0 else f"{tag}_{attempt}"

        try:
            order_id = await _submit_limit(access_token, instrument_key, remaining, side, price, attempt_tag,
                                           broker, exchange)
        except Exception as exc:  # noqa: BLE001 — outcome ambiguous (timeout) or rejected: stop, don't stack orders
            raise _fail(f"order submit failed on attempt {attempt + 1}: {exc}", ambiguous=True) from exc
        order_ids.append(order_id)

        state = await _await_terminal(access_token, order_id, broker, timeout)
        if state is None or not state["terminal"]:
            # IOC should be terminal almost instantly; an MCX DAY limit that hasn't traded is
            # still resting. Either way: cancel it and CONFIRM it is dead before re-pricing.
            if _is_mcx(exchange) or broker == "kotak":
                state = await cancel_until_terminal(access_token, order_id, broker)
            else:
                try:
                    await cancel_order(access_token, order_id, paper=False, broker=broker)
                except Exception as exc:  # noqa: BLE001
                    log.warning("Cancel of unresolved order %s failed: %s", order_id, exc)
                state = await _await_terminal(access_token, order_id, broker, timeout)
            if state is None or not state["terminal"]:
                raise _fail(f"order {order_id} state unknown (it may still be LIVE at the broker) — "
                            f"not retrying to avoid a duplicate", ambiguous=True)

        filled = state["filled_qty"]
        if state["status"] == "complete" and filled <= 0:
            filled = remaining
        filled = min(filled, remaining)
        if filled > 0:
            notional += filled * (state["avg_price"] or price or ref)
            filled_total += filled
            remaining -= filled

        if remaining <= 0:
            return {
                "order_id": order_ids[0],
                "fill_price": notional / filled_total,
                "filled_quantity": filled_total,
                "order_ids": order_ids,
            }

        log.warning(
            "%s %s attempt %d/%d not filled (%s, ref %.2f, buffer %.1f%%): status=%s filled=%d/%d %s",
            side, instrument_key, attempt + 1, attempts,
            "MARKET" if price is None else f"limit {price:.2f}", ref, buffer_pct,
            state["status"], filled_total, quantity, state["message"],
        )

    raise _fail(f"not filled after {attempts} attempts")


async def place_sell_market(
    access_token: str,
    instrument_key: str,
    quantity: int,
    tag: str,
    paper: bool,
    ltp: float = 0.0,
    broker: str = "upstox",
    delta_creds: dict | None = None,
    ltp_fn=None,
    ref_fallback: float = 0.0,
    exchange: str = "NSE",
) -> dict:
    """Sell (short) an instrument "at market" (verified fill; see settings.order_style).

    `ltp_fn` is an optional async callable returning a fresh LTP (used on retries);
    `ref_fallback` prices the order when no LTP is available.
    Returns {"order_id": str, "fill_price": float}. Raises OrderNotFilled on a miss.
    """
    if paper:
        oid = _paper_id()
        log.info("[PAPER] SELL MKT  %-40s qty=%-5s fill=%-8.4f tag=%s → %s",
                 instrument_key, quantity, ltp, tag, oid)
        return {"order_id": oid, "fill_price": ltp}

    if broker == "delta":
        from services import delta_service
        payload = {
            "product_id": int(instrument_key),
            "size": quantity,
            "side": "sell",
            "order_type": "market_order",
            "time_in_force": "ioc",
            "client_order_id": tag[:20],  # Delta limits to 20 chars
        }
        result = await delta_service.place_order(
            delta_creds["api_key"], delta_creds["api_secret"], payload
        )
        order_id = str(result.get("id", ""))
        fill_price = float(result.get("average_fill_price") or ltp)
        return {"order_id": order_id, "fill_price": fill_price}

    return await _place_protected(
        access_token=access_token,
        instrument_key=instrument_key,
        quantity=quantity,
        side="SELL",
        tag=tag,
        ltp=ltp,
        broker=broker,
        ltp_fn=ltp_fn,
        reference_fallback=ref_fallback,
        exchange=exchange,
    )


async def place_sl_market(
    access_token: str,
    instrument_key: str,
    quantity: int,
    trigger_price: float,
    tag: str,
    paper: bool,
    broker: str = "upstox",
    delta_creds: dict | None = None,
    exchange: str = "NSE",
) -> dict:
    """Place a BUY SL-M order (stop-loss for a short leg).

    The order lives on the broker's server; it fires automatically when
    the market price crosses trigger_price, even if our backend is down.

    Returns {"order_id": str}
    """
    if paper:
        oid = _paper_id()
        log.info("[PAPER] BUY SL-M  %-40s qty=%-5s trigger=%-8.4f tag=%s → %s",
                 instrument_key, quantity, trigger_price, tag, oid)
        return {"order_id": oid}

    if broker == "delta":
        from services import delta_service
        # Delta expresses a stop-MARKET SL as a market_order + stop_order_type=stop_loss_order.
        # (order_type only accepts "limit_order"/"market_order"; "stop_market_order" is invalid
        # and was being rejected, leaving live BTC shorts unprotected.)
        payload = {
            "product_id": int(instrument_key),
            "size": quantity,
            "side": "buy",
            "order_type": "market_order",
            "stop_order_type": "stop_loss_order",
            "stop_price": str(trigger_price),
            "stop_trigger_method": "mark_price",
            "reduce_only": True,       # SL only closes the existing short, never opens new
            "time_in_force": "gtc",    # Good Till Cancelled for SL orders
            "client_order_id": tag[:20],
        }
        result = await delta_service.place_order(
            delta_creds["api_key"], delta_creds["api_secret"], payload
        )
        return {"order_id": str(result.get("id", ""))}

    tick = tick_for(exchange)
    trigger_price = _round_up_tick(trigger_price, tick)
    protective_limit = sl_limit_price(trigger_price, tick)
    mcx = _is_mcx(exchange)

    if broker == "kotak":
        # Kotak: always a stop-LIMIT (SL-M is restricted in F&O and not offered on MCX options).
        from services import kotak_service
        seg, _tok, sym = kotak_service.parse_instrument_key(instrument_key)
        order_no = await kotak_service.place_order(
            access_token, segment=seg, trading_symbol=sym, side="BUY", quantity=quantity,
            order_type="SL", price=protective_limit, trigger_price=trigger_price,
            product=kotak_product(exchange), validity="DAY", tag=tag,
        )
        return {"order_id": order_no}

    if broker == "jainam":
        from services import jainam_service

        async def _place_jainam_sl(order_type: str, limit: float) -> str:
            resp = await jainam_service.place_order(access_token, {
                "exchangeSegment": jainam_segment(exchange),
                "exchangeInstrumentID": int(instrument_key),
                "productType": jainam_product(),
                "orderType": order_type,
                "orderSide": "BUY",
                "timeInForce": "DAY",
                "disclosedQuantity": 0,
                "orderQuantity": quantity,
                "limitPrice": limit,
                "stopPrice": trigger_price,
                "orderUniqueIdentifier": tag,
            })
            oid = resp.get("result", {}).get("appOrderID")
            if not oid:
                raise RuntimeError(f"Jainam {order_type} SL placement failed: no appOrderID returned")
            return str(oid)

        if mcx:
            # MCX options take no stop-market orders — go straight to a protective stop-limit.
            return {"order_id": await _place_jainam_sl("StopLimit", protective_limit)}
        try:
            app_order_id = await _place_jainam_sl("StopMarket", 0.0)
        except Exception as exc:  # noqa: BLE001 — NSE F&O rejects SL-M; fall back immediately.
            log.warning("Jainam StopMarket SL rejected (%s); placing StopLimit @ %.2f (trigger %.2f).",
                        exc, protective_limit, trigger_price)
            return {"order_id": await _place_jainam_sl("StopLimit", protective_limit)}

        repaired = await _repair_jainam_sl(
            access_token, app_order_id, trigger_price, protective_limit, quantity, tag
        )
        return {"order_id": repaired}

    async def _place_upstox_sl(order_type: str, price: float) -> str:
        resp = await _real_place(access_token, {
            "instrument_token": instrument_key,
            "quantity": quantity,
            "order_type": order_type,
            "transaction_type": "BUY",
            "product": upstox_product(),
            "validity": "DAY",
            "price": price,
            "disclosed_quantity": 0,
            "trigger_price": trigger_price,
            "is_amo": False,
            "tag": tag,
        })
        return resp.get("data", {}).get("order_id", "")

    if mcx:
        # MCX options take no stop-market orders — go straight to a protective stop-limit.
        return {"order_id": await _place_upstox_sl("SL", protective_limit)}
    try:
        # SL-M becomes a MARKET order once triggered; Upstox requires price=0 for it.
        order_id = await _place_upstox_sl("SL-M", 0)
    except Exception as exc:  # noqa: BLE001 — NSE F&O rejects SL-M; fall back immediately.
        log.warning("Upstox SL-M rejected (%s); placing SL @ limit %.2f (trigger %.2f).",
                    exc, protective_limit, trigger_price)
        return {"order_id": await _place_upstox_sl("SL", protective_limit)}

    repaired = await _repair_upstox_sl(
        access_token, order_id, trigger_price, protective_limit, quantity,
        instrument_key, tag,
    )
    return {"order_id": repaired}


# ── SL downgrade repair ───────────────────────────────────────────────────────

def _sl_limit_is_unsafe(limit: float, trigger: float, protective_limit: float) -> bool:
    """True when a BUY stop-limit's limit price is too tight to fill through a spike.

    A limit at (or below) the trigger is exactly the failure the user hit: price gaps
    past the trigger and the resting buy never fills. Anything short of the protective
    limit is treated as unsafe so it gets widened.
    """
    if limit <= 0:                     # limit 0 on a stop-LIMIT = unfillable
        return True
    return limit < min(protective_limit, trigger * 1.01)


async def _repair_upstox_sl(
    access_token: str,
    order_id: str,
    trigger_price: float,
    protective_limit: float,
    quantity: int,
    instrument_key: str,
    tag: str,
) -> str:
    """Widen an SL-M that Upstox downgraded to a stop-LIMIT at the trigger price.

    Returns the order id that is actually protecting the position — the original one if
    it was left alone or modified in place, or a replacement's id. Never raises: the
    existing SL (however tight) is better than none.
    """
    if not order_id:
        return order_id
    try:
        details = await get_order_details(access_token, order_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not read back SL %s to verify its type: %s", order_id, exc)
        return order_id

    order_type = str(details.get("order_type", "")).upper()
    if order_type in ("SL-M", "SLM"):
        return order_id  # honoured as a true stop-market — nothing to do.

    limit = float(details.get("price") or 0.0)
    if not _sl_limit_is_unsafe(limit, trigger_price, protective_limit):
        return order_id

    log.warning(
        "Upstox downgraded SL-M to %s with limit %.2f at trigger %.2f — widening to %.2f.",
        order_type or "SL", limit, trigger_price, protective_limit,
    )
    try:
        await _real_modify(access_token, {
            "order_id": order_id,
            "quantity": quantity,
            "validity": "DAY",
            "price": protective_limit,
            "order_type": "SL",
            "disclosed_quantity": 0,
            "trigger_price": trigger_price,
        })
        return order_id
    except Exception as exc:  # noqa: BLE001
        log.warning("SL modify failed for %s (%s) — replacing the order instead.", order_id, exc)

    # Modify unavailable: place the wider SL FIRST so the short is never unprotected,
    # then drop the tight one.
    try:
        resp = await _real_place(access_token, {
            "instrument_token": instrument_key,
            "quantity": quantity,
            "order_type": "SL",
            "transaction_type": "BUY",
            "product": upstox_product(),
            "validity": "DAY",
            "price": protective_limit,
            "disclosed_quantity": 0,
            "trigger_price": trigger_price,
            "is_amo": False,
            "tag": tag,
        })
        new_id = resp.get("data", {}).get("order_id", "")
        if not new_id:
            raise RuntimeError("replacement SL returned no order_id")
    except Exception as exc:  # noqa: BLE001
        log.error("Could not replace tight SL %s; keeping it: %s", order_id, exc)
        return order_id

    try:
        await _real_cancel(access_token, order_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("Placed wider SL %s but could not cancel the tight one %s: %s",
                    new_id, order_id, exc)
    return new_id


async def _repair_jainam_sl(
    access_token: str,
    app_order_id: str,
    trigger_price: float,
    protective_limit: float,
    quantity: int,
    tag: str,
) -> str:
    """Widen a StopMarket that Jainam (XTS) downgraded to StopLimit at the trigger price."""
    from services import jainam_service

    if not app_order_id:
        return app_order_id
    try:
        history = await jainam_service.get_order_history(access_token, app_order_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not read back Jainam SL %s to verify its type: %s", app_order_id, exc)
        return app_order_id
    if not history:
        return app_order_id

    latest = history[-1]
    order_type = str(latest.get("orderType") or latest.get("ordertype") or "").upper()
    if order_type in ("STOPMARKET", "STOP_MARKET", "SL-M"):
        return app_order_id

    limit = float(latest.get("orderPrice") or latest.get("limitPrice") or 0.0)
    if not _sl_limit_is_unsafe(limit, trigger_price, protective_limit):
        return app_order_id

    log.warning(
        "Jainam downgraded StopMarket to %s with limit %.2f at trigger %.2f — widening to %.2f.",
        order_type or "StopLimit", limit, trigger_price, protective_limit,
    )
    try:
        await jainam_service.modify_order(access_token, {
            "appOrderID": int(app_order_id),
            "modifiedProductType": jainam_product(),
            "modifiedOrderType": "StopLimit",
            "modifiedOrderQuantity": quantity,
            "modifiedDisclosedQuantity": 0,
            "modifiedLimitPrice": protective_limit,
            "modifiedStopPrice": trigger_price,
            "modifiedTimeInForce": "DAY",
            "orderUniqueIdentifier": tag,
        })
    except Exception as exc:  # noqa: BLE001
        log.error("Could not widen Jainam SL %s; keeping the tight one: %s", app_order_id, exc)
    return app_order_id


async def place_buy_market(
    access_token: str,
    instrument_key: str,
    quantity: int,
    tag: str,
    paper: bool,
    ltp: float = 0.0,
    broker: str = "upstox",
    delta_creds: dict | None = None,
    ltp_fn=None,
    ref_fallback: float = 0.0,
    exchange: str = "NSE",
) -> dict:
    """Buy (square-off a short leg) "at market" (verified fill; see settings.order_style).

    `ltp_fn` is an optional async callable returning a fresh LTP (used on retries);
    `ref_fallback` prices the order when no LTP is available.
    Returns {"order_id": str, "fill_price": float}. Raises OrderNotFilled on a miss.
    """
    if paper:
        oid = _paper_id()
        log.info("[PAPER] BUY  MKT  %-40s qty=%-5s fill=%-8.4f tag=%s → %s",
                 instrument_key, quantity, ltp, tag, oid)
        return {"order_id": oid, "fill_price": ltp}

    if broker == "delta":
        from services import delta_service
        payload = {
            "product_id": int(instrument_key),
            "size": quantity,
            "side": "buy",
            "order_type": "market_order",
            "time_in_force": "ioc",
            "client_order_id": tag[:20],
        }
        result = await delta_service.place_order(
            delta_creds["api_key"], delta_creds["api_secret"], payload
        )
        order_id = str(result.get("id", ""))
        fill_price = float(result.get("average_fill_price") or ltp)
        return {"order_id": order_id, "fill_price": fill_price}

    return await _place_protected(
        access_token=access_token,
        instrument_key=instrument_key,
        quantity=quantity,
        side="BUY",
        tag=tag,
        ltp=ltp,
        broker=broker,
        ltp_fn=ltp_fn,
        reference_fallback=ref_fallback,
        exchange=exchange,
    )


async def cancel_order(
    access_token: str,
    order_id: str,
    paper: bool,
    broker: str = "upstox",
    delta_creds: dict | None = None,
    product_id: str | int | None = None,
) -> dict:
    """Cancel an open order (e.g. SL-M before EOD square-off).

    Returns {"status": str}
    """
    if paper:
        log.info("[PAPER] CANCEL order %s", order_id)
        return {"status": "cancelled"}

    if broker == "delta":
        from services import delta_service
        creds = delta_creds or {}
        try:
            await delta_service.cancel_order(
                creds.get("api_key", ""),
                creds.get("api_secret", ""),
                order_id,
                product_id=product_id,
            )
        except Exception as exc:
            log.warning("Delta cancel order %s failed (non-fatal): %s", order_id, exc)
        return {"status": "cancelled"}

    if broker == "jainam":
        from services import jainam_service
        await jainam_service.cancel_order(access_token, order_id)
        return {"status": "cancelled"}

    if broker == "kotak":
        from services import kotak_service
        await kotak_service.cancel_order(access_token, order_id)
        return {"status": "cancelled"}

    resp = await _real_cancel(access_token, order_id)
    return {"status": resp.get("data", {}).get("status", "cancelled")}


async def _sl_order_state(
    access_token: str,
    order_id: str,
    broker: str,
    delta_creds: dict | None,
) -> tuple[str, float | None, str]:
    """Query a broker for an order's terminal state.

    Returns (state, fill_price, detail) where state is 'filled' | 'cancelled' | 'unknown'
    and detail is the raw broker status / error (surfaced in logs when state is unknown).
    Any error -> 'unknown' (the caller must treat that as "not safe to square off").
    """
    try:
        if broker == "delta":
            from services import delta_service
            creds = delta_creds or {}
            od = await delta_service.get_order_status(
                creds.get("api_key", ""), creds.get("api_secret", ""), order_id
            )
            state = str(od.get("state", "")).lower()
            if state == "closed":
                return "filled", float(od.get("average_fill_price") or 0) or None, state
            if state == "cancelled":
                return "cancelled", None, state
            return "unknown", None, state or "empty"

        if broker == "kotak":
            from services import kotak_service
            st = await kotak_service.order_state(access_token, order_id)
            if st["status"] == "complete":
                return "filled", (st["avg_price"] or None), st.get("raw_status") or "complete"
            if st["status"] in ("cancelled", "rejected"):
                # Even after a partial fill, a cancelled stop can no longer trade. The exit sizes
                # its BUY from the broker's net position, so a partly-filled stop is handled.
                detail = st.get("raw_status") or st["status"]
                if st["filled_qty"] > 0:
                    detail += f" (stop partly filled {st['filled_qty']} @ {st['avg_price']})"
                return "cancelled", None, detail
            return "unknown", None, st.get("raw_status") or st["status"]

        if broker == "jainam":
            from services import jainam_service
            hist = await jainam_service.get_order_history(access_token, order_id)
            statuses = [str(h.get("orderstatus", "")).upper() for h in hist]
            if any(s == "FILLED" for s in statuses):
                filled = [h for h in hist if str(h.get("orderstatus", "")).upper() == "FILLED"][-1]
                price = filled.get("averageprice") or filled.get("AverageTradedPrice") or 0
                return "filled", float(price) or None, "FILLED"
            if any(s in ("CANCELLED", "REJECTED") for s in statuses):
                return "cancelled", None, statuses[-1]
            return "unknown", None, statuses[-1] if statuses else "no history"

        # Upstox
        details = await get_order_details(access_token, order_id)
        status = str(details.get("status", "")).lower()
        if status == "complete":
            return "filled", float(details.get("average_price") or 0) or None, status
        if status in ("cancelled", "rejected") or status.startswith("cancelled"):
            return "cancelled", None, status
        msg = details.get("status_message") or ""
        return "unknown", None, f"status={status or 'empty'}" + (f" ({msg})" if msg else "")
    except Exception as e:  # noqa: BLE001
        log.warning("Could not query SL order state for %s (%s): %s", order_id, broker, e)
        return "unknown", None, f"status query failed: {e}"


async def get_net_position(access_token: str, instrument_key: str, broker: str,
                           exchange: str = "NSE") -> dict | None:
    """The broker's current NET position in one instrument.

    Returns {"net_qty": int (negative = short), "buy_price": float, "sell_price": float,
    "realised": float | None, "found": bool}, or None if it could not be determined.
    This is the source of truth before any exit BUY: Tradzo's own position record can be
    stale (leg closed by hand in the broker app, SL filled, partial fills, ...).
    """
    try:
        if broker == "kotak":
            from services import kotak_service
            snap = await kotak_service.net_position(access_token, instrument_key)
            # Kotak lists every instrument traded today (closed ones with net 0). A leg we sold
            # today with NO row means the read is incomplete — never treat it as "flat".
            return snap if snap.get("found") else None

        if broker == "jainam":
            from services import jainam_service
            rows = await jainam_service.get_positions(access_token)
            want_seg = jainam_segment(exchange)
            for r in rows:
                seg = str(_ci(r, "exchangesegment", default="") or "").upper()
                if seg and seg != want_seg:
                    continue                                  # same token, other exchange
                if str(_ci(r, "exchangeinstrumentid", "exchangeinstrumentidstr", default="")) == str(instrument_key):
                    qty = _ci(r, "quantity", "netquantity")
                    if qty is None:
                        return None                      # unfamiliar shape -> unknown
                    return {
                        "net_qty": int(float(qty)),
                        "buy_price": float(_ci(r, "buyaverageprice", default=0) or 0),
                        "sell_price": float(_ci(r, "sellaverageprice", default=0) or 0),
                        "realised": None,
                        "found": True,
                    }
            return None                                  # not listed / unfamiliar -> unknown

        headers = {"accept": "application/json", "Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{UPSTOX_BASE}/portfolio/short-term-positions", headers=headers)
        body = resp.json() if resp.content else {}
        if resp.status_code != 200:
            log.warning("Upstox positions failed %s: %s", resp.status_code, body)
            return None
        rows = [r for r in (body.get("data") or []) if str(r.get("instrument_token")) == str(instrument_key)]
        if not rows:
            return {"net_qty": 0, "buy_price": 0.0, "sell_price": 0.0, "realised": None, "found": False}
        realised = [r.get("realised") for r in rows if r.get("realised") is not None]
        return {
            "net_qty": sum(int(float(r.get("quantity") or 0)) for r in rows),
            "buy_price": float(rows[0].get("buy_price") or rows[0].get("day_buy_price") or 0),
            "sell_price": float(rows[0].get("sell_price") or rows[0].get("day_sell_price") or 0),
            "realised": float(sum(float(x) for x in realised)) if realised else None,
            "found": True,
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not read broker position for %s (%s): %s", instrument_key, broker, exc)
        return None


async def cancel_and_confirm_sl(
    access_token: str,
    order_id: str,
    paper: bool,
    broker: str = "upstox",
    delta_creds: dict | None = None,
    product_id: str | int | None = None,
) -> dict:
    """Cancel a resting SL order and CONFIRM it can no longer fill, before squaring off.

    Prevents a double-fill (SL + square-off both executing → net long): we only tell the
    caller it's safe to square off once the SL is verified cancelled.

    Returns one of:
      {"state": "cancelled"}                    → safe to place the square-off buy
      {"state": "filled", "fill_price": float}  → SL already closed the position; DON'T buy again
      {"state": "unknown"}                       → cannot confirm; DON'T buy (avoid double-fill)
    """
    if not order_id or paper:
        return {"state": "cancelled"}

    # 1. Attempt the cancel (best-effort — some brokers swallow their own errors).
    try:
        await cancel_order(
            access_token=access_token,
            order_id=order_id,
            paper=False,
            broker=broker,
            delta_creds=delta_creds,
            product_id=product_id,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("SL cancel raised for %s; will verify actual state: %s", order_id, e)

    # 2. Verify the order truly can't fill anymore (cancel is not always authoritative).
    #    Brokers often report "cancel pending"/"open" for a moment after a cancel, so poll
    #    briefly instead of giving up on the first read — an "unknown" here makes the caller
    #    skip the square-off entirely and leave the position open.
    state, fill_price, detail = "unknown", None, ""
    for rnd in range(2):
        for i in range(8):
            state, fill_price, detail = await _sl_order_state(access_token, order_id, broker, delta_creds)
            if state != "unknown":
                break
            if i < 7:
                await asyncio.sleep(0.4)
        if state != "unknown":
            break
        if rnd == 0:
            # Still not terminal after ~3s: the first cancel may simply not have landed.
            # Ask again (harmless if it's already gone), then give it one more window.
            log.warning("SL %s unconfirmed after first window (%s) - re-sending cancel.", order_id, detail)
            try:
                await cancel_order(access_token=access_token, order_id=order_id, paper=False,
                                   broker=broker, delta_creds=delta_creds, product_id=product_id)
            except Exception as e:  # noqa: BLE001
                log.warning("SL re-cancel raised for %s: %s", order_id, e)
    if state == "unknown":
        log.warning("SL %s still unconfirmed after polling: %s", order_id, detail)
    if state == "filled":
        return {"state": "filled", "fill_price": fill_price}
    if state == "cancelled":
        return {"state": "cancelled"}
    return {"state": "unknown", "detail": detail}

