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
"""
import logging
import uuid

import httpx

from config import settings

log = logging.getLogger("tradzo.orders")

UPSTOX_BASE = "https://api.upstox.com/v2"
PLACE_ORDER_URL = f"{UPSTOX_BASE}/order/place"
CANCEL_ORDER_URL = f"{UPSTOX_BASE}/order/cancel"


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

async def place_sell_market(
    access_token: str,
    instrument_key: str,
    quantity: int,
    tag: str,
    paper: bool,
    ltp: float = 0.0,
) -> dict:
    """Sell (short) an instrument at market price.

    Returns {"order_id": str, "fill_price": float}
    """
    if paper:
        oid = _paper_id()
        log.info("[PAPER] SELL MKT  %-40s qty=%-5s fill=%-8.2f tag=%s → %s",
                 instrument_key, quantity, ltp, tag, oid)
        return {"order_id": oid, "fill_price": ltp}

    payload = {
        "instrument_token": instrument_key,
        "quantity": quantity,
        "order_type": "MARKET",
        "transaction_type": "SELL",
        "product": "I",
        "validity": "DAY",
        "disclosed_quantity": 0,
        "trigger_price": 0,
        "is_amo": False,
        "tag": tag,
    }
    resp = await _real_place(access_token, payload)
    data = resp.get("data", {})
    return {
        "order_id": data.get("order_id", ""),
        "fill_price": data.get("average_price", 0.0),
    }


async def place_sl_market(
    access_token: str,
    instrument_key: str,
    quantity: int,
    trigger_price: float,
    tag: str,
    paper: bool,
) -> dict:
    """Place a BUY SL-M order (stop-loss for a short leg).

    The order lives on the broker's server; it fires automatically when
    the market price crosses trigger_price, even if our backend is down.

    Returns {"order_id": str}
    """
    if paper:
        oid = _paper_id()
        log.info("[PAPER] BUY SL-M  %-40s qty=%-5s trigger=%-8.2f tag=%s → %s",
                 instrument_key, quantity, trigger_price, tag, oid)
        return {"order_id": oid}

    payload = {
        "instrument_token": instrument_key,
        "quantity": quantity,
        "order_type": "SL-M",
        "transaction_type": "BUY",
        "product": "I",
        "validity": "DAY",
        "disclosed_quantity": 0,
        "trigger_price": trigger_price,
        "is_amo": False,
        "tag": tag,
    }
    resp = await _real_place(access_token, payload)
    return {"order_id": resp.get("data", {}).get("order_id", "")}


async def place_buy_market(
    access_token: str,
    instrument_key: str,
    quantity: int,
    tag: str,
    paper: bool,
    ltp: float = 0.0,
) -> dict:
    """Buy (square-off a short leg) at market price.

    Returns {"order_id": str, "fill_price": float}
    """
    if paper:
        oid = _paper_id()
        log.info("[PAPER] BUY  MKT  %-40s qty=%-5s fill=%-8.2f tag=%s → %s",
                 instrument_key, quantity, ltp, tag, oid)
        return {"order_id": oid, "fill_price": ltp}

    payload = {
        "instrument_token": instrument_key,
        "quantity": quantity,
        "order_type": "MARKET",
        "transaction_type": "BUY",
        "product": "I",
        "validity": "DAY",
        "disclosed_quantity": 0,
        "trigger_price": 0,
        "is_amo": False,
        "tag": tag,
    }
    resp = await _real_place(access_token, payload)
    data = resp.get("data", {})
    return {
        "order_id": data.get("order_id", ""),
        "fill_price": data.get("average_price", 0.0),
    }


async def cancel_order(
    access_token: str,
    order_id: str,
    paper: bool,
) -> dict:
    """Cancel an open order (e.g. SL-M before EOD square-off).

    Returns {"status": str}
    """
    if paper:
        log.info("[PAPER] CANCEL order %s", order_id)
        return {"status": "cancelled"}
    resp = await _real_cancel(access_token, order_id)
    return {"status": resp.get("data", {}).get("status", "cancelled")}
