"""Activity logging — writes structured events to Firestore `activityLogs`.

Best-effort: a logging failure must never break the calling flow (order
placement, OAuth, etc.), so Firestore errors are swallowed and logged locally.
"""
import logging
from typing import Any, Optional

from services import firebase_service

logger = logging.getLogger("tradzo.activity")


def log_activity(
    *,
    type: str,
    message: str,
    severity: str = "info",
    date: Optional[str] = None,
    strategyId: Optional[str] = None,
    strategyName: Optional[str] = None,
    userId: Optional[str] = None,
    userName: Optional[str] = None,
    positionId: Optional[str] = None,
    isPaper: bool = False,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    payload = {
        "type": type,
        "message": message,
        "severity": severity,
        "date": date,
        "strategyId": strategyId,
        "strategyName": strategyName,
        "userId": userId,
        "userName": userName,
        "positionId": positionId,
        "isPaper": isPaper,
        "metadata": metadata or {},
        "timestamp": firebase_service.server_timestamp(),
    }
    try:
        firebase_service.add_activity_log(payload)
    except Exception as exc:  # noqa: BLE001 — logging must not raise
        logger.warning("Could not write activity log (%s): %s", type, exc)
