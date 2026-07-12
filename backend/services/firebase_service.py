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
    if not cred_path or not os.path.exists(cred_path):
        _init_error = (
            f"Firebase credentials not found at '{cred_path}'. "
            "Set FIREBASE_CREDENTIALS_PATH in .env to the service-account JSON. "
            "The API will run but Firestore operations will fail."
        )
        logger.warning(_init_error)
        return

    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        _db = firestore.client()
        logger.info("Firebase Admin SDK initialised.")
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
