"""Live market-data feed — streams LTPs over websocket and marks open positions to market.

Two long-lived asyncio tasks are started from the FastAPI lifespan:

  run_upstox_feed()  — Upstox Market Data Feed V3 websocket. Subscribes to the instruments
                       of every currently-open NSE position and keeps an in-memory LTP cache.
  run_live_pnl()     — every `live_pnl_write_interval_seconds`, writes the unrealised P&L of
                       each open position back to its Firestore doc, which the UI streams.

Why a websocket: the old REST poll ran once a minute and only wrote `pnl` on exit, so an
open position always showed ₹0 in the UI.

`pnl` vs `unrealizedPnl`: marks are written to `unrealizedPnl` and never to `pnl`, which
stays reserved for the booked result the exit paths write. The UI shows `pnl` once it
exists and falls back to `unrealizedPnl` while the position is open, so a mark landing in
the same instant a position closes can't clobber the realised number.

Instrument keys
---------------
Upstox keys look like "NSE_FO|43427". Jainam stores the bare NSE token as `instrumentKey`,
which is the same number, so a Jainam position is subscribed as "NSE_FO|<instrumentKey>".

Delta Exchange (BTC) is not on this websocket — its positions are marked from the existing
Delta REST LTP endpoint on the same interval. BTC trades in a 30-minute window with two
legs, so the request volume is negligible.

Robustness
----------
Everything here is best-effort. The feed decoding is defensive (Upstox streams protobuf;
see `_decode_feed`), and any position the websocket has no tick for falls back to a REST
LTP fetch. A failure only means P&L updates lag — it can never block or alter execution.
"""
import asyncio
import json
import logging
import struct
import uuid
from datetime import datetime

import httpx
import pytz

from config import settings

log = logging.getLogger("tradzo.livefeed")

IST = pytz.timezone("Asia/Kolkata")
UPSTOX_AUTHORIZE_URL = "https://api.upstox.com/v3/feed/market-data-feed/authorize"

# instrument key → last traded price, populated by the websocket.
_ltp_cache: dict[str, float] = {}
# Instrument keys the feed should be subscribed to, refreshed from open positions.
_wanted: set[str] = set()
_subscribed: set[str] = set()
_resubscribe = asyncio.Event()

_stopping = False


def get_cached_ltp(instrument_key: str) -> float | None:
    return _ltp_cache.get(instrument_key)


def upstox_key_for(position: dict) -> str | None:
    """Upstox instrument key for an NSE position, or None if it isn't an NSE leg."""
    raw = str(position.get("instrumentKey") or "").strip()
    if not raw:
        return None
    if position.get("strategyCode") == "BTC_OPTION_SELLING" or position.get("broker") == "delta":
        return None
    if "|" in raw:
        return raw
    return f"NSE_FO|{raw}"


# ── Protobuf decoding ─────────────────────────────────────────────────────────
#
# Upstox V3 streams a protobuf `FeedResponse`. We only need one number out of it, so
# rather than pulling in protoc-generated bindings we walk the wire format directly:
#
#   FeedResponse.feeds = field 2, a map<string, Feed>
#   map entry          = field 1 (string key), field 2 (Feed value)
#   Feed.ltpc          = field 1 (LTPC), Feed.fullFeed = field 2 (wraps an LTPC)
#   LTPC.ltp           = field 1, double
#
# `_extract_ltp` searches those nested messages instead of hard-coding one path, so a
# mode change (ltpc vs full) still resolves. Anything unparseable is skipped and the
# position falls back to a REST LTP.

