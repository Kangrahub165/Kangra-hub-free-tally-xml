from datetime import datetime
import pytz
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.core.config import settings
from app.core.security import get_current_user, CurrentUser

from app.core import db

router = APIRouter(prefix="/usage", tags=["Usage"])

# In-memory usage tracker for daily page processing
# Key: (user_id, date_str) -> pages_used
_IN_MEMORY_DAILY_USAGE: Dict[str, int] = {}

# Per-user custom daily quota overrides. Key: user_id -> custom_daily_limit (int)
USER_CUSTOM_QUOTAS: Dict[str, Optional[int]] = {}

# Additional purchased / granted page balance (never resets at midnight IST)
# Key: user_id -> balance (int)
USER_ADDITIONAL_PAGES: Dict[str, int] = {}

def get_user_additional_pages(user_or_id: Any) -> int:
    """Gets additional page balance for a user. Never expires/resets at midnight."""
    if hasattr(user_or_id, "id"):
        uid = str(user_or_id.id)
        email = getattr(user_or_id, "email", "")
    else:
        uid = str(user_or_id)
        email = ""
    bal = db.get_additional_pages(uid)
    if bal == 0 and email:
        bal = db.get_additional_pages(email)
    if bal == 0:
        bal = USER_ADDITIONAL_PAGES.get(uid, 0) or (USER_ADDITIONAL_PAGES.get(email, 0) if email else 0)
    return max(0, bal)

def grant_user_additional_pages(user_id: str, pages: int, admin_email: Optional[str] = None, notes: Optional[str] = None) -> int:
    """Grants additional purchased pages to a user balance."""
    new_bal = db.grant_additional_pages(user_id, pages)
    USER_ADDITIONAL_PAGES[user_id] = new_bal
    return new_bal

def deduct_user_additional_pages(user_id: str, pages: int) -> int:
    """Deducts used pages from a user's additional page balance."""
    new_bal = db.deduct_additional_pages(user_id, pages)
    USER_ADDITIONAL_PAGES[user_id] = new_bal
    return new_bal

def get_kolkata_today() -> str:
    """Authoritative server-side IST date calculation for daily quota tracking."""
    tz = pytz.timezone(settings.default_timezone)
    return datetime.now(tz).strftime("%Y-%m-%d")

def get_user_daily_limit(user: CurrentUser) -> int:
    """
    Resolves authoritative daily page limit:
    1. Unlimited bypass (Admin / Unlimited VIP) -> 999999
    2. Per-user custom quota override (if configured by Admin)
    3. Global Free Daily Page Quota (settings.free_daily_page_limit)
    """
    if user.has_quota_bypass or user.role in ("ADMIN", "SUPER_ADMIN") or user.is_unlimited or user.is_admin:
        return 999999
    
    custom = db.get_custom_quota(user.id)
    if custom is None and user.email:
        custom = db.get_custom_quota(user.email)
    if custom is None:
        custom = USER_CUSTOM_QUOTAS.get(user.id)
        if custom is None and user.email:
            custom = USER_CUSTOM_QUOTAS.get(user.email)
        
    if custom is not None:
        return custom
        
    return settings.free_daily_page_limit

def get_user_quota_mode(user: CurrentUser) -> str:
    """Returns the quota mode: 'UNLIMITED', 'CUSTOM', or 'GLOBAL'."""
    if user.has_quota_bypass or user.role in ("ADMIN", "SUPER_ADMIN") or user.is_unlimited or user.is_admin:
        return "UNLIMITED"
    c = db.get_custom_quota(user.id)
    if c is None and user.email:
        c = db.get_custom_quota(user.email)
    if c is None:
        c = USER_CUSTOM_QUOTAS.get(user.id) or (USER_CUSTOM_QUOTAS.get(user.email) if user.email else None)
    if c is not None:
        return "CUSTOM"
    return "GLOBAL"

class UserUsageResponse(BaseModel):
    user_id: str
    daily_limit: int
    effective_daily_quota: int
    pages_used_today: int
    pages_remaining_today: int
    additional_page_balance: int = 0
    total_allowed_pages: int = 50
    price_per_page: float = 2.0
    is_unlimited: bool
    account_status: str
    quota_mode: str = "GLOBAL"  # "GLOBAL" | "CUSTOM" | "UNLIMITED"
    quota_source: str = "global"
    global_limit: int = 50
    global_quota: int = 50
    custom_limit: Optional[int] = None
    custom_quota: Optional[int] = None
    timezone: str = "Asia/Kolkata"
    reset_at_ist: str = "12:00 AM IST"
    conversion_count: int = 0
    completed_pages_today: int = 0
    needs_review_pages_today: int = 0

