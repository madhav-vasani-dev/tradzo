import logging
from fastapi import Header, HTTPException, Depends
from firebase_admin import auth
from services import firebase_service

log = logging.getLogger("tradzo.auth")


def verify_firebase_token(authorization: str = Header(None)) -> dict:
    """Validate Bearer Firebase ID Token in the Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Missing or invalid Authorization Bearer header.",
        )
    token = authorization.split("Bearer ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as exc:
        log.warning("Firebase token verification failed: %s", exc)
        raise HTTPException(
            status_code=401,
            detail=f"Unauthorized: Token verification failed: {exc}",
        )


def get_current_user(current_user: dict = Depends(verify_firebase_token)) -> dict:
    """Dependency to return the verified current user payload."""
    return current_user


def get_current_admin(current_user: dict = Depends(verify_firebase_token)) -> dict:
    """Dependency to check if the current user is an admin or superuser in Firestore."""
    uid = current_user.get("uid")
    if not uid:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Missing user UID in authentication token.",
        )

    # Resolve roles from Firestore
    try:
        db = firebase_service.get_db()
        snap = db.collection("users").document(uid).get()
        if snap.exists:
            user_data = snap.to_dict()
            if user_data.get("isAdmin") or user_data.get("isSuperUser"):
                return current_user
    except Exception as exc:
        log.error("Failed to query user roles from Firestore: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: Failed to verify roles: {exc}",
        )

    raise HTTPException(
        status_code=403,
        detail="Forbidden: Admin privileges required to execute this operation.",
    )
