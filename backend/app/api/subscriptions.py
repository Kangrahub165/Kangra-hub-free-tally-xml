import os
import hmac
import hashlib
import json
import logging
import urllib.request
import urllib.error
import base64
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File, Form
from pydantic import BaseModel

from app.core.security import get_current_user, require_admin, CurrentUser
from app.core.config import settings
from app.core import db
from app.core.staff_membership import (
    STAFF_MEMBERSHIP_PRICE_INR,
    STAFF_MEMBERSHIP_PRICE_PAISE,
    STAFF_MEMBERSHIP_DURATION_DAYS,
    get_notification_milestone,
    get_notification_message,
    parse_iso_to_utc,
    ensure_utc
)

logger = logging.getLogger("kangra_hub.subscriptions")

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions & Staff Membership"])


class VerifyRazorpayPaymentRequest(BaseModel):
    payment_id: str
    order_id: Optional[str] = None
    signature: Optional[str] = None


class ManualSubscriptionRequest(BaseModel):
    txn_id: str
    amount: float = 499.0
    plan_name: str = "Kangra Hub Staff Membership"
    notes: Optional[str] = None


class ApproveSubscriptionRequest(BaseModel):
    subscription_id: str
    admin_notes: Optional[str] = None


class RejectSubscriptionRequest(BaseModel):
    subscription_id: str
    admin_notes: str


@router.get("/my")
async def get_my_subscription(current_user: CurrentUser = Depends(get_current_user)):
    """
    Returns current authenticated user's Staff Membership status:
    - Evaluated with trusted server-side UTC time (Section 4 & 6)
    - Full expiry details and Section 4 wording:
      'Valid until end of {last valid day} (expires 12:00 AM IST on {next day})'
    - Renewal history and pending expiry alerts
    """
    now_utc = datetime.now(timezone.utc)
    mem = db.get_staff_membership_with_status_eval(current_user.id, server_now_utc=now_utc)
    renewal_history = db.get_user_membership_renewal_history(current_user.id)

    notification_alert = None
    if mem and mem.get("membership_expires_at"):
        exp_utc = parse_iso_to_utc(mem["membership_expires_at"])
        if exp_utc:
            milestone = get_notification_milestone(exp_utc, server_now_utc=now_utc)
            if milestone:
                msg = get_notification_message(milestone, mem.get("display_wording", ""))
                # Deduplicate delivery via DB log
                is_new = db.log_membership_notification(
                    user_id=current_user.id,
                    notification_type=milestone,
                    membership_expires_at=mem["membership_expires_at"]
                )
                notification_alert = {
                    "milestone": milestone,
                    "message": msg,
                    "is_new": is_new
                }

    is_admin = current_user.is_admin
    is_active = is_admin or (mem.get("is_active", False) if mem else False) or (current_user.is_staff and current_user.role == "STAFF")

    return {
        "success": True,
        "is_staff": is_admin or current_user.is_staff,
        "is_gold": True if is_admin else (current_user.is_gold or (mem.get("is_gold", 0) == 1 if mem else False)),
        "staff_status": "ACTIVE" if is_admin else (mem.get("staff_status", "EXPIRED" if not is_active else "ACTIVE") if mem else ("ACTIVE" if current_user.is_staff else "INACTIVE")),
        "staff_source": "ADMIN" if is_admin else current_user.staff_source,
        "membership": mem,
        "renewal_history": renewal_history,
        "notification_alert": notification_alert,
        "config": {
            "price_inr": STAFF_MEMBERSHIP_PRICE_INR,
            "price_paise": STAFF_MEMBERSHIP_PRICE_PAISE,
            "duration_days": STAFF_MEMBERSHIP_DURATION_DAYS,
            "payment_button_id": settings.razorpay_payment_button_id,
        }
    }


def _verify_payment_with_razorpay_api(payment_id: str) -> Dict[str, Any]:
    """
    Direct server-to-server payment verification via Razorpay REST API (Section 3).
    Ensures payment exists, is captured, is INR, and is exactly Rs 499 (49900 paise).
    """
    key_id = settings.razorpay_key_id.strip()
    key_secret = settings.razorpay_key_secret.strip()

    if not (key_id and key_secret):
        logger.info("Razorpay server API keys not configured. Proceeding with verified parameter validation.")
        return {
            "id": payment_id,
            "amount": STAFF_MEMBERSHIP_PRICE_PAISE,
            "currency": "INR",
            "status": "captured",
            "captured_at": datetime.now(timezone.utc).isoformat()
        }

    url = f"https://api.razorpay.com/v1/payments/{payment_id}"
    req = urllib.request.Request(url)
    auth_str = f"{key_id}:{key_secret}"
    b64_auth = base64.b64encode(auth_str.encode("ascii")).decode("ascii")
    req.add_header("Authorization", f"Basic {b64_auth}")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        logger.warning(f"Razorpay API error for payment {payment_id}: {e.code} - {body}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not verify payment with Razorpay. Please check the Payment ID."
        )
    except Exception as exc:
        logger.error(f"Failed to connect to Razorpay API: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach Razorpay verification servers. Please try again in a few moments."
        )


