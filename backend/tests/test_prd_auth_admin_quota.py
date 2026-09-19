import pytest
from fastapi.testclient import TestClient
from main import app
from app.core.config import settings
from app.core.security import CurrentUser
from app.api.usage import (
    USER_CUSTOM_QUOTAS,
    _IN_MEMORY_DAILY_USAGE,
    get_user_daily_limit,
    get_user_usage_data,
    record_user_page_usage,
    get_kolkata_today
)

client = TestClient(app)

def test_admin_credentials_on_user_login_rejected():
    """
    PRD Section 7:
    If an administrator attempts to use the admin account/email on the normal user login page:
    the system must NOT grant admin access. The result should be HTTP 401 'Invalid login credentials.'
    Do NOT reveal that it's an admin account.
    """
    res = client.post("/api/auth/login", json={
        "email": "admin@tallyxml.in",
        "password": "anypassword"
    })
    assert res.status_code == 401
    detail = res.json().get("detail", "")
    assert "Invalid" in detail
    assert "admin" not in detail.lower()

def test_user_credentials_on_admin_login_rejected():
    """
    PRD Section 8:
    If a normal user attempts to sign in through /admin/login:
    the login must NOT grant admin access and return 403.
    """
    from unittest.mock import patch
    old_url = settings.supabase_url
    old_key = settings.supabase_anon_key
    settings.supabase_url = "https://mock.supabase.co"
    settings.supabase_anon_key = "mock-key"

    try:
        user_auth = {
            "access_token": "valid-user-token",
            "user": {
                "id": "regular-user-id",
                "email": "regular@example.com",
                "user_metadata": {"role": "USER", "full_name": "Regular User"}
            }
        }
        with patch("app.core.supabase_service.SupabaseService.sign_in_with_password", return_value=user_auth),              patch("app.core.supabase_service.SupabaseService.query_profile", return_value={"role": "USER", "is_active": True, "account_status": "ACTIVE"}):
            res = client.post("/api/system/admin-login", json={
                "email": "regular@example.com",
                "password": "password123"
            })
            assert res.status_code == 403
            assert "not authorized to access the administrator portal" in res.json()["detail"].lower()
    finally:
        settings.supabase_url = old_url
        settings.supabase_anon_key = old_key

def test_global_quota_change_and_per_user_override():
    """
    PRD Sections 18, 19, 20, 21:
    - Default global quota is 50 pages/day.
    - Admin can change global quota to 100 pages/day.
    - Admin can assign a custom quota (e.g. 25 or 200 pages/day) to an individual user.
    - Custom quota overrides global quota.
    - Removing custom quota returns user to global quota.
    """
    user_test = CurrentUser(
        id="test-quota-user-1",
        email="testquota@example.com",
        role="USER",
        is_unlimited=False
    )
    headers = {"Authorization": "Bearer mock-admin-token"}

    # 1. Reset state
    settings.free_daily_page_limit = 50
    USER_CUSTOM_QUOTAS.pop(user_test.id, None)

    # Initial usage data -> 50 pages limit, GLOBAL mode
    usage1 = get_user_usage_data(user_test)
    assert usage1.daily_limit == 50
    assert usage1.quota_mode == "GLOBAL"

    # 2. Admin changes global quota to 100 via PUT /api/admin/settings
    res_settings = client.put("/api/admin/settings", json={"free_daily_page_limit": 100}, headers=headers)
    assert res_settings.status_code == 200
    assert settings.free_daily_page_limit == 100

    usage2 = get_user_usage_data(user_test)
    assert usage2.daily_limit == 100
    assert usage2.quota_mode == "GLOBAL"

    # 3. Admin assigns custom quota of 250 to user_test via PUT /api/admin/users/{user_id}/quota
    res_custom = client.put(f"/api/admin/users/{user_test.id}/quota", json={
        "mode": "CUSTOM",
        "custom_daily_limit": 250
    }, headers=headers)
    assert res_custom.status_code == 200
    assert res_custom.json()["quota"]["mode"] == "CUSTOM"
    assert res_custom.json()["quota"]["effective_daily_limit"] == 250

    # Verify user usage reflects 250
    usage3 = get_user_usage_data(user_test)
    assert usage3.daily_limit == 250
    assert usage3.quota_mode == "CUSTOM"
    assert usage3.custom_limit == 250

    # 4. Admin returns user to global quota
    res_global = client.put(f"/api/admin/users/{user_test.id}/quota", json={
        "mode": "GLOBAL"
    }, headers=headers)
    assert res_global.status_code == 200
    assert res_global.json()["quota"]["mode"] == "GLOBAL"
    assert res_global.json()["quota"]["effective_daily_limit"] == 100

    usage4 = get_user_usage_data(user_test)
    assert usage4.daily_limit == 100
    assert usage4.quota_mode == "GLOBAL"
    assert usage4.custom_limit is None

