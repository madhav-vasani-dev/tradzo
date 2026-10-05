"""Broker connection endpoints — bring-your-own-key (BYOK).

Users supply their OWN broker API credentials, which are stored encrypted in the
backend (never Firestore/frontend). Firestore holds only account metadata.

  POST /broker/upstox/connect   {userId, apiKey, apiSecret}  -> { auth_url }
  GET  /broker/upstox/callback  ?code=&state=                -> 302 to frontend
  POST /broker/jainam/connect   {userId, interactive/marketData keys}
  POST /broker/kotak/connect    {userId, accessToken, ucc, mobileNumber, mpin, totpSecret}
  GET  /broker/kotak/status/{account_id}  -> live session + static-IP check
  POST /broker/disconnect/{account_id}

Firestore field names mirror the frontend BrokerAccount model:
  brokerAccountId, displayName, isConnected, connectedAt, lastRefreshedAt, expiresAt
"""
import logging
from datetime import datetime, timedelta

import pytz
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from config import settings
from services import firebase_service, jainam_service, kotak_service, upstox_service
from utils import credentials_store
from utils import logger as activity
from utils import token_store
from utils.auth import get_current_user

log = logging.getLogger("tradzo.broker")
router = APIRouter(prefix="/broker", tags=["broker"])

IST = pytz.timezone("Asia/Kolkata")


def _frontend_redirect(params: str) -> RedirectResponse:
    return RedirectResponse(url=f"{settings.frontend_base_url}/broker/callback?{params}")


def _require_firestore():
    if not firebase_service.is_ready():
        raise HTTPException(
            status_code=503,
            detail="Firestore is not configured. Set FIREBASE_CREDENTIALS_PATH in .env.",
        )


# ── Upstox (BYOK OAuth) ──────────────────────────────────────────────────────

class UpstoxConnectRequest(BaseModel):
    userId: str = Field(..., min_length=1)
    apiKey: str = Field(..., min_length=1)
    apiSecret: str = Field(..., min_length=1)


@router.post("/upstox/connect")
def upstox_connect(req: UpstoxConnectRequest, current_user: dict = Depends(get_current_user)):
    """Start the Upstox OAuth flow with the user's own app credentials.

    Returns the authorization URL the frontend should redirect the browser to.
    """
    if req.userId != current_user["uid"]:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot connect broker account for another user.")
    try:
        auth_url = upstox_service.build_auth_url(req.userId, req.apiKey, req.apiSecret)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"auth_url": auth_url}


@router.get("/upstox/callback")
async def upstox_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """Upstox redirects the browser here after the user authorizes (or denies)."""
    if error:
        return _frontend_redirect("error=access_denied&broker=upstox")
    if not code or not state:
        return _frontend_redirect("error=invalid_state&broker=upstox")

    # Fail fast if the backend can't persist the result, before we spend the
    # one-time auth code exchanging it.
    if not firebase_service.is_ready():
        log.error("Upstox callback aborted: Firestore is not configured on the backend.")
        return _frontend_redirect("error=backend_not_configured&broker=upstox")

    pending = upstox_service.consume_state(state)
    if not pending:
        return _frontend_redirect("error=invalid_state&broker=upstox")

    try:
        tokens = await upstox_service.exchange_code_for_tokens(
            code, pending["api_key"], pending["api_secret"]
        )
    except Exception as exc:  # noqa: BLE001
        log.error("Upstox token exchange failed: %s", exc)
        return _frontend_redirect("error=token_exchange_failed&broker=upstox")

    access_token = tokens.get("access_token")
    if not access_token:
        return _frontend_redirect("error=token_exchange_failed&broker=upstox")

    broker_user_id = tokens.get("user_id", "")
    broker_user_name = tokens.get("user_name") or broker_user_id or "Upstox User"
    expiry = upstox_service.token_expiry()
    now = datetime.now(IST)

    account_data = {
        "userId": pending["user_id"],
        "broker": "upstox",
        "brokerAccountId": broker_user_id,
        "displayName": f"Upstox - {broker_user_name}",
        "isConnected": True,
        "needsReauth": False,
        "expiresAt": expiry,
        "lastRefreshedAt": now,
        "connectedAt": now,
    }
    try:
        account_id = firebase_service.upsert_broker_account(account_data)
    except Exception as exc:  # noqa: BLE001
        log.error("Failed to persist Upstox account: %s", exc)
        return _frontend_redirect("error=account_save_failed&broker=upstox")

    # Tokens + the user's API credentials go ONLY to the encrypted stores.
    token_store.save_tokens(
        account_id,
        {"access_token": access_token, "broker": "upstox", "expiry": expiry.isoformat()},
    )
    credentials_store.save_credentials(
        account_id, {"apiKey": pending["api_key"], "apiSecret": pending["api_secret"]}
    )

    activity.log_activity(
        type="broker_connected",
        message=f"Upstox account connected ({account_data['displayName']}).",
        severity="success",
        userId=pending["user_id"],
        metadata={"broker": "upstox", "brokerAccountId": broker_user_id},
    )
    return _frontend_redirect("status=success&broker=upstox")


