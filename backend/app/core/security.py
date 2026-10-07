import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from fastapi import Header, Query, Cookie, HTTPException, status, Depends, Request
from pydantic import BaseModel, model_validator
from app.core.config import settings

logger = logging.getLogger("kangra_hub")

class CurrentUser(BaseModel):
    id: str
    email: str
    role: str = "USER"
    is_unlimited: bool = False
    full_name: Optional[str] = "Kangra Hub User"
    mobile_number: Optional[str] = None
    gender: Optional[str] = None
    staff_source: Optional[str] = None  # 'ADMIN', 'SUBSCRIPTION', or None
    is_gold: bool = False               # Kangra Hub Gold Verified Tick
    subscription_expiry: Optional[str] = None  # ISO timestamp
    device_id: Optional[str] = None

    @model_validator(mode="after")
    def ensure_admin_attributes(self) -> "CurrentUser":
        if self.role in ("ADMIN", "SUPER_ADMIN", "STAFF") or (self.role and self.role.upper() == "STAFF"):
            self.is_gold = True
            self.is_unlimited = True
        return self

    @property
    def is_admin(self) -> bool:
        # Strictly verify ADMIN or SUPER_ADMIN role.
        # Note: Staff and is_unlimited MUST NEVER grant administrator authorization.
        return self.role in ("ADMIN", "SUPER_ADMIN")

    @property
    def is_staff(self) -> bool:
        # PRD Section 7: Staff group (Admin or Staff tier) has unlimited conversions
        return self.role in ("STAFF", "ADMIN", "SUPER_ADMIN")

    @property
    def has_quota_bypass(self) -> bool:
        # Quota bypass applies to daily bill conversion limits: Staff, Admin, or explicitly unlimited
        return self.is_admin or self.is_staff or self.is_unlimited

