"""Health check endpoint."""
from fastapi import APIRouter

from services import firebase_service

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "tradzo-backend",
        "firestore": "ready" if firebase_service.is_ready() else "unconfigured",
    }
