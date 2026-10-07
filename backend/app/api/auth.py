import logging
import uuid
import os
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Request, Depends, status, UploadFile, File
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from app.core.config import settings
from app.core.otp_service import otp_service
from app.core.security import CurrentUser, get_current_user, require_admin

logger = logging.getLogger("kangra_hub.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])

class SendSignupOtpRequest(BaseModel):
    email: str
    mobile_number: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    channel: Optional[str] = "EMAIL"  # "EMAIL" or "SMS"

class VerifySignupOtpRequest(BaseModel):
    email: str
    otp: str
    mobile_number: Optional[str] = None
    channel: Optional[str] = "EMAIL"  # "EMAIL" or "SMS"
    password: Optional[str] = None
    full_name: Optional[str] = None

class ResendOtpRequest(BaseModel):
    destination: str
    channel: Optional[str] = "EMAIL"  # "EMAIL" or "SMS"

class UserLoginRequest(BaseModel):
    email: str
    password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class CheckEmailRequest(BaseModel):
    email: str
    mobile_number: Optional[str] = None

class SupabaseSignupInitiateRequest(BaseModel):
    email: str
    mobile_number: str
    full_name: str
    gender: Optional[str] = "Male"
    password: str

class VerifyEmailOtpRequest(BaseModel):
    email: str
    otp: str
    mobile_number: Optional[str] = None

class ResendEmailOtpRequest(BaseModel):
    email: str
    mobile_number: Optional[str] = None

@router.post("/check-email")
async def check_email(payload: CheckEmailRequest):
    """
    Checks whether an email address is already associated with an account.
    Returns existing or pending status with 10-minute active window.
    """
    from app.core.user_store import check_email_status
    clean_email = payload.email.strip().lower()
    return check_email_status(clean_email, payload.mobile_number)

@router.post("/signup/supabase-initiate")
async def supabase_signup_initiate(payload: SupabaseSignupInitiateRequest):
    """
    Initiates user signup via Supabase Auth with Email OTP verification.
    Enforces 10-minute OTP session recovery:
    - If user re-submits with same email and same mobile while existing OTP is valid (<= 10 min):
      recognizes pending unverified signup, DOES NOT send duplicate OTP, and returns active pending state.
    - If OTP has expired after 10 minutes:
      allows user to request fresh OTP with a new 10-minute validity period.
    """
    clean_email = payload.email.strip().lower()
    clean_phone = "".join(c for c in payload.mobile_number if c.isdigit())[-10:]
    
    if len(clean_phone) != 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid 10-digit mobile number."
        )

    # 1. Check if user already exists and is verified
    from app.core.user_store import check_email_status, get_active_pending_signup, register_pending_signup
    status_info = check_email_status(clean_email, clean_phone)
    if status_info.get("exists") and status_info.get("verified"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email address is already linked to an account."
        )

    # Masked email formatting for display
    parts = clean_email.split("@")
    u_part = parts[0]
    dom_part = parts[1] if len(parts) > 1 else ""
    masked_email = f"{u_part[0]}****{u_part[-1]}@{dom_part}" if len(u_part) > 2 else f"{u_part}***@{dom_part}"

    # 2. Check for active pending verification (Session Recovery)
    active_pending = get_active_pending_signup(clean_email)

    if active_pending:
        # Check if mobile matches
        pending_phone = active_pending.get("mobile_number") or ""
        if pending_phone and pending_phone != clean_phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A pending verification with a different mobile number is already in progress for this email address. Please use the original mobile number or wait until the current OTP expires."
            )

        # RECOVERY SUCCESS: Return existing pending session without sending duplicate OTP
        remaining_secs = active_pending.get("remaining_seconds", 0)
        logger.info(f"Recovered pending OTP verification session for {clean_email} ({remaining_secs}s remaining)")
        return {
            "success": True,
            "status": "PENDING_OTP_ACTIVE",
            "message": "An unverified signup is already pending. You can enter the OTP that was already sent to your email.",
            "email": clean_email,
            "mobile_number": clean_phone,
            "masked_email": masked_email,
            "remaining_seconds": remaining_secs,
            "expires_at": active_pending.get("otp_expires_at")
        }

    # 3. No active pending verification (or previously expired): Send new Supabase Auth OTP
    from app.core.supabase_service import SupabaseService
    if not SupabaseService.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable."
        )

    try:
        # Sign up user with Supabase Auth
        meta = {
            "full_name": payload.full_name.strip(),
            "mobile_number": f"+91{clean_phone}",
            "phone": f"+91{clean_phone}",
            "gender": payload.gender or "Male",
            "role": "USER"
        }
        SupabaseService.sign_up(
            email=clean_email,
            password=payload.password,
            metadata=meta
        )
    except Exception as err:
        err_msg = str(err)
        if "already registered" in err_msg.lower():
            # If user already registered in Supabase but unconfirmed, dispatch fresh OTP
            try:
                SupabaseService.resend_signup_email_otp(clean_email)
            except Exception as resend_err:
                logger.warning(f"Resend signup OTP error: {resend_err}")
        elif "rate limit" in err_msg.lower():
            logger.warning(f"Supabase rate limit for {clean_email}: {err_msg}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many verification emails requested. Please wait a few minutes before trying again."
            )
        else:
            logger.error(f"Supabase signup error for {clean_email}: {err_msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=err_msg
            )

    # 4. Register new 10-minute pending state
    new_pending = register_pending_signup(
        email=clean_email,
        full_name=payload.full_name.strip(),
        mobile_number=clean_phone,
        gender=payload.gender or "Male",
        validity_seconds=600  # Exactly 10 minutes
    )

    logger.info(f"Supabase signup OTP issued for {clean_email} (valid for 600s)")
    return {
        "success": True,
        "status": "OTP_SENT",
        "message": "Verification code sent to your email address.",
        "email": clean_email,
        "mobile_number": clean_phone,
        "masked_email": masked_email,
        "remaining_seconds": 600,
        "expires_at": new_pending["otp_expires_at"]
    }

