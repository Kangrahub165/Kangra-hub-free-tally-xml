import logging
import uuid
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, status, Query, Request
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.supabase_service import SupabaseService
from app.core.user_store import get_user_by_email, get_user_suspension_info

logger = logging.getLogger("kangra_hub.appeals")

router = APIRouter(tags=["Appeals"])

_APPEALS_LOCK = threading.Lock()

# Thread-safe in-memory store for account appeals
APPEALS_STORE: Dict[str, Dict[str, Any]] = {}

class SubmitAppealRequest(BaseModel):
    email: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    subject: Optional[str] = "Request to review my suspended account"
    message: str

def get_appeals_for_user(user_id_or_email: str) -> List[Dict[str, Any]]:
    clean = user_id_or_email.strip().lower()
    results = []
    with _APPEALS_LOCK:
        for a in APPEALS_STORE.values():
            if a.get("user_email", "").lower() == clean or str(a.get("user_id", "")).lower() == clean:
                results.append(dict(a))

    # Also query Supabase if configured
    if SupabaseService.is_configured():
        try:
            db_appeals = SupabaseService.query_user_appeals(clean)
            if db_appeals:
                existing_ids = {r["id"] for r in results}
                for row in db_appeals:
                    if row["id"] not in existing_ids:
                        results.append(row)
        except Exception as e:
            logger.warning(f"Failed to query appeals from Supabase: {e}")

    # Sort descending by created_at
    return sorted(results, key=lambda x: str(x.get("created_at", "")), reverse=True)


@router.post("/submit")
async def submit_appeal(payload: SubmitAppealRequest, request: Request):
    """
    Suspended user appeal submission endpoint (PRD Sections 7, 8, 19).
    Validates message length, blocks duplicate pending submissions, and stores appeal.
    """
    clean_email = payload.email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid registered email address is required to submit an appeal."
        )

    clean_message = payload.message.strip()
    if not clean_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a message explaining your appeal."
        )

    if len(clean_message) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a more detailed explanation for your appeal (minimum 10 characters)."
        )

    # Check for existing user info
    u_info = get_user_by_email(clean_email)
    user_id = payload.user_id or (u_info.get("id") if u_info else f"usr-{clean_email.split('@')[0]}")
    user_name = payload.user_name or (u_info.get("full_name") if u_info else clean_email.split("@")[0].capitalize())

    # Prevent duplicate pending appeals (PRD Section 19)
    existing_appeals = get_appeals_for_user(clean_email)
    pending_appeal = next((a for a in existing_appeals if a.get("status") in ("pending", "under_review")), None)
    if pending_appeal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an appeal under review. Please wait for the administrator's response."
        )

    appeal_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    subject_text = (payload.subject or "Request to review my suspended account").strip()

    appeal_record = {
        "id": appeal_id,
        "user_id": user_id,
        "user_email": clean_email,
        "user_name": user_name,
        "subject": subject_text,
        "message": clean_message,
        "status": "pending",
        "admin_response": None,
        "created_at": now_iso,
        "updated_at": now_iso,
        "reviewed_at": None,
        "reviewed_by": None
    }

    with _APPEALS_LOCK:
        APPEALS_STORE[appeal_id] = appeal_record

    # Persist to Supabase public.account_appeals
    if SupabaseService.is_configured():
        try:
            SupabaseService.insert_appeal({
                "id": appeal_id,
                "user_id": user_id,
                "user_email": clean_email,
                "user_name": user_name,
                "subject": subject_text,
                "message": clean_message,
                "status": "pending",
                "created_at": now_iso,
                "updated_at": now_iso
            })
        except Exception as e:
            logger.warning(f"Failed to persist appeal to Supabase: {e}")

    logger.info(f"Appeal {appeal_id} submitted for user {clean_email}")

    return {
        "success": True,
        "request_id": appeal_id,
        "message": "Your request has been successfully submitted to the administrator. Your account will remain suspended while your request is being reviewed.",
        "status": "pending"
    }


@router.get("/status")
async def get_appeal_status(
    email: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None)
):
    """
    Public appeal status lookup for suspended user UI (PRD Section 18).
    """
    identifier = email or user_id
    if not identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or user ID is required to look up appeal status."
        )

    user_appeals = get_appeals_for_user(identifier)
    if not user_appeals:
        return {
            "has_appeal": False,
            "appeal": None
        }

    latest = user_appeals[0]
    return {
        "has_appeal": True,
        "appeal": {
            "id": latest.get("id"),
            "user_id": latest.get("user_id"),
            "user_email": latest.get("user_email"),
            "user_name": latest.get("user_name"),
            "subject": latest.get("subject"),
            "message": latest.get("message"),
            "status": latest.get("status"),
            "admin_response": latest.get("admin_response"),
            "created_at": latest.get("created_at"),
            "updated_at": latest.get("updated_at"),
            "reviewed_at": latest.get("reviewed_at")
        }
    }
