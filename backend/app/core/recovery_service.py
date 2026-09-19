import uuid
import logging
import hashlib
import hmac
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from app.core.audit_service import audit_service
from app.core.smtp_service import smtp_service

logger = logging.getLogger("kangra_hub.recovery")

# Secret salt for recovery OTP hashing
RECOVERY_OTP_SECRET = "kh_recovery_secret_salt_2026_tally"

class RecoveryRequest(BaseModel):
    id: str
    user_id: Optional[str] = None
    account_identifier: str
    known_email: Optional[str] = None
    known_mobile: Optional[str] = None
    requested_new_email: Optional[str] = None
    requested_new_mobile: Optional[str] = None
    reason: str
    identity_verification_info: Optional[str] = None
    # States: Pending | Under Review | Additional Verification Required | Approved | Rejected | Completed | Expired | Cancelled
    status: str = "Pending"
    submitted_at: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    decision_reason: Optional[str] = None
    notes: Optional[str] = None
    account_history: Dict[str, Any] = Field(default_factory=dict)

    # Step 1: Ownership cross-check
    step1_status: str = "PENDING"  # PENDING | PASSED | FAILED | ADDITIONAL_VERIFICATION_REQUIRED
    step1_notes: Optional[str] = None
    step1_verified_by: Optional[str] = None
    step1_verified_at: Optional[str] = None

    # Step 2: New email verification
    proposed_new_email: Optional[str] = None
    step2_status: str = "PENDING"  # PENDING | CODE_SENT | VERIFIED | FAILED
    step2_otp_hash: Optional[str] = None
    step2_otp_expires_at: Optional[str] = None
    step2_verified_at: Optional[str] = None
    completed_at: Optional[str] = None


