import os
import uuid
import mimetypes
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import get_current_user, require_admin, CurrentUser
from app.api.usage import (
    grant_user_additional_pages,
    get_user_additional_pages,
)

from app.core import db

router = APIRouter(tags=["Payments"])

# Storage directory for uploaded payment screenshots
PAYMENT_SCREENSHOT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "uploads",
    "payment_screenshots"
)
os.makedirs(PAYMENT_SCREENSHOT_DIR, exist_ok=True)

# In-memory store for fast lookup, preloaded from SQLite
PAYMENT_REQUESTS: Dict[str, Dict[str, Any]] = {}
try:
    for _pr in db.get_all_payment_requests():
        PAYMENT_REQUESTS[_pr["id"]] = dict(_pr)
except Exception as _e:
    pass

class PaymentConfigResponse(BaseModel):
    upi_id: str
    price_per_page: float
    qr_path: str
    whatsapp_number: str
    support_message: str

class PaymentRequestResponse(BaseModel):
    id: str
    user_id: str
    user_email: str
    user_name: Optional[str] = None
    requested_pages: int
    granted_pages: int
    amount_paid: float
    job_id: Optional[str] = None
    notes: Optional[str] = None
    screenshot_url: str
    status: str  # "PENDING" | "APPROVED" | "REJECTED"
    created_at: str
    updated_at: str
    admin_notes: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None

class ApprovePaymentRequest(BaseModel):
    granted_pages: Optional[int] = None
    verified_amount: Optional[float] = None
    admin_notes: Optional[str] = None

class RejectPaymentRequest(BaseModel):
    reason: Optional[str] = None

