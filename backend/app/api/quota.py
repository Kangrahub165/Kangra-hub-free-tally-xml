from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.core.security import get_current_user, CurrentUser
from app.core import db

router = APIRouter(prefix="/quota", tags=["Quota"])

class QuotaCounter(BaseModel):
    limit: Optional[int] = 50
    used: int = 0
    remaining: Optional[int] = 50

class DailyQuotaResponse(BaseModel):
    pdf_pages: QuotaCounter
    images: QuotaCounter
    reset_time_ist: str = "12:00 AM IST"
    date_ist: str
    is_admin: bool = False
    is_unlimited: bool = False
    is_paid: bool = False

def resolve_user_daily_quota(user: CurrentUser) -> DailyQuotaResponse:
    """
    Authoritative server-side quota resolution (PRD Oct 12, 2026).
    Enforces independent counters for PDF pages (50/day) and images (5/day).
    Resets at 00:00 IST decided by server clock.
    """
    today = db.get_ist_today()
    is_admin = bool(user.is_admin or user.role in ("ADMIN", "SUPER_ADMIN") or user.has_quota_bypass)

    # Check active approved exception
    exc = db.get_active_quota_exception(user.id, today)
    if not exc and getattr(user, "email", None):
        exc = db.get_active_quota_exception(user.email, today)

    # Check staff / membership subscription
    mem = None
    is_paid = False
    try:
        mem = db.get_active_staff_membership(user.id, getattr(user, "email", None))
        if mem and mem.get("is_active", 0) == 1:
            is_paid = True
    except Exception:
        pass

    is_unlim = bool(is_admin or getattr(user, "is_unlimited", False) or (mem and mem.get("is_unlimited", 0) == 1))

    # Default limits
    pdf_limit = 50
    img_limit = 5

    pdf_unlimited = bool(is_unlim)
    img_unlimited = bool(is_unlim)

    if exc:
        scope = (exc.get("scope") or "BOTH").upper()
        limit_type = (exc.get("limit_type") or "DAILY_LIMIT").upper()
        limit_val = exc.get("limit_value")

        if limit_type == "UNLIMITED":
            if scope in ("PDF_PAGE", "BOTH"):
                pdf_unlimited = True
            if scope in ("IMAGE", "BOTH"):
                img_unlimited = True
        elif limit_type == "DAILY_LIMIT" and limit_val is not None:
            if scope in ("PDF_PAGE", "BOTH"):
                pdf_limit = int(limit_val)
            if scope in ("IMAGE", "BOTH"):
                img_limit = int(limit_val)

    # Query persistent SQLite usage
    pdf_used = db.get_daily_quota_used(user.id, today, "PDF_PAGE")
    img_used = db.get_daily_quota_used(user.id, today, "IMAGE")

    if pdf_used == 0 and getattr(user, "email", None):
        pdf_used = db.get_daily_quota_used(user.email, today, "PDF_PAGE")
    if img_used == 0 and getattr(user, "email", None):
        img_used = db.get_daily_quota_used(user.email, today, "IMAGE")

    if pdf_unlimited:
        pdf_counter = QuotaCounter(limit=999999, used=pdf_used, remaining=999999)
    else:
        pdf_rem = max(0, pdf_limit - pdf_used)
        pdf_counter = QuotaCounter(limit=pdf_limit, used=pdf_used, remaining=pdf_rem)

    if img_unlimited:
        img_counter = QuotaCounter(limit=999999, used=img_used, remaining=999999)
    else:
        img_rem = max(0, img_limit - img_used)
        img_counter = QuotaCounter(limit=img_limit, used=img_used, remaining=img_rem)

    return DailyQuotaResponse(
        pdf_pages=pdf_counter,
        images=img_counter,
        reset_time_ist="12:00 AM IST",
        date_ist=today,
        is_admin=bool(is_admin),
        is_unlimited=bool(pdf_unlimited and img_unlimited),
        is_paid=bool(is_paid)
    )

@router.get("", response_model=DailyQuotaResponse)
async def get_quota_summary(current_user: CurrentUser = Depends(get_current_user)):
    """
    Returns the user's current daily quota usage and limits for both PDF pages and Images.
    Resets at 00:00 IST.
    """
    return resolve_user_daily_quota(current_user)
