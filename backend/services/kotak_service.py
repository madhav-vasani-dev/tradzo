"""Kotak Neo broker integration — Neo Trade API (TOTP + MPIN flow).

Reference: github.com/Kotak-Neo/Kotak-Neo (REST docs) and github.com/Kotak-Neo/kotak-neo-python
(official SDK v3). The old consumer-key/secret + OTP flow (gw-napi / napi.kotaksecurities.com)
was retired on 1 Oct 2025 — this module only speaks the current API.

Credentials (entered once by the client, stored Fernet-encrypted in `brokerCredentials`)
----------------------------------------------------------------------------------------
  accessToken  — "Trade API" token from Neo app/web → More → Trade API → Create Application.
                 Sent as a PLAIN `Authorization` header (no "Bearer").
  ucc          — Kotak client code (Neo app → Profile).
  mobileNumber — registered mobile, with ISD code (+91XXXXXXXXXX).
  mpin         — the 6-digit Neo MPIN.
  totpSecret   — base32 secret shown when registering TOTP on the API dashboard. Storing it
                 lets the backend generate the 6-digit TOTP itself, so the daily login is fully
                 automatic and the client never has to log in by hand.

Login (two calls, both to the fixed session host)
-------------------------------------------------
  POST https://mis.kotaksecurities.com/login/1.0/tradeApiLogin
       headers  Authorization: <accessToken>, neo-fin-key: neotradeapi
       body     {"mobileNumber", "ucc", "totp"}            → data.token (view), data.sid (view)
  POST https://mis.kotaksecurities.com/login/1.0/tradeApiValidate
       headers  + sid: <view sid>, Auth: <view token>
       body     {"mpin"}                                     → data.token, data.sid, data.baseUrl

Every later call goes to `data.baseUrl` (per-account; never hard-coded):
  * orders / reports / positions  → headers Auth=<session token>, Sid=<session sid>,
                                    neo-fin-key, form body `jData=<json>`
  * quotes / option chain / expiries → header Authorization=<accessToken> only

Static IP (SEBI, enforced since 1 Apr 2026)
-------------------------------------------
Place / modify / cancel are only accepted from an IP the client whitelisted on the Neo API
dashboard, and the SESSION must have been created from that same IP. This backend logs in and
trades from the same server, so the client whitelists the server's public (Elastic) IP once.
`stCode 100008` = IP not whitelisted, `stCode 1037` = session/IP mismatch.

Sessions
--------
Kotak does not publish the session lifetime, so we log in fresh every trading morning
(scheduler: `kotak_daily_login`), again lazily whenever a session is missing or older than
today, and once more if any call reports an invalid session. Sessions are cached in memory and
persisted (encrypted) in the token store, so a restart does not force a new login.

Instrument keys
---------------
Kotak orders need the exchange segment + trading symbol, quotes/positions need the
segment + token. Tradzo therefore stores a Kotak `instrumentKey` as "<seg>|<token>|<tradingSymbol>",
e.g. "mcx_fo|445566|CRUDEOILM26OCT6100CE" (see `make_instrument_key` / `parse_instrument_key`).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import struct
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytz

from config import settings

log = logging.getLogger("tradzo.kotak")
IST = pytz.timezone("Asia/Kolkata")

NEO_FIN_KEY = "neotradeapi"
ORDER_SOURCE = "NEOTRADEAPI"

LOGIN_PATH = "/login/1.0/tradeApiLogin"
VALIDATE_PATH = "/login/1.0/tradeApiValidate"
CLIENT_IP_PATH = "/login/1.0/get-client-ip"

PLACE_PATH = "/quick/order/rule/ms/place"
MODIFY_PATH = "/quick/order/vr/modify"
CANCEL_PATH = "/quick/order/cancel"
HISTORY_PATH = "/quick/order/history"
ORDER_BOOK_PATH = "/quick/user/orders"
POSITIONS_PATH = "/quick/user/positions"
POSITIONS_V2_PATH = "/portfolio/v2/positions"
LIMITS_PATH = "/quick/user/limits"
QUOTES_PATH = "/script-details/1.0/quotes/neosymbol/{symbols}/{kind}"
EXPIRIES_PATH = "/market-data/1.0/watchlist/expiries"
OPTION_CHAIN_PATH = "/market-data/1.0/watchlist/option-chain"

# stCodes / HTTP codes that mean "the session is gone — log in again".
_SESSION_INVALID_CODES = {1003, 1037}
_IP_NOT_WHITELISTED = 100008
_ORDER_ALREADY_COMPLETE = 1021

TERMINAL_COMPLETE = {"complete", "completed", "traded", "filled"}
TERMINAL_CANCELLED = {"cancelled", "canceled", "expired"}
TERMINAL_REJECTED = {"rejected"}


# ── Errors ────────────────────────────────────────────────────────────────────

class KotakError(RuntimeError):
    """A Kotak API call failed. `code` is the stCode/errorCode when the API sent one."""

    def __init__(self, message: str, *, code: int | None = None, http_status: int | None = None,
                 payload: Any = None):
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.payload = payload

    @property
    def session_invalid(self) -> bool:
        if self.code in _SESSION_INVALID_CODES:
            return True
        if self.http_status == 401:
            return True
        if self.http_status == 403 and self.code is None:
            return True
        msg = str(self).lower()
        return "invalid session" in msg or "session expired" in msg or "expired session" in msg

    @property
    def ip_not_whitelisted(self) -> bool:
        return self.code == _IP_NOT_WHITELISTED or self.code == 1037


class KotakLoginError(KotakError):
    """Login (TOTP or MPIN step) was refused."""


# ── TOTP (RFC 6238, SHA-1, 30 s, 6 digits — what Google/Microsoft Authenticator use) ──

def _normalise_secret(secret: str) -> bytes:
    s = "".join(str(secret or "").split()).upper().rstrip("=")
    if not s:
        raise ValueError("TOTP secret is empty")
    s += "=" * (-len(s) % 8)
    try:
        return base64.b32decode(s, casefold=True)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("TOTP secret is not valid base32 — copy the key shown under the QR code") from exc


def totp_now(secret: str, for_time: float | None = None, step: int = 30, digits: int = 6) -> str:
    key = _normalise_secret(secret)
    counter = int((for_time if for_time is not None else time.time()) // step)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def validate_totp_secret(secret: str) -> None:
    """Raise ValueError if the secret can't produce a TOTP."""
    totp_now(secret)