def _format_request_response(r: Dict[str, Any]) -> PaymentRequestResponse:
    return PaymentRequestResponse(
        id=r["id"],
        user_id=r["user_id"],
        user_email=r["user_email"],
        user_name=r.get("user_name"),
        requested_pages=r["requested_pages"],
        granted_pages=r.get("granted_pages", r["requested_pages"]),
        amount_paid=r["amount_paid"],
        job_id=r.get("job_id"),
        notes=r.get("notes"),
        screenshot_url=f"/api/payments/requests/{r['id']}/screenshot",
        status=r["status"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
        admin_notes=r.get("admin_notes"),
        approved_by=r.get("approved_by"),
        approved_at=r.get("approved_at"),
    )

# --- User & Public Endpoints ---

@router.get("/api/payments/config", response_model=PaymentConfigResponse)
async def get_payment_configuration():
    """Returns UPI payment parameters, pricing, and QR asset path."""
    return PaymentConfigResponse(
        upi_id=getattr(settings, "payment_upi_id", "9418250639@ybl"),
        price_per_page=getattr(settings, "page_price_inr", 2.0),
        qr_path=getattr(settings, "payment_qr_path", "/buy-a-coffee/googlepay_qr.png"),
        whatsapp_number=getattr(settings, "payment_whatsapp_number", "+919805987622"),
        support_message="Complete manual payment of ₹2/page via Google Pay / UPI, then upload the transaction screenshot here."
    )

@router.post("/api/payments/requests", response_model=PaymentRequestResponse)
async def submit_payment_request(
    requested_pages: int = Form(...),
    job_id: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    screenshot: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Submits a manual UPI payment verification request with uploaded screenshot.
    Pricing is authoritative server-side: requested_pages * settings.page_price_inr (₹2/page).
    """
    if requested_pages <= 0:
        raise HTTPException(status_code=400, detail="Requested page count must be greater than zero.")

    # Validate file format (images only: PNG, JPEG, WEBP)
    content_type = (screenshot.content_type or "").lower()
    ext = os.path.splitext(screenshot.filename or "")[1].lower()
    allowed_exts = (".png", ".jpg", ".jpeg", ".webp")
    if not (content_type.startswith("image/") or ext in allowed_exts):
        raise HTTPException(status_code=400, detail="Invalid screenshot format. Please upload a PNG, JPG, or WEBP image.")

    request_id = f"pay-{uuid.uuid4().hex[:10]}"
    safe_filename = f"{request_id}{ext if ext in allowed_exts else '.png'}"
    target_path = os.path.join(PAYMENT_SCREENSHOT_DIR, safe_filename)

    file_bytes = await screenshot.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded screenshot file is empty.")

    with open(target_path, "wb") as f:
        f.write(file_bytes)

    now_iso = datetime.now(timezone.utc).isoformat()
    price_per_page = getattr(settings, "page_price_inr", 2.0)
    amount = round(float(requested_pages * price_per_page), 2)

    req_record = {
        "id": request_id,
        "user_id": current_user.id,
        "user_email": current_user.email,
        "user_name": current_user.full_name or current_user.email,
        "requested_pages": requested_pages,
        "granted_pages": requested_pages,
        "amount_paid": amount,
        "job_id": job_id,
        "notes": notes,
        "screenshot_path": target_path,
        "screenshot_filename": screenshot.filename,
        "status": "PENDING",
        "created_at": now_iso,
        "updated_at": now_iso,
        "admin_notes": None,
        "approved_by": None,
        "approved_at": None,
    }
    PAYMENT_REQUESTS[request_id] = req_record
    try:
        db.save_payment_request(req_record)
    except Exception as e:
        pass

    return _format_request_response(req_record)

@router.get("/api/payments/requests/me", response_model=List[PaymentRequestResponse])
async def get_my_payment_requests(current_user: CurrentUser = Depends(get_current_user)):
    """Lists payment requests submitted by the logged in user."""
    db_requests = db.get_user_payment_requests(current_user.id)
    if not db_requests and current_user.email:
        db_requests = db.get_user_payment_requests(current_user.email)
    
    # Merge with in-memory
    seen_ids = set()
    combined = []
    for r in db_requests:
        seen_ids.add(r["id"])
        combined.append(r)
    for r in PAYMENT_REQUESTS.values():
        if (r["user_id"] == current_user.id or r["user_email"] == current_user.email) and r["id"] not in seen_ids:
            seen_ids.add(r["id"])
            combined.append(r)

    combined.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
    return [_format_request_response(r) for r in combined]

@router.get("/api/payments/requests/{request_id}/screenshot")
async def get_payment_screenshot(
    request_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Securely streams payment screenshot to authorized user or admin."""
    r = PAYMENT_REQUESTS.get(request_id) or db.get_payment_request(request_id)
    if not r:
        raise HTTPException(status_code=404, detail="Payment request not found.")
    
    is_owner = (r["user_id"] == current_user.id or r["user_email"] == current_user.email)
    is_admin_user = (current_user.is_admin or current_user.role in ("ADMIN", "SUPER_ADMIN"))
    if not (is_owner or is_admin_user):
        raise HTTPException(status_code=403, detail="Access denied.")

    screenshot_path = r.get("screenshot_path")
    if not screenshot_path or not os.path.exists(screenshot_path):
        raise HTTPException(status_code=404, detail="Screenshot file not found on server.")

    mime, _ = mimetypes.guess_type(screenshot_path)
    return FileResponse(path=screenshot_path, media_type=mime or "image/png")

# --- Admin Management Endpoints ---

@router.get("/api/admin/payments/requests", response_model=List[PaymentRequestResponse])
async def get_admin_payment_requests(
    status: Optional[str] = Query(None),
    admin: CurrentUser = Depends(require_admin)
):
    """Admin: lists payment requests with optional status filter ('ALL', 'PENDING', 'APPROVED', 'REJECTED')."""
    db_reqs = db.get_all_payment_requests(status)
    seen_ids = set()
    combined = []
    for r in db_reqs:
        seen_ids.add(r["id"])
        combined.append(r)
    for r in PAYMENT_REQUESTS.values():
        if r["id"] not in seen_ids:
            if not status or status.upper() == "ALL" or r["status"].upper() == status.upper():
                seen_ids.add(r["id"])
                combined.append(r)

    combined.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
    return [_format_request_response(r) for r in combined]

@router.post("/api/admin/payments/requests/{request_id}/approve")
async def approve_payment_request(
    request_id: str,
    payload: ApprovePaymentRequest,
    admin: CurrentUser = Depends(require_admin)
):
    """
    Admin: approves payment request and credits additional page balance to user account.
    Balance never resets at midnight.
    """
    r = PAYMENT_REQUESTS.get(request_id)
    if not r:
        raise HTTPException(status_code=404, detail="Payment request not found.")

    if r["status"] == "APPROVED":
        raise HTTPException(status_code=400, detail="This payment request has already been approved.")

    # Strict page calculation: FLOOR(payment_amount / 2)
    if payload.verified_amount is not None:
        pages_to_grant = int(payload.verified_amount // 2)
    elif payload.granted_pages is not None:
        pages_to_grant = int(payload.granted_pages)
    else:
        pages_to_grant = int(r["amount_paid"] // 2)

    if pages_to_grant <= 0:
        raise HTTPException(status_code=400, detail="Granted pages must be at least 1 (minimum payment ₹2).")

    user_id = r["user_id"]
    prev_balance = db.get_additional_pages(user_id)

    new_balance = grant_user_additional_pages(
        user_id=user_id,
        pages=pages_to_grant,
        admin_email=admin.email,
        notes=payload.admin_notes
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    r["status"] = "APPROVED"
    r["granted_pages"] = pages_to_grant
    r["admin_notes"] = payload.admin_notes
    r["approved_by"] = admin.email
    r["approved_at"] = now_iso
    r["updated_at"] = now_iso

    try:
        db.update_payment_request_status(
            request_id=request_id,
            status="APPROVED",
            admin_email=admin.email,
            granted_pages=pages_to_grant,
            notes=payload.admin_notes
        )
    except Exception as e:
        pass

    # Log immutable audit event
    try:
        db.log_page_credit_event(
            user_id=user_id,
            conversion_id=r.get("job_id"),
            payment_id=request_id,
            amount=payload.verified_amount if payload.verified_amount is not None else r["amount_paid"],
            pages_requested=r["requested_pages"],
            pages_approved=pages_to_grant,
            pages_credited=pages_to_grant,
            admin_id=admin.email,
            source="ADMIN_APPROVAL",
            previous_balance=prev_balance,
            new_balance=new_balance
        )
    except Exception as e:
        pass

    # Append to AUDIT_LOGS
    try:
        from app.api.admin import AUDIT_LOGS
        AUDIT_LOGS.append({
            "id": f"log-{uuid.uuid4().hex[:8]}",
            "admin_email": admin.email,
            "action": "PAGE_PAYMENT_APPROVED",
            "target": r["user_email"],
            "metadata": {
                "request_id": request_id,
                "granted_pages": pages_to_grant,
                "amount": r["amount_paid"],
                "notes": payload.admin_notes
            },
            "timestamp": datetime.now().isoformat()
        })
    except Exception:
        pass

    verified_amt = payload.verified_amount if payload.verified_amount is not None else r["amount_paid"]
    return {
        "success": True,
        "message": f"Approved {pages_to_grant} additional pages for {r['user_email']}.",
        "granted_pages": pages_to_grant,
        "amount_paid": verified_amt,
        "request": _format_request_response(r),
        "new_balance": new_balance
    }

@router.post("/api/admin/payments/requests/{request_id}/reject")
async def reject_payment_request(
    request_id: str,
    payload: RejectPaymentRequest,
    admin: CurrentUser = Depends(require_admin)
):
    """Admin: rejects a payment request with an optional reason."""
    r = PAYMENT_REQUESTS.get(request_id) or db.get_payment_request(request_id)
    if not r:
        raise HTTPException(status_code=404, detail="Payment request not found.")

    now_iso = datetime.now(timezone.utc).isoformat()
    r["status"] = "REJECTED"
    r["admin_notes"] = payload.reason
    r["rejected_by"] = admin.email
    r["rejected_at"] = now_iso
    r["updated_at"] = now_iso
    PAYMENT_REQUESTS[request_id] = r

    try:
        db.update_payment_request_status(
            request_id=request_id,
            status="REJECTED",
            admin_email=admin.email,
            notes=payload.reason
        )
    except Exception as e:
        pass

    try:
        from app.api.admin import AUDIT_LOGS
        AUDIT_LOGS.append({
            "id": f"log-{uuid.uuid4().hex[:8]}",
            "admin_email": admin.email,
            "action": "PAGE_PAYMENT_REJECTED",
            "target": r["user_email"],
            "metadata": {
                "request_id": request_id,
                "reason": payload.reason
            },
            "timestamp": datetime.now().isoformat()
        })
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Payment request {request_id} has been rejected.",
        "request": _format_request_response(r)
    }
