"""Delta Exchange REST API integration — market data and order placement.

Used by the BTC Option Selling strategy (entry at 17:01 IST, exit at 17:29 IST).

All API calls hit https://api.india.delta.exchange/v2 (Indian endpoint).

Authentication:
  Every signed request requires three extra headers:
    api-key   : the user's API key
    timestamp : epoch time in seconds (string)
    signature : HMAC-SHA256( method + timestamp + path + query_string + body )
                signed with the user's API secret (hex-encoded).

Instrument IDs:
  Delta uses numeric product_id (not string symbols) for order placement.
  The option chain returns product_id per strike/type.
"""
import hashlib
import hmac
import logging
import time as time_mod
from datetime import date, datetime, timezone

import httpx
import pytz

from config import settings

log = logging.getLogger("tradzo.delta")

IST = pytz.timezone("Asia/Kolkata")

DELTA_BASE = "https://api.india.delta.exchange/v2"

# BTC USD = 85 INR (configurable conversion rate)
USD_TO_INR = 85.0


# ── Expiry helpers ─────────────────────────────────────────────────────────────

def get_today_expiry_str() -> str:
    """Return today's date as 'DDMMYY' used in Delta option symbols.

    Delta BTC daily options expire today at 12:00 UTC (17:30 IST).
    At entry time (17:01 IST) the today-expiry is still live.
    """
    today = date.today()
    return today.strftime("%d%m%y")


def get_today_expiry_iso() -> str:
    """Return today's date in ISO format 'YYYY-MM-DD'."""
    return date.today().isoformat()


def get_atm_strike_btc(spot: float, step: int = 100) -> int:
    """Round BTC spot price to nearest multiple of step.

    Delta BTC options use $100 strike intervals.
    """
    return round(spot / step) * step


# ── HMAC-SHA256 auth signature ─────────────────────────────────────────────────

def _sign(method: str, path: str, query_string: str, body: str, secret: str) -> tuple[str, str]:
    """Return (timestamp_str, signature_hex) for a Delta Exchange request.

    Signature = HMAC-SHA256(method + timestamp + path + query_string + body)
    """
    ts = str(int(time_mod.time()))
    message = method.upper() + ts + path + query_string + body
    sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return ts, sig


def _signed_headers(api_key: str, api_secret: str, method: str, path: str,
                    query_string: str = "", body: str = "") -> dict:
    ts, sig = _sign(method, path, query_string, body, api_secret)
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "api-key": api_key,
        "timestamp": ts,
        "signature": sig,
    }


def _public_headers() -> dict:
    return {"Accept": "application/json"}


# ── BTC Spot Price ─────────────────────────────────────────────────────────────

async def get_btc_spot() -> float:
    """Fetch BTC spot index price from Delta Exchange (no auth required).

    Returns the last traded price of the BTCUSD perpetual as a proxy for spot.
    """
    path = "/v2/tickers"
    url = DELTA_BASE + "/tickers"
    params = {"contract_types": "perpetual_futures", "underlying_asset_symbols": "BTC"}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params, headers=_public_headers())

    if resp.status_code != 200:
        raise RuntimeError(f"Delta BTC spot fetch failed: {resp.status_code} {resp.text}")

    data = resp.json()
    results = data.get("result", [])
    # Find the BTCUSD perpetual
    for item in results:
        symbol = item.get("symbol", "")
        if symbol in ("BTCUSD", "BTCUSDT") or (
            "BTC" in symbol and "PERP" in symbol.upper()
        ):
            ltp = item.get("mark_price") or item.get("close") or 0.0
            log.info("BTC spot via Delta perp (%s): %.2f", symbol, float(ltp))
            return float(ltp)

    # Fallback: use spot index
    path_idx = "/v2/indices"
    async with httpx.AsyncClient(timeout=15) as client:
        resp2 = await client.get(DELTA_BASE + "/indices", headers=_public_headers())
    if resp2.status_code == 200:
        for idx in resp2.json().get("result", []):
            if idx.get("symbol", "").upper() in (".DEXBTUSD", "DEXBTUSD", ".BTCUSD"):
                price = float(idx.get("price", 0.0))
                log.info("BTC spot via Delta index (%s): %.2f", idx.get("symbol"), price)
                return price

    raise RuntimeError(f"BTC spot price not found in Delta response: {data}")


# ── Option Chain ───────────────────────────────────────────────────────────────

