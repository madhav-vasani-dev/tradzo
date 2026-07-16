"""Encrypted at-rest store for broker access/refresh tokens.

Design decision (per implementation plan): broker credentials live ONLY in the
Python backend, never in Firestore or the Angular app. Tokens are encrypted with
Fernet (AES-128-CBC + HMAC) using TOKEN_ENCRYPTION_KEY and persisted to Firestore.
"""
import json
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from config import settings
from services import firebase_service

logger = logging.getLogger("tradzo.tokenstore")

_LEGACY_PATH = os.path.join(os.path.dirname(__file__), "..", "token_store.enc")
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


def save_tokens(account_id: str, tokens: dict) -> None:
    """Encrypt and persist the token bundle to Firestore."""
    ciphertext = _get_fernet().encrypt(json.dumps(tokens).encode()).decode()
    firebase_service.set_broker_token(account_id, ciphertext)


def get_tokens(account_id: str) -> Optional[dict]:
    """Return the decrypted token bundle, or None if absent/undecryptable."""
    ciphertext = firebase_service.get_broker_token(account_id)
    if ciphertext:
        try:
            return json.loads(_get_fernet().decrypt(ciphertext.encode()).decode())
        except (InvalidToken, ValueError) as exc:
            logger.error("Stored tokens unreadable (wrong key or corrupt): %s", exc)
            return None

    # Fallback: migrate from the legacy local file if present.
    legacy = _read_legacy(account_id)
    if legacy is not None:
        logger.info("Migrating tokens for %s from legacy file to Firestore.", account_id)
        save_tokens(account_id, legacy)
    return legacy


def delete_tokens(account_id: str) -> None:
    firebase_service.delete_broker_token(account_id)


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
        logger.error("Legacy tokens file unreadable: %s", exc)
        return None