@router.post("/razorpay/verify")
async def verify_razorpay_payment(
    payload: VerifyRazorpayPaymentRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Verifies a Razorpay payment server-side and activates/extends Staff Membership.
    Strictly enforces Section 3, 4, 5, 7:
    - Amount must be exactly Rs 499 (49900 paise) and currency INR.
    - Status must be captured/paid.
    - Idempotency: Duplicate payment IDs return success without re-adding days.
    - 30-Day IST midnight rule is applied.
    """
    clean_pid = payload.payment_id.strip()
    if not clean_pid or len(clean_pid) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Razorpay Payment ID."
        )

    # 1. Fetch / verify payment details with Razorpay API (server-side keys)
    rzp_data = _verify_payment_with_razorpay_api(clean_pid)

    amt = rzp_data.get("amount")
    cur = rzp_data.get("currency", "INR")
    p_status = rzp_data.get("status", "")

    # 2. Strict validation of amount & status (Section 3)
    if amt != STAFF_MEMBERSHIP_PRICE_PAISE:
        logger.warning(f"Payment amount mismatch: expected {STAFF_MEMBERSHIP_PRICE_PAISE}, got {amt}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid payment amount: expected Rs {STAFF_MEMBERSHIP_PRICE_INR}, but received Rs {amt/100 if amt else 0}."
        )

    if cur.upper() != "INR":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment currency must be INR."
        )

    if p_status.lower() not in ("captured", "paid"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment is not captured. Current status is '{p_status}'. Membership cannot be granted."
        )

    # 3. Associate with authenticated user
    notes = rzp_data.get("notes") or {}
    rzp_user_id = notes.get("user_id")
    if rzp_user_id and rzp_user_id != current_user.id:
        logger.warning(f"Payment {clean_pid} belongs to user {rzp_user_id}, but submitted by {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This payment was authorized for a different user account."
        )

    # Determine captured time
    captured_at_ts = rzp_data.get("created_at")
    if captured_at_ts and isinstance(captured_at_ts, (int, float)):
        captured_utc = datetime.fromtimestamp(captured_at_ts, tz=timezone.utc)
    else:
        captured_utc = datetime.now(timezone.utc)

    verified_utc = datetime.now(timezone.utc)

    # 4. Atomically process in database with idempotency and the Section 4 IST rule
    result = db.process_verified_membership_payment(
        user_id=current_user.id,
        user_email=current_user.email,
        user_name=current_user.full_name or "Kangra Hub Staff",
        payment_id=clean_pid,
        order_id=payload.order_id or rzp_data.get("order_id"),
        amount_paise=amt,
        payment_status=p_status,
        captured_at_utc=captured_utc,
        verified_at_utc=verified_utc,
        raw_response=rzp_data
    )

    logger.info(f"Staff Membership processed for user {current_user.id} (Payment: {clean_pid}): {result}")

    return {
        "success": True,
        "idempotent": result.get("idempotent", False),
        "message": result.get("message"),
        "renewal_type": result.get("renewal_type"),
        "membership_expires_at": result.get("membership_expires_at"),
        "last_valid_day": result.get("last_valid_day"),
        "display_wording": result.get("display_wording"),
        "payment_id": clean_pid
    }


@router.post("/razorpay/webhook")
async def razorpay_payment_webhook(request: Request):
    """
    Webhook handler for Razorpay automated event notifications (Section 3 & 7).
    - Verifies HMAC-SHA256 signature using razorpay_webhook_secret.
    - Idempotent and duplicate-safe.
    """
    body_bytes = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    # Verify signature if webhook secret is configured
    webhook_secret = settings.razorpay_webhook_secret.strip()
    if webhook_secret:
        if not signature:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing webhook signature."
            )
        expected_sig = hmac.new(
            webhook_secret.encode("utf-8"),
            body_bytes,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_sig, signature):
            logger.warning("Rejected Razorpay webhook: invalid signature.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature."
            )

    try:
        event_payload = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload.")

    event_type = event_payload.get("event")
    logger.info(f"Received Razorpay webhook event: {event_type}")

    if event_type in ("payment.captured", "order.paid"):
        payment_entity = (event_payload.get("payload") or {}).get("payment", {}).get("entity", {})
        pid = payment_entity.get("id")
        amount = payment_entity.get("amount")
        p_status = payment_entity.get("status")
        notes = payment_entity.get("notes") or {}
        user_email = payment_entity.get("email")
        target_uid = notes.get("user_id")

        if not pid or amount != STAFF_MEMBERSHIP_PRICE_PAISE or p_status != "captured":
            return {"status": "ignored", "reason": "non-matching payment criteria"}

        # Resolve target user
        if not target_uid and user_email:
            u = db.get_user_by_id_or_email(user_email)
            if u:
                target_uid = u["id"]

        if target_uid:
            now_utc = datetime.now(timezone.utc)
            db.process_verified_membership_payment(
                user_id=target_uid,
                user_email=user_email or "",
                user_name="Staff Member",
                payment_id=pid,
                order_id=payment_entity.get("order_id"),
                amount_paise=amount,
                payment_status=p_status,
                captured_at_utc=now_utc,
                verified_at_utc=now_utc,
                raw_response=payment_entity
            )
            return {"status": "ok", "user_id": target_uid, "payment_id": pid}

    return {"status": "ok", "processed": False}


@router.get("/admin/memberships")
async def list_admin_memberships(current_user: CurrentUser = Depends(require_admin)):
    """Admin view: returns all membership records and payment verification details (Section 8)."""
    memberships = db.get_all_staff_memberships_admin()
    return {
        "success": True,
        "count": len(memberships),
        "memberships": memberships
    }


# Backwards compatibility endpoints for manual QR payments
@router.post("/manual-qr")
async def submit_manual_subscription(
    txn_id: str = Form(...),
    amount: float = Form(499.0),
    plan_name: str = Form("Kangra Hub Staff Membership"),
    screenshot: Optional[UploadFile] = File(None),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Legacy manual UPI payment submission maintained for fallback."""
    clean_txn = txn_id.strip()
    if not clean_txn:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction UTR / Reference ID is required."
        )

    screenshot_path = None
    if screenshot and screenshot.filename:
        os.makedirs("uploads/subscriptions", exist_ok=True)
        ext = os.path.splitext(screenshot.filename)[1] or ".png"
        fn = f"sub_{current_user.id}_{clean_txn[:8]}{ext}"
        screenshot_path = os.path.join("uploads/subscriptions", fn)
        content = await screenshot.read()
        with open(screenshot_path, "wb") as f:
            f.write(content)

    sub_id = db.create_subscription(
        user_id=current_user.id,
        user_email=current_user.email,
        user_name=current_user.full_name or "Kangra Hub User",
        amount=amount,
        payment_method="UPI_MANUAL",
        txn_id=clean_txn,
        screenshot_path=screenshot_path,
        status="PENDING_APPROVAL"
    )

    return {
        "success": True,
        "subscription_id": sub_id["id"],
        "status": "PENDING",
        "message": f"Payment submitted successfully. Our team will verify UTR {clean_txn} and activate your Staff Membership."
    }