async def get_option_chain(expiry_date: str | None = None) -> list[dict]:
    """Fetch BTC option chain from Delta Exchange.

    Filters products to BTC options (matching symbol 'C-BTC-' or 'P-BTC-').
    If expiry_date (ISO 'YYYY-MM-DD') is provided, filters to that expiry.
    If no options match expiry_date, falls back to the nearest live expiry.
    """
    url = DELTA_BASE + "/products"
    params = {
        "contract_types": "call_options,put_options",
        "states": "live",
    }

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, params=params, headers=_public_headers())

    if resp.status_code != 200:
        raise RuntimeError(f"Delta option chain fetch failed: {resp.status_code} {resp.text}")

    products = resp.json().get("result", [])
    btc_opts = [
        p for p in products
        if p.get("symbol", "").startswith(("C-BTC-", "P-BTC-"))
    ]

    if not expiry_date:
        return btc_opts

    filtered = []
    for p in btc_opts:
        st = p.get("settlement_time", "")
        if st:
            try:
                settle_date = datetime.fromisoformat(
                    st.replace("Z", "+00:00")
                ).date().isoformat()
                if settle_date == expiry_date:
                    filtered.append(p)
            except Exception:
                pass

    # Fallback to nearest upcoming live expiry if specific expiry date is not found
    if not filtered and btc_opts:
        expiries = sorted(list({p.get("settlement_time") for p in btc_opts if p.get("settlement_time")}))
        if expiries:
            nearest_expiry = expiries[0]
            filtered = [p for p in btc_opts if p.get("settlement_time") == nearest_expiry]
            log.info("Delta option chain: falling back to nearest live expiry %s", nearest_expiry)

    return filtered


# ── ATM Data ──────────────────────────────────────────────────────────────────

async def get_atm_data() -> dict:
    """One-shot helper that returns everything the BTC execution engine needs.

    Returns:
      {
        "spot":           float,          # BTC spot price in USD
        "atm_strike":     int,            # Nearest ATM strike from live chain
        "expiry":         "YYYY-MM-DD",   # expiry date
        "ce_product_id":  int,            # Delta product_id for the ATM call
        "pe_product_id":  int,            # Delta product_id for the ATM put
        "ce_symbol":      str,            # e.g. "C-BTC-66000-280726"
        "pe_symbol":      str,
        "ce_ltp":         float,          # last traded price in USD
        "pe_ltp":         float,
      }
    Raises RuntimeError if data cannot be fetched.
    """
    spot = await get_btc_spot()
    raw_atm = get_atm_strike_btc(spot)
    expiry = get_today_expiry_iso()

    log.info("BTC spot=%.2f  raw_atm=%d  expiry=%s", spot, raw_atm, expiry)

    chain = await get_option_chain(expiry)
    if not chain:
        chain = await get_option_chain(None)

    available_strikes = list({int(float(p.get("strike_price", 0))) for p in chain if p.get("strike_price")})
    if not available_strikes:
        raise RuntimeError("No live BTC option strikes found in Delta option chain.")

    # Select the strike in the live chain nearest to raw_atm
    atm = min(available_strikes, key=lambda s: abs(s - raw_atm))

    ce_product = pe_product = None
    for p in chain:
        strike = int(float(p.get("strike_price", 0)))
        if strike != atm:
            continue
        contract_type = p.get("contract_type", "")
        if contract_type == "call_options" and not ce_product:
            ce_product = p
        elif contract_type == "put_options" and not pe_product:
            pe_product = p

    if not ce_product or not pe_product:
        raise RuntimeError(
            f"ATM strike {atm} CE/PE pair not found in Delta BTC option chain. "
            f"Available strikes (sample): {sorted(available_strikes)[:10]}"
        )

    # Fetch LTPs for both legs
    ce_ltp = await get_option_ltp(ce_product["id"])
    pe_ltp = await get_option_ltp(pe_product["id"])

    # Fallback to close or mark price from product dict if ticker LTP is 0.0
    if ce_ltp <= 0:
        ce_ltp = float(ce_product.get("close") or ce_product.get("mark_price") or 50.0)
    if pe_ltp <= 0:
        pe_ltp = float(pe_product.get("close") or pe_product.get("mark_price") or 50.0)

    result = {
        "spot": spot,
        "atm_strike": atm,
        "expiry": expiry,
        "ce_product_id": ce_product["id"],
        "pe_product_id": pe_product["id"],
        "ce_symbol": ce_product.get("symbol", f"C-BTC-{atm}"),
        "pe_symbol": pe_product.get("symbol", f"P-BTC-{atm}"),
        "ce_ltp": ce_ltp,
        "pe_ltp": pe_ltp,
    }

    log.info(
        "Delta ATM: CE=%s id=%d ltp=%.4f | PE=%s id=%d ltp=%.4f",
        result["ce_symbol"], result["ce_product_id"], result["ce_ltp"],
        result["pe_symbol"], result["pe_product_id"], result["pe_ltp"],
    )
    return result


