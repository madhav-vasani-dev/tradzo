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
