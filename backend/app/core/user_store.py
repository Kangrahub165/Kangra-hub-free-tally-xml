import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Union
from app.core.security import CurrentUser
from app.core.config import settings
from app.core.supabase_service import SupabaseService

from app.core import db

logger = logging.getLogger("kangra_hub.user_store")

_LOCK = threading.Lock()

# Thread-safe in-memory store for registered users, initialized from persistent SQLite
REGISTERED_USERS: Dict[str, Dict[str, Any]] = {}
try:
    for _u in db.get_all_users():
        REGISTERED_USERS[_u["id"]] = dict(_u)
except Exception as _e:
    logger.warning(f"Unable to preload users from SQLite on startup: {_e}")


# Unverified pending signups
PENDING_VERIFICATIONS: Dict[str, Dict[str, Any]] = {}

def register_pending_signup(email: str, full_name: Optional[str] = None, mobile_number: Optional[str] = None):
    clean_email = email.strip().lower()
    with _LOCK:
        PENDING_VERIFICATIONS[clean_email] = {
            "email": clean_email,
            "full_name": full_name or "Pending User",
            "mobile_number": mobile_number or "",
            "initiated_at": datetime.now(timezone.utc).isoformat()
        }

def register_user(
    user_id: str,
    email: str,
    full_name: Optional[str] = None,
    mobile_number: Optional[str] = None,
    role: str = "USER",
    is_unlimited: bool = False,
    account_status: str = "ACTIVE",
    email_verified: bool = True,
    mobile_verified: bool = False,
    suspended_at: Optional[str] = None,
    suspension_reason: Optional[str] = None,
    suspension_delete_at: Optional[str] = None
) -> Dict[str, Any]:
    clean_email = email.strip().lower()
    now_iso = datetime.now(timezone.utc).isoformat()

    with _LOCK:
        # Clear from pending if present
        PENDING_VERIFICATIONS.pop(clean_email, None)

        user_entry = {
            "id": user_id,
            "email": clean_email,
            "role": role,
            "is_unlimited": is_unlimited,
            "full_name": full_name or "Registered User",
            "mobile_number": mobile_number or "",
            "account_status": account_status,
            "email_verified": email_verified,
            "mobile_verified": mobile_verified,
            "registration_date": now_iso,
            "last_login": now_iso,
            "suspended_at": suspended_at,
            "suspension_reason": suspension_reason,
            "suspension_delete_at": suspension_delete_at,
            "suspension_reviewed_at": None,
            "suspension_reviewed_by": None
        }
        REGISTERED_USERS[user_id] = user_entry

    # Persist to SQLite database
    try:
        db.upsert_user(user_entry)
    except Exception as e:
        logger.warning(f"Failed to persist user to SQLite: {e}")

    # Also attempt to upsert into Supabase public.profiles if configured
    if SupabaseService.is_configured():
        try:
            SupabaseService.upsert_profile({
                "user_id": user_id,
                "email": clean_email,
                "full_name": full_name or "Registered User",
                "mobile_number": mobile_number or "",
                "role": role,
                "account_status": account_status,
                "is_active": account_status == "ACTIVE",
                "email_verified": email_verified,
                "mobile_verified": mobile_verified,
                "suspended_at": suspended_at,
                "suspension_reason": suspension_reason,
                "suspension_delete_at": suspension_delete_at
            })
        except Exception as e:
            logger.debug(f"Supabase profile upsert skipped: {e}")

    return user_entry

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    clean_email = email.strip().lower()
    with _LOCK:
        for u in REGISTERED_USERS.values():
            if u["email"].lower() == clean_email:
                return dict(u)

    # Check SQLite persistent store
    db_u = db.get_user_by_id_or_email(clean_email)
    if db_u:
        with _LOCK:
            REGISTERED_USERS[db_u["id"]] = dict(db_u)
        return dict(db_u)

    # Fallback to Supabase query
    if SupabaseService.is_configured():
        try:
            p = SupabaseService.get_profile_by_email(clean_email)
            if p:
                user_id = str(p.get("user_id") or p.get("id"))
                entry = {
                    "id": user_id,
                    "email": p.get("email", clean_email),
                    "role": p.get("role", "USER"),
                    "is_unlimited": p.get("role") in ("ADMIN", "SUPER_ADMIN"),
                    "full_name": p.get("full_name", "Registered User"),
                    "mobile_number": p.get("mobile_number", ""),
                    "account_status": p.get("account_status", "ACTIVE"),
                    "email_verified": p.get("email_verified", True),
                    "mobile_verified": p.get("mobile_verified", False),
                    "registration_date": p.get("created_at", datetime.now(timezone.utc).isoformat()),
                    "last_login": p.get("last_login_at", datetime.now(timezone.utc).isoformat()),
                    "suspended_at": p.get("suspended_at"),
                    "suspension_reason": p.get("suspension_reason"),
                    "suspension_delete_at": p.get("suspension_delete_at"),
                    "suspension_reviewed_at": p.get("suspension_reviewed_at"),
                    "suspension_reviewed_by": p.get("suspension_reviewed_by")
                }
                with _LOCK:
                    REGISTERED_USERS[user_id] = entry
                db.upsert_user(entry)
                return entry
        except Exception as e:
            logger.debug(f"Supabase get_profile_by_email notice: {e}")

    return None