# ── LTP fetch ─────────────────────────────────────────────────────────────────

async def get_option_ltp(product_id: int) -> float:
    """Fetch the current mark/last price for a single Delta product."""
    url = f"{DELTA_BASE}/tickers/{product_id}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=_public_headers())
        if resp.status_code != 200:
            return 0.0
        data = resp.json().get("result", {})
        ltp = data.get("mark_price") or data.get("close") or data.get("last_price") or 0.0
        return float(ltp)
    except Exception as exc:
        log.warning("Delta LTP fetch failed for product %d: %s", product_id, exc)
        return 0.0


# ── Order Placement ───────────────────────────────────────────────────────────

async def place_order(api_key: str, api_secret: str, payload: dict) -> dict:
    """Place an order on Delta Exchange.

    Returns the raw result dict from the API.
    Raises RuntimeError on HTTP error or if order_id is missing.
    """
    path = "/v2/orders"
    body_str = __import__("json").dumps(payload)
    headers = _signed_headers(api_key, api_secret, "POST", path, "", body_str)

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(DELTA_BASE + "/orders", content=body_str, headers=headers)

    body = resp.json() if resp.content else {}
    if resp.status_code not in (200, 201):
        log.error("Delta order failed %s: %s", resp.status_code, body)
        raise RuntimeError(body.get("error", {}).get("message", "delta_order_placement_failed"))

    result = body.get("result", body)
    log.info("Delta order placed: id=%s side=%s size=%s product=%s",
             result.get("id"), result.get("side"), result.get("size"), result.get("product_id"))
    return result


async def cancel_order(
    api_key: str,
    api_secret: str,
    order_id: str | int,
    product_id: str | int | None = None,
) -> dict:
    """Cancel an open Delta Exchange order by order ID.

    Supports both DELETE /v2/orders with payload {"id": order_id, "product_id": product_id}
    and fallback to DELETE /v2/orders/{order_id}.
    """
    if not order_id:
        return {}

    path = "/v2/orders"
    payload = {"id": int(order_id)}
    if product_id is not None:
        try:
            payload["product_id"] = int(product_id)
        except (ValueError, TypeError):
            pass

    body_str = __import__("json").dumps(payload)
    headers = _signed_headers(api_key, api_secret, "DELETE", path, "", body_str)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.request("DELETE", DELTA_BASE + "/orders", content=body_str, headers=headers)

        body = resp.json() if resp.content else {}
        if resp.status_code in (200, 201, 204):
            return body.get("result", {})
    except Exception as exc:
        log.warning("Delta cancel order payload method failed for %s: %s", order_id, exc)

    # Fallback method: DELETE /v2/orders/{order_id}
    path_url = f"/v2/orders/{order_id}"
    headers_fallback = _signed_headers(api_key, api_secret, "DELETE", path_url)
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.delete(DELTA_BASE + f"/orders/{order_id}", headers=headers_fallback)

    body = resp.json() if resp.content else {}
    if resp.status_code not in (200, 201, 204):
        log.warning("Delta cancel order %s failed %s: %s", order_id, resp.status_code, body)
        raise RuntimeError(body.get("error", {}).get("message", "delta_cancel_order_failed"))
    return body.get("result", {})


async def get_order_status(api_key: str, api_secret: str, order_id: str | int) -> dict:
    """Fetch the current status of an order by ID.

    Returns the raw order dict.
    """
    path = f"/v2/orders/{order_id}"
    headers = _signed_headers(api_key, api_secret, "GET", path)

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(DELTA_BASE + f"/orders/{order_id}", headers=headers)

    if resp.status_code != 200:
        log.warning("Delta get order %s failed %s", order_id, resp.status_code)
        return {}
    return resp.json().get("result", {})


# ── Token helpers (used by execution engine) ───────────────────────────────────

def get_delta_credentials(token_store, account_id: str) -> tuple[str, str] | tuple[None, None]:
    """Return (api_key, api_secret) for a Delta account from the token store.

    Returns (None, None) if not found.
    """
    tokens = token_store.get_tokens(account_id)
    if not tokens or tokens.get("broker") != "delta":
        return None, None
    return tokens.get("api_key"), tokens.get("api_secret")


# ── USD ↔ INR conversion ───────────────────────────────────────────────────────

def usd_to_inr(usd_amount: float, rate: float = USD_TO_INR) -> float:
    """Convert USD amount to INR using a fixed or provided rate."""
    return round(usd_amount * rate, 2)
