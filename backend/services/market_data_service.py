"""Market Data Service — Upstox REST APIs for price discovery.

Used by the execution engine at 12:00 PM to:
  1. Fetch the Nifty 50 spot price.
  2. Fetch the option chain to find ATM CE/PE instrument keys + LTPs.
  3. Determine the current Tuesday expiry date.

All calls use the admin's market data access token (stored in token_store
against the isMarketDataSource broker account).

No WebSocket is used in Phase 1. Price polling for P&L display is REST-based.
"""
import logging
from datetime import datetime, date, timedelta

import httpx
import pytz

from utils import token_store
from services import firebase_service

log = logging.getLogger("tradzo.market_data")

UPSTOX_BASE = "https://api.upstox.com/v2"
NIFTY_INDEX_KEY = "NSE_INDEX|Nifty 50"

IST = pytz.timezone("Asia/Kolkata")


# ── Expiry helpers ────────────────────────────────────────────────────────────

def get_current_tuesday_expiry() -> date:
    """Return the current (or next) Tuesday's date — the Nifty weekly expiry.

    If today IS Tuesday, return today.
    If today is Wednesday–Monday, return the coming Tuesday.
    """
    today = date.today()
    weekday = today.weekday()   # Monday=0, Tuesday=1, …
    days_to_tuesday = (1 - weekday) % 7
    return today if days_to_tuesday == 0 else today + timedelta(days=days_to_tuesday)


def get_atm_strike(spot: float, step: int = 50) -> int:
    """Round spot price to nearest multiple of step (50 for Nifty)."""
    return round(spot / step) * step


# ── Market data token ─────────────────────────────────────────────────────────