async def get_current_user(
    request: Request = None,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    kh_auth_token: Optional[str] = Cookie(None),
    x_device_id: Optional[str] = Header(None, alias="X-Device-Id")
) -> CurrentUser:
    """
    Authoritative server-side identity and role verification via Supabase.
    Requires active Supabase session token or local verified session. Fails safely with 503 if unconfigured.
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

    # Extract device ID and client metadata if available
    effective_device_id = x_device_id
    client_ip = None
    client_ua = None
    if request:
        if not effective_device_id:
            effective_device_id = request.headers.get("x-device-id")
        client_ip = request.client.host if request.client else None
        client_ua = request.headers.get("user-agent")

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
        is_hardcoded_admin = (
            user_id == "c4eb4938-895b-4b09-a362-db5ea1189315"
            or (email.lower().strip() in ("admin@kangrahub.sales", "admin@tallyxml.in", "admin@kangrahub.com"))
        )
        role = "ADMIN" if is_hardcoded_admin else ((db_u.get("role") if db_u else None) or active_sess.get("role", "USER"))
        is_admin_user = role in ("ADMIN", "SUPER_ADMIN")
        is_unlim = is_admin_user or (bool(db_u.get("is_unlimited")) if db_u else bool(active_sess.get("is_unlimited", False)))
        is_gold = True if is_admin_user else (bool(db_u.get("is_gold", 0)) if db_u else bool(active_sess.get("is_gold", False)))
        staff_src = (db_u.get("staff_source") if db_u else None) or active_sess.get("staff_source")
        sub_exp = (db_u.get("subscription_expiry") if db_u else None) or active_sess.get("subscription_expiry")
        gender = (db_u.get("gender") if db_u else None) or active_sess.get("gender")

        # PRD Section 4 & 6: Check Staff Membership validity from staff_memberships table
        mem_eval = db.get_staff_membership_with_status_eval(user_id=user_id, user_email=email, server_now_utc=datetime.now(timezone.utc))
        if mem_eval and mem_eval.get("is_active"):
            if not is_admin_user:
                role = "STAFF"
            is_gold = True
            is_unlim = True
            staff_src = mem_eval.get("source") or staff_src or "RAZORPAY_STAFF"
            sub_exp = mem_eval.get("membership_expires_at") or sub_exp
        elif role == "STAFF":
            if mem_eval and not mem_eval.get("is_active"):
                # Membership expired at exact IST midnight! Revert to normal user limits
                role = "USER"
                is_gold = False
                is_unlim = is_admin_user
            elif not mem_eval and staff_src == "SUBSCRIPTION" and sub_exp:
                # Legacy check if staff_memberships row is not yet created
                try:
                    exp_dt = datetime.fromisoformat(sub_exp.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) >= exp_dt:
                        role = "USER"
                        is_gold = False
                        is_unlim = is_admin_user
                        db.remove_user_from_staff(user_id, admin_id="SYSTEM", admin_name="Subscription Expiry Daemon")
                except Exception as e:
                    logger.warning(f"Error checking subscription expiry: {e}")

        # Track device activity if device ID present
        if effective_device_id:
            try:
                db.record_device_activity(
                    device_id=effective_device_id,
                    user_id=user_id,
                    ip_address=client_ip,
                    user_agent=client_ua
                )
            except Exception as e:
                logger.warning(f"Error recording device activity: {e}")

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

        user_mobile = (db_u.get("mobile_number") if db_u else None) or active_sess.get("mobile_number") or ""
        return CurrentUser(
            id=user_id,
            email=email,
            role=role,
            is_unlimited=is_unlim,
            full_name=active_sess.get("full_name") or email.split("@")[0].capitalize(),
            mobile_number=user_mobile,
            gender=gender,
            staff_source=staff_src,
            is_gold=is_gold,
            subscription_expiry=sub_exp,
            device_id=effective_device_id
        )

    # Real Supabase Authentication (Zero fake/demo tokens permitted)
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


        is_hardcoded_admin = (
            user_id == "c4eb4938-895b-4b09-a362-db5ea1189315"
            or (user_email.lower().strip() in ("admin@kangrahub.sales", "admin@tallyxml.in", "admin@kangrahub.com"))
        )

        role = "ADMIN" if is_hardcoded_admin else (db_role or (u.get("user_metadata") or {}).get("role", "USER"))
        is_admin_user = role in ("ADMIN", "SUPER_ADMIN")

        from app.core import db
        db_u = db.get_user_by_id_or_email(user_id) or db.get_user_by_id_or_email(u.get("email") or "")
        if db_u and db_u.get("role"):
            role = "ADMIN" if is_hardcoded_admin else db_u.get("role")
            is_admin_user = role in ("ADMIN", "SUPER_ADMIN")

        is_gold = True if is_admin_user else (bool(db_u.get("is_gold", 0)) if db_u else False)
        staff_src = db_u.get("staff_source") if db_u else None
        sub_exp = db_u.get("subscription_expiry") if db_u else None
        gender = db_u.get("gender") if db_u else None

        # PRD Section 4 & 6: Check Staff Membership validity from staff_memberships table
        mem_eval = db.get_staff_membership_with_status_eval(user_id=user_id, user_email=user_email, server_now_utc=datetime.now(timezone.utc))
        if mem_eval and mem_eval.get("is_active"):
            if not is_admin_user:
                role = "STAFF"
            is_gold = True
            effective_unlimited = True
            staff_src = mem_eval.get("source") or staff_src or "RAZORPAY_STAFF"
            sub_exp = mem_eval.get("membership_expires_at") or sub_exp
        elif role == "STAFF":
            if mem_eval and not mem_eval.get("is_active"):
                role = "USER"
                is_gold = False
            elif not mem_eval and staff_src == "SUBSCRIPTION" and sub_exp:
                try:
                    exp_dt = datetime.fromisoformat(sub_exp.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) >= exp_dt:
                        role = "USER"
                        is_gold = False
                        db.remove_user_from_staff(user_id, admin_id="SYSTEM", admin_name="Subscription Expiry Daemon")
                except Exception as e:
                    logger.warning(f"Error checking subscription expiry: {e}")

        # Track device activity
        if effective_device_id:
            try:
                db.record_device_activity(
                    device_id=effective_device_id,
                    user_id=user_id,
                    ip_address=client_ip,
                    user_agent=client_ua
                )
            except Exception as e:
                logger.warning(f"Error recording device activity: {e}")

        # 4. Query public.user_access using authenticated user ID (auth.users.id)
        is_unlimited = False
        ua_data = SupabaseService.query_user_access(user_id, user_token=raw_token)
        if ua_data:
            is_unlimited = ua_data.get("unlimited") is True or ua_data.get("access_type") == "UNLIMITED"

        if role in ("STAFF", "ADMIN", "SUPER_ADMIN"):
            effective_unlimited = True
        else:
            effective_unlimited = is_admin_user or (bool(db_u.get("is_unlimited")) if db_u else is_unlimited)
        meta = u.get("user_metadata") or {}

        user_phone = (
            (p_data.get("mobile_number") if p_data else None)
            or (db_u.get("mobile_number") if db_u else None)
            or meta.get("mobile_number")
            or meta.get("phone")
            or ""
        )

        try:
            from app.core.user_store import register_user
            register_user(
                user_id=user_id,
                email=u.get("email") or "",
                full_name=meta.get("full_name") or "User",
                mobile_number=user_phone,
                role=role,
                is_unlimited=effective_unlimited,
                account_status="ACTIVE",
                email_verified=True,
                mobile_verified=bool(user_phone)
            )
        except Exception:
            pass
        return CurrentUser(
            id=user_id,
            email=u.get("email") or "",
            role=role,
            is_unlimited=True if role in ("ADMIN", "SUPER_ADMIN", "STAFF") else effective_unlimited,
            full_name=meta.get("full_name") or "User",
            mobile_number=user_phone,
            gender=gender,
            staff_source=staff_src,
            is_gold=is_gold,
            subscription_expiry=sub_exp,
            device_id=effective_device_id
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


async def require_staff(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """
    Enforces server-side active Staff membership check (Section 6).
    Rejects expired users with HTTP 403 and MEMBERSHIP_EXPIRED error code.
    """
    if not current_user.is_staff:
        from app.core import db
        mem = db.get_staff_membership(current_user.id)
        if mem and mem.get("staff_status") == "EXPIRED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "MEMBERSHIP_EXPIRED",
                    "code": "MEMBERSHIP_EXPIRED",
                    "message": "Your Staff Membership has expired. Please renew your membership to continue Staff benefits."
                }
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "STAFF_REQUIRED",
                "code": "STAFF_REQUIRED",
                "message": "Staff Membership required. Please upgrade to access this feature."
            }
        )
    return current_user
