import os
import uuid
import mimetypes
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

import hmac
import hashlib
import base64
import urllib.request
import json
import logging
from app.core.config import settings
from app.core.security import get_current_user, require_admin, CurrentUser
from app.api.usage import (
    grant_user_additional_pages,
    get_user_additional_pages,
)
from app.core import db
from app.core.plans import get_subscription_plans, get_plan_by_id, resolve_plan_id

logger = logging.getLogger("kangra_hub.payments")

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

# ============================================================================
# SUBSCRIPTION PLANS & CHECKOUT ENDPOINTS (PRD Sections 1, 2, & 3)
# ============================================================================

class CreateOrderRequest(BaseModel):
    planId: Optional[str] = "basic"
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None

class VerifyPaymentRequest(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: Optional[str] = None
    razorpay_signature: Optional[str] = None
    planId: Optional[str] = "basic"
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None

class UpdatePlanConfigRequest(BaseModel):
    bills_limit: Optional[int] = None
    price_inr: Optional[float] = None
    name: Optional[str] = None
    duration_days: Optional[int] = None

def _fetch_razorpay_payment(payment_id: str, key_id: str, key_secret: str) -> Optional[Dict[str, Any]]:
    """Fetches payment entity from Razorpay REST API."""
    url = f"https://api.razorpay.com/v1/payments/{payment_id}"
    req = urllib.request.Request(url)
    auth_str = f"{key_id}:{key_secret}"
    b64_auth = base64.b64encode(auth_str.encode("ascii")).decode("ascii")
    req.add_header("Authorization", f"Basic {b64_auth}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.debug(f"Razorpay API fetch failed for payment {payment_id}: {e}")
        return None

@router.get("/api/subscriptions/plans")
@router.get("/api/payments/plans")
async def list_subscription_plans(current_user: CurrentUser = Depends(get_current_user)):
    """
    Returns active subscription plans with exact pricing and bill limits.
    PRD REQUIREMENT: Users MUST log in before they can view subscription plans and their details.
    Unauthenticated requests return 401 Unauthorized.
    """
    return {
        "success": True,
        "plans": get_subscription_plans()
    }

@router.get("/api/subscriptions/me")
async def get_my_subscription(current_user: CurrentUser = Depends(get_current_user)):
    """Returns active subscription state, bill limits, and conversion counts for current user."""
    mem = db.get_active_staff_membership(current_user.id, current_user.email)
    bills_used = 0
    if mem and mem.get("membership_started_at"):
        bills_used = db.get_user_bills_converted_since(current_user.id, mem["membership_started_at"])
    elif mem:
        bills_used = db.get_user_bills_converted_since(current_user.id)

    plan_id = (mem.get("plan_id") if mem else current_user.subscription_plan_id) or "free"
    plan_info = get_plan_by_id(plan_id) if plan_id != "free" else None

    limit = mem.get("bills_limit") if mem else current_user.subscription_bill_limit
    if limit is None:
        limit = plan_info["bills_limit"] if plan_info else 0

    return {
        "success": True,
        "is_active": bool(mem and mem.get("is_active")),
        "plan_id": plan_id,
        "plan_name": mem.get("plan_name") if mem else (plan_info["name"] if plan_info else "Free Tier"),
        "bills_limit": limit,
        "is_unlimited": bool(mem.get("is_unlimited") if mem else (limit == -1 or current_user.is_unlimited)),
        "bills_converted_this_cycle": bills_used,
        "bills_remaining_this_cycle": "Unlimited" if (limit == -1 or current_user.is_unlimited) else max(0, limit - bills_used),
        "membership_expires_at": mem.get("membership_expires_at") if mem else None,
        "last_valid_day": mem.get("last_valid_day") if mem else None
    }

@router.put("/api/admin/subscriptions/plans/{plan_id}")
async def admin_update_subscription_plan(
    plan_id: str,
    payload: UpdatePlanConfigRequest,
    admin: CurrentUser = Depends(require_admin)
):
    """Admin: adjust subscription plan limits, pricing, and validity."""
    canonical = resolve_plan_id(plan_id)
    updated = db.upsert_subscription_plan_config(
        plan_id=canonical,
        name=payload.name,
        price_inr=payload.price_inr,
        bills_limit=payload.bills_limit,
        duration_days=payload.duration_days
    )
    return {
        "success": True,
        "message": f"Subscription plan '{canonical}' updated successfully.",
        "plan": get_plan_by_id(canonical)
    }

@router.post("/api/payments/create-order")
@router.post("/api/subscriptions/create-order")
async def create_payment_order(
    payload: Optional[CreateOrderRequest] = None,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Creates a Razorpay Order server-side (PRD: Exact subscription pricing, zero tax added).
    Amount is strictly determined server-side from authoritative plan configuration:
    - Basic: ₹199 (19900 paise, 50 bills)
    - Standard: ₹299 (29900 paise, 150 bills)
    - Premium: ₹499 (49900 paise, Unlimited bills)
    The client must never decide the price.
    """
    key_id = (getattr(settings, "razorpay_key_id", None) or "").strip()
    key_secret = (getattr(settings, "razorpay_key_secret", None) or "").strip()

    requested_plan = (payload.planId if payload else None) or "basic"
    plan_info = get_plan_by_id(requested_plan)
    amount_paise = plan_info["price_paise"]
    plan_id = plan_info["id"]
    plan_name = plan_info["name"]

    cust_phone = ((payload.customer_phone if payload else None) or "").strip() or current_user.mobile_number or ""
    cust_name = ((payload.customer_name if payload else None) or "").strip() or current_user.full_name or ""
    cust_email = ((payload.customer_email if payload else None) or "").strip().lower() or current_user.email or ""

    if not key_id or not key_secret:
        logger.error("Razorpay order creation rejected: RAZORPAY_KEY_ID or RAZORPAY_KEY_SECRET is not configured.")
        raise HTTPException(
            status_code=503,
            detail="Razorpay API credentials (RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET) are not configured on the backend server."
        )

    try:
        url = "https://api.razorpay.com/v1/orders"
        receipt_id = f"kh_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:6]}"[:40]
        order_data = {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt_id,
            "notes": {
                "plan_id": plan_id,
                "plan_name": plan_name,
                "bills_limit": str(plan_info["bills_limit"]),
                "user_id": current_user.id,
                "user_email": current_user.email,
                "customer_name": cust_name,
                "customer_email": cust_email,
                "customer_phone": cust_phone
            }
        }
        req = urllib.request.Request(url, data=json.dumps(order_data).encode("utf-8"))
        auth_str = f"{key_id}:{key_secret}"
        b64_auth = base64.b64encode(auth_str.encode("ascii")).decode("ascii")
        req.add_header("Authorization", f"Basic {b64_auth}")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            order_id = data.get("id")
            order_amount = data.get("amount", amount_paise)
            order_currency = data.get("currency", "INR")
            logger.info(f"Razorpay order created successfully: {order_id} ({order_amount} {order_currency}, plan={plan_id}) for user {current_user.id}")

            return {
                "orderId": order_id,
                "order_id": order_id,
                "amount": order_amount,
                "amount_paise": order_amount,
                "currency": order_currency,
                "keyId": key_id,
                "key_id": key_id,
                "planId": plan_id,
                "plan_id": plan_id,
                "planName": plan_name,
                "plan_name": plan_name,
                "billsLimit": plan_info["bills_limit"],
                "bills_limit": plan_info["bills_limit"],
                "isUnlimited": plan_info["is_unlimited"],
                "is_unlimited": plan_info["is_unlimited"]
            }
    except urllib.error.HTTPError as err:
        err_body = err.read().decode("utf-8")
        error_desc = err_body
        error_code = f"HTTP_{err.code}"
        try:
            err_json = json.loads(err_body)
            rzp_err = err_json.get("error", {})
            error_desc = rzp_err.get("description") or rzp_err.get("reason") or err_body
            error_code = rzp_err.get("code") or error_code
        except Exception:
            pass
        logger.error(f"Razorpay API rejected order creation ({error_code}): {error_desc}")
        raise HTTPException(
            status_code=502,
            detail=f"Payment gateway order creation failed: {error_desc}"
        )
    except Exception as exc:
        logger.error(f"Failed to create Razorpay order: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Unable to initialize payment order with gateway. Please try again."
        )

@router.post("/api/payments/verify")
@router.post("/api/subscriptions/verify")
async def verify_payment_order(
    payload: VerifyPaymentRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Verifies payment signature and atomically activates the subscription.
    Enforces exact pricing, correct bill limits (Basic 50, Standard 150, Premium Unlimited),
    and prevents duplicate activation (idempotent).
    """
    key_id = (getattr(settings, "razorpay_key_id", None) or "").strip()
    key_secret = (getattr(settings, "razorpay_key_secret", None) or "").strip()

    payment_id = (payload.razorpay_payment_id or "").strip()
    order_id = (payload.razorpay_order_id or "").strip()
    signature = (payload.razorpay_signature or "").strip()

    if not payment_id:
        raise HTTPException(status_code=400, detail="Payment ID (razorpay_payment_id) is required.")

    # 1. Cryptographic HMAC-SHA256 signature verification if signature is provided
    if order_id and signature:
        if not key_secret:
            raise HTTPException(status_code=503, detail="Gateway secret is not configured on the backend server.")

        message = f"{order_id}|{payment_id}"
        generated_signature = hmac.new(
            key_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(generated_signature, signature):
            logger.warning(f"Payment verification failed: invalid signature for payment {payment_id}, order {order_id}")
            raise HTTPException(status_code=400, detail="Invalid payment signature. Payment verification failed.")

    # 2. Server-side payment entity inspection via Razorpay REST API
    rzp_entity = _fetch_razorpay_payment(payment_id, key_id, key_secret) if (key_id and key_secret) else None
    captured_at_utc = datetime.now(timezone.utc)
    payment_status = "captured"
    amount_paise = None

    if rzp_entity:
        payment_status = rzp_entity.get("status", "captured")
        amount_paise = rzp_entity.get("amount")
        if payment_status not in ("captured", "authorized"):
            raise HTTPException(
                status_code=400,
                detail=f"Payment status is '{payment_status}'. Only successfully captured payments can activate a subscription."
            )
        captured_ts = rzp_entity.get("captured_at") or rzp_entity.get("created_at")
        if captured_ts:
            try:
                captured_at_utc = datetime.fromtimestamp(captured_ts, timezone.utc)
            except Exception:
                pass

    # Resolve plan details
    plan_info = get_plan_by_id(payload.planId)
    if not amount_paise:
        amount_paise = plan_info["price_paise"]

    verified_at_utc = datetime.now(timezone.utc)
    user_name = payload.customer_name or current_user.full_name or current_user.email
    user_email = payload.customer_email or current_user.email

    activation_res = db.process_verified_membership_payment(
        user_id=current_user.id,
        user_email=user_email,
        user_name=user_name,
        payment_id=payment_id,
        order_id=order_id or "direct_order",
        amount_paise=amount_paise,
        payment_status=payment_status,
        captured_at_utc=captured_at_utc,
        verified_at_utc=verified_at_utc,
        plan_id=plan_info["id"],
        customer_phone=payload.customer_phone
    )

    return {
        "ok": True,
        "success": True,
        **activation_res
    }

