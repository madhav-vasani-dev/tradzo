"""Upstox API v2 integration — OAuth and order placement.

Upstox OAuth notes (v2):
  * Authorization dialog:  GET  https://api.upstox.com/v2/login/authorization/dialog
  * Token exchange:        POST https://api.upstox.com/v2/login/authorization/token
  * Upstox v2 does NOT issue refresh tokens. The access token is valid for a
    single trading day and expires at ~03:30 AM IST, after which the user must
    re-authenticate. `token_expiry()` reflects that; the daily scheduler flags
    accounts whose token has lapsed (needsReauth) rather than silently renewing.
"""
import logging
import secrets
from datetime import datetime, time, timedelta
from urllib.parse import urlencode

import httpx
import pytz

from config import settings

logger = logging.getLogger("tradzo.upstox")

AUTH_DIALOG_URL = "https://api.upstox.com/v2/login/authorization/dialog"
TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"
PLACE_ORDER_URL = "https://api.upstox.com/v2/order/place"

IST = pytz.timezone("Asia/Kolkata")

# In-memory CSRF state -> pending-connection map for BYOK OAuth flows.
# Each entry carries the user's OWN Upstox app credentials so the callback can
# exchange the code with the same key/secret. Single-instance only; move to Redis
# (with a short TTL) if the backend is scaled out.
_pending_states: dict[str, dict] = {}


def build_auth_url(user_id: str, api_key: str, api_secret: str) -> str:
    """Construct the Upstox authorization URL for a user's OWN app (BYOK).

    `api_key`/`api_secret` are the user's Upstox app credentials; the secret is
    held with the pending state so the callback can exchange the code. The
    redirect URI is fixed (this backend's callback) and the user must register
    that exact URI in their Upstox app.
    """
    if not api_key or not api_secret:
        raise RuntimeError("Upstox API key and secret are required.")

    state = secrets.token_urlsafe(24)
    _pending_states[state] = {
        "user_id": user_id,
        "api_key": api_key,
        "api_secret": api_secret,
    }

    params = {
        "response_type": "code",
        "client_id": api_key,
        "redirect_uri": settings.upstox_redirect_uri,
        "state": state,
    }
    return f"{AUTH_DIALOG_URL}?{urlencode(params)}"


def consume_state(state: str) -> dict | None:
    """Validate + pop a state, returning {user_id, api_key, api_secret} (or None)."""
    return _pending_states.pop(state, None)


def token_expiry(now: datetime | None = None) -> datetime:
    """Upstox tokens expire at the next 03:30 AM IST boundary."""
    now = now or datetime.now(IST)
    if now.tzinfo is None:
        now = IST.localize(now)
    expiry = IST.localize(datetime.combine(now.date(), time(3, 30)))
    if now >= expiry:
        expiry += timedelta(days=1)
    return expiry


async def exchange_code_for_tokens(code: str, api_key: str, api_secret: str) -> dict:
    """Exchange an authorization code for an access token using the user's OWN
    Upstox app credentials (BYOK).

    Returns the raw Upstox token payload, which includes `access_token` and
    identity fields such as `user_id`, `user_name`, `email`.
    """
    data = {
        "code": code,
        "client_id": api_key,
        "client_secret": api_secret,
        "redirect_uri": settings.upstox_redirect_uri,
        "grant_type": "authorization_code",
    }
    headers = {"accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(TOKEN_URL, data=data, headers=headers)

    if resp.status_code != 200:
        logger.error("Upstox token exchange failed: %s %s", resp.status_code, resp.text)
        raise RuntimeError("token_exchange_failed")

    return resp.json()


async def place_order(access_token: str, order: dict) -> dict:
    """Place a single order via the Upstox order API.

    `order` should follow the Upstox place-order schema (quantity, product,
    validity, price, instrument_token, order_type, transaction_type, ...).
    """
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(PLACE_ORDER_URL, json=order, headers=headers)

    payload = resp.json() if resp.content else {}
    if resp.status_code not in (200, 201):
        logger.error("Upstox order failed: %s %s", resp.status_code, payload)
        raise RuntimeError(payload.get("errors", "order_failed"))
    return payload
