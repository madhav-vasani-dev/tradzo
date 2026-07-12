"""Deployment record — mirrors Firestore `userStrategies` collection."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

DeploymentStatus = Literal["active", "paused", "stopped"]


class UserStrategy(BaseModel):
    id: Optional[str] = None
    userId: str
    strategyId: str
    strategyName: str
    brokerAccountId: str
    brokerName: str
    deployedAmount: float
    status: DeploymentStatus = "active"
    deployedAt: Optional[datetime] = None
    lastTradedAt: Optional[datetime] = None
    pausedAt: Optional[datetime] = None
    stoppedAt: Optional[datetime] = None
    pausedByAdmin: bool = False