def check_email_status(email: str) -> Dict[str, Any]:
    """
    Checks if an email already exists and whether it is verified.
    Returns:
      {"exists": True, "verified": True, "message": "This email address is already linked to an account."}
      {"exists": True, "verified": False, "message": "This email address already has a pending verification."}
      {"exists": False, "verified": False}
    """
    clean_email = email.strip().lower()

    # 1. Check verified registered users
    existing = get_user_by_email(clean_email)
    if existing:
        is_ver = existing.get("email_verified", True)
        if is_ver:
            return {
                "exists": True,
                "verified": True,
                "message": "This email address is already linked to an account."
            }
        else:
            return {
                "exists": True,
                "verified": False,
                "message": "This email address already has a pending verification."
            }

    # 2. Check pending unverified signups
    with _LOCK:
        if clean_email in PENDING_VERIFICATIONS:
            return {
                "exists": True,
                "verified": False,
                "message": "This email address already has a pending verification."
            }

    return {"exists": False, "verified": False}

def update_user_email(user_id: str, new_email: str) -> bool:
    clean_email = new_email.strip().lower()
    with _LOCK:
        if user_id in REGISTERED_USERS:
            REGISTERED_USERS[user_id]["email"] = clean_email
    try:
        db.upsert_user({"id": user_id, "email": clean_email})
    except Exception as e:
        logger.warning(f"Failed to update user email in SQLite: {e}")

    # Also update Supabase
    if SupabaseService.is_configured():
        return SupabaseService.update_user_email(user_id, clean_email)
    return True

