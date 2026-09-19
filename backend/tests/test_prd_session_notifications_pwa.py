import pytest
from fastapi.testclient import TestClient
from main import app
from app.core.user_store import (
    create_user_session,
    get_user_session,
    refresh_user_session,
    revoke_user_session,
    ACTIVE_SESSIONS,
    REGISTERED_USERS
)
from app.api.admin import CONTACT_MESSAGES, READ_NOTIFICATION_IDS

client = TestClient(app)

def test_user_session_store_lifecycle():
    """Verify session creation, lookup, refresh, and revocation."""
    session = create_user_session(
        user_id="test-session-user-1",
        email="testsession@example.com",
        full_name="Session Test User"
    )
    assert session is not None
    token = session["token"]
    refresh_tok = session["refresh_token"]

    # Verify session lookup
    found = get_user_session(token)
    assert found is not None
    assert found["user_id"] == "test-session-user-1"
    assert found["email"] == "testsession@example.com"

    # Verify session refresh
    refreshed = refresh_user_session(refresh_tok)
    assert refreshed is not None
    new_token = refreshed["token"]
    assert new_token != token

    # Old token should be invalidated
    assert get_user_session(token) is None
    # New token should be active
    assert get_user_session(new_token) is not None

    # Revocation
    revoke_user_session(new_token)
    assert get_user_session(new_token) is None


def test_section_38_login_returns_active_session_and_authenticates():
    """Verify Section 38 fix: valid login credentials yield a token that immediately authenticates /api/usage without 401."""
    # User login in dev mode (or registered user)
    login_res = client.post("/api/auth/login", json={
        "email": "customer@example.com",
        "password": "Password123!"
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    data = login_res.json()
    token = data.get("token")
    assert token is not None, "Login response did not return a session token"

    # Verify token is in ACTIVE_SESSIONS
    active = get_user_session(token)
    assert active is not None
    assert active["email"] == "customer@example.com"

    # Access user usage without 401
    headers = {"Authorization": f"Bearer {token}"}
    usage_res = client.get("/api/usage", headers=headers)
    assert usage_res.status_code == 200, f"Usage returned error: {usage_res.status_code} - {usage_res.text}"
    usage_data = usage_res.json()
    assert "daily_limit" in usage_data or "pages_used_today" in usage_data


def test_public_contact_and_admin_notification_pipeline():
    """Verify contact submission feeds into Admin Notification Center with live counts."""
    # 1. Submit a public contact message
    contact_payload = {
        "name": "Rajesh Sharma",
        "email": "rajesh@kangrahub.test",
        "subject_type": "REPORT_ISSUE",
        "bank_name": "State Bank of India",
        "message": "Need assistance parsing cooperative bank statement format."
    }
    contact_res = client.post("/api/system/contact", json=contact_payload)
    assert contact_res.status_code == 200, f"Contact submission failed: {contact_res.text}"
    contact_data = contact_res.json()
    assert contact_data["success"] is True
    ref_id = contact_data["reference_id"]
    assert ref_id.startswith("msg-")

    # 2. Query admin notifications unread counts (using admin mock auth)
    admin_headers = {"Authorization": "Bearer mock-admin-token"}
    counts_res = client.get("/api/admin/notifications/unread-counts", headers=admin_headers)
    assert counts_res.status_code == 200
    counts = counts_res.json()
    assert counts["categories"]["contact_messages"] >= 1
    assert counts["total_unread"] >= 1

    # 3. Query admin notifications feed
    feed_res = client.get("/api/admin/notifications/feed", headers=admin_headers)
    assert feed_res.status_code == 200
    feed = feed_res.json()
    found_item = any(item.get("id") == ref_id for item in feed.get("items", []))
    assert found_item is True

    # 4. Mark notification as read
    mark_res = client.post("/api/admin/notifications/mark-read", json={"notification_id": ref_id}, headers=admin_headers)
    assert mark_res.status_code == 200
    assert mark_res.json()["success"] is True

    # 5. Query contact messages list in admin console
    inbox_res = client.get("/api/admin/contact-messages", headers=admin_headers)
    assert inbox_res.status_code == 200
    inbox_items = inbox_res.json().get("messages", [])
    assert any(msg["id"] == ref_id for msg in inbox_items)
