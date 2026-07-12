"""Position Service — Firestore CRUD for the positions collection.

Each position represents one open/closed option leg for one user deployment.
A straddle creates two positions (CE + PE) per user.

Document path: positions/{positionId}

Key design decisions:
  - `date` field ("YYYY-MM-DD") is set at creation for cheap date-range queries.
  - `status` is one of: "open" | "sl_hit" | "squared_off" | "error"
  - Logs are NEVER deleted. Old positions are permanently archived.
"""
import logging
from datetime import datetime, date
from typing import Optional

import pytz
from google.cloud.firestore_v1.base_query import FieldFilter

from services.firebase_service import get_db

log = logging.getLogger("tradzo.positions")
IST = pytz.timezone("Asia/Kolkata")


# ── Write helpers ─────────────────────────────────────────────────────────────

def create_position(data: dict) -> str:
    """Create a new position document. Returns the auto-generated document ID.

    `data` should include all fields except `id` and `createdAt` which are
    added here automatically.
    """
    db = get_db()
    ref = db.collection("positions").document()
    now = datetime.now(IST)
    doc = {
        **data,
        "id": ref.id,
        "createdAt": now,
        "date": data.get("date") or now.strftime("%Y-%m-%d"),
    }
    ref.set(doc)
    log.debug("Created position %s (%s %s)", ref.id, data.get("symbol"), data.get("optionType"))
    return ref.id


def update_position(position_id: str, updates: dict) -> None:
    """Merge-update a position document (only the provided keys are changed)."""
    get_db().collection("positions").document(position_id).update(updates)


# ── Read helpers ──────────────────────────────────────────────────────────────

def get_open_positions_for_date(date_str: str) -> list[dict]:
    """Return all positions with status='open' for the given date string."""
    docs = (
        get_db()
        .collection("positions")
        .where(filter=FieldFilter("date", "==", date_str))
        .where(filter=FieldFilter("status", "==", "open"))
        .stream()
    )
    return [{"id": d.id, **d.to_dict()} for d in docs]


def get_positions_for_date(date_str: str) -> list[dict]:
    """Return ALL positions (any status) for the given date string."""
    docs = (
        get_db()
        .collection("positions")
        .where(filter=FieldFilter("date", "==", date_str))
        .stream()
    )
    return [{"id": d.id, **d.to_dict()} for d in docs]


def get_user_positions_for_date(user_id: str, date_str: str) -> list[dict]:
    """Return all positions for a specific user on a given date."""
    docs = (
        get_db()
        .collection("positions")
        .where(filter=FieldFilter("userId", "==", user_id))
        .where(filter=FieldFilter("date", "==", date_str))
        .stream()
    )
    return [{"id": d.id, **d.to_dict()} for d in docs]


def get_open_positions_for_user_strategy(user_strategy_id: str, date_str: str) -> list[dict]:
    """Return open positions for a specific deployment on a given date.

    Used at entry to enforce idempotency — skip if positions already exist.
    """
    docs = (
        get_db()
        .collection("positions")
        .where(filter=FieldFilter("userStrategyId", "==", user_strategy_id))
        .where(filter=FieldFilter("date", "==", date_str))
        .stream()
    )
    return [{"id": d.id, **d.to_dict()} for d in docs]
