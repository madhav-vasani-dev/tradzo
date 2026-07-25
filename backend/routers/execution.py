"""Execution + readiness endpoints for the Morning Readiness Panel and global settings."""
import logging
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException, Depends

from services import execution_service, firebase_service
from utils.auth import get_current_user, get_current_admin

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
def readiness(recompute: bool = False, admin: dict = Depends(get_current_admin)):
    """Return the pre-market readiness snapshot.

    Pass ?recompute=true to force a fresh computation on demand.
    """
    _require_firestore()
    if recompute:
        return execution_service.pre_entry_check()
    return execution_service.get_cached_readiness()


@router.post("/pre-entry-check")
def run_pre_entry_check(admin: dict = Depends(get_current_admin)):
    """Trigger the pre-entry check job."""
    _require_firestore()
    return execution_service.pre_entry_check()


@router.post("/trigger-entry")
async def trigger_entry(admin: dict = Depends(get_current_admin)):
    """Manually trigger the 12:00 PM entry job."""
    _require_firestore()
    summary = await execution_service.execute_entry()
    return {"status": "executed_entry", **summary}


@router.post("/trigger-exit")
async def trigger_exit(admin: dict = Depends(get_current_admin)):
    """Manually trigger the 15:29 PM exit (square-off) job."""
    _require_firestore()
    summary = await execution_service.execute_exit()
    return {"status": "executed_exit", **summary}


@router.post("/reset-status")
def reset_status(admin: dict = Depends(get_current_admin)):
    """Manually trigger status reset to enabled."""
    _require_firestore()
    summary = execution_service.reset_daily_statuses()
    return {"status": "reset", **summary}


@router.post("/eod-cleanup")
def run_eod_cleanup(admin: dict = Depends(get_current_admin)):
    """Manually trigger EOD cleanup job."""
    _require_firestore()
    summary = execution_service.eod_cleanup()
    return {"status": "cleaned_up", **summary}


@router.post("/square-off/{user_strategy_id}")
async def square_off_user_strategy(user_strategy_id: str, current_user: dict = Depends(get_current_user)):
    """Manually square off all open positions for a specific deployment and disable it for today."""
    _require_firestore()
    
    db = firebase_service.get_db()
    strat_doc = db.collection("userStrategies").document(user_strategy_id).get()
    if not strat_doc.exists:
        raise HTTPException(status_code=404, detail="Deployment not found.")
        
    strat_data = strat_doc.to_dict()
    is_owner = strat_data.get("userId") == current_user["uid"]
    
    is_admin = False
    admin_doc = db.collection("users").document(current_user["uid"]).get()
    if admin_doc.exists:
        admin_data = admin_doc.to_dict()
        is_admin = bool(admin_data.get("isAdmin") or admin_data.get("isSuperUser"))
        
    if not is_owner and not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this strategy deployment.")

    summary = await execution_service.square_off_single_deployment(user_strategy_id)
    return {"status": "success", **summary}


@router.get("/trading-mode")
def get_trading_mode(current_user: dict = Depends(get_current_user)):
    """Get the current global trading mode (paper vs live)."""
    _require_firestore()
    return firebase_service.get_trading_mode()


@router.post("/trading-mode")
def update_trading_mode(req: TradingModeUpdateRequest, admin: dict = Depends(get_current_admin)):
    """Update the current global trading mode."""
    _require_firestore()
    firebase_service.set_trading_mode(
        paper=req.paperTrading,
        updated_by=req.userId,
        updated_by_name=req.userName,
    )
    return {"status": "success", "paperTrading": req.paperTrading}


@router.get("/debug-deployments")
def debug_deployments(admin: dict = Depends(get_current_admin)):
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


@router.get("/pnl")
def get_pnl_report(
    userId: str | None = None,
    strategyId: str | None = None,
    startDate: str | None = None,
    endDate: str | None = None,
    current_user: dict = Depends(get_current_user)
):
    """Get the P&L report for a user, strategy, and date range."""
    _require_firestore()
    caller_uid = current_user["uid"]
    target_uid = userId if userId else caller_uid

    if target_uid != caller_uid:
        # Check if caller is admin
        db = firebase_service.get_db()
        admin_doc = db.collection("users").document(caller_uid).get()
        is_admin = False
        if admin_doc.exists:
            admin_data = admin_doc.to_dict()
            is_admin = bool(admin_data.get("isAdmin") or admin_data.get("isSuperUser"))
            
        if not is_admin:
            raise HTTPException(status_code=403, detail="Forbidden: You cannot view another user's P&L report.")

    db = firebase_service.get_db()
    ref = db.collection("positions")
    
    query = ref
    from google.cloud.firestore_v1.base_query import FieldFilter
    query = query.where(filter=FieldFilter("userId", "==", target_uid))
    
    if strategyId:
        query = query.where(filter=FieldFilter("strategyId", "==", strategyId))
    if startDate:
        query = query.where(filter=FieldFilter("date", ">=", startDate))
    if endDate:
        query = query.where(filter=FieldFilter("date", "<=", endDate))
        
    docs = query.stream()
    positions = []
    for d in docs:
        pos = d.to_dict()
        pos["id"] = d.id
        for k, v in list(pos.items()):
            if hasattr(v, "isoformat"):
                pos[k] = v.isoformat()
        positions.append(pos)
        
    positions.sort(key=lambda p: (p.get("date", ""), p.get("symbol", "")))
    return {"positions": positions}


@router.post("/sync-orders")
async def trigger_sync_orders(admin: dict = Depends(get_current_admin)):
    """Manually trigger stop-loss order status syncing."""
    _require_firestore()
    summary = await execution_service.sync_order_statuses()
    return {"status": "success", **summary}


# ── BTC Option Selling (Delta Exchange) ──────────────────────────────────────

@router.post("/trigger-btc-entry")
async def trigger_btc_entry(admin: dict = Depends(get_current_admin)):
    """Manually trigger the 17:01 PM BTC option entry job (Delta Exchange)."""
    _require_firestore()
    summary = await execution_service.execute_btc_entry()
    return {"status": "executed_btc_entry", **summary}


@router.post("/trigger-btc-exit")
async def trigger_btc_exit(admin: dict = Depends(get_current_admin)):
    """Manually trigger the 17:29 PM BTC option exit job (Delta Exchange)."""
    _require_firestore()
    summary = await execution_service.execute_btc_exit()
    return {"status": "executed_btc_exit", **summary}