def get_all_users(search: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieves all registered users from SQLite, merged with Supabase and in-memory registry.
    """
    results: Dict[str, Dict[str, Any]] = {}

    # 1. Primary dataset: Persistent SQLite database
    try:
        db_users = db.get_all_users(search=search)
        for u in db_users:
            results[u["id"]] = dict(u)
    except Exception as e:
        logger.warning(f"Failed to query users from SQLite: {e}")

    # 2. Merge from Supabase profiles if configured
    if SupabaseService.is_configured():
        try:
            profiles = SupabaseService.list_profiles(search=search)
            for p in profiles:
                uid = str(p.get("user_id") or p.get("id"))
                if uid not in results:
                    results[uid] = {
                        "id": uid,
                        "email": p.get("email", ""),
                        "role": p.get("role", "USER"),
                        "is_unlimited": p.get("role") in ("ADMIN", "SUPER_ADMIN"),
                        "full_name": p.get("full_name", "Registered User"),
                        "mobile_number": p.get("mobile_number", ""),
                        "account_status": p.get("account_status", "ACTIVE"),
                        "email_verified": p.get("email_verified", True),
                        "mobile_verified": p.get("mobile_verified", False),
                        "registration_date": p.get("created_at", "2024-01-01T00:00:00Z"),
                        "last_login": p.get("last_login_at", datetime.now(timezone.utc).isoformat()),
                        "suspended_at": p.get("suspended_at"),
                        "suspension_reason": p.get("suspension_reason"),
                        "suspension_delete_at": p.get("suspension_delete_at"),
                        "suspension_reviewed_at": p.get("suspension_reviewed_at"),
                        "suspension_reviewed_by": p.get("suspension_reviewed_by")
                    }
        except Exception as e:
            logger.debug(f"Supabase list_profiles notice: {e}")

    # 3. Merge in-memory registered users (taking priority for local dev and overrides)
    with _LOCK:
        for uid, u in REGISTERED_USERS.items():
            if uid not in results:
                results[uid] = dict(u)
            else:
                # Merge fields
                for k, v in u.items():
                    if v is not None:
                        results[uid][k] = v

    # 4. Apply search filter if provided
    final_list = list(results.values())
    if search:
        s = search.lower().strip()
        final_list = [
            u for u in final_list
            if s in u.get("email", "").lower()
            or s in u.get("full_name", "").lower()
            or s in str(u.get("username", "")).lower()
            or s in str(u.get("id", "")).lower()
            or s in u.get("account_status", "").lower()
            or s in u.get("mobile_number", "").lower()
        ]

    # Sort descending by registration date
    return sorted(final_list, key=lambda x: str(x.get("registration_date", "")), reverse=True)

def calculate_deletion_date(suspended_at_input: Optional[Union[str, datetime]] = None) -> str:
    """Calculates scheduled deletion date exactly 3 calendar months (90 days) from suspended_at."""
    if not suspended_at_input:
        dt = datetime.now(timezone.utc)
    elif isinstance(suspended_at_input, datetime):
        dt = suspended_at_input
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    else:
        try:
            dt = datetime.fromisoformat(str(suspended_at_input).replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
    deletion_dt = dt + timedelta(days=90)
    return deletion_dt.isoformat()

def is_deletion_eligible(deletion_date_iso: Optional[str]) -> bool:
    """Returns True if the 3-month suspension window has lapsed."""
    if not deletion_date_iso:
        return False
    try:
        dt = datetime.fromisoformat(deletion_date_iso.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) >= dt
    except Exception:
        return False

def suspend_user(
    user_id: str,
    reason: Optional[str] = None,
    admin_by: Optional[str] = None
) -> Dict[str, Any]:
    """Suspends user account, records timestamps, calculates deletion date, and persists."""
    now_iso = datetime.now(timezone.utc).isoformat()
    deletion_iso = calculate_deletion_date(now_iso)
    with _LOCK:
        entry = REGISTERED_USERS.get(user_id)
        if not entry:
            for u in REGISTERED_USERS.values():
                if u.get("email") == user_id.lower().strip():
                    entry = u
                    user_id = u["id"]
                    break
        if entry:
            entry["account_status"] = "SUSPENDED"
            entry["suspended_at"] = now_iso
            entry["suspension_reason"] = reason
            entry["suspension_delete_at"] = deletion_iso
            entry["suspension_reviewed_at"] = now_iso
            entry["suspension_reviewed_by"] = admin_by
        else:
            entry = {
                "id": user_id,
                "email": user_id if "@" in user_id else f"{user_id}@example.com",
                "role": "USER",
                "is_unlimited": False,
                "full_name": "Suspended User",
                "mobile_number": "",
                "account_status": "SUSPENDED",
                "email_verified": True,
                "mobile_verified": False,
                "registration_date": now_iso,
                "last_login": now_iso,
                "suspended_at": now_iso,
                "suspension_reason": reason,
                "suspension_delete_at": deletion_iso,
                "suspension_reviewed_at": now_iso,
                "suspension_reviewed_by": admin_by
            }
            REGISTERED_USERS[user_id] = entry

    # Persist suspension to SQLite
    try:
        db.upsert_user(entry)
    except Exception as e:
        logger.warning(f"Failed to persist suspension to SQLite: {e}")

    # Update in admin globals
    try:
        from app.api.admin import USER_ACCOUNT_STATUSES, SUSPENDED_USERS
        USER_ACCOUNT_STATUSES[user_id] = "SUSPENDED"
        SUSPENDED_USERS.add(user_id)
        if entry.get("email"):
            USER_ACCOUNT_STATUSES[entry["email"]] = "SUSPENDED"
            SUSPENDED_USERS.add(entry["email"])
    except Exception:
        pass

    # Update Supabase profile if configured
    if SupabaseService.is_configured():
        try:
            SupabaseService.upsert_profile({
                "user_id": user_id,
                "account_status": "SUSPENDED",
                "is_active": False,
                "suspended_at": now_iso,
                "suspension_reason": reason,
                "suspension_delete_at": deletion_iso,
                "suspension_reviewed_at": now_iso,
                "suspension_reviewed_by": admin_by
            })
        except Exception as e:
            logger.debug(f"Failed to persist suspension to Supabase: {e}")

    return dict(entry)

def recover_user(
    user_id: str,
    admin_by: Optional[str] = None
) -> Dict[str, Any]:
    """Recovers user account, clears suspension fields, and restores active status."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        entry = REGISTERED_USERS.get(user_id)
        if not entry:
            for u in REGISTERED_USERS.values():
                if u.get("email") == user_id.lower().strip():
                    entry = u
                    user_id = u["id"]
                    break
        if entry:
            entry["account_status"] = "ACTIVE"
            entry["suspended_at"] = None
            entry["suspension_reason"] = None
            entry["suspension_delete_at"] = None
            entry["suspension_reviewed_at"] = now_iso
            entry["suspension_reviewed_by"] = admin_by
        else:
            entry = {
                "id": user_id,
                "email": user_id if "@" in user_id else f"{user_id}@example.com",
                "role": "USER",
                "is_unlimited": False,
                "full_name": "Recovered User",
                "mobile_number": "",
                "account_status": "ACTIVE",
                "email_verified": True,
                "mobile_verified": False,
                "registration_date": now_iso,
                "last_login": now_iso,
                "suspended_at": None,
                "suspension_reason": None,
                "suspension_delete_at": None,
                "suspension_reviewed_at": now_iso,
                "suspension_reviewed_by": admin_by
            }
            REGISTERED_USERS[user_id] = entry

    # Persist recovery to SQLite
    try:
        db.upsert_user(entry)
    except Exception as e:
        logger.warning(f"Failed to persist recovery to SQLite: {e}")

    # Update in admin globals
    try:
        from app.api.admin import USER_ACCOUNT_STATUSES, SUSPENDED_USERS
        USER_ACCOUNT_STATUSES[user_id] = "ACTIVE"
        SUSPENDED_USERS.discard(user_id)
        if entry.get("email"):
            USER_ACCOUNT_STATUSES[entry["email"]] = "ACTIVE"
            SUSPENDED_USERS.discard(entry["email"])
    except Exception:
        pass

    # Update Supabase profile
    if SupabaseService.is_configured():
        try:
            SupabaseService.upsert_profile({
                "user_id": user_id,
                "account_status": "ACTIVE",
                "is_active": True,
                "suspended_at": None,
                "suspension_reason": None,
                "suspension_delete_at": None,
                "suspension_reviewed_at": now_iso,
                "suspension_reviewed_by": admin_by
            })
        except Exception as e:
            logger.warning(f"Failed to persist recovery to Supabase: {e}")

    return dict(entry)

def get_user_suspension_info(user_id_or_email: str) -> Optional[Dict[str, Any]]:
    """Retrieves full suspension dossier for a user."""
    key = user_id_or_email.strip().lower()
    with _LOCK:
        user = REGISTERED_USERS.get(key)
        if not user:
            for u in REGISTERED_USERS.values():
                if u.get("email", "").lower() == key or str(u.get("id", "")).lower() == key:
                    user = u
                    break
        if user:
            status = user.get("account_status", "ACTIVE")
            is_susp = status in ("SUSPENDED", "BLOCKED", "DEACTIVATED")
            del_at = user.get("suspension_delete_at")
            return {
                "user_id": user.get("id"),
                "email": user.get("email"),
                "full_name": user.get("full_name"),
                "account_status": status,
                "is_suspended": is_susp,
                "suspended_at": user.get("suspended_at"),
                "suspension_reason": user.get("suspension_reason"),
                "suspension_delete_at": del_at,
                "is_eligible_for_deletion": is_deletion_eligible(del_at) if is_susp else False,
                "suspension_reviewed_at": user.get("suspension_reviewed_at"),
                "suspension_reviewed_by": user.get("suspension_reviewed_by")
            }
    return None

# ============================================================================
# ACTIVE USER SESSION & PERSISTENCE MANAGEMENT (PRD Section 38)
# ============================================================================
ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}
REFRESH_TOKENS: Dict[str, str] = {}  # refresh_token -> token

