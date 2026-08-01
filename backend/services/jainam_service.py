"""Jainam broker integration — Symphony XTS Retail API.

Unlike Upstox there is NO OAuth redirect. The user obtains four credentials from
Jainam support (Interactive key/secret + Market Data key/secret) and enters them
in the app. We log in directly:

  POST {base}/interactive/user/session      {appKey, secretKey, source}
      -> { type, result: { token, userID, ... } }
  POST {base}/apimarketdata/auth/login      {appKey, secretKey, source}
      -> { type, result: { token, userID } }

The returned session `token` is passed as the `authorization` header on all
subsequent calls (order placement, positions, market data). Tokens are valid for
the trading day. Docs: https://developers.symphonyfintech.in
"""
import logging

import httpx

from config import settings

logger = logging.getLogger("tradzo.jainam")

INTERACTIVE_LOGIN_PATH = "/interactive/user/session"
MARKETDATA_LOGIN_PATH = "/apimarketdata/auth/login"
PLACE_ORDER_PATH = "/interactive/orders"


def _base() -> str:
    return settings.jainam_xts_base_url.rstrip("/")


async def _login(path: str, app_key: str, secret_key: str) -> dict:
    if not app_key or not secret_key:
        raise RuntimeError("Jainam appKey and secretKey are required.")

    payload = {"appKey": app_key, "secretKey": secret_key, "source": settings.jainam_xts_source}
    async with httpx.AsyncClient(timeout=20, verify=True) as client:
        resp = await client.post(f"{_base()}{path}", json=payload)

    body = resp.json() if resp.content else {}
    if resp.status_code != 200 or body.get("type") != "success":
        desc = body.get("description") or body.get("result") or resp.text
        logger.error("Jainam login failed at %s: %s %s", path, resp.status_code, desc)
        raise RuntimeError(f"login_failed: {desc}")

    result = body.get("result", {})
    token = result.get("token")
    if not token:
        raise RuntimeError("login_failed: no token in response")
    return result


async def login_interactive(app_key: str, secret_key: str) -> dict:
    """Interactive (trading) session. Returns {token, userID, ...}."""
    return await _login(INTERACTIVE_LOGIN_PATH, app_key, secret_key)


async def login_marketdata(app_key: str, secret_key: str) -> dict:
    """Market Data session. Returns {token, userID, ...}."""
    return await _login(MARKETDATA_LOGIN_PATH, app_key, secret_key)


async def place_order(token: str, order: dict) -> dict:
    """Place an order via the XTS interactive API.

    `order` must follow the XTS place-order schema (exchangeSegment,
    exchangeInstrumentID, productType, orderType, orderSide, orderQuantity,
    limitPrice, orderUniqueIdentifier, ...).
    """
    headers = {"Content-Type": "application/json", "authorization": token}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{_base()}{PLACE_ORDER_PATH}", json=order, headers=headers)

    body = resp.json() if resp.content else {}
    if resp.status_code not in (200, 201) or body.get("type") != "success":
        desc = body.get("description") or resp.text
        logger.error("Jainam order failed: %s %s", resp.status_code, desc)
        raise RuntimeError(f"order_failed: {desc}")
    return body


async def modify_order(token: str, modification: dict) -> dict:
    """Modify a resting order via the XTS interactive API.

    `modification` must follow the XTS modify-order schema (appOrderID,
    modifiedProductType, modifiedOrderType, modifiedOrderQuantity,
    modifiedLimitPrice, modifiedStopPrice, modifiedTimeInForce, ...).
    """
    headers = {"Content-Type": "application/json", "authorization": token}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.put(f"{_base()}{PLACE_ORDER_PATH}", json=modification, headers=headers)

    body = resp.json() if resp.content else {}
    if resp.status_code not in (200, 201) or body.get("type") != "success":
        desc = body.get("description") or resp.text
        logger.error("Jainam order modification failed: %s %s", resp.status_code, desc)
        raise RuntimeError(f"order_modify_failed: {desc}")
    return body


async def get_option_instrument(
    token: str,
    symbol: str,
    expiry_date_str: str,
    option_type: str,
    strike_price: float,
) -> dict:
    """Resolve an option contract strike and expiry to Jainam exchangeInstrumentID."""
    from datetime import datetime
    dt = datetime.strptime(expiry_date_str, "%Y-%m-%d")
    formatted_expiry = dt.strftime("%d%b%Y")  # e.g. 21Jul2026
    
    headers = {"Content-Type": "application/json", "authorization": token}
    params = {
        "exchangeSegment": 2,  # NSEFO
        "series": "OPTIDX",
        "symbol": symbol,
        "expiryDate": formatted_expiry,
        "optionType": option_type,
        "strikePrice": int(strike_price),
    }
    
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{_base()}/apimarketdata/instruments/instrument/optionSymbol",
            params=params,
            headers=headers,
        )
        
    body = resp.json() if resp.content else {}
    if resp.status_code != 200 or body.get("type") != "success":
        desc = body.get("description") or resp.text
        logger.error("Jainam optionSymbol resolution failed: %s %s", resp.status_code, desc)
        raise RuntimeError(f"optionsymbol_resolution_failed: {desc}")
        
    result = body.get("result", {})
    instrument_id = result.get("exchangeInstrumentID")
    if not instrument_id:
        raise RuntimeError("optionsymbol_resolution_failed: no exchangeInstrumentID in result")
    return result


async def get_order_history(token: str, app_order_id: str) -> list[dict]:
    """Get history of an order by appOrderID."""
    headers = {"Content-Type": "application/json", "authorization": token}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{_base()}/interactive/orders?appOrderID={app_order_id}",
            headers=headers,
        )
    body = resp.json() if resp.content else {}
    if resp.status_code != 200 or body.get("type") != "success":
        desc = body.get("description") or resp.text
        logger.error("Jainam order details failed: %s %s", resp.status_code, desc)
        raise RuntimeError(f"order_details_failed: {desc}")
    return body.get("result", [])


async def cancel_order(token: str, app_order_id: str) -> dict:
    """Cancel an active order by appOrderID."""
    headers = {"Content-Type": "application/json", "authorization": token}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.delete(
            f"{_base()}/interactive/orders?appOrderID={app_order_id}",
            headers=headers,
        )
    body = resp.json() if resp.content else {}
    if resp.status_code != 200 or body.get("type") != "success":
        desc = body.get("description") or resp.text
        logger.error("Jainam order cancellation failed: %s %s", resp.status_code, desc)
        raise RuntimeError(f"order_cancellation_failed: {desc}")
    return body