@router.get("/signup/pending-status")
async def get_signup_pending_status(email: str, mobile_number: Optional[str] = None):
    """
    Checks active pending verification status for session recovery upon page reload or revisit.
    """
    clean_email = email.strip().lower()
    clean_phone = "".join(c for c in (mobile_number or "") if c.isdigit())[-10:] if mobile_number else ""

    from app.core.user_store import get_active_pending_signup
    active = get_active_pending_signup(clean_email)

    if not active:
        return {"active": False, "remaining_seconds": 0}

    # If mobile is provided, verify match
    pending_phone = active.get("mobile_number") or ""
    if clean_phone and pending_phone and clean_phone != pending_phone:
        return {"active": False, "remaining_seconds": 0, "reason": "MISMATCH"}

    parts = clean_email.split("@")
    u_part = parts[0]
    dom_part = parts[1] if len(parts) > 1 else ""
    masked_email = f"{u_part[0]}****{u_part[-1]}@{dom_part}" if len(u_part) > 2 else f"{u_part}***@{dom_part}"

    return {
        "active": True,
        "email": clean_email,
        "mobile_number": pending_phone,
        "full_name": active.get("full_name", ""),
        "masked_email": masked_email,
        "remaining_seconds": active.get("remaining_seconds", 0),
        "expires_at": active.get("otp_expires_at")
    }

@router.post("/signup/verify-email-otp")
async def verify_supabase_email_otp(payload: VerifyEmailOtpRequest):
    """
    Verifies Email OTP via Supabase Auth.
    Strictly enforces:
    - 10-minute validity window (rejects expired OTPs).
    - Email not marked as verified until Supabase confirms successful verification.
    - Creates authenticated session upon confirmed verification.
    """
    clean_email = payload.email.strip().lower()
    clean_otp = payload.otp.strip().replace(" ", "").replace("-", "")

    if not clean_otp or len(clean_otp) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid 8-digit verification code."
        )

    # 1. Enforce 10-minute validity window
    from app.core.user_store import get_active_pending_signup, delete_pending_signup, register_user, create_user_session
    pending = get_active_pending_signup(clean_email)
    if not pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification code has expired (10-minute validity exceeded). Please request a new OTP."
        )

    # 2. Verify with Supabase Auth
    from app.core.supabase_service import SupabaseService
    try:
        verify_res = SupabaseService.verify_email_otp(clean_email, clean_otp)
    except Exception as err:
        logger.warning(f"Supabase OTP verification rejected for {clean_email}: {err}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That verification code is incorrect or expired. Please check your email and try again."
        )

    # 3. Verification confirmed by Supabase Auth!
    user_data = verify_res.get("user") or {}
    session_data = verify_res.get("session") or {}
    user_id = user_data.get("id") or f"user-{uuid.uuid4().hex[:12]}"
    auth_token = session_data.get("access_token") or f"kh-usr-{uuid.uuid4().hex}"
    refresh_token = session_data.get("refresh_token") or f"kh-ref-{uuid.uuid4().hex}"

    clean_phone = pending.get("mobile_number") or ""
    full_name = pending.get("full_name") or (user_data.get("user_metadata") or {}).get("full_name") or "Verified User"

    # Register in application user store & SQLite
    register_user(
        user_id=user_id,
        email=clean_email,
        full_name=full_name,
        mobile_number=clean_phone,
        role="USER",
        is_unlimited=False,
        account_status="ACTIVE",
        email_verified=True,
        mobile_verified=bool(clean_phone)
    )

    # Create active session
    session_info = create_user_session(
        user_id=user_id,
        email=clean_email,
        role="USER",
        is_unlimited=False,
        full_name=full_name,
        mobile_number=clean_phone,
        explicit_token=auth_token
    )

    delete_pending_signup(clean_email)
    logger.info(f"User email verified and account activated for {clean_email} (ID: {user_id})")

    return {
        "success": True,
        "message": "Email verified successfully! Setting up your session...",
        "token": session_info["token"],
        "refresh_token": refresh_token,
        "user": {
            "id": user_id,
            "email": clean_email,
            "full_name": full_name,
            "mobile_number": clean_phone,
            "role": "USER",
            "daily_allowance": settings.free_daily_page_limit
        }
    }