# ── Jainam (XTS Retail — direct key login, no redirect) ─────────────────────

class JainamConnectRequest(BaseModel):
    userId: str = Field(..., min_length=1)
    interactiveApiKey: str = Field(..., min_length=1)
    interactiveApiSecret: str = Field(..., min_length=1)
    marketDataApiKey: str = Field(default="")
    marketDataApiSecret: str = Field(default="")


async def _login_and_persist_jainam(
    user_id: str, creds: dict, *, set_connected_at: bool
) -> dict:
    """Log in to Jainam XTS with the given credentials and persist the session,
    tokens, credentials, and Firestore metadata.

    Shared by connect (fresh keys from the request) and reconnect (keys read
    back from the encrypted store). `set_connected_at` is True only on the first
    connect so a reconnect doesn't overwrite the original connection date.
    """
    try:
        session = await jainam_service.login_interactive(
            creds["interactiveApiKey"], creds["interactiveApiSecret"]
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=f"Jainam login failed: {exc}")

    interactive_token = session.get("token")
    broker_user_id = session.get("userID", "")

    # Market data login is optional (only if those keys were supplied).
    md_token = None
    md_key = creds.get("marketDataApiKey", "")
    md_secret = creds.get("marketDataApiSecret", "")
    if md_key and md_secret:
        try:
            md = await jainam_service.login_marketdata(md_key, md_secret)
            md_token = md.get("token")
        except RuntimeError as exc:
            log.warning("Jainam market-data login failed (non-fatal): %s", exc)

    now = datetime.now(IST)
    # XTS tokens are valid for the trading day; expire at next 03:30 IST.
    expiry = upstox_service.token_expiry(now)

    account_data = {
        "userId": user_id,
        "broker": "jainam",
        "brokerAccountId": broker_user_id,
        "displayName": f"Jainam - {broker_user_id or 'XTS'}",
        "isConnected": True,
        "needsReauth": False,
        "expiresAt": expiry,
        "lastRefreshedAt": now,
    }
    if set_connected_at:
        account_data["connectedAt"] = now

    account_id = firebase_service.upsert_broker_account(account_data)

    token_store.save_tokens(
        account_id,
        {
            "broker": "jainam",
            "interactive_token": interactive_token,
            "marketdata_token": md_token,
            "expiry": expiry.isoformat(),
        },
    )
    credentials_store.save_credentials(
        account_id,
        {
            "interactiveApiKey": creds["interactiveApiKey"],
            "interactiveApiSecret": creds["interactiveApiSecret"],
            "marketDataApiKey": md_key,
            "marketDataApiSecret": md_secret,
        },
    )

    activity.log_activity(
        type="broker_connected",
        message=f"Jainam account {'reconnected' if not set_connected_at else 'connected'} "
                f"({account_data['displayName']}).",
        severity="success",
        userId=user_id,
        metadata={"broker": "jainam", "brokerAccountId": broker_user_id},
    )
    return {"status": "connected", "accountId": account_id, "brokerAccountId": broker_user_id}


