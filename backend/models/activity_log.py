"""Activity log entry — mirrors Firestore `activityLogs` collection."""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ActivityType = Literal[
    "order_placed", "order_failed", "order_modified",
    "strategy_triggered", "strategy_paused", "strategy_stopped",
    "broker_connected", "broker_disconnected", "broker_token_refreshed",
    "user_deployed", "user_paused", "admin_action",
]

Severity = Literal["info", "warning", "error", "success"]


class ActivityLog(BaseModel):
    id: Optional[str] = None
    type: ActivityType
    strategyId: Optional[str] = None
    strategyName: Optional[str] = None
    userId: Optional[str] = None
    userName: Optional[str] = None
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    severity: Severity = "info"
    timestamp: Optional[datetime] = None