def _read_varint(buf: bytes, i: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, i
        shift += 7


def _iter_fields(buf: bytes):
    """Yield (field_number, wire_type, value) for one protobuf message."""
    i, n = 0, len(buf)
    while i < n:
        tag, i = _read_varint(buf, i)
        field, wire = tag >> 3, tag & 7
        if wire == 0:
            val, i = _read_varint(buf, i)
        elif wire == 1:
            val, i = buf[i:i + 8], i + 8
        elif wire == 2:
            length, i = _read_varint(buf, i)
            val, i = buf[i:i + length], i + length
        elif wire == 5:
            val, i = buf[i:i + 4], i + 4
        else:
            return  # group wire types are not used by this schema
        yield field, wire, val


def _extract_ltp(feed: bytes, depth: int = 0) -> float | None:
    """Find LTPC.ltp inside a Feed message (possibly wrapped in a FullFeed)."""
    if depth > 3:
        return None
    for field, wire, val in _iter_fields(feed):
        if wire != 2 or not val:
            continue
        for f2, w2, v2 in _iter_fields(val):
            if f2 == 1 and w2 == 1 and len(v2) == 8:  # LTPC.ltp, double
                ltp = struct.unpack("<d", v2)[0]
                if ltp > 0:
                    return ltp
        nested = _extract_ltp(val, depth + 1)
        if nested is not None:
            return nested
    return None


def _decode_feed(payload: bytes) -> dict[str, float]:
    """Decode one FeedResponse frame into {instrument_key: ltp}."""
    out: dict[str, float] = {}
    try:
        for field, wire, val in _iter_fields(payload):
            if field != 2 or wire != 2:
                continue
            key = feed = None
            for f2, w2, v2 in _iter_fields(val):
                if f2 == 1 and w2 == 2:
                    key = v2.decode("utf-8", "replace")
                elif f2 == 2 and w2 == 2:
                    feed = v2
            if key and feed:
                ltp = _extract_ltp(feed)
                if ltp is not None:
                    out[key] = ltp
    except Exception as exc:  # noqa: BLE001 — a malformed frame must not kill the feed
        log.debug("Could not decode a feed frame: %s", exc)
    return out


# ── Subscription set ──────────────────────────────────────────────────────────

def _open_positions() -> list[dict] | None:
    """Today's open positions, or None if Firestore could not be read."""
    from services import position_service

    today = datetime.now(IST).strftime("%Y-%m-%d")
    try:
        return position_service.get_open_positions_for_date(today)
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not list open positions for the feed: %s", exc)
        return None


def _apply_subscriptions(positions: list[dict]) -> set[str]:
    """Point the websocket at exactly the instruments these positions need."""
    global _wanted
    keys = {k for k in (upstox_key_for(p) for p in positions) if k}
    if keys != _wanted:
        _wanted = keys
        _resubscribe.set()
    return _wanted


def refresh_subscriptions() -> set[str]:
    """Recompute the instrument set from today's open positions."""
    positions = _open_positions()
    return _wanted if positions is None else _apply_subscriptions(positions)


# ── Upstox websocket ──────────────────────────────────────────────────────────

async def _authorize_feed() -> str | None:
    """Exchange the market-data token for a one-shot websocket URL."""
    from services.market_data_service import _get_market_data_token

    token = _get_market_data_token()
    if not token:
        log.warning("No Upstox market-data token — live feed cannot connect.")
        return None
    headers = {"accept": "application/json", "Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(UPSTOX_AUTHORIZE_URL, headers=headers)
    if resp.status_code != 200:
        log.warning("Upstox feed authorize failed %s: %s", resp.status_code, resp.text[:200])
        return None
    return resp.json().get("data", {}).get("authorized_redirect_uri")


async def _send_subscription(ws, keys: set[str], method: str) -> None:
    if not keys:
        return
    await ws.send(json.dumps({
        "guid": uuid.uuid4().hex[:16],
        "method": method,
        "data": {"mode": "ltpc", "instrumentKeys": sorted(keys)},
    }))


async def _feed_session() -> None:
    """One websocket connection; returns when it drops so the caller can reconnect."""
    import websockets

    global _subscribed

    uri = await _authorize_feed()
    if not uri:
        return

    async with websockets.connect(uri, max_size=None, ping_interval=20) as ws:
        _subscribed = set()
        log.info("Upstox live feed connected.")

        async def _sync_subscriptions() -> None:
            global _subscribed
            while not _stopping:
                await _resubscribe.wait()
                _resubscribe.clear()
                add, drop = _wanted - _subscribed, _subscribed - _wanted
                if add:
                    await _send_subscription(ws, add, "sub")
                if drop:
                    await _send_subscription(ws, drop, "unsub")
                    for k in drop:
                        _ltp_cache.pop(k, None)
                _subscribed = set(_wanted)
                if add or drop:
                    log.info("Live feed subscriptions: %d instrument(s).", len(_subscribed))

        _resubscribe.set()  # push the initial subscription
        syncer = asyncio.create_task(_sync_subscriptions())
        try:
            async for message in ws:
                if isinstance(message, str):
                    continue  # control/ack frames
                _ltp_cache.update(_decode_feed(message))
        finally:
            syncer.cancel()


async def run_upstox_feed() -> None:
    """Keep the Upstox websocket alive, reconnecting with backoff."""
    if not settings.enable_live_feed:
        log.info("Live feed disabled via ENABLE_LIVE_FEED=false.")
        return

    backoff = 2
    while not _stopping:
        try:
            refresh_subscriptions()
            if not _wanted:
                await asyncio.sleep(30)  # nothing open — don't hold a socket open
                continue
            await _feed_session()
            backoff = 2
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("Live feed connection failed (%s); retrying in %ds.", exc, backoff)
        _subscribed.clear()
        if _stopping:
            break
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60)


# ── Mark-to-market writer ─────────────────────────────────────────────────────

async def _resolve_ltp(position: dict) -> float:
    """Current price for a position: websocket cache first, REST as a fallback."""
    if position.get("strategyCode") == "BTC_OPTION_SELLING" or position.get("broker") == "delta":
        from services import delta_service
        try:
            return float(await delta_service.get_option_ltp(int(position["instrumentKey"])))
        except Exception as exc:  # noqa: BLE001
            log.debug("Delta LTP fetch failed for %s: %s", position.get("symbol"), exc)
            return 0.0

    key = upstox_key_for(position)
    if not key:
        return 0.0
    cached = _ltp_cache.get(key)
    if cached:
        return cached
    from services import market_data_service
    try:
        return float(await market_data_service.get_option_ltp(key))
    except Exception as exc:  # noqa: BLE001
        log.debug("REST LTP fallback failed for %s: %s", key, exc)
        return 0.0


async def mark_open_positions() -> dict:
    """Write unrealised P&L onto every open position doc.

    Also re-points the websocket subscription, so one Firestore read per cycle serves
    both jobs. Returns {"marked": n, "open": n}.
    """
    from services import position_service

    positions = _open_positions()
    if positions is None:
        return {"marked": 0, "open": 0}
    _apply_subscriptions(positions)

    usd_inr = float(getattr(settings, "usd_to_inr_rate", 85.0))
    marked = 0

    for pos in positions:
        if pos.get("status") != "open":
            continue
        ltp = await _resolve_ltp(pos)
        if ltp <= 0:
            continue

        entry = float(pos.get("entryPrice") or 0.0)
        qty = float(pos.get("quantity") or 0)
        pnl = round((entry - ltp) * qty, 6)   # every leg is short

        # Deliberately NOT `pnl`: that field is the booked result written by the exit
        # paths. Marking into a separate field means a mark can never land on top of a
        # realised P&L if a position closes mid-cycle.
        updates: dict = {
            "ltp": round(ltp, 4),
            "unrealizedPnl": pnl,
            "pnlUpdatedAt": datetime.now(IST),
        }
        if str(pos.get("currency", "")).upper() == "USD":
            updates["ltpInr"] = round(ltp * usd_inr, 2)
            updates["unrealizedPnlInr"] = round(pnl * usd_inr, 2)

        # Skip no-op writes — the UI streams these docs and Firestore bills per write.
        if pos.get("unrealizedPnl") is not None and abs(float(pos["unrealizedPnl"]) - pnl) < 0.005:
            continue
        try:
            position_service.update_position(pos["id"], updates)
            marked += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("Live P&L write failed for position %s: %s", pos.get("id"), exc)

    return {"marked": marked, "open": len(positions)}


# Nothing is open for most of the day; back off so the idle loop isn't querying
# Firestore every few seconds around the clock.
IDLE_INTERVAL_SECONDS = 30.0


async def run_live_pnl() -> None:
    """Mark open positions to market forever, backing off while nothing is open."""
    if not settings.enable_live_feed:
        return
    interval = max(1.0, float(getattr(settings, "live_pnl_write_interval_seconds", 5.0)))
    while not _stopping:
        delay = IDLE_INTERVAL_SECONDS
        try:
            result = await mark_open_positions()
            if result["open"]:
                delay = interval
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("Live P&L cycle failed: %s", exc)
        await asyncio.sleep(delay)


# ── Lifecycle ─────────────────────────────────────────────────────────────────

_tasks: list[asyncio.Task] = []


def start() -> None:
    global _stopping
    if _tasks or not settings.enable_live_feed:
        return
    _stopping = False
    loop = asyncio.get_event_loop()
    _tasks.append(loop.create_task(run_upstox_feed()))
    _tasks.append(loop.create_task(run_live_pnl()))
    log.info("Live feed + live P&L started (write interval %.1fs).",
             settings.live_pnl_write_interval_seconds)


async def stop() -> None:
    global _stopping
    _stopping = True
    _resubscribe.set()
    for task in _tasks:
        task.cancel()
    for task in _tasks:
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
    _tasks.clear()