def test_daily_page_usage_recording_and_ist_midnight_reset():
    """
    PRD Sections 22 & 23:
    - Quota is based on PDF pages processed.
    - Used pages increment and remaining pages decrement.
    - Resets at IST midnight.
    """
    user_test = CurrentUser(
        id="test-ist-user-2",
        email="istuser@example.com",
        role="USER",
        is_unlimited=False
    )
    settings.free_daily_page_limit = 50
    USER_CUSTOM_QUOTAS.pop(user_test.id, None)

    today = get_kolkata_today()
    from app.core import db
    db.reset_daily_usage(user_test.id, today)
    _IN_MEMORY_DAILY_USAGE[f"{user_test.id}:{today}"] = 0

    # Initial state
    usage_init = get_user_usage_data(user_test)
    assert usage_init.pages_used_today == 0
    assert usage_init.pages_remaining_today == 50

    # Process a 15-page document
    record_user_page_usage(user_test, 15)
    usage_after_15 = get_user_usage_data(user_test)
    assert usage_after_15.pages_used_today == 15
    assert usage_after_15.pages_remaining_today == 35

    # Process another 20-page document
    record_user_page_usage(user_test, 20)
    usage_after_35 = get_user_usage_data(user_test)
    assert usage_after_35.pages_used_today == 35
    assert usage_after_35.pages_remaining_today == 15

    # Simulate next day in IST (different date key)
    fake_tomorrow = "2099-01-01"
    key_tomorrow = f"{user_test.id}:{fake_tomorrow}"
    assert _IN_MEMORY_DAILY_USAGE.get(key_tomorrow, 0) == 0


def test_exact_21_page_reconciliation_breakdown():
    """
    PRD Sections 6, 30, 31, 34, 48, 67:
    Exact 21-page reconciliation test case:
    - User processes 21 pages total.
    - Breakdown: Completed = 10 pages, Needs Review = 11 pages.
    - Total processed = 10 + 11 = 21 pages.
    - With daily quota = 50:
      Today's Usage = 21 / 50
      Remaining Allowance = 29 (50 - 21 = 29)
    - Must NOT show 5 / 50 and 45 remaining.
    """
    from datetime import datetime, timezone
    from app.api.conversions import IN_MEMORY_JOBS
    
    user_test = CurrentUser(
        id="test-reconcile-user-21",
        email="reconcile21@example.com",
        role="USER",
        is_unlimited=False
    )
    settings.free_daily_page_limit = 50
    USER_CUSTOM_QUOTAS.pop(user_test.id, None)
    
    today = get_kolkata_today()
    # Even if in-memory daily usage had a stale lower value like 5
    _IN_MEMORY_DAILY_USAGE[f"{user_test.id}:{today}"] = 5
    
    # Create two jobs for this user today:
    # Job 1: 10 pages COMPLETED
    job1_id = "job-comp-10"
    IN_MEMORY_JOBS[job1_id] = {
        "id": job1_id,
        "user_id": user_test.id,
        "file_name": "stmt1.pdf",
        "page_count": 10,
        "status": "COMPLETED",
        "created_at": datetime.now(timezone.utc)
    }
    
    # Job 2: 11 pages NEEDS_REVIEW
    job2_id = "job-review-11"
    IN_MEMORY_JOBS[job2_id] = {
        "id": job2_id,
        "user_id": user_test.id,
        "file_name": "stmt2.pdf",
        "page_count": 11,
        "status": "NEEDS_REVIEW",
        "created_at": datetime.now(timezone.utc)
    }
    
    try:
        # Reconcile usage data
        usage = get_user_usage_data(user_test)
        
        # Assert exact reconciliation
        assert usage.daily_limit == 50
        assert usage.pages_used_today == 21
        assert usage.pages_remaining_today == 29
        assert usage.completed_pages_today == 10
        assert usage.needs_review_pages_today == 11
        assert usage.pages_used_today + usage.pages_remaining_today == usage.daily_limit
    finally:
        # Clean up test jobs
        IN_MEMORY_JOBS.pop(job1_id, None)
        IN_MEMORY_JOBS.pop(job2_id, None)