@router.post("/signup/resend-email-otp")
async def resend_supabase_email_otp(payload: ResendEmailOtpRequest):
    """
    Resends fresh Email OTP via Supabase Auth and resets the 10-minute validity window.
    """
    clean_email = payload.email.strip().lower()
    clean_phone = "".join(c for c in (payload.mobile_number or "") if c.isdigit())[-10:] if payload.mobile_number else ""

    from app.core.user_store import check_email_status, register_pending_signup, get_active_pending_signup
    status_info = check_email_status(clean_email, clean_phone)
    if status_info.get("exists") and status_info.get("verified"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email address is already verified and active."
        )

    # Retrieve existing pending details if available to preserve name/mobile
    existing = get_active_pending_signup(clean_email)
    full_name = existing.get("full_name") if existing else "Pending User"
    saved_phone = clean_phone or (existing.get("mobile_number") if existing else "")
    gender = existing.get("gender") if existing else "Male"

    # Resend via Supabase Auth
    from app.core.supabase_service import SupabaseService
    try:
        SupabaseService.resend_signup_email_otp(clean_email)
    except Exception as err:
        logger.warning(f"Supabase resend OTP notice for {clean_email}: {err}")

    # Renew 10-minute validity period
    new_pending = register_pending_signup(
        email=clean_email,
        full_name=full_name,
        mobile_number=saved_phone,
        gender=gender,
        validity_seconds=600  # Fresh 10 minutes
    )

    return {
        "success": True,
        "message": "A fresh verification code has been dispatched to your email.",
        "remaining_seconds": 600,
        "expires_at": new_pending["otp_expires_at"],
        "cooldown_seconds": 60
    }

@router.post("/signup/send-otp")
async def send_signup_otp(payload: SendSignupOtpRequest, request: Request):
    """
    Dispatches verification OTP code to user's email or mobile number.
    Adheres strictly to the multi-step verification requirement.
    """
    if not settings.allow_new_signups:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="New registrations are currently closed by system administration."
        )

    client_ip = request.client.host if request.client else "unknown"
    channel = (payload.channel or "EMAIL").upper()

    if channel == "EMAIL":
        clean_dest = payload.email.strip().lower()
        if "@" not in clean_dest or "." not in clean_dest:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide a valid email address."
            )
        from app.core.user_store import check_email_status, register_pending_signup
        status_info = check_email_status(clean_dest)
        if status_info.get("exists") and status_info.get("verified"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email address is already linked to an account."
            )
        register_pending_signup(clean_dest, payload.full_name, payload.mobile_number)
        success, message, cooldown, ref_id = otp_service.generate_and_send_otp(
            destination=clean_dest,
            channel="EMAIL",
            ip=client_ip,
            recipient_name=payload.full_name
        )
        msg = "Verification code sent to your email address." if success else message
    else:
        clean_mobile = "".join(c for c in payload.mobile_number if c.isdigit())
        if len(clean_mobile) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide a valid 10-digit mobile number."
            )
        clean_dest = clean_mobile
        success, message, cooldown, ref_id = otp_service.generate_and_send_otp(
            destination=clean_dest,
            channel="SMS",
            ip=client_ip,
            recipient_name=payload.full_name
        )
        msg = "Verification code sent to your mobile number." if success else message

    if not success:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS if "wait" in message.lower() or "too many" in message.lower() else status.HTTP_400_BAD_REQUEST,
            detail={
                "message": message,
                "cooldown_seconds": cooldown,
                "reference_id": ref_id
            }
        )

    res_data = {
        "success": True,
        "message": msg,
        "destination_masked": otp_service.mask_destination(clean_dest),
        "cooldown_seconds": cooldown,
        "reference_id": ref_id,
        "channel": channel
    }
    return res_data