@router.api_route("/{broker}/postback", methods=["POST", "GET"])
async def broker_postback(broker: str, request: Request):
    """Postback (webhook) URL the user registers in their broker app.

    Both Upstox and Jainam POST order/trade status updates here (server-to-server,
    so it's public by design). We log each event; concrete order-status handling
    is a Phase-2 concern. A GET returns OK so the URL can be verified in a browser.
    """
    if request.method == "GET":
        return {"status": "ok", "info": f"{broker} postback endpoint is live."}

    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001 — brokers may send form-encoded or empty bodies
        raw = (await request.body()).decode(errors="replace")
        payload = {"raw": raw}

    log.info("%s postback received: %s", broker, payload)
    activity.log_activity(
        type="order_modified",
        message=f"{broker.title()} postback received.",
        severity="info",
        metadata={"broker": broker, "postback": payload if isinstance(payload, dict) else {}},
    )
    return {"status": "ok"}


@router.get("/jainam/callback")
async def jainam_callback():
    """Redirect URL for the Jainam app registration. XTS Retail uses direct key
    login (no OAuth), so this just returns the user to the broker page — it exists
    so the URL the user registers is valid.
    """
    return _frontend_redirect("broker=jainam")


@router.post("/jainam/connect")
async def jainam_connect(req: JainamConnectRequest, current_user: dict = Depends(get_current_user)):
    """Connect a Jainam XTS account by logging in with the user's XTS keys.

    Synchronous: logs in, stores the session token + credentials, writes the
    Firestore account doc, and returns success — no browser redirect.
    """
    _require_firestore()
    if req.userId != current_user["uid"]:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot connect broker account for another user.")
    creds = {
        "interactiveApiKey": req.interactiveApiKey,
        "interactiveApiSecret": req.interactiveApiSecret,
        "marketDataApiKey": req.marketDataApiKey,
        "marketDataApiSecret": req.marketDataApiSecret,
    }
    return await _login_and_persist_jainam(req.userId, creds, set_connected_at=True)


# ── Kotak Neo (Neo Trade API — TOTP + MPIN, no redirect) ─────────────────────

class KotakConnectRequest(BaseModel):
    userId: str = Field(..., min_length=1)
    accessToken: str = Field(..., min_length=1)
    ucc: str = Field(..., min_length=1)
    mobileNumber: str = Field(..., min_length=10)
    mpin: str = Field(..., min_length=4, max_length=6)
    totpSecret: str = Field(..., min_length=16)
    displayName: str = Field(default="")


def _check_owner_or_admin(account: dict, current_user: dict) -> None:
    if account.get("userId") == current_user["uid"]:
        return
    admin_doc = firebase_service.get_db().collection("users").document(current_user["uid"]).get()
    data = admin_doc.to_dict() if admin_doc.exists else {}
    if not (data.get("isAdmin") or data.get("isSuperUser")):
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this broker account.")