def normalise_mobile(mobile: str) -> str:
    digits = "".join(ch for ch in str(mobile or "") if ch.isdigit() or ch == "+")
    if digits.startswith("+"):
        return digits
    digits = digits.lstrip("0")
    if len(digits) == 10:
        return f"+91{digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    return f"+{digits}" if digits else ""


# ── Instrument keys ───────────────────────────────────────────────────────────

def make_instrument_key(segment: str, token: str | int, trading_symbol: str) -> str:
    return f"{segment}|{token}|{trading_symbol}"


def parse_instrument_key(key: str) -> tuple[str, str, str]:
    """"mcx_fo|445566|CRUDEOILM26OCT6100CE" → ("mcx_fo", "445566", "CRUDEOILM26OCT6100CE")."""
    parts = str(key or "").split("|", 2)
    if len(parts) != 3 or not all(parts):
        raise ValueError(f"Not a Kotak instrument key: {key!r}")
    return parts[0], parts[1], parts[2]


def is_kotak_key(key: str) -> bool:
    try:
        parse_instrument_key(key)
        return True
    except ValueError:
        return False


# ── Session model ─────────────────────────────────────────────────────────────

@dataclass
class KotakSession:
    account_id: str
    access_token: str
    ucc: str
    auth: str
    sid: str
    base_url: str
    data_center: str = ""
    created_at: str = ""            # ISO, IST
    expires_at: str | None = None    # ISO, from the session JWT's `exp`, when present
    extra: dict = field(default_factory=dict)

    def to_handle(self) -> str:
        """Opaque string the execution engine passes around as `access_token`."""
        return json.dumps({"kotak": 1, **asdict(self)}, separators=(",", ":"))

    @classmethod
    def from_handle(cls, handle: str | dict) -> "KotakSession":
        data = json.loads(handle) if isinstance(handle, str) else dict(handle)
        data.pop("kotak", None)
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})

    def created_dt(self) -> datetime | None:
        try:
            dt = datetime.fromisoformat(self.created_at)
            return dt if dt.tzinfo else IST.localize(dt)
        except (TypeError, ValueError):
            return None

    def expires_dt(self) -> datetime | None:
        if not self.expires_at:
            return None
        try:
            dt = datetime.fromisoformat(self.expires_at)
            return dt if dt.tzinfo else IST.localize(dt)
        except (TypeError, ValueError):
            return None

    def is_fresh(self, now: datetime | None = None) -> bool:
        """Usable for trading today: created today (IST) and not past its JWT expiry."""
        now = now or datetime.now(IST)
        created = self.created_dt()
        if not created or created.astimezone(IST).date() != now.date():
            return False
        exp = self.expires_dt()
        if exp and exp <= now + timedelta(minutes=2):
            return False
        return bool(self.auth and self.sid and self.base_url)


