import logging
from typing import Optional, Dict, Any
from fastapi import Header, Query, Cookie, HTTPException, status, Depends
from pydantic import BaseModel
from app.core.config import settings

logger = logging.getLogger("kangra_hub")

class CurrentUser(BaseModel):
    id: str
    email: str
    role: str = "USER"
    is_unlimited: bool = False
    full_name: Optional[str] = "Kangra Hub User"
    mobile_number: Optional[str] = None

    @property
    def is_admin(self) -> bool:
        # Strictly verify ADMIN or SUPER_ADMIN role.
        # Note: is_unlimited MUST NEVER grant administrator authorization.
        return self.role in ("ADMIN", "SUPER_ADMIN")

    @property
    def has_quota_bypass(self) -> bool:
        # Quota bypass applies to daily page conversion limits only.
        return self.is_admin or self.is_unlimited

async def get_current_user(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    kh_auth_token: Optional[str] = Cookie(None)
) -> CurrentUser:
    """
    Authoritative server-side identity and role verification via Supabase.
    Requires active Supabase session token. Fails safely with 503 if unconfigured.
    Zero fallback passwords or mock users in production.
    """
    raw_token = None
    if authorization:
        scheme, _, bearer_token = authorization.partition(" ")
        if scheme.lower() == "bearer" and bearer_token:
            raw_token = bearer_token
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization token format."
            )
    elif token:
        raw_token = token
    elif kh_auth_token:
        raw_token = kh_auth_token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in."
        )

    # Check active user sessions first (PRD Section 38 - fixes session expiration race conditions)
    from app.core.user_store import get_user_session, get_user_suspension_info
    try:
        from app.api.admin import SUSPENDED_USERS, USER_ACCOUNT_STATUSES
    except ImportError:
        SUSPENDED_USERS, USER_ACCOUNT_STATUSES = set(), {}

    active_sess = get_user_session(raw_token)
    if active_sess:
        user_id = active_sess["user_id"]
        email = active_sess["email"]
        s_info = get_user_suspension_info(user_id) or get_user_suspension_info(email) or {}
        is_susp = bool(
            user_id in SUSPENDED_USERS
            or email in SUSPENDED_USERS
            or USER_ACCOUNT_STATUSES.get(user_id) in ("SUSPENDED", "BLOCKED", "DEACTIVATED")
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
                    "user_id": user_id,
                    "email": email,
                    "full_name": s_info.get("full_name") or active_sess.get("full_name"),
                    "suspension_reason": reason,
                    "suspended_at": suspended_at,
                    "suspension_delete_at": delete_at
                }
            )
        # Ensure session user exists in persistent store with authoritative SQLite role & quota
        from app.core import db
        db_u = db.get_user_by_id_or_email(user_id) or db.get_user_by_id_or_email(email)
        role = (db_u.get("role") if db_u else None) or active_sess.get("role", "USER")
        is_admin_user = role in ("ADMIN", "SUPER_ADMIN")
        # Standard user is ONLY unlimited if explicitly set in SQLite by Admin!
        is_unlim = is_admin_user or (bool(db_u.get("is_unlimited")) if db_u else bool(active_sess.get("is_unlimited", False)))

        try:
            from app.core.user_store import register_user
            register_user(
                user_id=user_id,
                email=email,
                role=role,
                is_unlimited=is_unlim,
                full_name=active_sess.get("full_name") or email.split("@")[0].capitalize(),
                account_status="ACTIVE"
            )
        except Exception:
            pass

        return CurrentUser(
            id=user_id,
            email=email,
            role=role,
            is_unlimited=is_unlim,
            full_name=active_sess.get("full_name") or email.split("@")[0].capitalize()
        )

    # In development mode, support mock tokens for seamless local testing
    if getattr(settings, "app_env", "").lower() == "development":

        if raw_token in ("mock-admin-token", "admin"):
            try:
                from app.core.user_store import register_user
                register_user(
                    user_id="test-admin-id",
                    email="admin@tallyxml.in",
                    role="ADMIN",
                    is_unlimited=True,
                    full_name="Admin TallyXML"
                )
            except Exception:
                pass
            return CurrentUser(
                id="test-admin-id",
                email="admin@tallyxml.in",
                role="ADMIN",
                is_unlimited=True,
                full_name="Admin TallyXML"
            )
        elif raw_token in ("mock-user-token", "user"):
            user_id = "test-user-id"
            email = "user@example.com"
            s_info = get_user_suspension_info(user_id) or get_user_suspension_info(email) or {}
            is_susp = bool(user_id in SUSPENDED_USERS or USER_ACCOUNT_STATUSES.get(user_id) in ("SUSPENDED", "BLOCKED", "DEACTIVATED") or s_info.get("is_suspended"))
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
                        "user_id": user_id,
                        "email": email,
                        "full_name": s_info.get("full_name") or "Test Standard User",
                        "suspension_reason": reason,
                        "suspended_at": suspended_at,
                        "suspension_delete_at": delete_at
                    }
                )
            try:
                from app.core.user_store import register_user
                register_user(
                    user_id=user_id,
                    email=email,
                    role="USER",
                    is_unlimited=False,
                    full_name="Test Standard User"
                )
            except Exception:
                pass
            return CurrentUser(
                id=user_id,
                email=email,
                role="USER",
                is_unlimited=False,
                full_name="Test Standard User"
            )
        elif raw_token in ("mock-unlimited-token", "unlimited"):
            user_id = "test-unlimited-id"
            email = "unlimited@example.com"
            s_info = get_user_suspension_info(user_id) or get_user_suspension_info(email) or {}
            is_susp = user_id in SUSPENDED_USERS or USER_ACCOUNT_STATUSES.get(user_id) in ("SUSPENDED", "BLOCKED", "DEACTIVATED") or s_info.get("is_suspended")
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
                        "user_id": user_id,
                        "email": email,
                        "full_name": s_info.get("full_name") or "Test Unlimited User",
                        "suspension_reason": reason,
                        "suspended_at": suspended_at,
                        "suspension_delete_at": delete_at
                    }
                )
            try:
                from app.core.user_store import register_user
                register_user(
                    user_id=user_id,
                    email=email,
                    role="USER",
                    is_unlimited=True,
                    full_name="Test Unlimited User"
                )
            except Exception:
                pass
            return CurrentUser(
                id=user_id,
                email=email,
                role="USER",
                is_unlimited=True,
                full_name="Test Unlimited User"
            )

    # 1. Require Supabase configuration - Fail safely if missing
    from app.core.supabase_service import SupabaseService
    if not SupabaseService.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase authentication service is not configured on the server. Please configure SUPABASE_URL and SUPABASE_ANON_KEY in backend/.env."
        )

    # 2. Verify token with Supabase Auth
    try:
        u = SupabaseService.get_user(raw_token)
        user_id = u.get("id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session token."
            )

        user_email = u.get("email") or ""

        # 3. Query public.profiles using authenticated user ID (auth.users.id)
        p_data = SupabaseService.query_profile(user_id, user_token=raw_token)
        db_role = None
        if p_data:
            db_role = p_data.get("role")
            db_status = p_data.get("account_status")
            is_active = p_data.get("is_active", True)
            if not is_active or db_status in ("SUSPENDED", "BLOCKED", "DEACTIVATED"):
                if db_status == "BLOCKED":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Your account has been blocked due to security violations. Please contact support."
                    )
                elif db_status == "DEACTIVATED":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="This account has been deactivated."
                    )
                else:
                    from app.core.user_store import get_user_suspension_info
                    s_info = get_user_suspension_info(user_id) or get_user_suspension_info(user_email) or {}
                    reason = p_data.get("suspension_reason") or s_info.get("suspension_reason")
                    suspended_at = p_data.get("suspended_at") or s_info.get("suspended_at")
                    delete_at = p_data.get("suspension_delete_at") or s_info.get("suspension_delete_at")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "error": "ACCOUNT_SUSPENDED",
                            "code": "ACCOUNT_SUSPENDED",
                            "message": "Your Kangra Hub account has been temporarily suspended due to a policy or account-related issue.",
                            "user_id": user_id,
                            "email": user_email,
                            "full_name": p_data.get("full_name") or s_info.get("full_name") or "User",
                            "suspension_reason": reason,
                            "suspended_at": suspended_at,
                            "suspension_delete_at": delete_at
                        }
                    )

        # In-memory status check
        try:
            from app.api.admin import SUSPENDED_USERS, USER_ACCOUNT_STATUSES
            from app.core.user_store import get_user_suspension_info
            mem_status = USER_ACCOUNT_STATUSES.get(user_id) or USER_ACCOUNT_STATUSES.get(user_email)
            s_info = get_user_suspension_info(user_id) or get_user_suspension_info(user_email) or {}
            if user_id in SUSPENDED_USERS or user_email in SUSPENDED_USERS or mem_status in ("SUSPENDED", "BLOCKED", "DEACTIVATED") or s_info.get("is_suspended"):
                if mem_status == "BLOCKED":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Your account has been blocked due to security violations. Please contact support."
                    )
                elif mem_status == "DEACTIVATED":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="This account has been deactivated."
                    )
                else:
                    reason = s_info.get("suspension_reason")
                    suspended_at = s_info.get("suspended_at")
                    delete_at = s_info.get("suspension_delete_at")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "error": "ACCOUNT_SUSPENDED",
                            "code": "ACCOUNT_SUSPENDED",
                            "message": "Your Kangra Hub account has been temporarily suspended due to a policy or account-related issue.",
                            "user_id": user_id,
                            "email": user_email,
                            "full_name": s_info.get("full_name") or (u.get("user_metadata") or {}).get("full_name") or "User",
                            "suspension_reason": reason,
                            "suspended_at": suspended_at,
                            "suspension_delete_at": delete_at
                        }
                    )
        except ImportError:
            pass


        role = db_role or (u.get("user_metadata") or {}).get("role", "USER")
        is_admin_user = role in ("ADMIN", "SUPER_ADMIN")

        from app.core import db
        db_u = db.get_user_by_id_or_email(user_id) or db.get_user_by_id_or_email(u.get("email") or "")

        # 4. Query public.user_access using authenticated user ID (auth.users.id)
        is_unlimited = False
        ua_data = SupabaseService.query_user_access(user_id, user_token=raw_token)
        if ua_data:
            is_unlimited = ua_data.get("unlimited") is True or ua_data.get("access_type") == "UNLIMITED"

        effective_unlimited = is_admin_user or (bool(db_u.get("is_unlimited")) if db_u else is_unlimited)
        meta = u.get("user_metadata") or {}

        try:
            from app.core.user_store import register_user
            register_user(
                user_id=user_id,
                email=u.get("email") or "",
                full_name=meta.get("full_name") or "User",
                mobile_number=meta.get("mobile_number") or "",
                role=role,
                is_unlimited=effective_unlimited,
                account_status="ACTIVE",
                email_verified=True,
                mobile_verified=bool(meta.get("mobile_number"))
            )
        except Exception:
            pass

        return CurrentUser(
            id=user_id,
            email=u.get("email") or "",
            role=role,
            is_unlimited=effective_unlimited,
            full_name=meta.get("full_name") or "User",
            mobile_number=meta.get("mobile_number") or ""
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Supabase token verification failed: {e}")
        err_str = str(e).lower()
        if "expired" in err_str or "invalid claims" in err_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your session has expired. Please log in again to continue."
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in to continue."
        )


async def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Enforces server-side ADMIN role requirement."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden. Administrator privileges required."
        )
    return current_user
