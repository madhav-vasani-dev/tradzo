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

Stop-loss orders
----------------
Every SL is placed as a stop-MARKET. NSE discontinued SL-M in the F&O segment, so an
Indian broker may silently downgrade it to a stop-LIMIT priced AT the trigger, which
does not fill when the market gaps through. After placing, we read the order back and,
if it was downgraded, repair the limit price to `trigger × (1 + sl_limit_buffer_pct)`
so it still fills on a spike with a bounded worst price.
"""
import logging
import math
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


# ── Product-type helpers ──────────────────────────────────────────────────────

def _is_delivery() -> bool:
    return str(getattr(settings, "equity_product", "delivery")).lower() != "intraday"


def upstox_product() -> str:
    """Upstox product code: "D" = delivery/carry-forward, "I" = intraday."""
    return "D" if _is_delivery() else "I"


def jainam_product() -> str:
    """Jainam (XTS) product code: "NRML" = carry-forward, "MIS" = intraday."""
    return "NRML" if _is_delivery() else "MIS"


# ── Stop-loss price helpers ───────────────────────────────────────────────────

def _round_up_tick(price: float, tick: float = NSE_TICK) -> float:
    return round(math.ceil(price / tick) * tick, 2)


def sl_limit_price(trigger_price: float) -> float:
    """Protective limit price for a BUY stop order that must fill through a spike.

    Sits `sl_limit_buffer_pct` ABOVE the trigger so the order behaves like a market
    order once triggered, while capping the worst fill.
    """
    buffer_pct = float(getattr(settings, "sl_limit_buffer_pct", 10.0))
    return _round_up_tick(trigger_price * (1 + buffer_pct / 100.0))


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


async def place_sell_market(
    access_token: str,
    instrument_key: str,
    quantity: int,
    tag: str,
    paper: bool,
    ltp: float = 0.0,
    broker: str = "upstox",
    delta_creds: dict | None = None,
) -> dict:
    """Sell (short) an instrument at market price.

    Returns {"order_id": str, "fill_price": float}
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

    if broker == "jainam":
        payload = {
            "exchangeSegment": "NSEFO",
            "exchangeInstrumentID": int(instrument_key),
            "productType": jainam_product(),
            "orderType": "Market",
            "orderSide": "SELL",
            "timeInForce": "DAY",
            "disclosedQuantity": 0,
            "orderQuantity": quantity,
            "limitPrice": 0.0,
            "stopPrice": 0.0,
            "orderUniqueIdentifier": tag,
        }
        from services import jainam_service
        resp = await jainam_service.place_order(access_token, payload)
        app_order_id = resp.get("result", {}).get("appOrderID")
        if not app_order_id:
            raise RuntimeError("Jainam order placement failed: no appOrderID returned")
        fill_price = await _get_jainam_fill_price(access_token, app_order_id, ltp)
        return {"order_id": app_order_id, "fill_price": fill_price}

    payload = {
        "instrument_token": instrument_key,
        "quantity": quantity,
        "order_type": "MARKET",
        "transaction_type": "SELL",
        "product": upstox_product(),
        "validity": "DAY",
        "price": 0,            # Upstox requires price=0 for MARKET orders (UDAPI1008 otherwise)
        "disclosed_quantity": 0,
        "trigger_price": 0,
        "is_amo": False,
        "tag": tag,
    }
    resp = await _real_place(access_token, payload)
    data = resp.get("data", {})
    order_id = data.get("order_id", "")
    # Upstox does not return a fill price on placement — fetch the real average fill.
    fill_price = data.get("average_price") or await _get_upstox_fill_price(access_token, order_id, ltp)
    return {
        "order_id": order_id,
        "fill_price": fill_price,
    }


