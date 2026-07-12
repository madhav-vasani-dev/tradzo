"""Execution + readiness endpoints for the Morning Readiness Panel."""
import logging

from fastapi import APIRouter, HTTPException

from services import execution_service, firebase_service

log = logging.getLogger("tradzo.execution.router")
router = APIRouter(prefix="/execution", tags=["execution"])


def _require_firestore():
    if not firebase_service.is_ready():
        raise HTTPException(
            status_code=503,
            detail="Firestore is not configured. Set FIREBASE_CREDENTIALS_PATH in .env.",
        )


@router.get("/readiness")
def readiness(recompute: bool = False):
    """Return the pre-market readiness snapshot.

    The scheduler recomputes this at 8:05 AM IST; pass ?recompute=true to force a
    fresh computation on demand (used by the panel's manual refresh).
    """
    _require_firestore()
    if recompute:
        return execution_service.compute_readiness()
    cached = execution_service.get_cached_readiness()
    if cached.get("computedAt") is None:
        return execution_service.compute_readiness()
    return cached


@router.post("/run-now")
async def run_now():
    """Manually trigger morning execution (superuser 'Run Now'). Auth is enforced
    at the gateway/frontend in Phase 1; wire a token check here before production.
    """
    _require_firestore()
    summary = await execution_service.execute_morning_strategies()
    return {"status": "executed", **summary}
