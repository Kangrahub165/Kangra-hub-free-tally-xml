import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from app.core.config import settings
from app.core.supabase_service import SupabaseService

client = TestClient(app)


def test_login_diagnostics_unconfigured_supabase():
    """Verify that both /api/auth/login and /api/system/admin-login return clear 503 diagnostic messages when Supabase is not configured."""
    old_url = settings.supabase_url
    old_key = settings.supabase_anon_key
    old_env = settings.app_env
    settings.supabase_url = ""
    settings.supabase_anon_key = ""
    settings.app_env = "staging"

    try:
        # 1. Normal user login
        resp_user = client.post("/api/auth/login", json={"email": "user@example.com", "password": "password123"})
        assert resp_user.status_code == 503
        detail_user = resp_user.json().get("detail", "")
        assert "Supabase authentication service is not configured on the server" in detail_user
        assert "SUPABASE_URL" in detail_user and "SUPABASE_ANON_KEY" in detail_user

        # 2. Administrator login
        resp_admin = client.post("/api/system/admin-login", json={"email": "admin@tallyxml.in", "password": "password123"})
        assert resp_admin.status_code == 503
        detail_admin = resp_admin.json().get("detail", "")
        assert "Supabase authentication service is not configured on the server" in detail_admin
        assert "SUPABASE_URL" in detail_admin and "SUPABASE_ANON_KEY" in detail_admin

        # 3. Health check reports unconfigured state
        resp_health = client.get("/health")
        assert resp_health.status_code == 200
        health_data = resp_health.json()
        assert health_data["supabase_connected"] is False
        assert health_data["supabase_url_configured"] is False
        assert health_data["supabase_key_configured"] is False
    finally:
        settings.supabase_url = old_url
        settings.supabase_anon_key = old_key
        settings.app_env = old_env


def test_user_login_success_with_supabase():
    """Verify normal user login succeeds when Supabase is configured with valid credentials."""
    old_url = settings.supabase_url
    old_key = settings.supabase_anon_key
    old_env = settings.app_env
    settings.supabase_url = "https://mock.supabase.co"
    settings.supabase_anon_key = "mock-anon-key"
    settings.app_env = "staging"

    user_auth = {
        "access_token": "valid-user-jwt-token",
        "refresh_token": "valid-refresh-token",
        "user": {
            "id": "mock-user-123",
            "email": "normal.user@example.com",
            "user_metadata": {"full_name": "Normal Test User", "role": "USER"}
        }
    }

    try:
        with patch.object(SupabaseService, "sign_in_with_password", return_value=user_auth), \
             patch.object(SupabaseService, "query_profile", return_value={"role": "USER", "is_active": True, "account_status": "ACTIVE"}), \
             patch.object(SupabaseService, "query_user_access", return_value={"unlimited": False}):
            resp = client.post("/api/auth/login", json={"email": "normal.user@example.com", "password": "validpassword"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["token"] == "valid-user-jwt-token"
            assert data["user"]["email"] == "normal.user@example.com"
            assert data["user"]["role"] == "USER"
    finally:
        settings.supabase_url = old_url
        settings.supabase_anon_key = old_key
        settings.app_env = old_env


def test_user_login_invalid_credentials_rejected():
    """Verify normal user login rejects invalid credentials with HTTP 401."""
    old_url = settings.supabase_url
    old_key = settings.supabase_anon_key
    old_env = settings.app_env
    settings.supabase_url = "https://mock.supabase.co"
    settings.supabase_anon_key = "mock-anon-key"
    settings.app_env = "staging"

    try:
        with patch.object(SupabaseService, "sign_in_with_password", side_effect=RuntimeError("Invalid login credentials")):
            resp = client.post("/api/auth/login", json={"email": "normal.user@example.com", "password": "wrongpassword"})
            assert resp.status_code == 401
            assert "Invalid email or password" in resp.json().get("detail", "")
    finally:
        settings.supabase_url = old_url
        settings.supabase_anon_key = old_key
        settings.app_env = old_env


def test_admin_login_success_with_supabase():
    """Verify administrator login succeeds when Supabase is configured with valid admin credentials."""
    old_url = settings.supabase_url
    old_key = settings.supabase_anon_key
    settings.supabase_url = "https://mock.supabase.co"
    settings.supabase_anon_key = "mock-anon-key"

    admin_auth = {
        "access_token": "valid-admin-jwt-token",
        "user": {
            "id": "mock-admin-456",
            "email": "admin@tallyxml.in",
            "user_metadata": {"full_name": "Platform Admin", "role": "ADMIN"}
        }
    }

    try:
        with patch.object(SupabaseService, "sign_in_with_password", return_value=admin_auth), \
             patch.object(SupabaseService, "query_profile", return_value={"role": "ADMIN", "is_active": True, "account_status": "ACTIVE"}), \
             patch.object(SupabaseService, "query_user_access", return_value={"unlimited": True}):
            resp = client.post("/api/system/admin-login", json={"email": "admin@tallyxml.in", "password": "adminpassword"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["is_admin"] is True
            assert data["token"] == "valid-admin-jwt-token"
            assert data["user"]["role"] in ("ADMIN", "SUPER_ADMIN")
    finally:
        settings.supabase_url = old_url
        settings.supabase_anon_key = old_key


def test_admin_login_non_admin_blocked():
    """Verify standard user attempting admin portal login is blocked with HTTP 403."""
    old_url = settings.supabase_url
    old_key = settings.supabase_anon_key
    settings.supabase_url = "https://mock.supabase.co"
    settings.supabase_anon_key = "mock-anon-key"

    standard_user_auth = {
        "access_token": "standard-user-token",
        "user": {
            "id": "standard-user-789",
            "email": "standard@example.com",
            "user_metadata": {"full_name": "Standard User", "role": "USER"}
        }
    }

    try:
        with patch.object(SupabaseService, "sign_in_with_password", return_value=standard_user_auth), \
             patch.object(SupabaseService, "query_profile", return_value={"role": "USER", "is_active": True, "account_status": "ACTIVE"}):
            resp = client.post("/api/system/admin-login", json={"email": "standard@example.com", "password": "userpassword"})
            assert resp.status_code == 403
            assert "not authorized to access the administrator portal" in resp.json().get("detail", "").lower()
    finally:
        settings.supabase_url = old_url
        settings.supabase_anon_key = old_key


def test_resilient_next_public_env_detection():
    """Verify that NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY are dynamically detected."""
    old_url = settings.supabase_url
    old_key = settings.supabase_anon_key
    settings.supabase_url = ""
    settings.supabase_anon_key = ""

    with patch.dict(os.environ, {
        "NEXT_PUBLIC_SUPABASE_URL": "https://resilient.supabase.co",
        "NEXT_PUBLIC_SUPABASE_ANON_KEY": "resilient-anon-key-123"
    }):
        assert SupabaseService.get_url() == "https://resilient.supabase.co"
        assert SupabaseService.get_api_key() == "resilient-anon-key-123"
        assert SupabaseService.is_configured() is True
    settings.supabase_url = old_url
    settings.supabase_anon_key = old_key