class AccountRecoveryService:
    """
    Manages controlled user account recovery when primary email is lost.
    Enforces two independent verification steps:
      Step 1: Admin ownership cross-check against account history.
      Step 2: New email verification via secure OTP dispatch.
    Only when both Step 1 is PASSED and Step 2 is VERIFIED can the email change be completed.
    """

    def __init__(self):
        self._requests: Dict[str, RecoveryRequest] = {
            "rec-sample-01": RecoveryRequest(
                id="rec-sample-01",
                user_id="usr-demo-1",
                account_identifier="customer@example.com",
                known_email="customer@example.com",
                known_mobile="+919876543211",
                requested_new_email="rajesh.updated@example.com",
                requested_new_mobile="+919876543299",
                reason="Lost access to registered company email domain. Need to update to verified personal address.",
                identity_verification_info="Registered under name Rajesh Sharma, regularly converts SBI statements.",
                status="Pending",
                submitted_at=datetime.now(timezone.utc).isoformat(),
                account_history={
                    "user_id": "usr-demo-1",
                    "full_name": "Rajesh Sharma",
                    "email": "customer@example.com",
                    "mobile": "+919876543211",
                    "account_status": "ACTIVE",
                    "registered_at": "2024-01-15T10:00:00Z",
                    "last_login": datetime.now(timezone.utc).isoformat(),
                    "total_conversions": 14,
                    "successful_conversions": 14
                },
                step1_status="PENDING",
                step2_status="PENDING"
            )
        }

    def _hash_otp(self, otp: str) -> str:
        return hmac.new(
            RECOVERY_OTP_SECRET.encode("utf-8"),
            otp.strip().encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def submit_request(
        self,
        account_identifier: str,
        reason: str,
        user_id: Optional[str] = None,
        known_email: Optional[str] = None,
        known_mobile: Optional[str] = None,
        requested_new_email: Optional[str] = None,
        requested_new_mobile: Optional[str] = None,
        identity_verification_info: Optional[str] = None,
        account_history: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> RecoveryRequest:
        req_id = f"rec-{uuid.uuid4().hex[:8]}"
        req = RecoveryRequest(
            id=req_id,
            user_id=user_id,
            account_identifier=account_identifier.strip(),
            known_email=known_email.strip().lower() if known_email else None,
            known_mobile=known_mobile.strip() if known_mobile else None,
            requested_new_email=requested_new_email.strip().lower() if requested_new_email else None,
            requested_new_mobile=requested_new_mobile.strip() if requested_new_mobile else None,
            proposed_new_email=requested_new_email.strip().lower() if requested_new_email else None,
            reason=reason.strip(),
            identity_verification_info=identity_verification_info.strip() if identity_verification_info else None,
            status="Pending",
            submitted_at=datetime.now(timezone.utc).isoformat(),
            account_history=account_history or {},
            step1_status="PENDING",
            step2_status="PENDING"
        )
        self._requests[req_id] = req

        audit_service.log_event(
            action="RECOVERY_REQUESTED",
            user_id=account_identifier,
            target_type="ACCOUNT_RECOVERY",
            target_id=req_id,
            ip_address=ip_address,
            metadata={
                "reason": reason,
                "requested_new_email": requested_new_email,
                "requested_new_mobile": requested_new_mobile
            }
        )
        return req

    def get_request(self, request_id: str) -> Optional[RecoveryRequest]:
        return self._requests.get(request_id)

    def list_requests(self, status: Optional[str] = None) -> List[RecoveryRequest]:
        reqs = list(self._requests.values())
        if status and status.upper() != "ALL":
            reqs = [r for r in reqs if r.status.upper() == status.upper() or r.status == status]
        return sorted(reqs, key=lambda x: x.submitted_at, reverse=True)

    def review_step1(
        self,
        request_id: str,
        admin_email: str,
        result: str,  # "PASSED" | "FAILED" | "ADDITIONAL_VERIFICATION_REQUIRED"
        notes: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> RecoveryRequest:
        req = self._requests.get(request_id)
        if not req:
            raise ValueError(f"Recovery request '{request_id}' not found.")

        normalized = result.upper().strip()
        now_iso = datetime.now(timezone.utc).isoformat()
        req.step1_verified_by = admin_email
        req.step1_verified_at = now_iso
        req.step1_notes = notes.strip() if notes else None

        if normalized == "PASSED":
            req.step1_status = "PASSED"
            req.status = "Under Review"
            audit_action = "RECOVERY_STEP1_PASSED"
        elif normalized == "FAILED":
            req.step1_status = "FAILED"
            req.status = "Rejected"
            req.decision_reason = notes or "Account ownership verification failed."
            audit_action = "RECOVERY_STEP1_FAILED"
        elif normalized in ("ADDITIONAL_VERIFICATION_REQUIRED", "MORE_INFO"):
            req.step1_status = "ADDITIONAL_VERIFICATION_REQUIRED"
            req.status = "Additional Verification Required"
            req.decision_reason = notes or "Additional ownership verification information required."
            audit_action = "RECOVERY_STEP1_MORE_INFO_REQUESTED"
        else:
            raise ValueError(f"Invalid Step 1 result: '{result}'. Must be PASSED, FAILED, or ADDITIONAL_VERIFICATION_REQUIRED.")

        audit_service.log_event(
            action=audit_action,
            user_id=admin_email,
            target_type="ACCOUNT_RECOVERY",
            target_id=request_id,
            result="SUCCESS",
            reason=notes or "",
            ip_address=ip_address,
            metadata={"step1_status": req.step1_status, "request_status": req.status}
        )
        return req

    def initiate_step2(
        self,
        request_id: str,
        admin_email: str,
        proposed_new_email: str,
        existing_emails: Optional[List[str]] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Triggers Step 2: Verification code dispatch to proposed new email.
        Enforces:
          1. Step 1 ownership verification MUST be completed and PASSED.
          2. Proposed new email must not already belong to an existing user.
        """
        req = self._requests.get(request_id)
        if not req:
            raise ValueError(f"Recovery request '{request_id}' not found.")

        if req.step1_status != "PASSED":
            raise ValueError("Step 1 ownership verification must be completed and PASSED before initiating Step 2.")

        clean_new_email = proposed_new_email.strip().lower()
        if "@" not in clean_new_email or "." not in clean_new_email:
            raise ValueError("Please provide a valid proposed new email address.")

        # Check for duplicate email across platform
        if existing_emails and clean_new_email in [e.lower() for e in existing_emails]:
            raise ValueError("This email address is already associated with another account.")

        # Generate 6-digit secure numeric OTP
        otp_code = f"{secrets.randbelow(900000) + 100000}"
        expiry = datetime.now(timezone.utc) + timedelta(minutes=15)

        req.proposed_new_email = clean_new_email
        req.requested_new_email = clean_new_email
        req.step2_status = "CODE_SENT"
        req.step2_otp_hash = self._hash_otp(otp_code)
        req.step2_otp_expires_at = expiry.isoformat()

        audit_service.log_event(
            action="RECOVERY_STEP2_CODE_SENT",
            user_id=admin_email,
            target_type="ACCOUNT_RECOVERY",
            target_id=request_id,
            ip_address=ip_address,
            metadata={"proposed_new_email": clean_new_email}
        )

        # Dispatch via SMTP if available
        if smtp_service.is_configured():
            try:
                subject = "Kangra Hub — Verify Your New Account Email Address"
                body = (
                    f"Hello,\n\n"
                    f"A request to update your Kangra Hub account email address was initiated (Ref: {request_id}).\n\n"
                    f"Your 6-digit verification code is:\n\n"
                    f"    {otp_code}\n\n"
                    f"This code is valid for 15 minutes. If you did not request this, please contact support immediately.\n\n"
                    f"Kangra Hub Security Team"
                )
                html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 32px 16px; color: #0f172a;">
  <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 20px; border: 1px solid #e2e8f0; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <div style="margin-bottom: 24px; display: table; width: 100%;">
      <div style="display: table-cell; vertical-align: middle; width: 44px;">
        <img src="https://ueslsgzfixvkaomgogan.supabase.co/storage/v1/object/public/Logo/logo.png" alt="Kangra Hub" width="44" height="44" style="border-radius: 10px; display: block;" />
      </div>
      <div style="display: table-cell; vertical-align: middle; padding-left: 12px;">
        <h1 style="font-size: 20px; font-weight: 800; color: #0f172a; margin: 0 0 2px 0;">Kangra Hub</h1>
        <div style="font-size: 11px; font-weight: 700; color: #2563eb; text-transform: uppercase; letter-spacing: 0.05em;">Account Recovery</div>
      </div>
    </div>
    <div style="font-size: 14px; color: #334155; line-height: 1.6; margin-bottom: 20px;">
      A request to update your Kangra Hub account email address was initiated (Ref: <code>{request_id}</code>). Your verification code is:
    </div>
    <div style="background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 12px; padding: 18px 24px; text-align: center; margin: 20px 0;">
      <span style="font-family: monospace, Courier, sans-serif; font-size: 32px; font-weight: 800; letter-spacing: 8px; color: #1e3a8a; display: inline-block;">
        {otp_code}
      </span>
    </div>
    <div style="font-size: 12px; color: #64748b; line-height: 1.5; margin-top: 24px; border-top: 1px solid #f1f5f9; padding-top: 16px;">
      This code is valid for 15 minutes. If you did not request this update, please contact support immediately.
    </div>
  </div>
</body>
</html>"""
                smtp_service.send_email(to_email=clean_new_email, subject=subject, body_text=body, html_content=html_body)
            except Exception as e:
                logger.warning(f"Unable to send recovery email to {clean_new_email}: {e}")

        logger.info(f"Recovery Step 2 code generated for {clean_new_email} (Ref: {request_id})")

        return {
            "success": True,
            "message": f"Verification code sent to {clean_new_email}.",
            "request_id": request_id,
            "proposed_new_email": clean_new_email,
            "expires_at": req.step2_otp_expires_at,
            # In development test environments without SMTP, expose code safely for automated testing
            "dev_code": otp_code if not smtp_service.is_configured() else None
        }

    def verify_step2(
        self,
        request_id: str,
        entered_otp: str,
        ip_address: Optional[str] = None
    ) -> RecoveryRequest:
        """
        Verifies the OTP submitted for the proposed new email.
        """
        req = self._requests.get(request_id)
        if not req:
            raise ValueError(f"Recovery request '{request_id}' not found.")

        if req.step2_status not in ("CODE_SENT", "VERIFIED"):
            raise ValueError("Step 2 verification code has not been dispatched yet.")

        if not req.step2_otp_hash or not req.step2_otp_expires_at:
            raise ValueError("No active verification code found for this request.")

        # Check expiration
        expires_at = datetime.fromisoformat(req.step2_otp_expires_at)
        if datetime.now(timezone.utc) > expires_at:
            req.step2_status = "FAILED"
            raise ValueError("The verification code has expired. Please request a new code.")

        entered_hash = self._hash_otp(entered_otp.strip())
        if not hmac.compare_digest(entered_hash, req.step2_otp_hash):
            raise ValueError("Incorrect verification code. Please check and try again.")

        now_iso = datetime.now(timezone.utc).isoformat()
        req.step2_status = "VERIFIED"
        req.step2_verified_at = now_iso
        req.status = "Approved"

        audit_service.log_event(
            action="RECOVERY_STEP2_VERIFIED",
            user_id=req.proposed_new_email or "unknown",
            target_type="ACCOUNT_RECOVERY",
            target_id=request_id,
            ip_address=ip_address,
            metadata={"status": "VERIFIED"}
        )
        return req

    def complete_recovery(
        self,
        request_id: str,
        admin_email: str,
        existing_emails: Optional[List[str]] = None,
        ip_address: Optional[str] = None
    ) -> RecoveryRequest:
        """
        Completes recovery and approves email change.
        Strictly enforces:
          1. Step 1 ownership verification MUST be 'PASSED'.
          2. Step 2 new email verification MUST be 'VERIFIED'.
          3. Proposed new email MUST not belong to another existing account.
        """
        req = self._requests.get(request_id)
        if not req:
            raise ValueError(f"Recovery request '{request_id}' not found.")

        if req.step1_status != "PASSED":
            raise ValueError("Cannot complete email change: Step 1 ownership verification must be PASSED.")

        if req.step2_status != "VERIFIED":
            raise ValueError("Cannot complete email change: Step 2 new-email verification must be VERIFIED.")

        new_email = (req.proposed_new_email or req.requested_new_email or "").strip().lower()
        if not new_email:
            raise ValueError("Missing verified new email address.")

        if existing_emails and new_email in [e.lower() for e in existing_emails]:
            raise ValueError("This email address is already associated with another account.")

        now_iso = datetime.now(timezone.utc).isoformat()
        req.status = "Completed"
        req.completed_at = now_iso
        req.reviewed_by = admin_email
        req.reviewed_at = now_iso
        req.decision_reason = f"Account recovery successfully verified and completed by {admin_email}."

        audit_service.log_event(
            action="RECOVERY_COMPLETED",
            user_id=admin_email,
            target_type="ACCOUNT_RECOVERY",
            target_id=request_id,
            result="SUCCESS",
            ip_address=ip_address,
            metadata={
                "previous_email": req.known_email,
                "new_email": new_email,
                "completed_at": now_iso
            }
        )
        return req

    def reject_request(
        self,
        request_id: str,
        admin_email: str,
        reason: str,
        notes: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> RecoveryRequest:
        req = self._requests.get(request_id)
        if not req:
            raise ValueError(f"Recovery request '{request_id}' not found.")

        if not reason or not reason.strip():
            raise ValueError("A valid rejection reason is mandatory.")

        now_iso = datetime.now(timezone.utc).isoformat()
        req.status = "Rejected"
        req.reviewed_by = admin_email
        req.reviewed_at = now_iso
        req.decision_reason = reason.strip()
        req.notes = notes.strip() if notes else None

        audit_service.log_event(
            action="RECOVERY_REJECTED",
            user_id=admin_email,
            target_type="ACCOUNT_RECOVERY",
            target_id=request_id,
            reason=reason,
            ip_address=ip_address,
            metadata={"decision": "REJECTED", "notes": notes}
        )
        return req


recovery_service = AccountRecoveryService()