def create_user_session(
    user_id: str,
    email: str,
    role: str = "USER",
    is_unlimited: bool = False,
    full_name: Optional[str] = None,
    explicit_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Issues and persists an authenticated user session.
    Guarantees session persistence and eliminates false 'session expired' race conditions.
    """
    import uuid
    token = explicit_token or f"kh-ses-{uuid.uuid4().hex}"
    refresh_token = f"kh-ref-{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=7)

    clean_email = email.strip().lower()
    clean_name = full_name or clean_email.split("@")[0].capitalize()

    with _LOCK:
        session_data = {
            "token": token,
            "refresh_token": refresh_token,
            "user_id": user_id,
            "email": clean_email,
            "role": role,
            "is_unlimited": is_unlimited,
            "full_name": clean_name,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat()
        }
        ACTIVE_SESSIONS[token] = session_data
        REFRESH_TOKENS[refresh_token] = token

    logger.info(f"Active session created for {clean_email} ({user_id})")
    return session_data

def get_user_session(token: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves and validates an active user session by token.
    Returns session dict if valid and non-expired; None otherwise.
    """
    if not token:
        return None
    with _LOCK:
        session = ACTIVE_SESSIONS.get(token)
        if not session:
            return None
        # Check expiration
        try:
            exp = datetime.fromisoformat(session["expires_at"])
            if datetime.now(timezone.utc) > exp:
                # Expired
                ACTIVE_SESSIONS.pop(token, None)
                REFRESH_TOKENS.pop(session.get("refresh_token", ""), None)
                return None
        except Exception:
            pass
        return dict(session)

def refresh_user_session(refresh_token: str) -> Optional[Dict[str, Any]]:
    """
    Rotates session tokens using a valid refresh token.
    """
    if not refresh_token:
        return None
    import uuid
    with _LOCK:
        old_token = REFRESH_TOKENS.get(refresh_token)
        if not old_token:
            return None
        old_session = ACTIVE_SESSIONS.get(old_token)
        if not old_session:
            REFRESH_TOKENS.pop(refresh_token, None)
            return None

        # Generate fresh tokens
        new_token = f"kh-ses-{uuid.uuid4().hex}"
        new_refresh = f"kh-ref-{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=7)

        new_session = {
            **old_session,
            "token": new_token,
            "refresh_token": new_refresh,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat()
        }

        # Purge old mappings and store new
        ACTIVE_SESSIONS.pop(old_token, None)
        REFRESH_TOKENS.pop(refresh_token, None)

        ACTIVE_SESSIONS[new_token] = new_session
        REFRESH_TOKENS[new_refresh] = new_token

        logger.info(f"Refreshed session for user {new_session.get('email')}")
        return {
            "token": new_token,
            "refresh_token": new_refresh,
            "user_id": new_session["user_id"],
            "email": new_session["email"]
        }

def revoke_user_session(token: str) -> bool:
    """Revokes an active session."""
    with _LOCK:
        session = ACTIVE_SESSIONS.pop(token, None)
        if session:
            REFRESH_TOKENS.pop(session.get("refresh_token", ""), None)
            return True
    return False