async def place_sl_market(
    access_token: str,
    instrument_key: str,
    quantity: int,
    trigger_price: float,
    tag: str,
    paper: bool,
    broker: str = "upstox",
    delta_creds: dict | None = None,
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

    protective_limit = sl_limit_price(trigger_price)

    if broker == "jainam":
        from services import jainam_service

        async def _place_jainam_sl(order_type: str, limit: float) -> str:
            resp = await jainam_service.place_order(access_token, {
                "exchangeSegment": "NSEFO",
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
) -> dict:
    """Buy (square-off a short leg) at market price.

    Returns {"order_id": str, "fill_price": float}
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

    if broker == "jainam":
        payload = {
            "exchangeSegment": "NSEFO",
            "exchangeInstrumentID": int(instrument_key),
            "productType": jainam_product(),
            "orderType": "Market",
            "orderSide": "BUY",
            "timeInForce": "DAY",
            "disclosedQuantity": 0,
            "orderQuantity": quantity,
            "limitPrice": 0.0,
            "stopPrice": 0.0,
            "orderUniqueIdentifier": tag,
        }
        from services import jainam_service
        resp = await jainam_service.place_order(access_token, payload)
        app_order_id = resp.get("result", {}).get("appOrderID")
        if not app_order_id:
            raise RuntimeError("Jainam exit order placement failed: no appOrderID returned")
        fill_price = await _get_jainam_fill_price(access_token, app_order_id, ltp)
        return {"order_id": app_order_id, "fill_price": fill_price}

    payload = {
        "instrument_token": instrument_key,
        "quantity": quantity,
        "order_type": "MARKET",
        "transaction_type": "BUY",
        "product": upstox_product(),
        "validity": "DAY",
        "price": 0,            # Upstox requires price=0 for MARKET orders (UDAPI1008 otherwise)
        "disclosed_quantity": 0,
        "trigger_price": 0,
        "is_amo": False,
        "tag": tag,
    }
    resp = await _real_place(access_token, payload)
    data = resp.get("data", {})
    order_id = data.get("order_id", "")
    # Upstox does not return a fill price on placement — fetch the real average fill.
    fill_price = data.get("average_price") or await _get_upstox_fill_price(access_token, order_id, ltp)
    return {
        "order_id": order_id,
        "fill_price": fill_price,
    }


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

    resp = await _real_cancel(access_token, order_id)
    return {"status": resp.get("data", {}).get("status", "cancelled")}


async def _sl_order_state(
    access_token: str,
    order_id: str,
    broker: str,
    delta_creds: dict | None,
) -> tuple[str, float | None]:
    """Query a broker for an order's terminal state.

    Returns (state, fill_price) where state is 'filled' | 'cancelled' | 'unknown'.
    Any error → 'unknown' (the caller must treat that as "not safe to square off").
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
                return "filled", float(od.get("average_fill_price") or 0) or None
            if state == "cancelled":
                return "cancelled", None
            return "unknown", None

        if broker == "jainam":
            from services import jainam_service
            hist = await jainam_service.get_order_history(access_token, order_id)
            statuses = [str(h.get("orderstatus", "")).upper() for h in hist]
            if any(s == "FILLED" for s in statuses):
                filled = [h for h in hist if str(h.get("orderstatus", "")).upper() == "FILLED"][-1]
                price = filled.get("averageprice") or filled.get("AverageTradedPrice") or 0
                return "filled", float(price) or None
            if any(s in ("CANCELLED", "REJECTED") for s in statuses):
                return "cancelled", None
            return "unknown", None

        # Upstox
        details = await get_order_details(access_token, order_id)
        status = str(details.get("status", "")).lower()
        if status == "complete":
            return "filled", float(details.get("average_price") or 0) or None
        if status in ("cancelled", "rejected"):
            return "cancelled", None
        return "unknown", None
    except Exception as e:  # noqa: BLE001
        log.warning("Could not query SL order state for %s (%s): %s", order_id, broker, e)
        return "unknown", None


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
    state, fill_price = await _sl_order_state(access_token, order_id, broker, delta_creds)
    if state == "filled":
        return {"state": "filled", "fill_price": fill_price}
    if state == "cancelled":
        return {"state": "cancelled"}
    return {"state": "unknown"}

