"""Execution + readiness endpoints for the Morning Readiness Panel and global settings."""
import logging
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException

from services import execution_service, firebase_service

log = logging.getLogger("tradzo.execution.router")
router = APIRouter(prefix="/execution", tags=["execution"])


class TradingModeUpdateRequest(BaseModel):
    paperTrading: bool
    userId: str
    userName: str


def _require_firestore():
    if not firebase_service.is_ready():
        raise HTTPException(
            status_code=503,
            detail="Firestore is not configured. Set FIREBASE_CREDENTIALS_PATH in .env.",
        )


@router.get("/readiness")
def readiness(recompute: bool = False):
    """Return the pre-market readiness snapshot.

    Pass ?recompute=true to force a fresh computation on demand.
    """
    _require_firestore()
    if recompute:
        return execution_service.pre_entry_check()
    return execution_service.get_cached_readiness()


@router.post("/pre-entry-check")
def run_pre_entry_check():
    """Trigger the pre-entry check job."""
    _require_firestore()
    return execution_service.pre_entry_check()


@router.post("/trigger-entry")
async def trigger_entry():
    """Manually trigger the 12:00 PM entry job."""
    _require_firestore()
    summary = await execution_service.execute_entry()
    return {"status": "executed_entry", **summary}


@router.post("/trigger-exit")
async def trigger_exit():
    """Manually trigger the 15:29 PM exit (square-off) job."""
    _require_firestore()
    summary = await execution_service.execute_exit()
    return {"status": "executed_exit", **summary}


@router.post("/reset-status")
def reset_status():
    """Manually trigger status reset to enabled."""
    _require_firestore()
    summary = execution_service.reset_daily_statuses()
    return {"status": "reset", **summary}


@router.post("/eod-cleanup")
def run_eod_cleanup():
    """Manually trigger EOD cleanup job."""
    _require_firestore()
    summary = execution_service.eod_cleanup()
    return {"status": "cleaned_up", **summary}


@router.post("/square-off/{user_strategy_id}")
async def square_off_user_strategy(user_strategy_id: str):
    """Manually square off all open positions for a specific deployment and disable it for today."""
    _require_firestore()
    summary = await execution_service.square_off_single_deployment(user_strategy_id)
    return {"status": "success", **summary}


@router.get("/trading-mode")
def get_trading_mode():
    """Get the current global trading mode (paper vs live)."""
    _require_firestore()
    return firebase_service.get_trading_mode()


@router.post("/trading-mode")
def update_trading_mode(req: TradingModeUpdateRequest):
    """Update the current global trading mode."""
    _require_firestore()
    firebase_service.set_trading_mode(
        paper=req.paperTrading,
        updated_by=req.userId,
        updated_by_name=req.userName,
    )
    return {"status": "success", "paperTrading": req.paperTrading}


@router.get("/debug-deployments")
def debug_deployments():
    """Temporary endpoint to dump all enabled deployments for debugging."""
    _require_firestore()
    deployments = firebase_service.list_deployments_by_status("enabled")
    
    debug_info = []
    for d in deployments:
        debug_info.append({
            "id": d.get("id"),
            "status": d.get("status"),
            "pausedByAdmin": d.get("pausedByAdmin"),
            "pausedByAdmin_type": str(type(d.get("pausedByAdmin"))),
            "userId": d.get("userId"),
        })
        
    return {
        "count": len(deployments),
        "deployments": debug_info,
        "paper": firebase_service.is_paper_trading(),
    }
