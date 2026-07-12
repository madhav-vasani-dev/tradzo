"""Broker account metadata mirrored to Firestore `brokerAccounts` collection.

IMPORTANT: access/refresh tokens are NEVER stored here. They live only in the
encrypted token store (utils/token_store.py). Firestore holds status + expiry.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

BrokerName = Literal["upstox", "jainam"]


class BrokerAccount(BaseModel):
    id: Optional[str] = None
    userId: str
    broker: BrokerName
    # Broker's own account/client id (field name mirrors the frontend model).
    brokerAccountId: str
    displayName: str
    isConnected: bool = True
    # True when the stored token has expired and the user must re-authenticate.
    needsReauth: bool = False
    expiresAt: Optional[datetime] = None
    lastRefreshedAt: Optional[datetime] = None
    connectedAt: Optional[datetime] = None
