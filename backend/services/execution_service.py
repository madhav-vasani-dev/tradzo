"""Morning execution orchestrator + readiness snapshot.

Responsibilities:
  * compute_readiness()  — build the pre-market status served to the admin panel.
  * execute_morning_strategies() — place orders for every active deployment that
    has a valid broker token; respect admin force-pause; log every outcome.

Order construction is intentionally a stub (`_build_orders_for`) — the concrete
instrument/quantity logic depends on each strategy's definition and is a Phase-2
concern. The orchestration, guarding, and logging around it are real.
"""
import logging
from datetime import datetime
from typing import Any, Optional

import pytz

from services import firebase_service, upstox_service
from utils import logger as activity
from utils import token_store

log = logging.getLogger("tradzo.execution")
IST = pytz.timezone("Asia/Kolkata")

# Cached readiness snapshot for the /execution/readiness endpoint.
_readiness_cache: dict[str, Any] = {
    "computedAt": None,
    "totalUsers": 0,
    "readyUsers": 0,
    "estimatedOrders": 0,
    "users": [],
    "strategies": [],
}


def _token_status(account: Optional[dict]) -> str:
    """Classify a broker account's token as valid / expiring / expired / missing."""
    if not account or not account.get("isConnected"):
        return "missing"
    tokens = token_store.get_tokens(account["id"])
    if not tokens:
        return "missing"
    expiry_raw = account.get("expiresAt")
    if expiry_raw is None:
        return "valid"
    expiry = _to_dt(expiry_raw)
    now = datetime.now(IST)
    if expiry <= now:
        return "expired"
    if (expiry - now).total_seconds() < 3600:
        return "expiring"
    return "valid"


def _to_dt(value: Any) -> datetime:
    """Coerce a Firestore timestamp / ISO string / datetime to an aware datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo else IST.localize(value)
    if hasattr(value, "timestamp"):  # Firestore DatetimeWithNanoseconds
        return datetime.fromtimestamp(value.timestamp(), IST)
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return datetime.now(IST)


def _accounts_by_id() -> dict[str, dict]:
    return {a["id"]: a for a in firebase_service.list_broker_accounts()}


def compute_readiness() -> dict:
    """Build and cache the readiness snapshot for the morning panel."""
    deployments = firebase_service.list_active_user_strategies()
    accounts = _accounts_by_id()

    user_rows: list[dict] = []
    strategy_counts: dict[str, int] = {}
    ready = 0

    for dep in deployments:
        account = accounts.get(dep.get("brokerAccountId"))
        status = _token_status(account)
        if status == "valid":
            ready += 1
        strategy_counts[dep.get("strategyName", "Unknown")] = (
            strategy_counts.get(dep.get("strategyName", "Unknown"), 0) + 1
        )
        user_rows.append(
            {
                "userId": dep.get("userId"),
                "strategyName": dep.get("strategyName"),
                "broker": dep.get("brokerName"),
                "tokenStatus": status,
                "lastRefreshedAt": (
                    _to_dt(account["lastRefreshedAt"]).isoformat()
                    if account and account.get("lastRefreshedAt")
                    else None
                ),
            }
        )

    snapshot = {
        "computedAt": datetime.now(IST).isoformat(),
        "totalUsers": len(deployments),
        "readyUsers": ready,
        "estimatedOrders": len(deployments),  # 1 order/deployment in Phase 1
        "users": user_rows,
        "strategies": [
            {"strategyName": name, "userCount": count}
            for name, count in sorted(strategy_counts.items())
        ],
    }
    _readiness_cache.update(snapshot)
    log.info("Readiness computed: %s/%s users ready.", ready, len(deployments))
    return snapshot


def get_cached_readiness() -> dict:
    return _readiness_cache


def _build_orders_for(deployment: dict) -> list[dict]:
    """Translate a deployment into concrete broker orders.

    STUB: real instrument selection / sizing comes from the strategy definition
    in Phase 2. Returns [] so execution is a safe no-op until implemented.
    """
    return []


async def execute_morning_strategies() -> dict:
    """Place orders for every eligible active deployment. Returns a summary."""
    deployments = firebase_service.list_active_user_strategies()
    accounts = _accounts_by_id()
    placed = failed = skipped = 0

    for dep in deployments:
        if dep.get("pausedByAdmin"):
            skipped += 1
            continue

        account = accounts.get(dep.get("brokerAccountId"))
        if _token_status(account) != "valid":
            skipped += 1
            activity.log_activity(
                type="order_failed",
                message=f"Skipped {dep.get('strategyName')}: broker token not valid.",
                severity="warning",
                userId=dep.get("userId"),
                strategyId=dep.get("strategyId"),
                strategyName=dep.get("strategyName"),
            )
            continue

        tokens = token_store.get_tokens(account["id"])
        access_token = (tokens or {}).get("access_token")
        orders = _build_orders_for(dep)

        for order in orders:
            try:
                result = await upstox_service.place_order(access_token, order)
                placed += 1
                activity.log_activity(
                    type="order_placed",
                    message=f"Order placed for {dep.get('strategyName')}.",
                    severity="success",
                    userId=dep.get("userId"),
                    strategyId=dep.get("strategyId"),
                    strategyName=dep.get("strategyName"),
                    metadata={"orderId": result.get("data", {}).get("order_id")},
                )
            except Exception as exc:  # noqa: BLE001
                failed += 1
                activity.log_activity(
                    type="order_failed",
                    message=f"Order failed for {dep.get('strategyName')}: {exc}",
                    severity="error",
                    userId=dep.get("userId"),
                    strategyId=dep.get("strategyId"),
                    strategyName=dep.get("strategyName"),
                    metadata={"errorMessage": str(exc)},
                )

    summary = {"placed": placed, "failed": failed, "skipped": skipped}
    log.info("Morning execution complete: %s", summary)
    return summary


def refresh_broker_tokens() -> dict:
    """Flag broker accounts whose token has expired as needing re-authentication.

    Upstox v2 has no refresh token, so 'refresh' here means: detect lapsed tokens
    and surface them (needsReauth) so the user is prompted to reconnect.
    """
    flagged = 0
    for account in firebase_service.list_broker_accounts():
        if not account.get("isConnected"):
            continue
        if _token_status(account) == "expired":
            firebase_service.update_broker_account(
                account["id"], {"needsReauth": True}
            )
            token_store.delete_tokens(account["id"])
            flagged += 1
            activity.log_activity(
                type="broker_token_refreshed",
                message="Broker token expired — re-authentication required.",
                severity="warning",
                userId=account.get("userId"),
                metadata={"accountId": account["id"]},
            )
    log.info("Token refresh sweep flagged %s account(s).", flagged)
    return {"flagged": flagged}
