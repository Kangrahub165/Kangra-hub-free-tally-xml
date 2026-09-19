import pytest
import sys
import os
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app

client = TestClient(app)

def test_health_check():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["app"] == "Kangra Hub Free Tally XML"

def test_public_settings():
    res = client.get("/api/system/public-settings")
    assert res.status_code == 200
    data = res.json()
    assert "site_mode" in data
    assert data["free_daily_page_limit"] == 50

def test_list_banks():
    res = client.get("/api/banks")
    assert res.status_code == 200
    banks = res.json()
    assert len(banks) >= 38
    pnb = next((b for b in banks if "Punjab National Bank" in b["bank_name"]), None)
    assert pnb is not None

def test_user_usage_endpoint():
    res = client.get("/api/usage", headers={"Authorization": "Bearer mock-user-token"})
    assert res.status_code == 200
    data = res.json()
    assert data["daily_limit"] == 50
    assert data["is_unlimited"] is False

def test_admin_metrics_access_control():
    # Regular user attempting admin access -> 403 Forbidden
    res = client.get("/api/admin/metrics", headers={"Authorization": "Bearer mock-user-token"})
    assert res.status_code == 403

    # Admin access -> 200 OK
    res_admin = client.get("/api/admin/metrics", headers={"Authorization": "Bearer mock-admin-token"})
    assert res_admin.status_code == 200
    metrics = res_admin.json()
    assert "total_users" in metrics
    assert "current_site_mode" in metrics