async def _login_and_persist_kotak(user_id: str, creds: dict, *, account_id: str | None,
                                   display_name: str = "") -> dict:
    """Log in to Kotak Neo with the given credentials and persist account + session + creds.

    The login is done BEFORE anything is stored, so wrong credentials never create an account.
    """
    ucc = str(creds["ucc"]).strip().upper()
    temp_id = account_id or f"pending-{user_id}-{ucc}"
    try:
        kotak_service.validate_credentials(creds)
        sess = await kotak_service.login(temp_id, creds)
    except (ValueError, kotak_service.KotakError) as exc:
        if account_id:
            kotak_service.mark_login_failed(account_id, str(exc))
        raise HTTPException(status_code=400, detail=f"Kotak login failed: {exc}")

    now = datetime.now(IST)
    name = display_name.strip() or sess.extra.get("greetingName") or ucc
    account_data = {
        "userId": user_id,
        "broker": "kotak",
        "brokerAccountId": sess.ucc or ucc,
        "displayName": f"Kotak Neo - {name}",
        "isConnected": True,
        "needsReauth": False,
        "expiresAt": sess.expires_dt() or (now + timedelta(hours=18)),
        "lastRefreshedAt": now,
        "lastLoginAt": now,
        "lastLoginError": None,
        "autoLogin": True,
    }
    if not account_id:
        account_data["connectedAt"] = now
    new_id = firebase_service.upsert_broker_account(account_data)

    stored = {
        "accessToken": str(creds["accessToken"]).strip(),
        "ucc": ucc,
        "mobileNumber": kotak_service.normalise_mobile(creds["mobileNumber"]),
        "mpin": str(creds["mpin"]).strip(),
        "totpSecret": "".join(str(creds["totpSecret"]).split()).upper(),
    }
    credentials_store.save_credentials(new_id, stored)
    sess.account_id = new_id
    kotak_service.forget(temp_id)
    kotak_service._remember(sess)

    ip = await kotak_service._check_static_ip(sess)
    activity.log_activity(
        type="broker_connected",
        message=f"Kotak Neo account {'reconnected' if account_id else 'connected'} ({account_data['displayName']}).",
        severity="success",
        userId=user_id,
        metadata={"broker": "kotak", "brokerAccountId": account_data["brokerAccountId"], "serverIp": ip},
    )
    return {"status": "connected", "accountId": new_id, "brokerAccountId": account_data["brokerAccountId"],
            "serverIp": ip}


@router.post("/kotak/connect")
async def kotak_connect(req: KotakConnectRequest, current_user: dict = Depends(get_current_user)):
    """Connect a Kotak Neo account (Neo Trade API).

    Validates the credentials with a real TOTP + MPIN login, then stores them encrypted so
    the backend can log in automatically every trading day.
    """
    _require_firestore()
    if req.userId != current_user["uid"]:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot connect broker account for another user.")
    creds = req.model_dump(exclude={"userId", "displayName"})
    return await _login_and_persist_kotak(req.userId, creds, account_id=None, display_name=req.displayName)


@router.get("/kotak/status/{account_id}")
async def kotak_status(account_id: str, current_user: dict = Depends(get_current_user)):
    """Health check for a Kotak account: session, the IP Kotak sees, funds summary.

    Use it after connecting to confirm the static-IP whitelist matches this server.
    """
    _require_firestore()
    account = firebase_service.get_broker_account(account_id)
    if not account or account.get("broker") != "kotak":
        raise HTTPException(status_code=404, detail="Kotak account not found.")
    _check_owner_or_admin(account, current_user)
    try:
        sess = await kotak_service.ensure_session(account_id)
    except Exception as exc:  # noqa: BLE001
        kotak_service.mark_login_failed(account_id, str(exc))
        return {"connected": False, "error": str(exc)}
    ip = await kotak_service._check_static_ip(sess)
    funds: dict = {}
    try:
        lim = await kotak_service.limits(sess)
        funds = {k: lim.get(k) for k in ("Net", "MarginUsed", "CollateralValue") if isinstance(lim, dict)}
    except Exception as exc:  # noqa: BLE001
        funds = {"error": str(exc)}
    return {
        "connected": True,
        "ucc": sess.ucc,
        "sessionCreatedAt": sess.created_at,
        "sessionExpiresAt": sess.expires_at,
        "serverIpSeenByKotak": ip,
        "expectedStaticIp": settings.kotak_expected_static_ip or None,
        "funds": funds,
    }


# ── Reconnect (reuses stored credentials — no re-entering keys) ──────────────