@router.post("/signup/verify-otp")
async def verify_signup_otp(payload: VerifySignupOtpRequest, request: Request):
    """
    Verifies user OTP code against secure salted hash.
    If channel is EMAIL: confirms email verification.
    If channel is SMS: confirms mobile and creates completed account session.
    """
    client_ip = request.client.host if request.client else "unknown"
    channel = (payload.channel or "EMAIL").upper()
    destination = payload.email.strip().lower() if channel == "EMAIL" else "".join(c for c in payload.mobile_number if c.isdigit())

    is_valid, msg = otp_service.verify_otp(
        destination=destination,
        entered_otp=payload.otp,
        ip=client_ip
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg
        )

    if channel == "EMAIL" and not payload.password:
        return {
            "success": True,
            "email_verified": True,
            "message": "Email address verified successfully."
        }

    # Complete user account creation upon successful OTP verification
    from app.core.supabase_service import SupabaseService
    user_id = f"user-{uuid.uuid4().hex[:12]}"
    auth_token = f"kh-usr-{uuid.uuid4().hex}"

    clean_mobile = "".join(c for c in (payload.mobile_number or "") if c.isdigit())
    clean_email = payload.email.strip().lower()

    if SupabaseService.is_configured() and payload.password:
        try:
            # Check if user already exists and has password set to prevent duplicate signup confirmation emails
            try:
                login_res = SupabaseService.sign_in_with_password(clean_email, payload.password)
                session = login_res.get("session") or {}
                user_data = login_res.get("user") or {}
                if session.get("access_token"):
                    auth_token = session["access_token"]
                if user_data.get("id"):
                    user_id = user_data["id"]
            except Exception:
                # If not signed in, create user account via Supabase
                signup_res = SupabaseService.sign_up(
                    email=clean_email,
                    password=payload.password,
                    metadata={
                        "full_name": payload.full_name or "Verified User",
                        "mobile_number": f"+91{clean_mobile[-10:]}" if len(clean_mobile) >= 10 else clean_mobile,
                        "email_verified": True,
                        "mobile_verified": True
                    }
                )
                session = signup_res.get("session") or {}
                user_data = signup_res.get("user") or {}
                if session.get("access_token"):
                    auth_token = session["access_token"]
                if user_data.get("id"):
                    user_id = user_data["id"]
        except Exception as err:
            logger.warning(f"Supabase auth registration notice: {err}")

    # Register user in unified user store so they appear in Admin Dashboard immediately
    from app.core.user_store import register_user, create_user_session
    register_user(
        user_id=user_id,
        email=clean_email,
        full_name=payload.full_name or "Verified User",
        mobile_number=clean_mobile,
        role="USER",
        is_unlimited=False,
        account_status="ACTIVE",
        email_verified=True,
        mobile_verified=bool(clean_mobile)
    )

    session_info = create_user_session(
        user_id=user_id,
        email=clean_email,
        role="USER",
        is_unlimited=False,
        full_name=payload.full_name or "Verified User",
        explicit_token=auth_token
    )

    logger.info(f"User signup completed successfully for {clean_email} (ID: {user_id})")

    return {
        "success": True,
        "message": "Account verified and registered successfully.",
        "token": session_info["token"],
        "refresh_token": session_info["refresh_token"],
        "user": {
            "id": user_id,
            "email": clean_email,
            "full_name": payload.full_name or "Verified User",
            "mobile_number": clean_mobile,
            "role": "USER",
            "daily_allowance": settings.free_daily_page_limit
        }
    }

@router.post("/signup/resend-otp")
async def resend_signup_otp(payload: ResendOtpRequest, request: Request):
    """
    Resends fresh OTP code to user adhering to rate limits and 60-second cooldown.
    """
    channel = (payload.channel or "EMAIL").upper()
    if channel == "EMAIL" or "@" in payload.destination:
        clean_dest = payload.destination.strip().lower()
        actual_channel = "EMAIL"
    else:
        clean_dest = "".join(c for c in payload.destination if c.isdigit())
        actual_channel = "SMS"

    client_ip = request.client.host if request.client else "unknown"

    success, message, cooldown, ref_id = otp_service.generate_and_send_otp(
        destination=clean_dest,
        channel=actual_channel,
        ip=client_ip
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS if "wait" in message.lower() else status.HTTP_400_BAD_REQUEST,
            detail={
                "message": message,
                "cooldown_seconds": cooldown,
                "reference_id": ref_id
            }
        )

    res_data = {
        "success": True,
        "message": f"Verification code resent to your {'email address' if actual_channel == 'EMAIL' else 'mobile number'}.",
        "cooldown_seconds": cooldown,
        "reference_id": ref_id,
        "channel": actual_channel
    }
    return res_data


