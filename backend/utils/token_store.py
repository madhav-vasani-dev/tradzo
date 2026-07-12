"""Encrypted at-rest store for broker access/refresh tokens.

Design decision (per implementation plan): broker credentials live ONLY in the
Python backend, never in Firestore or the Angular app. Tokens are encrypted with
Fernet (AES-128-CBC + HMAC) using TOKEN_ENCRYPTION_KEY and persisted to a local
file. Swap the file backend for a secrets manager (AWS Secrets Manager, GCP
Secret Manager, Vault) in production without changing callers.
"""
import json
import logging
import os
from threading import Lock
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from config import settings

logger = logging.getLogger("tradzo.tokenstore")

_STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "token_store.enc")
_lock = Lock()
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


def _read_all() -> dict:
    if not os.path.exists(_STORE_PATH):
        return {}
    try:
        with open(_STORE_PATH, "rb") as fh:
            raw = fh.read()
        if not raw:
            return {}
        return json.loads(_get_fernet().decrypt(raw).decode())
    except (InvalidToken, ValueError) as exc:
        logger.error("Token store unreadable (wrong key or corrupt): %s", exc)
        return {}


def _write_all(data: dict) -> None:
    encrypted = _get_fernet().encrypt(json.dumps(data).encode())
    with open(_STORE_PATH, "wb") as fh:
        fh.write(encrypted)


def save_tokens(account_id: str, tokens: dict) -> None:
    """Store the token bundle for a broker account id."""
    with _lock:
        data = _read_all()
        data[account_id] = tokens
        _write_all(data)


def get_tokens(account_id: str) -> Optional[dict]:
    with _lock:
        return _read_all().get(account_id)


def delete_tokens(account_id: str) -> None:
    with _lock:
        data = _read_all()
        if account_id in data:
            del data[account_id]
            _write_all(data)