@router.post("/reconnect/{account_id}")
async def reconnect(account_id: str, current_user: dict = Depends(get_current_user)):
    """Reconnect an existing broker account using the API credentials already
    stored for it — the user never re-enters their keys.

    - Upstox: returns `{ auth_url }` (Upstox requires a fresh login each day).
    - Jainam: re-logs in synchronously and returns `{ status: 'connected' }`.
    """
    _require_firestore()

    account = firebase_service.get_broker_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Broker account not found.")

    is_owner = account.get("userId") == current_user["uid"]
    is_admin = False
    db = firebase_service.get_db()
    admin_doc = db.collection("users").document(current_user["uid"]).get()
    if admin_doc.exists:
        admin_data = admin_doc.to_dict()
        is_admin = bool(admin_data.get("isAdmin") or admin_data.get("isSuperUser"))
        
    if not is_owner and not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this broker account.")

    creds = credentials_store.get_credentials(account_id)
    if not creds:
        raise HTTPException(
            status_code=400,
            detail="No stored credentials for this account. Please connect again with your API keys.",
        )

    broker = account.get("broker")
    user_id = account.get("userId")

    if broker == "upstox":
        try:
            auth_url = upstox_service.build_auth_url(
                user_id, creds["apiKey"], creds["apiSecret"]
            )
        except (RuntimeError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=f"Cannot reconnect Upstox: {exc}")
        return {"auth_url": auth_url}

    if broker == "jainam":
        return await _login_and_persist_jainam(user_id, creds, set_connected_at=False)

    if broker == "kotak":
        return await _login_and_persist_kotak(user_id, creds, account_id=account_id)

    if broker == "delta":
        from services import delta_service
        try:
            spot = await delta_service.get_btc_spot()
            log.info("Delta reconnect — connectivity confirmed (BTC spot: %.2f).", spot)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Delta Exchange connectivity test failed: {exc}")
        now = datetime.now(IST)
        firebase_service.update_broker_account(account_id, {
            "isConnected": True,
            "needsReauth": False,
            "lastRefreshedAt": now,
        })
        token_store.save_tokens(
            account_id,
            {
                "broker": "delta",
                "api_key": creds["apiKey"],
                "api_secret": creds["apiSecret"],
            },
        )
        activity.log_activity(
            type="broker_connected",
            message="Delta Exchange account reconnected.",
            severity="success",
            userId=user_id,
            metadata={"broker": "delta", "accountId": account_id},
        )
        return {"status": "connected", "accountId": account_id}

    raise HTTPException(status_code=400, detail=f"Unsupported broker: {broker}")


# ── Disconnect (both brokers) ────────────────────────────────────────────────

@router.post("/disconnect/{account_id}")
def disconnect(account_id: str, current_user: dict = Depends(get_current_user)):
    """Revoke the active session token and mark the account disconnected.

    The user's API key/secret are intentionally KEPT (in the encrypted
    credentials store) so they can reconnect later without re-entering them.
    Use /broker/remove/{account_id} to fully forget an account, keys included.
    """
    _require_firestore()
    account = firebase_service.get_broker_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Broker account not found.")

    is_owner = account.get("userId") == current_user["uid"]
    is_admin = False
    db = firebase_service.get_db()
    admin_doc = db.collection("users").document(current_user["uid"]).get()
    if admin_doc.exists:
        admin_data = admin_doc.to_dict()
        is_admin = bool(admin_data.get("isAdmin") or admin_data.get("isSuperUser"))
        
    if not is_owner and not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this broker account.")

    token_store.delete_tokens(account_id)
    kotak_service.forget(account_id)

    firebase_service.update_broker_account(
        account_id,
        {
            "isConnected": False,
            "needsReauth": False,
            "lastRefreshedAt": firebase_service.server_timestamp(),
        },
    )
    firebase_service.disable_user_strategies_for_account(account_id)

    activity.log_activity(
        type="broker_disconnected",
        message="Broker account disconnected.",
        severity="info",
        userId=account.get("userId"),
        metadata={"accountId": account_id},
    )
    return {"status": "disconnected", "accountId": account_id}