@router.post("/login")
async def user_login(payload: UserLoginRequest, request: Request):
    """
    Standard user authentication endpoint.
    Verifies user credentials against Supabase Auth, strictly denies suspended accounts.
    """
    from app.core.supabase_service import SupabaseService
    email = payload.email.strip().lower()
    password = payload.password

    from app.core.user_store import get_user_suspension_info, get_user_by_email
    from app.api.admin import SUSPENDED_USERS, USER_ACCOUNT_STATUSES

    existing_user = get_user_by_email(email)
    user_id = existing_user["id"] if existing_user else None
    s_info = (get_user_suspension_info(user_id) if user_id else None) or get_user_suspension_info(email) or {}

    is_susp = (
        (user_id and user_id in SUSPENDED_USERS) 
        or email in SUSPENDED_USERS
        or (user_id and USER_ACCOUNT_STATUSES.get(user_id) in ("SUSPENDED", "BLOCKED", "DEACTIVATED"))
        or USER_ACCOUNT_STATUSES.get(email) in ("SUSPENDED", "BLOCKED", "DEACTIVATED")
        or s_info.get("is_suspended")
    )
    if is_susp:
        reason = s_info.get("suspension_reason")
        suspended_at = s_info.get("suspended_at")
        delete_at = s_info.get("suspension_delete_at")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "ACCOUNT_SUSPENDED",
                "code": "ACCOUNT_SUSPENDED",
                "message": "Your Kangra Hub account has been temporarily suspended due to a policy or account-related issue.",
                "user_id": user_id or f"usr-{email.split('@')[0]}",
                "email": email,
                "full_name": s_info.get("full_name") or (existing_user.get("full_name") if existing_user else email.split("@")[0].capitalize()),
                "suspension_reason": reason,
                "suspended_at": suspended_at,
                "suspension_delete_at": delete_at
            }
        )

    # PRD Section 7: Reject admin credentials on normal user login page
    if existing_user and (existing_user.get("role") in ("ADMIN", "SUPER_ADMIN") or email in ("admin@kangrahub.sales", "admin@tallyxml.in", "admin@kangrahub.com")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login credentials."
        )

    if not SupabaseService.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable."
        )

    try:
        auth_data = SupabaseService.sign_in_with_password(email, password)
        access_token = auth_data.get("access_token")
        u = auth_data.get("user") or {}
        user_id = u.get("id")

        if not (access_token and user_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password. Please check your credentials and try again."
            )

        # Query profile status
        profile = SupabaseService.query_profile(user_id, user_token=access_token)
        from app.core.user_store import get_user_suspension_info
        from app.api.admin import SUSPENDED_USERS, USER_ACCOUNT_STATUSES
        s_info = get_user_suspension_info(user_id) or get_user_suspension_info(email) or {}

        account_status = (profile.get("account_status") if profile else None) or USER_ACCOUNT_STATUSES.get(user_id) or s_info.get("account_status", "ACTIVE")
        is_active = (profile.get("is_active", True) if profile else True) and (account_status == "ACTIVE")

        if user_id in SUSPENDED_USERS or email in SUSPENDED_USERS or not is_active or account_status in ("SUSPENDED", "BLOCKED", "DEACTIVATED"):
            if account_status == "BLOCKED":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your account has been blocked due to security violations. Please contact support."
                )
            elif account_status == "DEACTIVATED":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This account has been deactivated."
                )
            else:
                reason = (profile.get("suspension_reason") if profile else None) or s_info.get("suspension_reason")
                suspended_at = (profile.get("suspended_at") if profile else None) or s_info.get("suspended_at")
                delete_at = (profile.get("suspension_delete_at") if profile else None) or s_info.get("suspension_delete_at")
                meta = u.get("user_metadata") or {}
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "ACCOUNT_SUSPENDED",
                        "code": "ACCOUNT_SUSPENDED",
                        "message": "Your Kangra Hub account has been temporarily suspended due to a policy or account-related issue.",
                        "user_id": user_id,
                        "email": email,
                        "full_name": (profile.get("full_name") if profile else None) or meta.get("full_name") or s_info.get("full_name") or "User",
                        "suspension_reason": reason,
                        "suspended_at": suspended_at,
                        "suspension_delete_at": delete_at
                    }
                )

        role = (profile or {}).get("role") or (u.get("user_metadata") or {}).get("role", "USER")
        if role in ("ADMIN", "SUPER_ADMIN"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid login credentials."
            )
        meta = u.get("user_metadata") or {}

        # Query user access for unlimited status
        is_unlimited = False
        ua_data = SupabaseService.query_user_access(user_id, user_token=access_token)
        if ua_data:
            is_unlimited = ua_data.get("unlimited") is True or ua_data.get("access_type") == "UNLIMITED"

        # Cache active session in internal store for high-performance retrieval and zero false expiration
        from app.core.user_store import register_user, create_user_session
        from app.core.db import get_user_by_id_or_email
        existing_u = get_user_by_id_or_email(user_id) or get_user_by_id_or_email(email)
        user_mobile = (
            (existing_u.get("mobile_number") if existing_u else None)
            or (profile.get("mobile_number") if profile else None)
            or meta.get("mobile_number")
            or meta.get("phone")
            or ""
        )
        register_user(
            user_id=user_id,
            email=u.get("email", email),
            role=role,
            is_unlimited=is_unlimited or (role in ("ADMIN", "SUPER_ADMIN")),
            full_name=meta.get("full_name") or "User",
            mobile_number=user_mobile
        )
        create_user_session(
            user_id=user_id,
            email=u.get("email", email),
            role=role,
            is_unlimited=is_unlimited or (role in ("ADMIN", "SUPER_ADMIN")),
            full_name=meta.get("full_name") or "User",
            mobile_number=user_mobile,
            explicit_token=access_token
        )

        return {
            "token": access_token,
            "refresh_token": auth_data.get("refresh_token"),
            "user": {
                "id": user_id,
                "email": u.get("email", email),
                "full_name": meta.get("full_name") or "User",
                "mobile_number": user_mobile,
                "role": role,
                "is_unlimited": is_unlimited or (role in ("ADMIN", "SUPER_ADMIN"))
            }
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(f"User login failure for {email}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please check your credentials and try again."
        )

@router.post("/refresh")
async def refresh_user_token(payload: RefreshTokenRequest):
    """
    Refreshes an expiring or expired user session token.
    Supports both internal active session store and Supabase Auth.
    """
    # 1. Try internal active session store first
    from app.core.user_store import refresh_user_session
    refreshed = refresh_user_session(payload.refresh_token)
    if refreshed:
        return {
            "token": refreshed["token"],
            "refresh_token": refreshed["refresh_token"]
        }

    # 2. Try Supabase Auth if configured
    from app.core.supabase_service import SupabaseService
    if SupabaseService.is_configured():
        try:
            res = SupabaseService.refresh_session(payload.refresh_token)
            new_token = res.get("access_token")
            new_refresh = res.get("refresh_token")
            if new_token:
                return {
                    "token": new_token,
                    "refresh_token": new_refresh
                }
        except Exception as exc:
            logger.warning(f"Supabase session refresh error: {exc}")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Your session has expired. Please log in again to continue."
    )

