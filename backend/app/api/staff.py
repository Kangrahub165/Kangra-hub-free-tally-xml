import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.security import require_admin, CurrentUser
from app.core import db

logger = logging.getLogger("kangra_hub.staff")

router = APIRouter(prefix="/staff", tags=["Staff Management"])

class AddStaffRequest(BaseModel):
    user_id_or_email: str
    is_gold: bool = False
    expiry_days: Optional[int] = None
    notes: Optional[str] = None

class RemoveStaffRequest(BaseModel):
    user_id_or_email: str
    reason: Optional[str] = None

class ToggleGoldRequest(BaseModel):
    user_id: str
    is_gold: bool

class ExtendExpiryRequest(BaseModel):
    user_id: str
    days: int = 30

class WhitelistDeviceRequest(BaseModel):
    device_id: str
    is_whitelisted: bool = True

@router.get("/list")
async def list_staff_members(current_user: CurrentUser = Depends(require_admin)):
    """
    Returns all Staff group members.
    Requires ADMIN privileges. (Staff users are blocked with 403).
    """
    staff_members = db.get_all_staff_users()
    return {
        "success": True,
        "count": len(staff_members),
        "staff": staff_members
    }

@router.post("/add")
async def add_staff_member(
    req: AddStaffRequest,
    current_user: CurrentUser = Depends(require_admin)
):
    """
    Adds a user to the Staff group:
    PRD Section 7: Staff added manually by admin receives unlimited bills, no daily limit counters,
    and no admin powers. By default is_gold=False unless explicitly specified.
    """
    target = req.user_id_or_email.strip().lower()
    u = db.get_user_by_id_or_email(target)
    if not u:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{req.user_id_or_email}' not found."
        )

    uid = u["id"]
    from datetime import datetime, timezone, timedelta
    expiry_iso = None
    if req.expiry_days and req.expiry_days > 0:
        expiry_iso = (datetime.now(timezone.utc) + timedelta(days=req.expiry_days)).isoformat()

    success = db.add_user_to_staff(
        user_id=uid,
        admin_id=current_user.id,
        admin_name=current_user.full_name or current_user.email,
        source="ADMIN",
        is_gold=req.is_gold,
        expiry=expiry_iso
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add user to Staff group."
        )

    return {
        "success": True,
        "message": f"User {u.get('email')} successfully added to Staff group.",
        "user_id": uid,
        "email": u.get("email"),
        "role": "STAFF",
        "is_gold": req.is_gold,
        "subscription_expiry": expiry_iso
    }

@router.post("/remove")
async def remove_staff_member(
    req: RemoveStaffRequest,
    current_user: CurrentUser = Depends(require_admin)
):
    """
    Removes a user from the Staff group:
    Restores role to 'USER', revokes Gold Tick, restores 5 bills/day limit immediately.
    """
    target = req.user_id_or_email.strip().lower()
    u = db.get_user_by_id_or_email(target)
    if not u:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{req.user_id_or_email}' not found."
        )

    uid = u["id"]
    success = db.remove_user_from_staff(
        user_id=uid,
        admin_id=current_user.id,
        admin_name=current_user.full_name or current_user.email
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove user from Staff group."
        )

    return {
        "success": True,
        "message": f"User {u.get('email')} removed from Staff group and reverted to standard plan.",
        "user_id": uid
    }

@router.post("/toggle-gold")
async def toggle_gold_tick(
    req: ToggleGoldRequest,
    current_user: CurrentUser = Depends(require_admin)
):
    """Grants or revokes the Kangra Hub Gold Tick for a user."""
    success = db.set_user_gold_tick(
        user_id=req.user_id,
        is_gold=req.is_gold,
        admin_id=current_user.id,
        admin_name=current_user.full_name or current_user.email
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or operation failed."
        )
    return {
        "success": True,
        "user_id": req.user_id,
        "is_gold": req.is_gold,
        "message": f"Gold Tick {'granted' if req.is_gold else 'revoked'} successfully."
    }

@router.post("/extend-expiry")
async def extend_staff_subscription(
    req: ExtendExpiryRequest,
    current_user: CurrentUser = Depends(require_admin)
):
    """Extends a Staff member's subscription expiry by N days."""
    if req.days <= 0:
        raise HTTPException(status_code=400, detail="Extension days must be greater than 0.")
    success = db.extend_user_subscription(
        user_id=req.user_id,
        days=req.days,
        admin_id=current_user.id,
        admin_name=current_user.full_name or current_user.email
    )
    if not success:
        raise HTTPException(status_code=404, detail="User not found or operation failed.")
    return {
        "success": True,
        "message": f"Subscription extended by {req.days} days."
    }

@router.get("/audit-logs")
async def get_staff_audit_history(
    limit: int = 50,
    offset: int = 0,
    current_user: CurrentUser = Depends(require_admin)
):
    """Retrieves full audit log of all staff administrative actions."""
    logs = db.get_staff_audit_logs(limit=limit, offset=offset)
    return {
        "success": True,
        "logs": logs
    }

@router.get("/suspicious-activity")
async def get_suspicious_activity(current_user: CurrentUser = Depends(require_admin)):
    """
    Anti-Abuse Monitor:
    Detects shared devices across multiple accounts, duplicate bill uploads across accounts, etc.
    """
    signals = db.get_suspicious_activity_logs()
    return {
        "success": True,
        "signals": signals
    }

@router.post("/whitelist-device")
async def set_device_whitelist(
    req: WhitelistDeviceRequest,
    current_user: CurrentUser = Depends(require_admin)
):
    """Whitelists or un-whitelists a device ID to allow multi-account access."""
    db.set_device_whitelist(req.device_id, req.is_whitelisted)
    return {
        "success": True,
        "device_id": req.device_id,
        "is_whitelisted": req.is_whitelisted,
        "message": f"Device {req.device_id[:12]}... {'whitelisted' if req.is_whitelisted else 'un-whitelisted'}."
    }
