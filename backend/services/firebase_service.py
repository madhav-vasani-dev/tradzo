"""Firebase Admin SDK wrapper — the backend's single gateway to Firestore.

Initialises lazily so the API can still boot (and serve /health) even when the
service-account file is missing; any Firestore call then raises a clear error.
"""
import logging
import os
from typing import Any, Optional

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from config import settings

logger = logging.getLogger("tradzo.firebase")

_db: Optional[Any] = None
_init_error: Optional[str] = None


def init_firebase() -> None:
    """Initialise the Admin SDK once at startup. Never raises — logs instead."""
    global _db, _init_error
    if _db is not None or firebase_admin._apps:
        if _db is None and firebase_admin._apps:
            _db = firestore.client()
        return

    cred_path = settings.firebase_credentials_path

    # Support for production deployments (e.g. Fly.io) where the service-account
    # JSON is stored as an environment variable instead of a file.
    firebase_credentials_json = os.environ.get("FIREBASE_CREDENTIALS_JSON", "")
    if firebase_credentials_json:
        import json
        try:
            cred_dict = json.loads(firebase_credentials_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            _db = firestore.client()
            logger.info("Firebase Admin SDK initialised from FIREBASE_CREDENTIALS_JSON env var.")
            return
        except Exception as exc:  # noqa: BLE001
            _init_error = f"Failed to initialise Firebase from FIREBASE_CREDENTIALS_JSON: {exc}"
            logger.error(_init_error)
            return

    if not cred_path or not os.path.exists(cred_path):
        _init_error = (
            f"Firebase credentials not found at '{cred_path}'. "
            "Set FIREBASE_CREDENTIALS_PATH in .env to the service-account JSON, "
            "or set FIREBASE_CREDENTIALS_JSON to the raw JSON string. "
            "The API will run but Firestore operations will fail."
        )
        logger.warning(_init_error)
        return

    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        _db = firestore.client()
        logger.info("Firebase Admin SDK initialised from file.")
    except Exception as exc:  # noqa: BLE001 — startup must never crash here
        _init_error = f"Failed to initialise Firebase Admin SDK: {exc}"
        logger.error(_init_error)



def get_db():
    """Return the Firestore client or raise if it was never initialised."""
    if _db is None:
        raise RuntimeError(_init_error or "Firestore is not initialised.")
    return _db


def is_ready() -> bool:
    return _db is not None


# ── Collection helpers ───────────────────────────────────────────────────────

def upsert_broker_account(data: dict) -> str:
    """Create or update a brokerAccounts doc. Returns the document id.

    One account per (userId, broker) — we key on that pair to avoid duplicates.
    """
    db = get_db()
    col = db.collection("brokerAccounts")
    existing = (
        col.where(filter=FieldFilter("userId", "==", data["userId"]))
        .where(filter=FieldFilter("broker", "==", data["broker"]))
        .limit(1)
        .get()
    )
    if existing:
        doc_ref = existing[0].reference
        doc_ref.set(data, merge=True)
        return doc_ref.id
    doc_ref = col.document()
    data["id"] = doc_ref.id
    doc_ref.set(data)
    return doc_ref.id


def get_broker_account(account_id: str) -> Optional[dict]:
    snap = get_db().collection("brokerAccounts").document(account_id).get()
    return {**snap.to_dict(), "id": snap.id} if snap.exists else None


def update_broker_account(account_id: str, data: dict) -> None:
    get_db().collection("brokerAccounts").document(account_id).set(data, merge=True)


def delete_broker_account(account_id: str) -> None:
    get_db().collection("brokerAccounts").document(account_id).delete()


# ── Encrypted broker credentials (brokerCredentials/{accountId}) ─────────────
# Stores ONLY the Fernet ciphertext. The browser can never read this collection
# (see firestore.rules: allow read, write: if false). Only the backend Admin
# SDK, holding TOKEN_ENCRYPTION_KEY, can decrypt it.

def set_broker_credentials(account_id: str, ciphertext: str) -> None:
    get_db().collection("brokerCredentials").document(account_id).set({"enc": ciphertext})


def get_broker_credentials(account_id: str) -> Optional[str]:
    snap = get_db().collection("brokerCredentials").document(account_id).get()
    return snap.to_dict().get("enc") if snap.exists else None


def delete_broker_credentials(account_id: str) -> None:
    get_db().collection("brokerCredentials").document(account_id).delete()


def list_broker_accounts() -> list[dict]:
    return [
        {**d.to_dict(), "id": d.id}
        for d in get_db().collection("brokerAccounts").stream()
    ]


def list_active_user_strategies() -> list[dict]:
    docs = (
        get_db()
        .collection("userStrategies")
        .where(filter=FieldFilter("status", "==", "active"))
        .stream()
    )
    return [{**d.to_dict(), "id": d.id} for d in docs]


def add_activity_log(data: dict) -> str:
    db = get_db()
    doc_ref = db.collection("activityLogs").document()
    data["id"] = doc_ref.id
    doc_ref.set(data)
    return doc_ref.id


def server_timestamp():
    """Firestore server timestamp sentinel."""
    return firestore.SERVER_TIMESTAMP


# ── Trading mode (settings/tradingMode) ──────────────────────────────────────

def get_trading_mode() -> dict:
    """Return the current trading mode settings document.

    Returns {"paperTrading": bool, ...} or {"paperTrading": True} as default.
    """
    snap = get_db().collection("settings").document("tradingMode").get()
    return snap.to_dict() if snap.exists else {"paperTrading": True}


def set_trading_mode(paper: bool, updated_by: str, updated_by_name: str) -> None:
    """Toggle paper trading mode. Only callable by superuser (enforced in router)."""
    from datetime import datetime
    import pytz
    get_db().collection("settings").document("tradingMode").set({
        "paperTrading": paper,
        "updatedBy": updated_by,
        "updatedByName": updated_by_name,
        "updatedAt": datetime.now(pytz.timezone("Asia/Kolkata")),
    })


def is_paper_trading() -> bool:
    """Quick boolean check — defaults to True (safe) if document is missing."""
    return get_trading_mode().get("paperTrading", True)


# ── Market data source account ────────────────────────────────────────────────

def get_market_data_account() -> Optional[dict]:
    """Return the broker account designated for fetching Nifty spot/options.
    
    Admin marks their account with isMarketDataSource=True.
    If none is explicitly marked, fall back to any connected Upstox account.
    """
    db = get_db()
    docs = (
        db.collection("brokerAccounts")
        .where(filter=FieldFilter("isMarketDataSource", "==", True))
        .where(filter=FieldFilter("isConnected", "==", True))
        .limit(1)
        .get()
    )
    if docs:
        return {**docs[0].to_dict(), "id": docs[0].id}
        
    # Fallback: use any connected upstox account
    docs = (
        db.collection("brokerAccounts")
        .where(filter=FieldFilter("broker", "==", "upstox"))
        .where(filter=FieldFilter("isConnected", "==", True))
        .limit(1)
        .get()
    )
    if docs:
        return {**docs[0].to_dict(), "id": docs[0].id}
        
    return None


# ── userStrategies helpers ────────────────────────────────────────────────────

def list_deployments_by_status(status: str) -> list[dict]:
    """Return all userStrategy deployments with the given status."""
    docs = (
        get_db()
        .collection("userStrategies")
        .where(filter=FieldFilter("status", "==", status))
        .stream()
    )
    return [{**d.to_dict(), "id": d.id} for d in docs]


def list_deployments_by_strategy(strategy_id: str) -> list[dict]:
    """Return all deployments (any status) for a given strategy."""
    docs = (
        get_db()
        .collection("userStrategies")
        .where(filter=FieldFilter("strategyId", "==", strategy_id))
        .stream()
    )
    return [{**d.to_dict(), "id": d.id} for d in docs]


def update_user_strategy_status(doc_id: str, status: str) -> None:
    """Update only the status field of a userStrategy document."""
    from datetime import datetime
    import pytz
    get_db().collection("userStrategies").document(doc_id).update({
        "status": status,
        "statusUpdatedAt": datetime.now(pytz.timezone("Asia/Kolkata")),
    })


def reset_all_strategy_statuses_to_enabled() -> int:
    """Reset all non-paused userStrategies to 'enabled' (called at 08:00 AM).

    Returns the count of documents updated.
    """
    docs = get_db().collection("userStrategies").stream()
    count = 0
    for d in docs:
        data = d.to_dict()
        if not data.get("pausedByAdmin") and data.get("status") != "enabled":
            update_user_strategy_status(d.id, "enabled")
            count += 1
    return count


# ── Strategy document helpers ─────────────────────────────────────────────────

def get_strategy_config(strategy_id: str) -> Optional[dict]:
    """Fetch a strategy configuration document by ID."""
    snap = get_db().collection("strategies").document(strategy_id).get()
    return {**snap.to_dict(), "id": snap.id} if snap.exists else None

