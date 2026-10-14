"""Market Data Service — Upstox REST APIs for price discovery.

Used by the execution engine at 12:00 PM to:
  1. Fetch the Nifty 50 spot price.
  2. Fetch the option chain to find ATM CE/PE instrument keys + LTPs.
  3. Determine the nearest live expiry from Upstox's own contract list.

All calls use the admin's market data access token (stored in token_store
against the isMarketDataSource broker account).

No WebSocket is used in Phase 1. Price polling for P&L display is REST-based.
"""
import logging
import math
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
# The expiry is NEVER computed from a calendar rule. NSE moves it for holidays (and has
# changed the weekday before), so it is read from Upstox's contract list instead.

_expiry_cache: dict[str, date] = {}     # today's IST date -> chosen expiry


def _today_ist() -> date:
    return datetime.now(IST).date()


def pick_nearest_expiry(expiries: list[date], today: date) -> date | None:
    """The soonest expiry on or after `today` (today itself counts: expiry-day trading)."""
    upcoming = sorted(e for e in expiries if e >= today)
    return upcoming[0] if upcoming else None


async def get_nifty_expiries(access_token: str | None = None) -> list[date]:
    """Every live Nifty option expiry on/after today, from Upstox's option-contract list."""
    token = access_token or _get_market_data_token()
    if not token:
        raise RuntimeError("No valid access token available for market data.")

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{UPSTOX_BASE}/option/contract",
            params={"instrument_key": NIFTY_INDEX_KEY},
            headers=_auth_headers(token),
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Option contract list failed: {resp.status_code} {resp.text}")

    today = _today_ist()
    found: set[date] = set()
    for row in resp.json().get("data") or []:
        raw = row.get("expiry")
        if not raw:
            continue
        try:
            d = date.fromisoformat(str(raw)[:10])
        except ValueError:
            continue
        if d >= today:
            found.add(d)
    return sorted(found)


async def _probe_expiry_via_chain(token: str | None, today: date, days: int = 14) -> date | None:
    """Fallback: walk forward from today and take the first date that HAS an option chain."""
    for offset in range(days + 1):
        d = today + timedelta(days=offset)
        if d.weekday() >= 5:
            continue
        try:
            if await get_option_chain(d, token):
                log.info("Expiry found by probing the option chain: %s", d)
                return d
        except Exception as exc:  # noqa: BLE001 — a missing expiry just means no chain
            log.debug("No chain for %s: %s", d, exc)
    return None


async def get_nearest_expiry(access_token: str | None = None, *, refresh: bool = False) -> date:
    """The nearest live Nifty expiry, resolved from Upstox (cached for the day).

    Order of trust: Upstox's contract list -> probing option chains day by day.
    Raises RuntimeError only if neither can find one.
    """
    today = _today_ist()
    key = today.isoformat()
    if not refresh and key in _expiry_cache:
        return _expiry_cache[key]

    expiry: date | None = None
    try:
        expiry = pick_nearest_expiry(await get_nifty_expiries(access_token), today)
    except Exception as exc:  # noqa: BLE001
        log.warning("Contract-list expiry lookup failed (%s) - probing option chains instead.", exc)
    if expiry is None:
        expiry = await _probe_expiry_via_chain(access_token, today)
    if expiry is None:
        raise RuntimeError("Could not determine the Nifty option expiry from Upstox.")

    _expiry_cache.clear()
    _expiry_cache[key] = expiry
    log.info("Nifty expiry resolved from Upstox: %s", expiry)
    return expiry


def get_atm_strike(spot: float, step: int = 50) -> int:
    """Nearest multiple of `step` to spot; exact ties round UP (22725 -> 22750).

    (Python's round() is banker's rounding, which sent 22725 down but 22775 up.)
    """
    return int(math.floor(spot / step + 0.5)) * step


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


def atm_from_chain(chain: list[dict], spot: float, expiry: date) -> dict:
    """Pick the ATM row for `spot` out of an already-fetched option chain."""
    atm = get_atm_strike(spot)
    for row in chain:
        if int(row.get("strike_price", 0)) == atm:
            ce = row.get("call_options", {})
            pe = row.get("put_options", {})
            return {
                "spot": spot,
                "atm_strike": atm,
                "expiry": expiry.isoformat(),
                "ce_key": ce.get("instrument_key", ""),
                "pe_key": pe.get("instrument_key", ""),
                "ce_ltp": ce.get("market_data", {}).get("ltp", 0.0),
                "pe_ltp": pe.get("market_data", {}).get("ltp", 0.0),
            }
    strikes = sorted(int(r.get("strike_price", 0)) for r in chain)
    near = [k for k in strikes if abs(k - atm) <= 300]
    raise RuntimeError(
        f"ATM strike {atm} (spot {spot:.2f}) not found in the option chain for expiry {expiry} "
        f"({len(chain)} strikes; near spot: {near or strikes[:5]})."
    )


async def get_atm_data(access_token: str | None = None) -> dict:
    """One-shot helper that returns everything the execution engine needs at entry.

    Returns:
      {
        "spot":         float,
        "atm_strike":   int,
        "expiry":       "YYYY-MM-DD",   # resolved from Upstox, never calendar-guessed
        "ce_key":       str,   # Upstox instrument key for CE leg
        "pe_key":       str,   # Upstox instrument key for PE leg
        "ce_ltp":       float,
        "pe_ltp":       float,
        "chain":        list,  # the full chain, so the strike can be re-picked on a fresher spot
      }

    Raises RuntimeError if data cannot be fetched.
    """
    spot = await get_nifty_spot(access_token)
    expiry = await get_nearest_expiry(access_token)

    chain = await get_option_chain(expiry, access_token)
    if not chain:
        # The cached/resolved expiry has no chain (rolled, or stale) - resolve again, once.
        log.warning("No option chain for %s - re-resolving the expiry.", expiry)
        expiry = await get_nearest_expiry(access_token, refresh=True)
        chain = await get_option_chain(expiry, access_token)
    if not chain:
        raise RuntimeError(f"Option chain for expiry {expiry} is empty.")

    result = atm_from_chain(chain, spot, expiry)
    result["chain"] = chain
    log.info(
        "Nifty spot=%.2f ATM=%d expiry=%s | CE=%s ltp=%.2f | PE=%s ltp=%.2f",
        spot, result["atm_strike"], expiry,
        result["ce_key"], result["ce_ltp"], result["pe_key"], result["pe_ltp"],
    )
    return result