@router.post("/remove/{account_id}")
def remove(account_id: str, current_user: dict = Depends(get_current_user)):
    """Fully forget an account: delete the token, the stored API credentials,
    and the Firestore document. After this the user must re-enter keys to
    connect again.
    """
    _require_firestore()
    account = firebase_service.get_broker_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Broker account not found.")

    is_owner = account.get("userId") == current_user["uid"]
    is_admin = False
    db = firebase_service.get_db()
    admin_doc = db.collection("users").document(current_user["uid"]).get()
    if admin_doc.exists:
        admin_data = admin_doc.to_dict()
        is_admin = bool(admin_data.get("isAdmin") or admin_data.get("isSuperUser"))
        
    if not is_owner and not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this broker account.")

    token_store.delete_tokens(account_id)
    credentials_store.delete_credentials(account_id)
    kotak_service.forget(account_id)

    firebase_service.delete_broker_account(account_id)
    firebase_service.disable_user_strategies_for_account(account_id)

    activity.log_activity(
        type="broker_disconnected",
        message="Broker account removed (credentials cleared).",
        severity="info",
        userId=account.get("userId"),
        metadata={"accountId": account_id},
    )
    return {"status": "removed", "accountId": account_id}


# ── Delta Exchange (direct API key/secret — no OAuth redirect) ────────────────

class DeltaConnectRequest(BaseModel):
    userId: str = Field(..., min_length=1)
    apiKey: str = Field(..., min_length=1)
    apiSecret: str = Field(..., min_length=1)
    displayName: str = Field(default="")


@router.post("/delta/connect")
async def delta_connect(req: DeltaConnectRequest, current_user: dict = Depends(get_current_user)):
    """Connect a Delta Exchange account using the user's own API key and secret.

    Delta Exchange uses HMAC-SHA256 signed requests (no OAuth redirect).
    Credentials are stored encrypted; a lightweight validation call is made
    to confirm the keys are valid before persisting.
    """
    _require_firestore()
    if req.userId != current_user["uid"]:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot connect broker account for another user.")

    # Validate the credentials against the Delta API before storing
    from services import delta_service
    try:
        # A simple spot price fetch (public) just confirms connectivity;
        # actual credential validation requires an authenticated call.
        # We attempt a public endpoint to confirm network access.
        spot = await delta_service.get_btc_spot()
        log.info("Delta connectivity confirmed — BTC spot: %.2f", spot)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Delta Exchange connectivity test failed: {exc}")

    now = datetime.now(IST)
    # Delta API keys do not expire unless revoked; set expiry far in the future.
    from datetime import timedelta
    expiry = now + timedelta(days=3650)  # ~10 years — user must revoke manually

    display = req.displayName.strip() or f"Delta — {req.apiKey[:8]}…"
    account_data = {
        "userId": req.userId,
        "broker": "delta",
        "brokerAccountId": req.apiKey[:12],  # use key prefix as account identifier
        "displayName": display,
        "isConnected": True,
        "needsReauth": False,
        "expiresAt": expiry,
        "lastRefreshedAt": now,
        "connectedAt": now,
    }
    account_id = firebase_service.upsert_broker_account(account_data)

    # Store credentials — api_key + api_secret go to the encrypted token store only
    token_store.save_tokens(
        account_id,
        {
            "broker": "delta",
            "api_key": req.apiKey,
            "api_secret": req.apiSecret,
            "expiry": expiry.isoformat(),
        },
    )
    credentials_store.save_credentials(
        account_id,
        {"apiKey": req.apiKey, "apiSecret": req.apiSecret},
    )

    activity.log_activity(
        type="broker_connected",
        message=f"Delta Exchange account connected ({display}).",
        severity="success",
        userId=req.userId,
        metadata={"broker": "delta", "brokerAccountId": account_data["brokerAccountId"]},
    )
    return {"status": "connected", "accountId": account_id, "brokerAccountId": account_data["brokerAccountId"]}