def get_user_usage_data(user: CurrentUser) -> UserUsageResponse:
    today = get_kolkata_today()
    key = f"{user.id}:{today}"
    
    # Authoritative reconciliation against today's conversion jobs
    # Both Completed and Needs Review pages consume daily quota (PRD Section 31)
    from app.api.conversions import IN_MEMORY_JOBS
    jobs_today_pages = 0
    completed_pages = 0
    needs_review_pages = 0
    conversions_today_count = 0

    tz = pytz.timezone(settings.default_timezone)
    for j in IN_MEMORY_JOBS.values():
        if j.get("user_id") == user.id or j.get("user_id") == getattr(user, "email", ""):
            c_at = j.get("created_at")
            j_date = None
            if c_at:
                if hasattr(c_at, "astimezone"):
                    j_date = c_at.astimezone(tz).strftime("%Y-%m-%d")
                elif isinstance(c_at, str):
                    j_date = c_at[:10]
            if not j_date:
                j_date = today

            if j_date == today:
                conversions_today_count += 1
                status = j.get("status")
                # When partial conversion occurred, only count pages actually processed from free quota
                free_used = j.get("free_quota_used")
                if free_used is not None:
                    p_count = free_used
                elif j.get("pages_processed") is not None:
                    p_count = j.get("pages_processed", 0)
                else:
                    p_count = j.get("page_count", 0)

                if status in ("COMPLETED", "PARTIALLY_COMPLETED"):
                    completed_pages += p_count
                    jobs_today_pages += p_count
                elif status == "NEEDS_REVIEW":
                    needs_review_pages += p_count
                    jobs_today_pages += p_count
                elif status not in ("FAILED", "QUOTA_EXHAUSTED"):
                    jobs_today_pages += p_count

    # Check persistent SQLite daily usage
    db_recorded_pages = db.get_daily_usage(user.id, today)
    if db_recorded_pages == 0 and getattr(user, "email", None):
        db_recorded_pages = db.get_daily_usage(user.email, today)

    mem_recorded_pages = _IN_MEMORY_DAILY_USAGE.get(key, 0)
    recorded_pages = max(db_recorded_pages, mem_recorded_pages)

    # Bugfix: Never force 0 just because in-memory dictionary is empty!
    is_explicitly_zero = (key in _IN_MEMORY_DAILY_USAGE and _IN_MEMORY_DAILY_USAGE[key] == 0)
    if is_explicitly_zero:
        pages_used = 0
    else:
        pages_used = max(recorded_pages, jobs_today_pages)
        _IN_MEMORY_DAILY_USAGE[key] = pages_used
    
    is_unlim = user.has_quota_bypass or user.role in ("ADMIN", "SUPER_ADMIN") or user.is_unlimited or user.is_admin
    daily_limit = get_user_daily_limit(user)
    remaining = 999999 if is_unlim else max(0, daily_limit - pages_used)
    mode = get_user_quota_mode(user)
    
    additional_bal = get_user_additional_pages(user)
    total_allowed = 999999 if is_unlim else (remaining + additional_bal)
    price_per_pg = getattr(settings, "page_price_inr", 2.0)

    custom_val = db.get_custom_quota(user.id) or (db.get_custom_quota(user.email) if user.email else None)
    if custom_val is None:
        custom_val = USER_CUSTOM_QUOTAS.get(user.id) or (USER_CUSTOM_QUOTAS.get(user.email) if user.email else None)

    if user.is_admin or user.role in ("ADMIN", "SUPER_ADMIN"):
        status_label = "Admin Unlimited"
    elif user.is_unlimited:
        status_label = "Unlimited Approved"
    elif mode == "CUSTOM":
        status_label = f"Custom Quota ({daily_limit} Pgs/Day)"
    elif settings.site_mode == "PAID":
        status_label = "Paid Account"
    else:
        status_label = "Free Account"

    return UserUsageResponse(
        user_id=user.id,
        daily_limit=daily_limit,
        effective_daily_quota=daily_limit,
        pages_used_today=pages_used,
        pages_remaining_today=remaining,
        additional_page_balance=additional_bal,
        total_allowed_pages=total_allowed,
        price_per_page=price_per_pg,
        is_unlimited=is_unlim,
        account_status=status_label,
        quota_mode=mode,
        quota_source=mode.lower(),
        global_limit=settings.free_daily_page_limit,
        global_quota=settings.free_daily_page_limit,
        custom_limit=custom_val,
        custom_quota=custom_val,
        timezone="Asia/Kolkata",
        reset_at_ist="12:00 AM IST",
        conversion_count=conversions_today_count,
        completed_pages_today=completed_pages,
        needs_review_pages_today=needs_review_pages
    )

def record_user_page_usage(user: CurrentUser, pages: int):
    """Authoritative server-side page usage tracker."""
    if user.has_quota_bypass or user.is_admin or user.role in ("ADMIN", "SUPER_ADMIN") or user.is_unlimited:
        return
    today = get_kolkata_today()
    key = f"{user.id}:{today}"
    db.record_daily_usage(user.id, today, pages)
    _IN_MEMORY_DAILY_USAGE[key] = _IN_MEMORY_DAILY_USAGE.get(key, 0) + pages

@router.get("", response_model=UserUsageResponse)
async def get_current_usage(current_user: CurrentUser = Depends(get_current_user)):
    """Returns today's usage, remaining allowance, and quota status."""
    return get_user_usage_data(current_user)