def test_admin_grant_unlimited_flow():
    # Admin grants unlimited to a test user
    target_user_id = "test-user-grant"
    res = client.post(
        f"/api/admin/users/{target_user_id}/unlimited",
        headers={"Authorization": "Bearer mock-admin-token"}
    )
    assert res.status_code == 200
    assert res.json()["success"] is True

    # Check user list has unlimited
    users_res = client.get("/api/admin/users", headers={"Authorization": "Bearer mock-admin-token"})
    target = next((u for u in users_res.json() if u["id"] == target_user_id), None)
    assert target is not None
    assert target["is_unlimited"] is True

    # Revoke unlimited
    rev_res = client.delete(
        f"/api/admin/users/{target_user_id}/unlimited",
        headers={"Authorization": "Bearer mock-admin-token"}
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["success"] is True

def test_unauthenticated_requests_return_401():
    # Calling protected user endpoints without auth header must return 401
    res_usage = client.get("/api/usage")
    assert res_usage.status_code == 401
    assert "Authentication required" in res_usage.json()["detail"]

    # Calling admin endpoints without auth header must return 401
    res_admin = client.get("/api/admin/metrics")
    assert res_admin.status_code == 401

    # Calling upload without auth header must return 401
    res_upload = client.post("/api/conversions/upload")
    assert res_upload.status_code == 401

def test_admin_verify_endpoint():
    # 1. Unauthenticated -> 401
    res_no_auth = client.get("/api/admin/verify")
    assert res_no_auth.status_code == 401

    # 2. Standard user -> 403 Forbidden
    res_user = client.get("/api/admin/verify", headers={"Authorization": "Bearer mock-user-token"})
    assert res_user.status_code == 403

    # 3. Unlimited (non-admin) user -> 403 Forbidden (CRITICAL: unlimited != admin)
    res_unlimited = client.get("/api/admin/verify", headers={"Authorization": "Bearer mock-unlimited-token"})
    assert res_unlimited.status_code == 403

    # 4. Verified Admin -> 200 OK
    res_admin = client.get("/api/admin/verify", headers={"Authorization": "Bearer mock-admin-token"})
    assert res_admin.status_code == 200
    data = res_admin.json()
    assert data["is_admin"] is True
    assert data["status"] == "authorized"
    assert data["user"]["role"] in ("ADMIN", "SUPER_ADMIN")

def test_admin_login_fails_without_supabase_configuration():
    """
    CRITICAL SECURITY TEST:
    Verify that when Supabase is not configured, admin login FAILS SAFELY with HTTP 503.
    It MUST NEVER accept fallback passwords (e.g. 'admin12345'), MUST NOT issue tokens,
    and MUST NOT create admin sessions.
    """
    from app.core.config import settings
    # Ensure supabase settings are empty
    old_url = settings.supabase_url
    old_key = settings.supabase_anon_key
    settings.supabase_url = ""
    settings.supabase_anon_key = ""

    try:
        # 1. Even with correct email and legacy dev password -> 503 Service Unavailable
        res = client.post("/api/system/admin-login", json={"email": "admin@tallyxml.in", "password": "admin12345"})
        assert res.status_code == 503
        assert "Supabase authentication service is not configured" in res.json()["detail"]

        # 2. Random credentials -> also 503 Service Unavailable
        res2 = client.post("/api/system/admin-login", json={"email": "anyone@example.com", "password": "anypassword"})
        assert res2.status_code == 503
    finally:
        settings.supabase_url = old_url
        settings.supabase_anon_key = old_key


def test_admin_login_with_supabase_mock():
    """
    Verify complete Supabase Authentication & Role Verification:
    - Invalid credentials -> 401 Unauthorized
    - Standard user (profiles.role == 'USER') -> 403 Forbidden
    - Verified administrator (profiles.role == 'ADMIN') -> 200 OK with token
    """
    from unittest.mock import MagicMock, patch
    from app.core.config import settings

    old_url = settings.supabase_url
    old_key = settings.supabase_anon_key
    settings.supabase_url = "https://mock.supabase.co"
    settings.supabase_anon_key = "mock-anon-key"

    try:
        # 1. Invalid credentials -> Auth error -> 401
        with patch("app.core.supabase_service.SupabaseService.sign_in_with_password", side_effect=RuntimeError("Invalid login credentials")):
            res_bad = client.post("/api/system/admin-login", json={"email": "admin@tallyxml.in", "password": "wrong"})
            assert res_bad.status_code == 401
            assert "Authentication failed" in res_bad.json()["detail"]

        # 2. Standard user (role = 'USER') -> 403 Forbidden
        user_auth_data = {
            "access_token": "valid-user-jwt",
            "user": {
                "id": "standard-user-id",
                "email": "standard@example.com",
                "user_metadata": {"role": "USER", "full_name": "Standard User"}
            }
        }
        with patch("app.core.supabase_service.SupabaseService.sign_in_with_password", return_value=user_auth_data), \
             patch("app.core.supabase_service.SupabaseService.query_profile", return_value={"role": "USER", "is_active": True, "account_status": "ACTIVE"}):
            res_user = client.post("/api/system/admin-login", json={"email": "standard@example.com", "password": "password"})
            assert res_user.status_code == 403
            assert "Access Denied" in res_user.json()["detail"]

        # 3. Valid Admin (role = 'ADMIN') -> 200 OK
        admin_auth_data = {
            "access_token": "valid-admin-jwt",
            "user": {
                "id": "admin-uuid-1234",
                "email": "admin@tallyxml.in",
                "user_metadata": {"role": "ADMIN", "full_name": "Authoritative Admin"}
            }
        }
        with patch("app.core.supabase_service.SupabaseService.sign_in_with_password", return_value=admin_auth_data), \
             patch("app.core.supabase_service.SupabaseService.query_profile", return_value={"role": "ADMIN", "is_active": True, "account_status": "ACTIVE"}), \
             patch("app.core.supabase_service.SupabaseService.query_user_access", return_value={"unlimited": True, "access_type": "UNLIMITED"}):
            res_admin = client.post("/api/system/admin-login", json={"email": "admin@tallyxml.in", "password": "realpassword"})
            assert res_admin.status_code == 200
            data = res_admin.json()
            assert data["is_admin"] is True
            assert data["token"] == "valid-admin-jwt"
            assert data["user"]["role"] == "ADMIN"
            assert data["user"]["email"] == "admin@tallyxml.in"
    finally:
        settings.supabase_url = old_url
        settings.supabase_anon_key = old_key

def test_unlimited_user_blocked_from_all_admin_endpoints():
    """Verify that having is_unlimited=True does NOT give access to any admin route."""
    headers = {"Authorization": "Bearer mock-unlimited-token"}
    routes = [
        "/api/admin/metrics",
        "/api/admin/users",
        "/api/admin/conversions",
        "/api/admin/parsers/health",
        "/api/admin/settings",
        "/api/admin/logs",
        "/api/admin/accounting",
        "/api/admin/notifications",
        "/api/admin/security",
    ]
    for route in routes:
        res = client.get(route, headers=headers)
        assert res.status_code == 403, f"Expected 403 for unlimited non-admin on {route}, got {res.status_code}"


def test_admin_forgot_password_workflow():
    """Verify admin password recovery logic and administrative notifications routing."""
    from unittest.mock import MagicMock, patch
    from app.core.config import settings

    old_url = settings.supabase_url
    old_key = settings.supabase_anon_key

    try:
        # 1. Unconfigured Supabase -> 503
        settings.supabase_url = ""
        settings.supabase_anon_key = ""
        res_503 = client.post("/api/system/admin-forgot-password", json={"email": "admin@tallyxml.in"})
        assert res_503.status_code == 503

        # Configure mock Supabase
        settings.supabase_url = "https://mock.supabase.co"
        settings.supabase_anon_key = "mock-anon-key"

        mock_client = MagicMock()

        # 2. Non-admin email -> 404
        with patch("app.core.supabase_service.SupabaseService.query_profile", return_value=None):
            res_not_found = client.post("/api/system/admin-forgot-password", json={"email": "intruder@example.com"})
            assert res_not_found.status_code == 404

        # 3. Valid admin login email -> 200 with kangrahub@gmail.com recovery notice
        with patch("app.core.supabase_service.SupabaseService.reset_password", return_value={}):
            res_ok = client.post("/api/system/admin-forgot-password", json={"email": "admin@tallyxml.in"})
            assert res_ok.status_code == 200
            data = res_ok.json()
            assert data["success"] is True
            assert data["recovery_email"] == "kangrahub@gmail.com"
            assert "kangrahub@gmail.com" in data["message"]
    finally:
        settings.supabase_url = old_url
        settings.supabase_anon_key = old_key


