import json
import logging
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List
from app.core.config import settings

logger = logging.getLogger("kangra_hub")

class SupabaseService:
    """
    Universal Supabase HTTP Client supporting both legacy JWT keys and
    modern publishable keys (sb_publishable_*) without external SDK regex limitations.
    """

    @staticmethod
    def is_configured() -> bool:
        return bool(settings.supabase_url and (settings.supabase_anon_key or settings.supabase_service_role_key))

    @staticmethod
    def get_api_key() -> str:
        return settings.supabase_anon_key or settings.supabase_service_role_key

    @classmethod
    def sign_in_with_password(cls, email: str, password: str) -> Dict[str, Any]:
        """Authenticates a user via Supabase Auth."""
        if not cls.is_configured():
            raise RuntimeError("Supabase authentication is not configured.")

        url = f"{settings.supabase_url.rstrip('/')}/auth/v1/token?grant_type=password"
        payload = json.dumps({"email": email.strip(), "password": password}).encode("utf-8")
        headers = {
            "apikey": cls.get_api_key(),
            "Content-Type": "application/json"
        }

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8")
            try:
                err_json = json.loads(err_body)
                error_msg = err_json.get("msg") or err_json.get("error_description") or err_json.get("message") or err_body
            except Exception:
                error_msg = err_body
            raise RuntimeError(error_msg)
        except Exception as exc:
            raise RuntimeError(str(exc))

    @classmethod
    def sign_up(cls, email: str, password: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Registers a new user in Supabase Auth."""
        if not cls.is_configured():
            raise RuntimeError("Supabase authentication is not configured.")

        url = f"{settings.supabase_url.rstrip('/')}/auth/v1/signup"
        payload_data: Dict[str, Any] = {"email": email.strip(), "password": password}
        if metadata:
            payload_data["data"] = metadata

        payload = json.dumps(payload_data).encode("utf-8")
        headers = {
            "apikey": cls.get_api_key(),
            "Content-Type": "application/json"
        }

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8")
            try:
                err_json = json.loads(err_body)
                error_msg = err_json.get("msg") or err_json.get("error_description") or err_json.get("message") or err_body
            except Exception:
                error_msg = err_body
            raise RuntimeError(error_msg)
        except Exception as exc:
            raise RuntimeError(str(exc))

    @classmethod
    def refresh_session(cls, refresh_token: str) -> Dict[str, Any]:
        """Refreshes session token via Supabase Auth."""
        if not cls.is_configured():
            raise RuntimeError("Supabase authentication is not configured.")

        url = f"{settings.supabase_url.rstrip('/')}/auth/v1/token?grant_type=refresh_token"
        payload = json.dumps({"refresh_token": refresh_token.strip()}).encode("utf-8")
        headers = {
            "apikey": cls.get_api_key(),
            "Content-Type": "application/json"
        }

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8")
            try:
                err_json = json.loads(err_body)
                error_msg = err_json.get("msg") or err_json.get("error_description") or err_json.get("message") or err_body
            except Exception:
                error_msg = err_body
            raise RuntimeError(error_msg)
        except Exception as exc:
            raise RuntimeError(str(exc))

    @classmethod
    def get_user(cls, access_token: str) -> Dict[str, Any]:
        """Retrieves user profile data from Supabase Auth using their session JWT."""
        if not cls.is_configured():
            raise RuntimeError("Supabase authentication is not configured.")

        url = f"{settings.supabase_url.rstrip('/')}/auth/v1/user"
        headers = {
            "apikey": cls.get_api_key(),
            "Authorization": f"Bearer {access_token}"
        }

        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8")
            try:
                err_json = json.loads(err_body)
                error_msg = err_json.get("msg") or err_json.get("error_description") or err_json.get("message") or err_body
            except Exception:
                error_msg = err_body
            raise RuntimeError(error_msg)

    @classmethod
    def reset_password(cls, email: str, redirect_to: Optional[str] = None) -> Dict[str, Any]:
        """Dispatches password recovery email via Supabase Auth."""
        if not cls.is_configured():
            raise RuntimeError("Supabase authentication is not configured.")

        url = f"{settings.supabase_url.rstrip('/')}/auth/v1/recover"
        body: Dict[str, Any] = {"email": email.strip()}
        if redirect_to:
            body["redirect_to"] = redirect_to
        payload = json.dumps(body).encode("utf-8")
        headers = {
            "apikey": cls.get_api_key(),
            "Content-Type": "application/json"
        }

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as res:
                content = res.read().decode("utf-8")
                return json.loads(content) if content else {}
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8")
            try:
                err_json = json.loads(err_body)
                error_msg = err_json.get("msg") or err_json.get("error_description") or err_json.get("message") or err_body
            except Exception:
                error_msg = err_body
            raise RuntimeError(error_msg)

    @classmethod
    def query_profile(cls, user_id: str, user_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Queries public.profiles for user role and status."""
        if not cls.is_configured():
            return None

        auth_token = settings.supabase_service_role_key or user_token or cls.get_api_key()
        url = f"{settings.supabase_url.rstrip('/')}/rest/v1/profiles?user_id=eq.{user_id}&select=role,account_status,is_active"
        headers = {
            "apikey": cls.get_api_key(),
            "Authorization": f"Bearer {auth_token}"
        }

        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req) as res:
                data = json.loads(res.read().decode("utf-8"))
                if data and isinstance(data, list) and len(data) > 0:
                    return data[0]
                return None
        except Exception as exc:
            logger.warning(f"Unable to query profiles for {user_id}: {exc}")
            return None

    @classmethod
    def query_user_access(cls, user_id: str, user_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Queries public.user_access for unlimited entitlement."""
        if not cls.is_configured():
            return None

        auth_token = settings.supabase_service_role_key or user_token or cls.get_api_key()
        url = f"{settings.supabase_url.rstrip('/')}/rest/v1/user_access?user_id=eq.{user_id}&select=unlimited,access_type"
        headers = {
            "apikey": cls.get_api_key(),
            "Authorization": f"Bearer {auth_token}"
        }

        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req) as res:
                data = json.loads(res.read().decode("utf-8"))
                if data and isinstance(data, list) and len(data) > 0:
                    return data[0]
                return None
        except Exception as exc:
            logger.warning(f"Unable to query user_access for {user_id}: {exc}")
            return None

    @classmethod
    def list_profiles(cls, user_token: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """Queries public.profiles for all user profiles."""
        if not cls.is_configured():
            return []

        auth_token = settings.supabase_service_role_key or user_token or cls.get_api_key()
        url = f"{settings.supabase_url.rstrip('/')}/rest/v1/profiles?select=*&order=created_at.desc"
        headers = {
            "apikey": cls.get_api_key(),
            "Authorization": f"Bearer {auth_token}"
        }

        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req) as res:
                data = json.loads(res.read().decode("utf-8"))
                if isinstance(data, list):
                    if search:
                        s = search.lower()
                        return [
                            p for p in data
                            if s in (p.get("email") or "").lower()
                            or s in (p.get("full_name") or "").lower()
                            or s in str(p.get("user_id") or "").lower()
                        ]
                    return data
                return []
        except Exception as exc:
            logger.warning(f"Unable to list profiles from Supabase: {exc}")
            return []

    @classmethod
    def get_profile_by_email(cls, email: str, user_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Finds a profile in public.profiles by email address."""
        if not cls.is_configured():
            return None

        clean_email = email.strip().lower()
        auth_token = settings.supabase_service_role_key or user_token or cls.get_api_key()
        url = f"{settings.supabase_url.rstrip('/')}/rest/v1/profiles?email=eq.{clean_email}&select=*"
        headers = {
            "apikey": cls.get_api_key(),
            "Authorization": f"Bearer {auth_token}"
        }

        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req) as res:
                data = json.loads(res.read().decode("utf-8"))
                if data and isinstance(data, list) and len(data) > 0:
                    return data[0]
                return None
        except Exception as exc:
            logger.warning(f"Unable to get profile by email for {clean_email}: {exc}")
            return None

    @classmethod
    def upsert_profile(cls, profile_data: Dict[str, Any], user_token: Optional[str] = None) -> bool:
        """Upserts a user profile in public.profiles."""
        if not cls.is_configured():
            return False

        auth_token = settings.supabase_service_role_key or user_token or cls.get_api_key()
        url = f"{settings.supabase_url.rstrip('/')}/rest/v1/profiles"
        payload = json.dumps(profile_data).encode("utf-8")
        headers = {
            "apikey": cls.get_api_key(),
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as res:
                return res.status in (200, 201, 204)
        except Exception as exc:
            logger.warning(f"Unable to upsert profile for {profile_data.get('email')}: {exc}")
            return False

    @classmethod
    def update_user_email(cls, user_id: str, new_email: str, admin_token: Optional[str] = None) -> bool:
        """Updates user email in public.profiles and Supabase Auth admin if key is available."""
        if not cls.is_configured():
            return False

        clean_email = new_email.strip().lower()
        auth_token = settings.supabase_service_role_key or admin_token or cls.get_api_key()

        # Update profile table
        url_profile = f"{settings.supabase_url.rstrip('/')}/rest/v1/profiles?user_id=eq.{user_id}"
        payload = json.dumps({"email": clean_email}).encode("utf-8")
        headers = {
            "apikey": cls.get_api_key(),
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }

        profile_updated = False
        try:
            req = urllib.request.Request(url_profile, data=payload, headers=headers, method="PATCH")
            with urllib.request.urlopen(req) as res:
                profile_updated = res.status in (200, 204)
        except Exception as exc:
            logger.warning(f"Unable to update profile email for {user_id}: {exc}")

        # Try admin auth update if service role is available
        if settings.supabase_service_role_key:
            try:
                url_auth = f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users/{user_id}"
                auth_payload = json.dumps({"email": clean_email, "email_confirm": True}).encode("utf-8")
                auth_headers = {
                    "apikey": settings.supabase_service_role_key,
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                    "Content-Type": "application/json"
                }
                auth_req = urllib.request.Request(url_auth, data=auth_payload, headers=auth_headers, method="PUT")
                with urllib.request.urlopen(auth_req) as res:
                    pass
            except Exception as exc:
                logger.warning(f"Unable to update auth user email in Supabase Auth for {user_id}: {exc}")

        return profile_updated

    @classmethod
    def list_appeals(cls, status: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """Queries public.account_appeals via REST."""
        if not cls.is_configured():
            return []
        auth_token = settings.supabase_service_role_key or cls.get_api_key()
        url = f"{settings.supabase_url.rstrip('/')}/rest/v1/account_appeals?select=*&order=created_at.desc"
        if status and status.upper() != "ALL":
            url += f"&status=eq.{status.lower()}"
        headers = {
            "apikey": cls.get_api_key(),
            "Authorization": f"Bearer {auth_token}"
        }
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req) as res:
                data = json.loads(res.read().decode("utf-8"))
                if isinstance(data, list):
                    if search:
                        s = search.lower()
                        return [
                            a for a in data
                            if s in (a.get("user_email") or "").lower()
                            or s in (a.get("user_name") or "").lower()
                            or s in str(a.get("id") or "").lower()
                        ]
                    return data
                return []
        except Exception as exc:
            logger.warning(f"Unable to list account_appeals from Supabase: {exc}")
            return []

    @classmethod
    def get_appeal(cls, appeal_id: str) -> Optional[Dict[str, Any]]:
        """Queries a single appeal by ID from public.account_appeals."""
        if not cls.is_configured():
            return None
        auth_token = settings.supabase_service_role_key or cls.get_api_key()
        url = f"{settings.supabase_url.rstrip('/')}/rest/v1/account_appeals?id=eq.{appeal_id}&select=*"
        headers = {
            "apikey": cls.get_api_key(),
            "Authorization": f"Bearer {auth_token}"
        }
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req) as res:
                data = json.loads(res.read().decode("utf-8"))
                if data and isinstance(data, list) and len(data) > 0:
                    return data[0]
                return None
        except Exception as exc:
            logger.warning(f"Unable to get appeal {appeal_id} from Supabase: {exc}")
            return None

    @classmethod
    def insert_appeal(cls, appeal_data: Dict[str, Any]) -> bool:
        """Inserts a new appeal into public.account_appeals."""
        if not cls.is_configured():
            return False
        auth_token = settings.supabase_service_role_key or cls.get_api_key()
        url = f"{settings.supabase_url.rstrip('/')}/rest/v1/account_appeals"
        payload = json.dumps(appeal_data).encode("utf-8")
        headers = {
            "apikey": cls.get_api_key(),
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req) as res:
                return res.status in (200, 201, 204)
        except Exception as exc:
            logger.warning(f"Unable to insert appeal into Supabase: {exc}")
            return False

    @classmethod
    def update_appeal(cls, appeal_id: str, update_data: Dict[str, Any]) -> bool:
        """Updates an appeal in public.account_appeals."""
        if not cls.is_configured():
            return False
        auth_token = settings.supabase_service_role_key or cls.get_api_key()
        url = f"{settings.supabase_url.rstrip('/')}/rest/v1/account_appeals?id=eq.{appeal_id}"
        payload = json.dumps(update_data).encode("utf-8")
        headers = {
            "apikey": cls.get_api_key(),
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="PATCH")
            with urllib.request.urlopen(req) as res:
                return res.status in (200, 204)
        except Exception as exc:
            logger.warning(f"Unable to update appeal {appeal_id} in Supabase: {exc}")
            return False

    @classmethod
    def query_user_appeals(cls, identifier: str) -> List[Dict[str, Any]]:
        """Queries appeals for a user by email or user_id."""
        if not cls.is_configured():
            return []
        clean = identifier.strip().lower()
        auth_token = settings.supabase_service_role_key or cls.get_api_key()
        url = f"{settings.supabase_url.rstrip('/')}/rest/v1/account_appeals?or=(user_email.eq.{clean},user_id.eq.{clean})&select=*&order=created_at.desc"
        headers = {
            "apikey": cls.get_api_key(),
            "Authorization": f"Bearer {auth_token}"
        }
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req) as res:
                data = json.loads(res.read().decode("utf-8"))
                if isinstance(data, list):
                    return data
                return []
        except Exception as exc:
            logger.warning(f"Unable to query user appeals from Supabase: {exc}")
            return []