@router.get("/telemetry")
async def get_otp_telemetry(
    limit: int = 50,
    current_admin: CurrentUser = Depends(require_admin)
):
    """
    Admin-only endpoint to inspect OTP delivery telemetry audit log.
    Ensures zero plain OTPs are disclosed.
    """
    return {
        "count": len(otp_service.get_telemetry_logs(limit)),
        "logs": otp_service.get_telemetry_logs(limit)
    }

class RecoverySubmissionRequest(BaseModel):
    account_identifier: str
    reason: str
    known_email: Optional[str] = None
    known_mobile: Optional[str] = None
    requested_new_email: Optional[str] = None
    requested_new_mobile: Optional[str] = None
    identity_verification_info: Optional[str] = None

@router.post("/recovery/request")
async def submit_account_recovery(payload: RecoverySubmissionRequest, request: Request):
    """
    Submits an account recovery request when primary email or mobile is lost.
    Queues for administrator security review.
    """
    from app.core.recovery_service import recovery_service
    if not payload.account_identifier or not payload.account_identifier.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please specify your registered account email, mobile number, or User ID."
        )
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide the reason for account recovery."
        )

    client_ip = request.client.host if request.client else "unknown"

    # Locate account history if user exists in registered accounts
    from app.core.user_store import get_all_users
    from app.api.conversions import IN_MEMORY_JOBS
    ident = payload.account_identifier.strip().lower()
    all_users = get_all_users()
    found_user = None
    for u in all_users:
        if (u.get("email", "").lower() == ident or 
            (u.get("mobile_number") and u.get("mobile_number").lower() == ident) or 
            str(u.get("id", "")).lower() == ident):
            found_user = u
            break

    account_history = {}
    found_user_id = None
    if found_user:
        found_user_id = found_user.get("id")
        user_jobs = [j for j in IN_MEMORY_JOBS.values() if j.get("user_id") == found_user_id]
        account_history = {
            "user_id": found_user_id,
            "full_name": found_user.get("full_name"),
            "email": found_user.get("email"),
            "mobile": found_user.get("mobile_number"),
            "account_status": found_user.get("account_status", "ACTIVE"),
            "registered_at": found_user.get("registration_date", "2024-01-15T10:00:00Z"),
            "total_conversions": len(user_jobs),
            "successful_conversions": sum(1 for j in user_jobs if j.get("status") == "COMPLETED")
        }

    rec = recovery_service.submit_request(
        account_identifier=payload.account_identifier,
        reason=payload.reason,
        user_id=found_user_id,
        known_email=payload.known_email or (found_user.get("email") if found_user else None),
        known_mobile=payload.known_mobile or (found_user.get("mobile_number") if found_user else None),
        requested_new_email=payload.requested_new_email,
        requested_new_mobile=payload.requested_new_mobile,
        identity_verification_info=payload.identity_verification_info,
        account_history=account_history,
        ip_address=client_ip
    )

    return {
        "success": True,
        "request_id": rec.id,
        "status": rec.status,
        "submitted_at": rec.submitted_at,
        "message": "Your recovery request has been received and submitted for administrative security review."
    }

@router.get("/recovery/status/{request_id}")
async def get_recovery_status(request_id: str):
    """
    Public tracking endpoint for users to check their recovery status via Request ID.
    """
    from app.core.recovery_service import recovery_service
    rec = recovery_service.get_request(request_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recovery request not found. Please check your Reference ID."
        )
    return {
        "request_id": rec.id,
        "status": rec.status,
        "step1_status": rec.step1_status,
        "step2_status": rec.step2_status,
        "submitted_at": rec.submitted_at,
        "reviewed_at": rec.reviewed_at,
        "decision_reason": rec.decision_reason if rec.status not in ("Pending", "PENDING_ADMIN_REVIEW") else None
    }

