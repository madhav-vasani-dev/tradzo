"""Position Service — Firestore CRUD for the positions collection.

Each position represents one open/closed option leg for one user deployment.
A straddle creates two positions (CE + PE) per user.

Document path: positions/{positionId}

Key design decisions:
  - `date` field ("YYYY-MM-DD") is set at creation for cheap date-range queries.
  - `status` is one of: "open" | "closing" | "sl_hit" | "target_hit" | "squared_off" | "error"
  - Logs are NEVER deleted. Old positions are permanently archived.

Exit claims
-----------
Closing a position takes several seconds of broker round-trips (cancel the SL, confirm it,
place the buy). Anything that exits a position MUST first win `claim_position_for_exit`,
which atomically flips "open" → "closing" in a Firestore transaction. Without it, two
overlapping requests — a double-clicked square-off, or a manual square-off overlapping the
15:29 job — both see status "open" and both send a BUY, leaving the user net long.

A claim that is never resolved (process killed mid-exit) goes stale after
`stale_after_seconds` so the EOD job can still close the position.
"""
import logging
from datetime import datetime, date
from typing import Optional

import pytz
from google.cloud.firestore_v1 import transactional
from google.cloud.firestore_v1.base_query import FieldFilter

from services.firebase_service import get_db

log = logging.getLogger("tradzo.positions")
IST = pytz.timezone("Asia/Kolkata")

CLOSING_STATUS = "closing"
# A position stuck in "closing" for longer than this is treated as abandoned and reclaimable.
STALE_CLAIM_SECONDS = 120


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


def _as_aware(value) -> Optional[datetime]:
    """Coerce a Firestore timestamp to an aware datetime, or None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else IST.localize(value)
    if hasattr(value, "timestamp"):
        return datetime.fromtimestamp(value.timestamp(), IST)
    return None


def claim_position_for_exit(
    position_id: str,
    stale_after_seconds: int = STALE_CLAIM_SECONDS,
) -> bool:
    """Atomically take ownership of closing a position.

    Returns True only for the caller that flips the position from "open" (or from an
    abandoned "closing") to "closing". Every other concurrent caller gets False and must
    NOT place an exit order. Call `release_position_claim` if the exit is abandoned
    cleanly, so a retry doesn't have to wait out the staleness window.
    """
    db = get_db()
    ref = db.collection("positions").document(position_id)

    @transactional
    def _claim(txn) -> bool:
        snapshot = ref.get(transaction=txn)
        if not snapshot.exists:
            return False
        data = snapshot.to_dict() or {}
        status = data.get("status")

        if status == CLOSING_STATUS:
            started = _as_aware(data.get("closingAt"))
            age = (datetime.now(IST) - started).total_seconds() if started else None
            if age is None or age < stale_after_seconds:
                return False
            log.warning(
                "Position %s left in 'closing' for %.0fs — reclaiming as abandoned.",
                position_id, age,
            )
        elif status != "open":
            return False  # already sl_hit / target_hit / squared_off / error

        txn.update(ref, {"status": CLOSING_STATUS, "closingAt": datetime.now(IST)})
        return True

    try:
        return _claim(db.transaction())
    except Exception as exc:  # noqa: BLE001 — never exit a position we couldn't claim
        log.error("Exit claim failed for position %s: %s", position_id, exc)
        return False


def release_position_claim(position_id: str) -> None:
    """Hand a claimed-but-unclosed position back, so the next attempt can take it."""
    try:
        get_db().collection("positions").document(position_id).update({
            "status": "open",
            "closingAt": None,
        })
    except Exception as exc:  # noqa: BLE001
        log.error("Could not release exit claim on position %s: %s", position_id, exc)


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


def get_exitable_positions_for_date(date_str: str) -> list[dict]:
    """Positions that still need closing — "open", plus any stuck mid-exit in "closing".

    The EOD square-off uses this rather than `get_open_positions_for_date` so a position
    abandoned by a crashed exit still gets closed instead of silently carrying overnight.
    """
    docs = (
        get_db()
        .collection("positions")
        .where(filter=FieldFilter("date", "==", date_str))
        .where(filter=FieldFilter("status", "in", ["open", CLOSING_STATUS]))
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