def _to_dt(value) -> datetime:
    """Coerce a Firestore timestamp / ISO string / datetime to an aware datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo else IST.localize(value)
    if hasattr(value, "timestamp"):
        return datetime.fromtimestamp(value.timestamp(), IST)
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return datetime.now(IST)


def _get_market_data_token() -> str | None:
    """Return the access token for the account flagged as market data source.

    Falls back to any connected Upstox account with a valid, non-expired decrypted token.
    """
    # 1. Try the primary market data account first
    account = firebase_service.get_market_data_account()
    if account:
        tokens = token_store.get_tokens(account["id"])
        if tokens and tokens.get("access_token"):
            expiry_raw = account.get("expiresAt")
            if expiry_raw is None or _to_dt(expiry_raw) > datetime.now(IST):
                return tokens["access_token"]
            else:
                log.warning("Market data account %s has expired token.", account["id"])
        else:
            log.warning("Market data account %s token is corrupt or missing.", account["id"])

    # 2. Fall back to any other connected Upstox account with a valid token
    log.info("Searching other connected Upstox accounts for active market data token...")
    for acc in firebase_service.list_broker_accounts():
        if acc.get("broker") == "upstox" and acc.get("isConnected"):
            tokens = token_store.get_tokens(acc["id"])
            if tokens and tokens.get("access_token"):
                expiry_raw = acc.get("expiresAt")
                if expiry_raw is None or _to_dt(expiry_raw) > datetime.now(IST):
                    log.info("Using Upstox account %s as market data source fallback.", acc["id"])
                    return tokens["access_token"]

    log.error("No connected Upstox account has a valid, decrypted market data token.")
    return None


# ── Upstox REST helpers ───────────────────────────────────────────────────────

def _auth_headers(token: str) -> dict:
    return {
        "accept": "application/json",
        "Authorization": f"Bearer {token}",
    }


async def get_nifty_spot(access_token: str | None = None) -> float:
    """Fetch the current Nifty 50 index LTP via Upstox market-quote LTP API.

    Uses the provided token or falls back to the market data source token.
    Raises RuntimeError if the price cannot be fetched.
    """
    token = access_token or _get_market_data_token()
    if not token:
        raise RuntimeError("No valid access token available for market data.")

    url = f"{UPSTOX_BASE}/market-quote/ltp"
    params = {"instrument_key": NIFTY_INDEX_KEY}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params, headers=_auth_headers(token))

    if resp.status_code != 200:
        raise RuntimeError(
            f"Nifty spot fetch failed: {resp.status_code} {resp.text}"
        )

    data = resp.json().get("data", {})
    # Key is like "NSE_INDEX:Nifty 50" in the response
    for key, val in data.items():
        if "Nifty 50" in key or "NIFTY" in key.upper():
            ltp = val.get("last_price") or val.get("ltp") or 0.0
            log.info("Nifty 50 spot LTP: %.2f", ltp)
            return float(ltp)

    raise RuntimeError(f"Nifty 50 LTP not found in response: {data}")


async def get_option_chain(
    expiry: date,
    access_token: str | None = None,
) -> list[dict]:
    """Fetch the Nifty option chain for the given expiry date.

    Returns a list of strike dicts from the Upstox option chain API.
    Each dict has the shape:
      {
        "strike_price": float,
        "call_options": {
          "instrument_key": str,
          "market_data": {"ltp": float, ...}
        },
        "put_options": { ... }
      }
    """
    token = access_token or _get_market_data_token()
    if not token:
        raise RuntimeError("No valid access token available for market data.")

    url = f"{UPSTOX_BASE}/option/chain"
    params = {
        "instrument_key": NIFTY_INDEX_KEY,
        "expiry_date": expiry.isoformat(),
    }

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, params=params, headers=_auth_headers(token))

    if resp.status_code != 200:
        raise RuntimeError(
            f"Option chain fetch failed: {resp.status_code} {resp.text}"
        )

    return resp.json().get("data", [])


async def get_atm_data(access_token: str | None = None) -> dict:
    """One-shot helper that returns everything the execution engine needs at entry.

    Returns:
      {
        "spot":         float,
        "atm_strike":   int,
        "expiry":       "YYYY-MM-DD",
        "ce_key":       str,   # Upstox instrument key for CE leg
        "pe_key":       str,   # Upstox instrument key for PE leg
        "ce_ltp":       float,
        "pe_ltp":       float,
      }

    Raises RuntimeError if data cannot be fetched.
    """
    spot = await get_nifty_spot(access_token)
    atm = get_atm_strike(spot)
    expiry = get_current_tuesday_expiry()

    log.info("Nifty spot=%.2f  ATM=%d  expiry=%s", spot, atm, expiry)

    chain = await get_option_chain(expiry, access_token)

    for row in chain:
        if int(row.get("strike_price", 0)) == atm:
            ce = row.get("call_options", {})
            pe = row.get("put_options", {})
            result = {
                "spot": spot,
                "atm_strike": atm,
                "expiry": expiry.isoformat(),
                "ce_key": ce.get("instrument_key", ""),
                "pe_key": pe.get("instrument_key", ""),
                "ce_ltp": ce.get("market_data", {}).get("ltp", 0.0),
                "pe_ltp": pe.get("market_data", {}).get("ltp", 0.0),
            }
            log.info(
                "ATM data: CE=%s ltp=%.2f | PE=%s ltp=%.2f",
                result["ce_key"], result["ce_ltp"],
                result["pe_key"], result["pe_ltp"],
            )
            return result

    raise RuntimeError(
        f"ATM strike {atm} not found in option chain for expiry {expiry}. "
        f"Available strikes: {[r.get('strike_price') for r in chain[:5]]} …"
    )


async def get_option_ltp(
    instrument_key: str,
    access_token: str | None = None,
) -> float:
    """Fetch the current LTP for a single option instrument (for P&L display)."""
    token = access_token or _get_market_data_token()
    if not token:
        return 0.0

    url = f"{UPSTOX_BASE}/market-quote/ltp"
    params = {"instrument_key": instrument_key}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params, headers=_auth_headers(token))
        if resp.status_code != 200:
            return 0.0
        data = resp.json().get("data", {})
        for val in data.values():
            return float(val.get("last_price") or val.get("ltp") or 0.0)
    except Exception as exc:  # noqa: BLE001
        log.warning("LTP fetch failed for %s: %s", instrument_key, exc)
    return 0.0