class RecoveryVerifyStep2Request(BaseModel):
    request_id: str
    otp: str

@router.post("/recovery/verify-step2")
async def verify_recovery_step2(payload: RecoveryVerifyStep2Request, request: Request):
    """
    Public endpoint for a user to enter the 6-digit verification code sent to their new email.
    """
    from app.core.recovery_service import recovery_service
    client_ip = request.client.host if request.client else "unknown"
    try:
        req = recovery_service.verify_step2(
            request_id=payload.request_id,
            entered_otp=payload.otp,
            ip_address=client_ip
        )
        return {
            "success": True,
            "message": "New email verified successfully. Your recovery request is now ready for administrative completion.",
            "request_id": req.id,
            "status": req.status,
            "step2_status": req.step2_status
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    mobile_number: Optional[str] = None
    gender: Optional[str] = None

@router.get("/me")
async def get_current_auth_user(current_user: CurrentUser = Depends(get_current_user)):
    """Returns comprehensive profile information for the authenticated user session."""
    from app.core.db import get_user_by_id_or_email
    db_user = get_user_by_id_or_email(current_user.id) or get_user_by_id_or_email(current_user.email) or {}
    
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "is_unlimited": current_user.is_unlimited,
        "is_staff": current_user.is_staff,
        "is_gold": current_user.is_gold,
        "staff_source": current_user.staff_source,
        "subscription_expiry": current_user.subscription_expiry,
        "full_name": db_user.get("full_name") or current_user.full_name or "Verified User",
        "mobile_number": db_user.get("mobile_number") or current_user.mobile_number or "",
        "gender": db_user.get("gender") or "Not specified",
        "account_status": db_user.get("account_status", "ACTIVE"),
        "email_verified": db_user.get("email_verified", True),
        "avatar_url": db_user.get("avatar_url") or getattr(current_user, "avatar_url", None),
        "created_at": db_user.get("registration_date") or db_user.get("created_at")
    }

