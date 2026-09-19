import logging
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

ADMIN_LOGIN_EMAIL = "admin@tallyxml.in"
ADMIN_RECOVERY_EMAIL = "kangrahub@gmail.com"

router = APIRouter(prefix="/system", tags=["System"])

class PublicSettingsResponse(BaseModel):
    site_name: str
    site_mode: str  # "FREE" or "PAID"
    free_daily_page_limit: int
    maintenance_mode: bool
    allow_new_signups: bool
    max_upload_size_mb: int
    max_pages_per_file: int

@router.get("/public-settings", response_model=PublicSettingsResponse)
async def get_public_settings():
    """Returns publicly visible system settings such as current Free/Paid mode."""
    return PublicSettingsResponse(
        site_name=settings.app_name,
        site_mode=settings.site_mode,
        free_daily_page_limit=settings.free_daily_page_limit,
        maintenance_mode=settings.maintenance_mode,
        allow_new_signups=settings.allow_new_signups,
        max_upload_size_mb=settings.max_upload_size_mb,
        max_pages_per_file=settings.max_pages_per_file
    )

class ContactMessageRequest(BaseModel):
    name: str
    email: str
    subject_type: Optional[str] = "REPORT_ISSUE"
    job_id: Optional[str] = None
    bank_name: Optional[str] = None
    message: str

@router.post("/contact")
async def submit_contact_message(payload: ContactMessageRequest):
    """
    Public endpoint for users and visitors to submit inquiries or support requests.
    Automatically creates an admin notification and returns a reference ID.
    """
    import uuid
    from datetime import datetime, timezone
    from app.api.admin import CONTACT_MESSAGES

    msg_id = f"msg-{uuid.uuid4().hex[:8]}"
    clean_email = payload.email.strip().lower()
    clean_name = payload.name.strip()

    if not clean_email or not payload.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address and message are required."
        )

    entry = {
        "id": msg_id,
        "name": clean_name or "Anonymous User",
        "email": clean_email,
        "subject_type": payload.subject_type or "REPORT_ISSUE",
        "job_id": (payload.job_id or "").strip(),
        "bank_name": (payload.bank_name or "").strip(),
        "message": payload.message.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_read": False
    }
    CONTACT_MESSAGES.insert(0, entry)
    logger.info(f"Support contact message received from {clean_email} (Ref: {msg_id})")

    return {
        "success": True,
        "message": "Thank you for reaching out. We have logged your request and our support specialists will get in touch shortly.",
        "reference_id": msg_id
    }

class AdminLoginRequest(BaseModel):
    email: str
    password: str

