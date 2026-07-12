"""Encrypted store for per-user broker API keys/secrets (BYOK).

Credentials are encrypted with Fernet (AES-128-CBC + HMAC) using
TOKEN_ENCRYPTION_KEY, then persisted to Firestore at `brokerCredentials/{id}`
as ciphertext. Firestore holds only the encrypted blob — the browser can never
read this collection (firestore.rules denies all client access), and even a
Firestore admin sees only ciphertext without the backend's key.

Payload shape is broker-specific, e.g.
  Upstox : {"apiKey": "...", "apiSecret": "..."}
  Jainam : {"interactiveApiKey": "...", "interactiveApiSecret": "...",
            "marketDataApiKey": "...", "marketDataApiSecret": "..."}
"""
import json
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from config import settings
from services import firebase_service

logger = logging.getLogger("tradzo.credstore")

# Legacy on-disk store (pre-Firestore). Read-only fallback so accounts connected
# before this change keep working; values are migrated up to Firestore on read.
_LEGACY_PATH = os.path.join(os.path.dirname(__file__), "..", "credentials_store.enc")
_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = settings.token_encryption_key
        if not key:
            raise RuntimeError(
                "TOKEN_ENCRYPTION_KEY is not set. Generate one with:\n"
                '  python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )
        _fernet = Fernet(key.encode())
    return _fernet


def save_credentials(account_id: str, creds: dict) -> None:
    """Encrypt and persist the credential bundle to Firestore."""
    ciphertext = _get_fernet().encrypt(json.dumps(creds).encode()).decode()
    firebase_service.set_broker_credentials(account_id, ciphertext)


def get_credentials(account_id: str) -> Optional[dict]:
    """Return the decrypted credential bundle, or None if absent/undecryptable."""
    ciphertext = firebase_service.get_broker_credentials(account_id)
    if ciphertext:
        try:
            return json.loads(_get_fernet().decrypt(ciphertext.encode()).decode())
        except (InvalidToken, ValueError) as exc:
            logger.error("Stored credentials unreadable (wrong key or corrupt): %s", exc)
            return None

    # Fallback: migrate from the legacy local file if present.
    legacy = _read_legacy(account_id)
    if legacy is not None:
        logger.info("Migrating credentials for %s from legacy file to Firestore.", account_id)
        save_credentials(account_id, legacy)
    return legacy


def delete_credentials(account_id: str) -> None:
    firebase_service.delete_broker_credentials(account_id)


def _read_legacy(account_id: str) -> Optional[dict]:
    if not os.path.exists(_LEGACY_PATH):
        return None
    try:
        with open(_LEGACY_PATH, "rb") as fh:
            raw = fh.read()
        if not raw:
            return None
        data = json.loads(_get_fernet().decrypt(raw).decode())
        return data.get(account_id)
    except (InvalidToken, ValueError) as exc:
        logger.error("Legacy credentials file unreadable: %s", exc)
        return None