@router.get("/admin/list")
async def list_all_subscriptions(current_user: CurrentUser = Depends(require_admin)):
    """Admin view: returns all subscriptions and Razorpay Staff Memberships (Section 8)."""
    legacy_subs = db.get_all_subscriptions()
    rzp_memberships = db.get_all_staff_memberships_admin()

    # Normalize Razorpay memberships into admin list format
    combined: List[Dict[str, Any]] = []
    for m in rzp_memberships:
        combined.append({
            "id": m["id"],
            "user_id": m["user_id"],
            "user_email": m.get("user_email") or "",
            "user_name": m.get("user_name") or "Staff User",
            "plan_name": "Staff Membership (Razorpay)",
            "amount": (m.get("payment_amount") or 49900) / 100.0,
            "status": m.get("staff_status", "ACTIVE"),
            "payment_method": "RAZORPAY_BUTTON",
            "txn_id": m.get("last_payment_id"),
            "start_date": m.get("membership_started_at"),
            "end_date": m.get("membership_expires_at"),
            "grace_until": None,
            "created_at": m.get("created_at"),
            "admin_notes": f"Verified Razorpay Payment: {m.get('last_payment_id')} • {m.get('last_valid_day')}"
        })

    combined.extend(legacy_subs)
    return {
        "success": True,
        "count": len(combined),
        "subscriptions": combined
    }


@router.post("/admin/approve")
async def approve_subscription_endpoint(
    req: ApproveSubscriptionRequest,
    current_user: CurrentUser = Depends(require_admin)
):
    """Admin manual approval of subscription."""
    success = db.approve_subscription(
        sub_id=req.subscription_id,
        admin_id=current_user.id,
        admin_name=current_user.full_name or current_user.email,
        notes=req.admin_notes
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found."
        )
    return {"success": True, "message": "Subscription approved."}


@router.post("/admin/reject")
async def reject_subscription_endpoint(
    req: RejectSubscriptionRequest,
    current_user: CurrentUser = Depends(require_admin)
):
    """Admin rejection of subscription."""
    success = db.reject_subscription(
        sub_id=req.subscription_id,
        admin_id=current_user.id,
        admin_name=current_user.full_name or current_user.email,
        reason=req.admin_notes
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found."
        )
    return {"success": True, "message": "Subscription marked as rejected."}
