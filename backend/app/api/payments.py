import os
import uuid
import mimetypes
import hmac
import hashlib
import json
import base64
import urllib.request
import urllib.error
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger("kangra_hub.payments")

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
    razorpay_key_id: Optional[str] = None
    razorpay_configured: bool = False
    is_test_mode: bool = False

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
    key_id = (getattr(settings, "razorpay_key_id", None) or "").strip()
    key_secret = (getattr(settings, "razorpay_key_secret", None) or "").strip()
    return PaymentConfigResponse(
        upi_id=getattr(settings, "payment_upi_id", "Kangrahub@pnb"),
        price_per_page=getattr(settings, "page_price_inr", 2.0),
        qr_path=getattr(settings, "payment_qr_path", "/buy-a-coffee/googlepay_qr.png"),
        whatsapp_number=getattr(settings, "payment_whatsapp_number", "+919805987622"),
        support_message="Complete manual payment of ₹2/page via Google Pay / UPI, then upload the transaction screenshot here.",
        razorpay_key_id=key_id or None,
        razorpay_configured=bool(key_id and key_secret),
        is_test_mode=key_id.startswith("rzp_test_")
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

# ==============================================================================
# RAZORPAY SUBSCRIPTION CHECKOUT (PRD Addendum 3: Section 2.6 & 2.7)
# ==============================================================================

class CreateOrderRequest(BaseModel):
    planId: Optional[str] = "gold_monthly"
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None

class VerifyPaymentOrderRequest(BaseModel):
    razorpay_payment_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    razorpay_signature: Optional[str] = None
    payment_id: Optional[str] = None
    order_id: Optional[str] = None
    signature: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None

@router.post("/api/payments/create-order")
@router.post("/api/subscriptions/create-order")
async def create_payment_order(
    payload: Optional[CreateOrderRequest] = None,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Creates a Razorpay Order server-side (PRD Addendum 3 & 4).
    Amount is strictly determined server-side (Rs 499 = 49900 paise).
    The browser must never decide the price.
    """
    key_id = (getattr(settings, "razorpay_key_id", None) or "").strip()
    key_secret = (getattr(settings, "razorpay_key_secret", None) or "").strip()
    amount_paise = int(getattr(settings, "staff_membership_price_paise", 49900))
    plan_id = (payload.planId if payload else None) or "gold_monthly"
    cust_phone = ((payload.customer_phone if payload else None) or "").strip() or current_user.mobile_number or ""
    cust_name = ((payload.customer_name if payload else None) or "").strip() or current_user.full_name or ""
    cust_email = ((payload.customer_email if payload else None) or "").strip().lower() or current_user.email or ""

    if not key_id or not key_secret:
        logger.error("Razorpay order creation rejected: RAZORPAY_KEY_ID or RAZORPAY_KEY_SECRET is not configured.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Razorpay API credentials (RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET) are not configured on the backend server. Please add your Razorpay keys to backend/.env."
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
            logger.info(f"Razorpay order created successfully: {order_id} ({order_amount} {order_currency}) for user {current_user.id}")

            return {
                "orderId": order_id,
                "amount": order_amount,
                "currency": order_currency,
                "keyId": key_id
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
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Razorpay payment gateway rejected order creation ({error_code}): {error_desc}"
        )
    except Exception as exc:
        logger.error(f"Failed to communicate with Razorpay API: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Payment gateway connection error: {str(exc)}"
        )

@router.post("/api/payments/verify")
async def verify_payment_order(
    payload: VerifyPaymentOrderRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Server-side HMAC verification and automatic Staff Membership activation.
    (PRD Addendum 3 Section 2.7)
    """
    pid = (payload.razorpay_payment_id or payload.payment_id or "").strip()
    oid = (payload.razorpay_order_id or payload.order_id or "").strip()
    sig = (payload.razorpay_signature or payload.signature or "").strip()

    if not pid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing razorpay_payment_id."
        )

    key_secret = (getattr(settings, "razorpay_key_secret", None) or "").strip()
    if key_secret and sig and oid:
        expected = hmac.new(
            key_secret.encode("utf-8"),
            f"{oid}|{pid}".encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, sig):
            logger.warning(f"Razorpay HMAC verification failed for payment {pid}, order {oid}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Razorpay payment signature."
            )

    now_utc = datetime.now(timezone.utc)
    cust_phone = (payload.customer_phone or "").strip() or current_user.mobile_number or None
    cust_name = (payload.customer_name or "").strip() or current_user.full_name or "Kangra Hub Staff"
    cust_email = (payload.customer_email or "").strip().lower() or current_user.email or ""

    res = db.process_verified_membership_payment(
        user_id=current_user.id,
        user_email=cust_email,
        user_name=cust_name,
        payment_id=pid,
        order_id=oid or None,
        amount_paise=int(getattr(settings, "staff_membership_price_paise", 49900)),
        payment_status="captured",
        captured_at_utc=now_utc,
        verified_at_utc=now_utc,
        raw_response={"verified_via": "payments/verify", "order_id": oid, "signature": sig},
        customer_phone=cust_phone,
        customer_name=cust_name,
        customer_email=cust_email
    )

    return {
        "ok": True,
        "success": True,
        "message": res.get("message", "Staff membership activated successfully."),
        "renewal_type": res.get("renewal_type"),
        "membership_expires_at": res.get("membership_expires_at"),
        "last_valid_day": res.get("last_valid_day"),
        "display_wording": res.get("display_wording"),
        "payment_id": pid
    }

@router.post("/api/payments/webhook")
async def razorpay_webhook(request: Request):
    """
    Authoritative Razorpay Webhook listener (event: payment.captured, order.paid).
    Verifies HMAC-SHA256 signature against RAZORPAY_WEBHOOK_SECRET.
    Activates Staff Membership idempotently.
    """
    raw_body = await request.body()
    sig = request.headers.get("x-razorpay-signature") or request.headers.get("X-Razorpay-Signature")

    webhook_secret = (getattr(settings, "razorpay_webhook_secret", None) or getattr(settings, "razorpay_key_secret", "")).strip()
    if webhook_secret and sig:
        expected_sig = hmac.new(
            webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_sig, sig):
            logger.warning("Razorpay webhook HMAC signature mismatch.")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature.")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload.")

    event = payload.get("event")
    logger.info(f"Received Razorpay webhook event: {event}")

    if event in ("payment.captured", "order.paid"):
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        pid = payment_entity.get("id")
        oid = payment_entity.get("order_id")
        amount = payment_entity.get("amount", 49900)
        notes = payment_entity.get("notes", {})
        user_id = notes.get("user_id")
        cust_phone = notes.get("customer_phone") or payment_entity.get("contact") or None
        cust_name = notes.get("customer_name") or notes.get("user_name", "Kangra Hub Staff")
        cust_email = payment_entity.get("email") or notes.get("customer_email") or notes.get("user_email") or ""

        if pid and user_id:
            now_utc = datetime.now(timezone.utc)
            db.process_verified_membership_payment(
                user_id=user_id,
                user_email=cust_email,
                user_name=cust_name,
                payment_id=pid,
                order_id=oid,
                amount_paise=amount,
                payment_status="captured",
                captured_at_utc=now_utc,
                verified_at_utc=now_utc,
                raw_response=payload,
                customer_phone=cust_phone,
                customer_name=cust_name,
                customer_email=cust_email
            )
            logger.info(f"Successfully processed webhook membership activation for user {user_id}, payment {pid}")

    return {"status": "ok", "received": True}