@router.put("/profile")
async def update_current_user_profile(
    payload: UpdateProfileRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Updates the authenticated user's profile (full_name, mobile_number, gender).
    Updates SQLite DB, user session cache, Supabase metadata, and records an activity audit log.
    """
    from app.core.db import update_user_profile, add_user_activity_log
    from app.core.user_store import register_user

    # Validate mobile if provided
    clean_mobile = None
    if payload.mobile_number is not None:
        clean_mobile = "".join(c for c in payload.mobile_number if c.isdigit())
        if len(clean_mobile) > 0 and len(clean_mobile) != 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mobile number must be a valid 10-digit number."
            )

    updated = update_user_profile(
        user_id=current_user.id,
        full_name=payload.full_name,
        mobile_number=clean_mobile,
        gender=payload.gender
    )

    if not updated:
        # Fallback by email
        updated = update_user_profile(
            user_id=current_user.email,
            full_name=payload.full_name,
            mobile_number=clean_mobile,
            gender=payload.gender
        )

    # Sync into in-memory store
    register_user(
        user_id=current_user.id,
        email=current_user.email,
        full_name=payload.full_name or current_user.full_name,
        mobile_number=clean_mobile or current_user.mobile_number,
        role=current_user.role,
        is_unlimited=current_user.is_unlimited
    )

    # Sync into Supabase user metadata if available
    from app.core.supabase_service import SupabaseService
    if SupabaseService.is_configured():
        try:
            SupabaseService.update_profile(
                user_id=current_user.id,
                full_name=payload.full_name or current_user.full_name,
                mobile_number=clean_mobile or current_user.mobile_number
            )
        except Exception as e:
            logger.warning(f"Could not sync Supabase profile update: {e}")

    # Audit log WHO did WHAT, WHEN, in WHICH MODULE, with WHAT STATUS
    add_user_activity_log(
        user_id=current_user.id,
        user_email=current_user.email,
        action="PROFILE_UPDATED",
        module="USER_PROFILE",
        resource_id=current_user.id,
        status="SUCCESS",
        metadata={
            "full_name": payload.full_name,
            "mobile_number_set": bool(clean_mobile),
            "gender": payload.gender
        }
    )

    return {
        "success": True,
        "message": "Profile updated successfully.",
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": (updated or {}).get("full_name") or payload.full_name or current_user.full_name,
            "mobile_number": (updated or {}).get("mobile_number") or clean_mobile or current_user.mobile_number,
            "gender": (updated or {}).get("gender") or payload.gender or "Not specified",
            "role": current_user.role,
            "is_unlimited": current_user.is_unlimited,
            "avatar_url": (updated or {}).get("avatar_url") or current_user.avatar_url
        }
    }

AVATARS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "uploads", "avatars")
os.makedirs(AVATARS_DIR, exist_ok=True)

@router.post("/profile/picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Uploads or updates the authenticated user's profile picture.
    Stores the image server-side in persistent storage and associates it with the user account.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    ext = os.path.splitext(file.filename.lower())[1]
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image file extension '{ext}'. Allowed formats: JPG, PNG, WEBP, GIF."
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image size exceeds 5MB limit.")

    clean_uid = "".join(c for c in current_user.id if c.isalnum() or c in ("-", "_"))
    filename = f"avatar_{clean_uid}_{uuid.uuid4().hex[:8]}{ext}"
    dest_path = os.path.join(AVATARS_DIR, filename)

    try:
        with open(dest_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to save profile picture: {e}")
        raise HTTPException(status_code=500, detail="Failed to save profile picture on server.")

    avatar_url = f"/api/auth/profile/picture/{filename}"

    # Remove old avatar file if replacing
    from app.core.db import get_user_by_id_or_email, set_user_avatar, add_user_activity_log
    db_u = get_user_by_id_or_email(current_user.id) or {}
    old_avatar = db_u.get("avatar_url") or current_user.avatar_url
    if old_avatar and "/api/auth/profile/picture/" in old_avatar:
        old_filename = old_avatar.split("/api/auth/profile/picture/")[-1]
        old_path = os.path.join(AVATARS_DIR, os.path.basename(old_filename))
        if os.path.exists(old_path) and os.path.abspath(old_path) != os.path.abspath(dest_path):
            try:
                os.remove(old_path)
            except Exception as _rm_e:
                logger.warning(f"Failed to remove replaced avatar file: {_rm_e}")

    # Update in SQLite users table
    set_user_avatar(current_user.id, avatar_url)

    # Sync into in-memory store & sessions
    from app.core import user_store
    with user_store._LOCK:
        if current_user.id in user_store.REGISTERED_USERS:
            user_store.REGISTERED_USERS[current_user.id]["avatar_url"] = avatar_url
        for sess in user_store.ACTIVE_SESSIONS.values():
            if sess.get("user_id") == current_user.id or sess.get("email") == current_user.email:
                sess["avatar_url"] = avatar_url

    # Sync to Supabase profile if configured
    from app.core.supabase_service import SupabaseService
    if SupabaseService.is_configured():
        try:
            SupabaseService.upsert_profile({
                "id": current_user.id,
                "avatar_url": avatar_url
            })
        except Exception as _sb_e:
            logger.warning(f"Could not sync avatar to Supabase: {_sb_e}")

    add_user_activity_log(
        user_id=current_user.id,
        user_email=current_user.email,
        action="AVATAR_UPLOADED",
        module="USER_PROFILE",
        resource_id=current_user.id,
        status="SUCCESS",
        metadata={"filename": filename, "avatar_url": avatar_url}
    )

    return {
        "success": True,
        "avatar_url": avatar_url,
        "message": "Profile picture updated successfully."
    }

@router.get("/profile/picture/{filename}")
async def get_profile_picture(filename: str):
    """Serves the user's profile picture with secure caching."""
    clean_name = os.path.basename(filename)
    file_path = os.path.join(AVATARS_DIR, clean_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Profile picture not found.")

    ext = os.path.splitext(clean_name.lower())[1]
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif"
    }
    media_type = media_types.get(ext, "application/octet-stream")

    return FileResponse(
        path=file_path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"}
    )

@router.delete("/profile/picture")
async def delete_profile_picture(current_user: CurrentUser = Depends(get_current_user)):
    """Removes the authenticated user's profile picture."""
    from app.core.db import get_user_by_id_or_email, set_user_avatar, add_user_activity_log
    db_u = get_user_by_id_or_email(current_user.id) or {}
    old_avatar = db_u.get("avatar_url") or current_user.avatar_url

    if old_avatar and "/api/auth/profile/picture/" in old_avatar:
        old_filename = old_avatar.split("/api/auth/profile/picture/")[-1]
        old_path = os.path.join(AVATARS_DIR, os.path.basename(old_filename))
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception as e:
                logger.warning(f"Failed to remove old avatar file: {e}")

    set_user_avatar(current_user.id, None)

    # Sync in-memory store & sessions
    from app.core import user_store
    with user_store._LOCK:
        if current_user.id in user_store.REGISTERED_USERS:
            user_store.REGISTERED_USERS[current_user.id]["avatar_url"] = None
        for sess in user_store.ACTIVE_SESSIONS.values():
            if sess.get("user_id") == current_user.id or sess.get("email") == current_user.email:
                sess["avatar_url"] = None

    # Sync to Supabase profile
    from app.core.supabase_service import SupabaseService
    if SupabaseService.is_configured():
        try:
            SupabaseService.upsert_profile({
                "id": current_user.id,
                "avatar_url": None
            })
        except Exception as _sb_e:
            logger.warning(f"Could not clear avatar in Supabase: {_sb_e}")

    add_user_activity_log(
        user_id=current_user.id,
        user_email=current_user.email,
        action="AVATAR_REMOVED",
        module="USER_PROFILE",
        resource_id=current_user.id,
        status="SUCCESS",
        metadata={}
    )

    return {
        "success": True,
        "avatar_url": None,
        "message": "Profile picture removed successfully."
    }