def is_handle(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("{"):
        return False
    try:
        return json.loads(value).get("kotak") == 1
    except (ValueError, AttributeError):
        return False


def _jwt_exp(token: str) -> datetime | None:
    """Read `exp` from a JWT WITHOUT verifying it (only used to know when to re-login)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        exp = json.loads(base64.urlsafe_b64decode(payload)).get("exp")
        return datetime.fromtimestamp(int(exp), IST) if exp else None
    except Exception:  # noqa: BLE001
        return None


# ── HTTP plumbing ─────────────────────────────────────────────────────────────

def _login_base() -> str:
    return str(getattr(settings, "kotak_login_base_url", "https://mis.kotaksecurities.com")).rstrip("/")


def _timeout() -> float:
    return float(getattr(settings, "kotak_http_timeout_seconds", 15.0))


def _as_int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _error_from(resp: httpx.Response, body: Any, what: str) -> KotakError | None:
    """Turn an error-shaped response into a KotakError, or None if it's a success."""
    if isinstance(body, dict):
        stat = str(body.get("stat") or body.get("status") or "").lower()
        code = _as_int(body.get("stCode") if body.get("stCode") is not None else body.get("errorCode"))
        msg = (body.get("emsg") or body.get("errMsg") or body.get("message")
               or body.get("error") or body.get("Error") or "")
        is_err = (
            resp.status_code >= 400
            or stat in ("not_ok", "error", "notok")
            or (code is not None and code not in (0, 200))
        )
        if is_err:
            if isinstance(msg, (dict, list)):
                msg = json.dumps(msg)
            text = f"{what}: {msg or resp.reason_phrase or 'error'}"
            if code is not None:
                text += f" (code {code})"
            return KotakError(text, code=code, http_status=resp.status_code, payload=body)
        return None
    if resp.status_code >= 400:
        return KotakError(f"{what}: HTTP {resp.status_code} {resp.text[:300]}",
                          http_status=resp.status_code, payload=body)
    return None


async def _send(method: str, url: str, *, headers: dict, params: dict | None = None,
                json_body: dict | None = None, jdata: dict | None = None, what: str = "kotak") -> Any:
    kwargs: dict[str, Any] = {"headers": {k: v for k, v in headers.items() if v is not None}}
    if params:
        kwargs["params"] = params
    if json_body is not None:
        kwargs["json"] = json_body
    if jdata is not None:
        kwargs["data"] = {"jData": json.dumps(jdata, separators=(",", ":"))}
    async with httpx.AsyncClient(timeout=_timeout()) as client:
        resp = await client.request(method, url, **kwargs)
    try:
        body = resp.json() if resp.content else {}
    except ValueError:
        body = {"raw": resp.text[:500]}
    err = _error_from(resp, body, what)
    if err:
        raise err
    return body


def _session_headers(sess: KotakSession) -> dict:
    return {
        "accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "Auth": sess.auth,
        "Sid": sess.sid,
        "neo-fin-key": NEO_FIN_KEY,
        # The official SDK also sends the access token on order calls; harmless elsewhere.
        "Authorization": sess.access_token,
    }


def _data_headers(access_token: str) -> dict:
    return {"accept": "application/json", "Content-Type": "application/json",
            "Authorization": access_token}


# ── Login ─────────────────────────────────────────────────────────────────────

REQUIRED_CRED_KEYS = ("accessToken", "ucc", "mobileNumber", "mpin", "totpSecret")


def validate_credentials(creds: dict) -> None:
    missing = [k for k in REQUIRED_CRED_KEYS if not str(creds.get(k) or "").strip()]
    if missing:
        raise ValueError(f"Missing Kotak credentials: {', '.join(missing)}")
    mpin = str(creds["mpin"]).strip()
    if not (mpin.isdigit() and len(mpin) in (4, 6)):
        raise ValueError("MPIN must be your 4 or 6 digit Kotak Neo MPIN")
    if not normalise_mobile(creds["mobileNumber"]).startswith("+"):
        raise ValueError("Mobile number is invalid")
    validate_totp_secret(creds["totpSecret"])


async def login(account_id: str, creds: dict) -> KotakSession:
    """Full TOTP + MPIN login. Raises KotakLoginError with a client-readable message."""
    try:
        validate_credentials(creds)
    except ValueError as exc:
        raise KotakLoginError(str(exc)) from exc

    access_token = str(creds["accessToken"]).strip()
    ucc = str(creds["ucc"]).strip().upper()
    mobile = normalise_mobile(creds["mobileNumber"])

    # Never submit a code that is about to roll over — it can expire in flight.
    remaining = 30 - (time.time() % 30)
    if remaining < 3:
        await asyncio.sleep(remaining + 0.5)
    totp = totp_now(creds["totpSecret"])

    base = _login_base()
    try:
        step1 = await _send(
            "POST", f"{base}{LOGIN_PATH}",
            headers={"Authorization": access_token, "neo-fin-key": NEO_FIN_KEY,
                     "Content-Type": "application/json", "accept": "application/json"},
            json_body={"mobileNumber": mobile, "ucc": ucc, "totp": totp},
            what="Kotak TOTP login",
        )
    except KotakError as exc:
        raise KotakLoginError(_friendly_login_error(exc, "TOTP"), code=exc.code,
                              http_status=exc.http_status, payload=exc.payload) from exc
    d1 = step1.get("data") if isinstance(step1, dict) else None
    if not isinstance(d1, dict) or not d1.get("token") or not d1.get("sid"):
        raise KotakLoginError(f"Kotak TOTP login returned no session: {_brief(step1)}", payload=step1)

    try:
        step2 = await _send(
            "POST", f"{base}{VALIDATE_PATH}",
            headers={"Authorization": access_token, "neo-fin-key": NEO_FIN_KEY,
                     "Content-Type": "application/json", "accept": "application/json",
                     "sid": d1["sid"], "Auth": d1["token"]},
            json_body={"mpin": str(creds["mpin"]).strip()},
            what="Kotak MPIN validation",
        )
    except KotakError as exc:
        raise KotakLoginError(_friendly_login_error(exc, "MPIN"), code=exc.code,
                              http_status=exc.http_status, payload=exc.payload) from exc
    d2 = step2.get("data") if isinstance(step2, dict) else None
    if not isinstance(d2, dict) or not d2.get("token") or not d2.get("sid"):
        raise KotakLoginError(f"Kotak MPIN validation returned no session: {_brief(step2)}", payload=step2)

    base_url = str(d2.get("baseUrl") or "").rstrip("/")
    if not base_url.startswith("http"):
        raise KotakLoginError("Kotak login succeeded but returned no baseUrl — cannot route orders.")

    now = datetime.now(IST)
    exp = _jwt_exp(d2["token"])
    sess = KotakSession(
        account_id=account_id,
        access_token=access_token,
        ucc=str(d2.get("ucc") or d1.get("ucc") or ucc),
        auth=d2["token"],
        sid=d2["sid"],
        base_url=base_url,
        data_center=str(d2.get("dataCenter") or ""),
        created_at=now.isoformat(),
        expires_at=exp.isoformat() if exp else None,
        extra={
            "greetingName": d1.get("greetingName") or d2.get("greetingName") or "",
            "feedUrl": d2.get("feedUrl") or "",
            "isTrialAccount": d2.get("isTrialAccount"),
        },
    )
    log.info("Kotak login OK for %s (ucc=%s, dc=%s, session exp=%s).",
             account_id, sess.ucc, sess.data_center, sess.expires_at or "unknown")
    return sess


def _brief(body: Any) -> str:
    try:
        return json.dumps(body)[:300]
    except (TypeError, ValueError):
        return str(body)[:300]


def _friendly_login_error(exc: KotakError, step: str) -> str:
    raw = str(exc)
    low = raw.lower()
    if step == "TOTP":
        if "totp" in low or exc.http_status == 401:
            return ("Kotak rejected the TOTP/credentials. Check the client code (UCC), mobile number "
                    "(+91…) and that the TOTP secret is the one registered on the Neo API dashboard. "
                    f"[{raw}]")
        if "service" in low:
            return ("Kotak login is temporarily blocked (too many attempts). Wait 5 minutes and try "
                    f"again. [{raw}]")
        if exc.http_status == 403 or "token" in low or "consumer" in low:
            return ("Kotak rejected the API access token. Copy it again from Neo → More → Trade API "
                    f"(a token reset invalidates the old one). [{raw}]")
    if step == "MPIN":
        return f"Kotak rejected the MPIN. Enter the 6-digit Neo MPIN. [{raw}]"
    return raw


# ── Session cache (in-memory + encrypted token store) ─────────────────────────

_cache: dict[str, KotakSession] = {}
_cache_lock = threading.Lock()
_login_locks: dict[tuple[int, str], tuple[asyncio.AbstractEventLoop, asyncio.Lock]] = {}
_last_login_attempt: dict[str, float] = {}
_LOGIN_COOLDOWN_SECONDS = 45.0


def _loop_lock(account_id: str) -> asyncio.Lock:
    """Per-(event loop, account) login lock. Scheduler jobs each run their own loop
    (asyncio.run in a worker thread), so a single asyncio.Lock can't be shared."""
    loop = asyncio.get_running_loop()
    key = (id(loop), account_id)
    with _cache_lock:
        for k in [k for k, (lp, _) in _login_locks.items() if lp.is_closed()]:
            _login_locks.pop(k, None)              # drop locks of finished jobs' loops
        entry = _login_locks.get(key)
        if entry is None or entry[0] is not loop:
            entry = _login_locks[key] = (loop, asyncio.Lock())
    return entry[1]


def cached_session(account_id: str) -> KotakSession | None:
    with _cache_lock:
        sess = _cache.get(account_id)
    if sess:
        return sess
    try:
        from utils import token_store
        tokens = token_store.get_tokens(account_id) or {}
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not read stored Kotak session for %s: %s", account_id, exc)
        return None
    handle = tokens.get("session") if tokens.get("broker") == "kotak" else None
    if not handle:
        return None
    try:
        sess = KotakSession.from_handle(handle)
    except Exception:  # noqa: BLE001
        return None
    with _cache_lock:
        _cache[account_id] = sess
    return sess


def _remember(sess: KotakSession, persist: bool = True) -> None:
    with _cache_lock:
        _cache[sess.account_id] = sess
    if persist:
        try:
            from utils import token_store
            token_store.save_tokens(sess.account_id, {
                "broker": "kotak",
                "access_token": sess.to_handle(),   # what the engine passes to order_service
                "session": sess.to_handle(),
                "expiry": sess.expires_at,
                "created_at": sess.created_at,
            })
        except Exception as exc:  # noqa: BLE001
            log.error("Could not persist Kotak session for %s: %s", sess.account_id, exc)


def forget(account_id: str) -> None:
    with _cache_lock:
        _cache.pop(account_id, None)


async def ensure_session(account_id: str, *, force: bool = False,
                         stale: KotakSession | None = None) -> KotakSession:
    """Return a usable session for the account, logging in if needed.

    `stale` — the session a caller just saw fail; we only re-login if the cache still holds
    that same session (another coroutine may already have refreshed it).
    """
    async with _loop_lock(account_id):
        current = cached_session(account_id)
        if current and not force:
            if stale is None and current.is_fresh():
                return current
            if stale is not None and current.auth != stale.auth and current.is_fresh():
                return current

        last = _last_login_attempt.get(account_id, 0.0)
        wait = _LOGIN_COOLDOWN_SECONDS - (time.monotonic() - last)
        if wait > 0 and not force:
            if current and current.is_fresh() and stale is None:
                return current
            raise KotakLoginError(
                f"Kotak login for {account_id} was attempted {int(_LOGIN_COOLDOWN_SECONDS - wait)}s ago; "
                "waiting before retrying to avoid a TOTP lock-out."
            )
        _last_login_attempt[account_id] = time.monotonic()

        from utils import credentials_store
        creds = credentials_store.get_credentials(account_id)
        if not creds:
            raise KotakLoginError("No stored Kotak credentials for this account — connect it again.")
        sess = await login(account_id, creds)
        _remember(sess)
        _mark_account_ok(sess)
        return sess


def ensure_session_sync(account_id: str, *, force: bool = False) -> KotakSession:
    return run_sync(ensure_session(account_id, force=force))


def run_sync(coro):
    """Run a coroutine from sync code, whether or not an event loop is running here."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(asyncio.run, coro).result()


def _mark_account_ok(sess: KotakSession) -> None:
    try:
        from services import firebase_service
        now = datetime.now(IST)
        firebase_service.update_broker_account(sess.account_id, {
            "isConnected": True,
            "needsReauth": False,
            "lastRefreshedAt": now,
            "expiresAt": sess.expires_dt() or (now + timedelta(hours=18)),
            "lastLoginError": None,
            "lastLoginAt": now,
        })
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not update Kotak account %s after login: %s", sess.account_id, exc)


def mark_login_failed(account_id: str, message: str) -> None:
    """Flag the account for attention WITHOUT disabling the client's strategies —
    the next scheduled login (or a manual reconnect) can recover it."""
    try:
        from services import firebase_service
        firebase_service.update_broker_account(account_id, {
            "needsReauth": True,
            "lastLoginError": message[:500],
            "lastLoginErrorAt": datetime.now(IST),
        })
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not flag Kotak account %s: %s", account_id, exc)


def _session_from(handle_or_session: str | KotakSession) -> KotakSession:
    if isinstance(handle_or_session, KotakSession):
        return handle_or_session
    if not is_handle(handle_or_session):
        raise KotakError("Kotak session handle missing — the account must be reconnected.")
    sess = KotakSession.from_handle(handle_or_session)
    # Prefer a newer cached session for the same account (e.g. after a mid-day re-login).
    cached = cached_session(sess.account_id)
    if cached and cached.created_at >= sess.created_at:
        return cached
    return sess


async def _send_throttled(method: str, url: str, **kw) -> Any:
    """`_send` with back-off on HTTP 429 (a throttled request was never accepted, so a
    retry — even of an order placement — cannot duplicate anything)."""
    for attempt in range(3):
        try:
            return await _send(method, url, **kw)
        except KotakError as exc:
            if exc.http_status != 429 or attempt == 2:
                raise
            await asyncio.sleep(0.6 * (attempt + 1))


async def _session_call(handle, method: str, path: str, *, jdata: dict | None = None,
                        params: dict | None = None, what: str, retry_on_invalid: bool = True) -> Any:
    sess = _session_from(handle)
    try:
        return await _send_throttled(method, f"{sess.base_url}{path}", headers=_session_headers(sess),
                                     params=params, jdata=jdata, what=what)
    except KotakError as exc:
        if not (retry_on_invalid and exc.session_invalid):
            raise
        log.warning("%s: Kotak session invalid (%s) — logging in again.", what, exc)
        fresh = await ensure_session(sess.account_id, stale=sess)
        return await _send_throttled(method, f"{fresh.base_url}{path}", headers=_session_headers(fresh),
                                     params=params, jdata=jdata, what=what)


async def _data_call(handle, path: str, *, params: dict | None = None, what: str) -> Any:
    sess = _session_from(handle)
    return await _send_throttled("GET", f"{sess.base_url}{path}", headers=_data_headers(sess.access_token),
                                 params=params, what=what)


# ── Orders ────────────────────────────────────────────────────────────────────

def _fmt_price(p: float | int | None) -> str:
    if not p:
        return "0"
    return f"{float(p):.2f}"


async def place_order(handle, *, segment: str, trading_symbol: str, side: str, quantity: int,
                      order_type: str, price: float = 0.0, trigger_price: float = 0.0,
                      product: str = "NRML", validity: str = "DAY", tag: str = "") -> str:
    """Place one order and return Kotak's order number (nOrdNo).

    side: "BUY"/"SELL" (or "B"/"S"). order_type: "L" | "MKT" | "SL" | "SL-M".
    """
    tt = "B" if str(side).upper().startswith("B") else "S"
    pt = str(order_type).upper()
    if pt in ("L", "SL") and (not price or price <= 0):
        # Kotak/exchange may substitute a default price for 0 on a limit order — never send it.
        raise KotakError(f"Refusing {pt} order with price {price!r} — a limit price is required.")
    if pt in ("SL", "SL-M") and (not trigger_price or trigger_price <= 0):
        raise KotakError("Refusing stop order without a trigger price.")
    if int(quantity) <= 0:
        raise KotakError(f"Refusing order with quantity {quantity!r}.")
    rt = "DAY" if segment == "mcx_fo" else (validity or "DAY")   # MCX accepts DAY only
    body = {
        "am": "NO",
        "dq": "0",
        "es": segment,
        "mp": "0",
        "pc": product,
        "pf": "N",
        "pr": _fmt_price(price) if pt in ("L", "SL") else "0",
        "pt": pt,
        "qt": str(int(quantity)),
        "rt": rt,
        "tp": _fmt_price(trigger_price) if pt in ("SL", "SL-M") else "0",
        "ts": trading_symbol,
        "tt": tt,
        "os": ORDER_SOURCE,
    }
    if tag:
        body["ig"] = tag[:20]
    resp = await _session_call(handle, "POST", PLACE_PATH, jdata=body, what="Kotak place order")
    order_no = str((resp or {}).get("nOrdNo") or "").strip()
    if not order_no:
        raise KotakError(f"Kotak place order returned no order number: {_brief(resp)}", payload=resp)
    log.info("Kotak order %s: %s %s %s qty=%s pr=%s tp=%s tag=%s", order_no, tt, pt, trading_symbol,
             quantity, body["pr"], body["tp"], tag)
    return order_no


async def modify_order(handle, *, order_no: str, segment: str, trading_symbol: str, token: str,
                       side: str, quantity: int, order_type: str, price: float = 0.0,
                       trigger_price: float = 0.0, product: str = "NRML",
                       validity: str = "DAY") -> str:
    pt = str(order_type).upper()
    if pt in ("L", "SL") and (not price or price <= 0):
        raise KotakError(f"Refusing to modify to {pt} with price {price!r}.")
    body = {
        "no": str(order_no),
        "tk": str(token),
        "es": segment,
        "ts": trading_symbol,
        "tt": "B" if str(side).upper().startswith("B") else "S",
        "pc": product,
        "pt": pt,
        "pr": _fmt_price(price) if pt in ("L", "SL") else "0",
        "tp": _fmt_price(trigger_price) if pt in ("SL", "SL-M") else "0",
        "qt": str(int(quantity)),
        "vd": "DAY" if segment == "mcx_fo" else (validity or "DAY"),
        "dq": "0",
        "mp": "0",
        "am": "NO",
        "dd": "NA",
        "os": ORDER_SOURCE,
    }
    resp = await _session_call(handle, "POST", MODIFY_PATH, jdata=body, what="Kotak modify order")
    return str((resp or {}).get("nOrdNo") or order_no)


async def cancel_order(handle, order_no: str) -> dict:
    """Cancel an order. An already-complete order raises KotakError(code=1021)."""
    return await _session_call(handle, "POST", CANCEL_PATH,
                               jdata={"on": str(order_no), "am": "NO"}, what="Kotak cancel order")


async def order_history(handle, order_no: str) -> list[dict]:
    resp = await _session_call(handle, "POST", HISTORY_PATH, jdata={"nOrdNo": str(order_no)},
                               what="Kotak order history")
    rows = resp.get("data") if isinstance(resp, dict) else resp
    if isinstance(rows, dict):
        rows = rows.get("data") or [rows]
    return [r for r in (rows or []) if isinstance(r, dict)]


def _num(v: Any) -> float:
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _row_time(r: dict) -> float:
    for k in ("updRecvTm", "hsUpTm", "boeSec"):
        v = _num(r.get(k))
        if v:
            return v
    return 0.0


def normalise_order_state(rows: list[dict]) -> dict:
    """{terminal, status, filled_qty, avg_price, message, order_type, price, trigger}.

    status ∈ complete | cancelled | rejected | open | unknown.
    """
    if not rows:
        return {"terminal": False, "status": "unknown", "filled_qty": 0, "avg_price": 0.0,
                "message": "no order history", "order_type": "", "price": 0.0, "trigger": 0.0}
    # History is newest-first in Kotak's samples; sort defensively when timestamps exist.
    ordered = sorted(rows, key=_row_time, reverse=True) if any(_row_time(r) for r in rows) else list(rows)
    statuses = [str(r.get("ordSt") or r.get("stat") or "").strip().lower() for r in ordered]

    status = "open"
    if any(s in TERMINAL_COMPLETE for s in statuses):
        status = "complete"
    elif any(s in TERMINAL_REJECTED for s in statuses):
        status = "rejected"
    elif any(s in TERMINAL_CANCELLED for s in statuses):
        status = "cancelled"
    elif not any(statuses):
        status = "unknown"

    filled = int(max((_num(r.get("fldQty")) for r in ordered), default=0))
    avg = 0.0
    for r in ordered:
        a = _num(r.get("avgPrc"))
        if a > 0:
            avg = a
            break
    latest = ordered[0]
    msg = str(latest.get("rejRsn") or "")
    if msg in ("--", "NA"):
        msg = ""
    if status == "rejected" and not msg:
        for r in ordered:
            m = str(r.get("rejRsn") or "")
            if m and m not in ("--", "NA"):
                msg = m
                break
    return {
        "terminal": status in ("complete", "cancelled", "rejected"),
        "status": status,
        "filled_qty": filled,
        "avg_price": avg,
        "message": msg,
        "raw_status": statuses[0] if statuses else "",
        "order_type": str(latest.get("prcTp") or "").upper(),
        "price": _num(latest.get("prc")),
        "trigger": _num(latest.get("trgPrc")),
    }


async def order_state(handle, order_no: str) -> dict:
    return normalise_order_state(await order_history(handle, order_no))


async def order_book(handle) -> list[dict]:
    resp = await _session_call(handle, "GET", ORDER_BOOK_PATH, what="Kotak order book")
    rows = resp.get("data") if isinstance(resp, dict) else resp
    return [r for r in (rows or []) if isinstance(r, dict)]


_OPEN_STATES = {"open", "open pending", "trigger pending", "validation pending", "put order req received",
                "modified", "modify pending", "modify validation pending", "after market order req received"}


async def cancel_open_orders(handle, instrument_key: str, side: str = "B") -> list[str]:
    """Cancel every still-open order on this instrument and side (e.g. a stop-loss whose
    placement timed out and so was never recorded). Returns the cancelled order numbers."""
    seg, tok, sym = parse_instrument_key(instrument_key)
    cancelled = []
    for r in await order_book(handle):
        if str(r.get("trdSym") or "").upper() != sym.upper() and str(r.get("tok") or "") != str(tok):
            continue
        if str(r.get("trnsTp") or "").upper()[:1] != side.upper()[:1]:
            continue
        if str(r.get("ordSt") or "").strip().lower() not in _OPEN_STATES:
            continue
        try:
            await cancel_order(handle, str(r.get("nOrdNo")))
            cancelled.append(str(r.get("nOrdNo")))
        except KotakError as exc:
            log.warning("Could not cancel stray Kotak order %s: %s", r.get("nOrdNo"), exc)
    return cancelled


# ── Positions ─────────────────────────────────────────────────────────────────

async def positions(handle) -> list[dict]:
    try:
        resp = await _session_call(handle, "GET", POSITIONS_PATH, what="Kotak positions")
    except KotakError as exc:
        if exc.http_status not in (404, 405):
            raise
        resp = await _session_call(handle, "GET", POSITIONS_V2_PATH, what="Kotak positions v2")
    rows = resp.get("data") if isinstance(resp, dict) else resp
    return [r for r in (rows or []) if isinstance(r, dict)]


def summarise_position_rows(rows: list[dict], segment: str, token: str, trading_symbol: str) -> dict:
    """Net position for one instrument across product rows.

    Returns {net_qty, buy_price, sell_price, realised, found}. Kotak has no net-qty field:
    net = (cfBuy + flBuy) − (cfSell + flSell); averages divide amounts by qty × NF, where
    NF = multiplier × genNum/genDen × prcNum/prcDen (same as the official SDK).
    """
    match = []
    for r in rows:
        if str(r.get("exSeg") or "").lower() != segment.lower():
            continue
        tok = str(r.get("tok") or "").strip()
        sym = str(r.get("trdSym") or "").strip()
        if (tok and tok == str(token)) or (sym and sym.upper() == trading_symbol.upper()):
            match.append(r)
    if not match:
        return {"net_qty": 0, "buy_price": 0.0, "sell_price": 0.0, "realised": None, "found": False}

    buy_q = sell_q = buy_amt = sell_amt = 0.0
    nf = 1.0
    for r in match:
        buy_q += _num(r.get("flBuyQty")) + _num(r.get("cfBuyQty"))
        sell_q += _num(r.get("flSellQty")) + _num(r.get("cfSellQty"))
        buy_amt += _num(r.get("buyAmt")) + _num(r.get("cfBuyAmt"))
        sell_amt += _num(r.get("sellAmt")) + _num(r.get("cfSellAmt"))
        mult = _num(r.get("multiplier")) or 1.0
        gn, gd = _num(r.get("genNum")) or 1.0, _num(r.get("genDen")) or 1.0
        pn, pd = _num(r.get("prcNum")) or 1.0, _num(r.get("prcDen")) or 1.0
        nf = (mult * (gn / gd) * (pn / pd)) or 1.0
    net = int(round(buy_q - sell_q))
    buy_avg = buy_amt / (buy_q * nf) if buy_q else 0.0
    sell_avg = sell_amt / (sell_q * nf) if sell_q else 0.0
    realised = None
    if net == 0 and buy_q and sell_q:
        realised = round(sell_amt - buy_amt, 2)
    return {"net_qty": net, "buy_price": round(buy_avg, 4), "sell_price": round(sell_avg, 4),
            "realised": realised, "found": True}


async def net_position(handle, instrument_key: str) -> dict:
    seg, tok, sym = parse_instrument_key(instrument_key)
    return summarise_position_rows(await positions(handle), seg, tok, sym)


# ── Market data (access-token only — no session needed) ───────────────────────

async def quotes_ltp(handle, neo_symbols: list[str]) -> dict[str, float]:
    """{"seg|token": ltp} for up to 50 instruments."""
    if not neo_symbols:
        return {}
    syms = ",".join(neo_symbols[:50])
    path = QUOTES_PATH.format(symbols=urllib.parse.quote(syms, safe="|,"), kind="ltp")
    resp = await _data_call(handle, path, what="Kotak quotes")
    rows = resp if isinstance(resp, list) else (resp.get("data") if isinstance(resp, dict) else None) or []
    out: dict[str, float] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        key = f"{r.get('exchange') or ''}|{r.get('exchange_token') or ''}"
        ltp = _num(r.get("ltp") or r.get("last_traded_price"))
        if ltp > 0:
            out[key] = ltp
    return out


async def get_ltp(handle, instrument_key: str) -> float:
    """LTP for a Kotak instrument key; 0.0 if unavailable (never raises)."""
    try:
        seg, tok, _ = parse_instrument_key(instrument_key)
        data = await quotes_ltp(handle, [f"{seg}|{tok}"])
        return float(data.get(f"{seg}|{tok}") or next(iter(data.values()), 0.0))
    except Exception as exc:  # noqa: BLE001
        log.debug("Kotak LTP failed for %s: %s", instrument_key, exc)
        return 0.0


async def expiries(handle, underlying: str, exchange: str, instrument_type: str = "option") -> list[str]:
    resp = await _data_call(handle, EXPIRIES_PATH, params={
        "underlying": underlying, "exchange": exchange, "instrument_type": instrument_type,
    }, what="Kotak expiries")
    data = resp.get("data", resp) if isinstance(resp, dict) else {}
    return sorted(str(e) for e in (data.get("expiries") or []))


async def option_chain(handle, *, exchange: str, underlying: str, expiry: str | None = None,
                       instrument_type: str = "option", count: int = 40) -> dict:
    params: dict[str, Any] = {"exchange": exchange, "underlying": underlying,
                              "instrument_type": instrument_type}
    if expiry:
        params["expiry"] = expiry
    if instrument_type == "option":
        params["count"] = count
    resp = await _data_call(handle, OPTION_CHAIN_PATH, params=params, what="Kotak option chain")
    data = resp.get("data") if isinstance(resp, dict) else None
    if not isinstance(data, dict):
        raise KotakError(f"Kotak option chain returned no data: {_brief(resp)}", payload=resp)
    return data


# ── Account utilities ─────────────────────────────────────────────────────────

async def client_ip(handle) -> str:
    """The public IP Kotak sees this server calling from (what the client must whitelist)."""
    sess = _session_from(handle)
    try:
        resp = await _send("GET", f"{_login_base()}{CLIENT_IP_PATH}",
                           headers={"Authorization": sess.access_token, "Sid": sess.sid,
                                    "Auth": sess.auth, "accept": "application/json"},
                           what="Kotak client IP")
    except KotakError as exc:
        log.info("Kotak client-ip lookup failed: %s", exc)
        return ""
    if isinstance(resp, dict):
        d = resp.get("data") if isinstance(resp.get("data"), dict) else resp
        for k in ("clientIp", "client_ip", "ip", "ipAddress"):
            if d.get(k):
                return str(d[k])
    return ""


async def limits(handle) -> dict:
    return await _session_call(handle, "POST", LIMITS_PATH,
                               jdata={"seg": "ALL", "exch": "ALL", "prod": "ALL"}, what="Kotak limits")


# ── Option-chain helpers used by the execution engine ─────────────────────────

def _chain_rows(chain: dict, side: str) -> list[dict]:
    rows = chain.get(side) or chain.get(side.upper()) or []
    return [r for r in rows if isinstance(r, dict)]


def chain_lot_info(chain: dict) -> tuple[int, float]:
    """(market lot, price multiplier) from an option-chain `common_data` block."""
    common = chain.get("common_data") or {}
    lot = int(_num(common.get("mktLot")) or 0)
    mult = _num(common.get("multiplier")) or 1.0
    return lot, mult


def chain_strikes(chain: dict) -> dict[float, dict]:
    """{strike: {"CE": {...}, "PE": {...}}} where each leg is {key, token, symbol, ltp, segment}."""
    out: dict[float, dict] = {}
    for side in ("call", "put"):
        for row in _chain_rows(chain, side):
            inst = row.get("instrument") or row.get("inst") or {}
            neo = str(inst.get("neoSymbol") or "")
            sym = str(inst.get("symbol") or "")
            if "|" not in neo or not sym:
                continue
            seg, tok = neo.split("|", 1)
            strike = _num(inst.get("strikePrice"))
            opt = str(inst.get("optionType") or ("CE" if side == "call" else "PE")).upper()
            quote = row.get("quote") or {}
            out.setdefault(strike, {})[opt] = {
                "key": make_instrument_key(seg, tok, sym),
                "segment": seg,
                "token": tok,
                "symbol": sym,
                "ltp": _num(quote.get("ltp")),
            }
    return out


async def option_legs(handle, *, exchange: str, underlying: str, expiry: str, strike: float,
                      count: int = 40) -> dict:
    """Kotak instrument keys + LTPs for the CE and PE at one strike/expiry.

    Returns {"CE": leg, "PE": leg, "lot": int, "multiplier": float}. Raises KotakError if the
    strike is not in Kotak's chain.
    """
    chain = await option_chain(handle, exchange=exchange, underlying=underlying, expiry=expiry,
                               count=count)
    strikes = chain_strikes(chain)
    row = strikes.get(float(strike))
    if not row or "CE" not in row or "PE" not in row:
        sample = sorted(strikes)[:3] + ["…"] + sorted(strikes)[-3:] if strikes else []
        raise KotakError(f"Strike {strike} ({expiry}) not in Kotak {underlying} chain; have {sample}")
    lot, mult = chain_lot_info(chain)
    return {"CE": row["CE"], "PE": row["PE"], "lot": lot, "multiplier": mult}


# ── Scheduled daily login ─────────────────────────────────────────────────────

async def daily_login_all() -> dict:
    """Log every connected Kotak account in for the day (scheduler, Mon–Fri morning).

    A failure flags the account (needsReauth + lastLoginError + an activity-log warning)
    but does not disable the client's strategies; pre-entry checks retry the login.
    """
    from services import firebase_service
    from utils import logger as activity

    accounts = [a for a in firebase_service.list_broker_accounts()
                if a.get("broker") == "kotak" and a.get("isConnected")]
    ok = failed = 0
    for acc in accounts:
        try:
            sess = await ensure_session(acc["id"], force=True)
            ok += 1
            await _check_static_ip(sess)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            msg = str(exc)
            log.error("Kotak daily login failed for %s: %s", acc["id"], msg)
            mark_login_failed(acc["id"], msg)
            activity.log_activity(
                type="token_invalid",
                message=f"Kotak daily login failed — {msg}",
                severity="error",
                userId=acc.get("userId"),
                metadata={"broker": "kotak", "accountId": acc["id"]},
            )
        await asyncio.sleep(1.0)   # stay well inside Kotak's login rate limits
    log.info("Kotak daily login: %d ok, %d failed.", ok, failed)
    return {"ok": ok, "failed": failed}


async def _check_static_ip(sess: KotakSession) -> str:
    """Record the IP Kotak sees; warn when it differs from the configured static IP."""
    ip = await client_ip(sess)
    expected = str(getattr(settings, "kotak_expected_static_ip", "") or "").strip()
    try:
        from services import firebase_service
        update = {"kotakSeenIp": ip or None}
        if expected and ip and ip != expected:
            update["lastLoginError"] = (f"Kotak sees this server as {ip}, but the whitelisted static IP "
                                        f"is configured as {expected}. Orders will be rejected.")
        firebase_service.update_broker_account(sess.account_id, update)
    except Exception as exc:  # noqa: BLE001
        log.debug("Could not record Kotak client IP: %s", exc)
    return ip