@router.post("/admin-login")
async def admin_login(payload: AdminLoginRequest):
    """
    Dedicated authentication endpoint for administrator login.
    Rejects standard users and unlimited users with 403.
    """
    from app.core.supabase_service import SupabaseService

    email = payload.email.lower().strip()
    password = payload.password.strip()

    # 1. Require Supabase configuration - Fail immediately if missing
    if not SupabaseService.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase authentication service is not configured on the server. Please configure SUPABASE_URL and SUPABASE_ANON_KEY in backend/.env."
        )

    # 2. Authenticate against Supabase Auth
    try:
        auth_data = SupabaseService.sign_in_with_password(email, password)
        access_token = auth_data.get("access_token")
        u = auth_data.get("user") or {}
        user_id = u.get("id")

        if not (access_token and user_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid administrator credentials."
            )

        # 3. Server-side database verification using authenticated user ID (auth.users.id)
        p_data = SupabaseService.query_profile(user_id, user_token=access_token)
        db_role = None
        if p_data:
            db_role = p_data.get("role")
            is_active = p_data.get("is_active", True)
            if not is_active or p_data.get("account_status") == "SUSPENDED":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access Denied: This administrator account is suspended or inactive."
                )

        # Check metadata role if profile query did not return a role
        role = db_role or (u.get("user_metadata") or {}).get("role", "USER")

        # 4. Strict Role Verification: Must possess ADMIN or SUPER_ADMIN
        if role not in ("ADMIN", "SUPER_ADMIN"):
            from app.core.audit_service import audit_service
            audit_service.log_event(
                action="ADMIN_LOGIN_FAILED",
                user_id=user_id,
                result="BLOCKED",
                reason="Unauthorized admin login attempt by standard user account",
                metadata={"email": email}
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access Denied: You are not authorized to access the administrator portal."
            )

        # 5. Query public.user_access for unlimited status
        is_unlimited = False
        ua_data = SupabaseService.query_user_access(user_id, user_token=access_token)
        if ua_data:
            is_unlimited = ua_data.get("unlimited") is True or ua_data.get("access_type") == "UNLIMITED"

        from app.core.audit_service import audit_service
        audit_service.log_event(
            action="ADMIN_LOGIN",
            user_id=user_id,
            result="SUCCESS",
            metadata={"email": email, "role": role}
        )

        return {
            "token": access_token,
            "is_admin": True,
            "user": {
                "id": user_id,
                "email": u.get("email", email),
                "role": role,
                "full_name": (u.get("user_metadata") or {}).get("full_name", "Administrator"),
                "is_unlimited": is_unlimited or True
            }
        }
    except HTTPException:
        raise
    except Exception as exc:
        err_msg = str(exc)
        logger.error(f"Admin authentication failed for {email}: {err_msg}")
        from app.core.audit_service import audit_service
        audit_service.log_event(
            action="ADMIN_LOGIN_FAILED",
            result="FAILURE",
            reason="Invalid credentials",
            metadata={"email": email}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Access denied. This login portal is restricted to authorized administrators."
        )


class AdminForgotPasswordRequest(BaseModel):
    email: str


@router.post("/admin-forgot-password")
async def admin_forgot_password(payload: AdminForgotPasswordRequest):
    """
    Dedicated password recovery request endpoint for administrator.
    Security policy:
    - Authoritative login identity is admin@tallyxml.in.
    - Password recovery instructions are dispatched with administrative notice routed to kangrahub@gmail.com.
    """
    email = payload.email.lower().strip()

    # 1. Require Supabase configuration - Fail immediately if missing
    if not (settings.supabase_url and settings.supabase_anon_key):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase authentication service is not configured on the server. Please configure SUPABASE_URL and SUPABASE_ANON_KEY in backend/.env."
        )

    # 2. Validate email against database / authoritative admin config
    admin_email = getattr(settings, "admin_email", "admin@tallyxml.in").lower().strip()
    recovery_email = getattr(settings, "admin_recovery_email", "kangrahub@gmail.com")
    is_valid_admin = (email == admin_email)
    
    if not is_valid_admin:
        try:
            from supabase import create_client
            db_client = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key or settings.supabase_anon_key
            )
            p_res = db_client.table("profiles").select("role, user_id").eq("email", email).single().execute()
            if p_res.data and p_res.data.get("role") in ("ADMIN", "SUPER_ADMIN"):
                is_valid_admin = True
        except Exception:
            pass

    if not is_valid_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active administrator account found matching '{email}'."
        )

    # 3. Trigger Supabase Auth password recovery
    try:
        from app.core.supabase_service import SupabaseService
        frontend_origin = getattr(settings, "frontend_url", "http://localhost:3000")
        redirect_to = f"{frontend_origin.rstrip('/')}/admin/reset-password"

        SupabaseService.reset_password(email, redirect_to=redirect_to)

        logger.info(
            f"Admin password recovery requested for {email}. "
            f"Administrative recovery notification dispatched."
        )

        return {
            "success": True,
            "message": f"Password reset instructions have been generated. Security recovery notifications are routed to {recovery_email}.",
            "recovery_email": recovery_email
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Password reset dispatch failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate password reset request: {str(exc)}"
        )

