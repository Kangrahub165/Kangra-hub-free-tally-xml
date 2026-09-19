import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from main import app
from app.core.config import settings
from app.core.security import CurrentUser
from app.core import db
from app.core.user_store import register_user, suspend_user, REGISTERED_USERS
from app.api.usage import (
    record_user_page_usage,
    get_kolkata_today,
    _IN_MEMORY_DAILY_USAGE,
    USER_CUSTOM_QUOTAS,
    get_user_usage_data
)
from app.api.conversions import IN_MEMORY_JOBS

client = TestClient(app)
ADMIN_HEADERS = {"Authorization": "Bearer mock-admin-token"}

@pytest.fixture(autouse=True)
def setup_test_state():
    """Ensure baseline settings for every test."""
    settings.free_daily_page_limit = 50

def test_a_new_user_registration_appears_in_admin():
    """
    Test A: New user registration appears in Admin Users with 0 pages used and 50 pages remaining.
    """
    new_uid = "usr-test-a-newbie"
    new_email = "newbie_test_a@example.com"
    new_name = "Alice Test A"
    
    reg_user = register_user(
        user_id=new_uid,
        email=new_email,
        full_name=new_name,
        role="USER",
        is_unlimited=False
    )
    assert reg_user["email"] == new_email

    # Query admin users endpoint
    res = client.get(f"/api/admin/users?search={new_email}", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    users = res.json()
    assert len(users) >= 1
    target = next((u for u in users if u["email"] == new_email), None)
    assert target is not None
    assert target["full_name"] == new_name
    assert target["today_usage"] == 0
    assert target["role"] == "USER"
    assert target["is_suspended"] is False

    # Also check inspect/details endpoint
    res_details = client.get(f"/api/admin/users/{new_uid}", headers=ADMIN_HEADERS)
    assert res_details.status_code == 200
    details = res_details.json()
    assert details["today_usage"] == 0
    assert details["pages_remaining_today"] == 50
    assert details["total_conversions"] == 0

def test_b_existing_old_user_appears():
    """
    Test B: Existing old user created before recent changes appears with full name and email.
    """
    old_uid = "usr-old-legacy-user"
    old_email = "legacy_b@example.com"
    old_name = "Legacy Bob"

    db.upsert_user({
        "id": old_uid,
        "email": old_email,
        "full_name": old_name,
        "username": "legacybob",
        "mobile_number": "+919123456780",
        "role": "USER",
        "registration_date": "2023-01-01T00:00:00Z"
    })

    res = client.get(f"/api/admin/users?search={old_email}", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    users = res.json()
    found = next((u for u in users if u["email"] == old_email), None)
    assert found is not None
    assert found["full_name"] == old_name
    assert found["mobile_number"] == "+919123456780"

def test_c_user_processes_10_pages():
    """
    Test C: User processes 10 pages -> today_usage = 10, remaining = 40.
    """
    uid = "usr-test-c-usage"
    email = "test_c_usage@example.com"
    today = get_kolkata_today()
    register_user(user_id=uid, email=email, full_name="Charlie C")
    db.reset_daily_usage(uid, today)
    _IN_MEMORY_DAILY_USAGE[f"{uid}:{today}"] = 0

    user_obj = CurrentUser(id=uid, email=email, role="USER", is_unlimited=False)
    
    # Record 10 pages used
    record_user_page_usage(user_obj, 10)

    # Check via admin list
    res = client.get(f"/api/admin/users?search={email}", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    target = next((u for u in res.json() if u["email"] == email), None)
    assert target is not None
    assert target["today_usage"] == 10

    # Check via admin details
    res_details = client.get(f"/api/admin/users/{uid}", headers=ADMIN_HEADERS)
    assert res_details.status_code == 200
    details = res_details.json()
    assert details["today_usage"] == 10
    assert details["pages_remaining_today"] == 40

def test_d_user_processes_20_more_pages():
    """
    Test D: Same user from Test C processes 20 more pages -> today_usage = 30, remaining = 20.
    """
    uid = "usr-test-c-usage"
    email = "test_c_usage@example.com"
    today = get_kolkata_today()
    db.reset_daily_usage(uid, today)
    db.record_daily_usage(uid, today, 10)
    _IN_MEMORY_DAILY_USAGE[f"{uid}:{today}"] = 10

    user_obj = CurrentUser(id=uid, email=email, role="USER", is_unlimited=False)

    record_user_page_usage(user_obj, 20)

    res_details = client.get(f"/api/admin/users/{uid}", headers=ADMIN_HEADERS)
    assert res_details.status_code == 200
    details = res_details.json()
    assert details["today_usage"] == 30
    assert details["pages_remaining_today"] == 20

def test_e_103_page_pdf_partial_processing_quota_accounting():
    """
    Test E: 103-page PDF with 50 free quota:
    - 50 pages processed, 53 pages skipped.
    - today_usage = 50, remaining = 0.
    - Skipped pages are NEVER added to usage.
    """
    uid = "usr-test-e-partial"
    email = "partial_test_e@example.com"
    today = get_kolkata_today()
    register_user(user_id=uid, email=email, full_name="Partial Tester E")
    db.reset_daily_usage(uid, today)
    _IN_MEMORY_DAILY_USAGE[f"{uid}:{today}"] = 0

    user_obj = CurrentUser(id=uid, email=email, role="USER", is_unlimited=False)

    # Save conversion record
    job_id = "job-partial-103-pages"
    db.save_conversion({
        "id": job_id,
        "user_id": uid,
        "user_email": email,
        "file_name": "large_statement_103.pdf",
        "bank_name": "HDFC Bank",
        "statement_format": "PDF",
        "total_pdf_pages": 103,
        "pages_processed": 50,
        "pages_skipped": 53,
        "free_quota_used": 50,
        "additional_quota_used": 0,
        "transaction_count": 210,
        "status": "PARTIALLY_COMPLETED",
        "is_partial_conversion": 1
    })

    # Record ONLY processed pages to quota
    record_user_page_usage(user_obj, 50)

    # Verify admin details
    res_details = client.get(f"/api/admin/users/{uid}", headers=ADMIN_HEADERS)
    assert res_details.status_code == 200
    details = res_details.json()
    assert details["today_usage"] == 50
    assert details["pages_remaining_today"] == 0

    # Verify conversion history
    convs = details["conversions"]
    assert len(convs) >= 1
    conv = next((c for c in convs if c["id"] == job_id), None)
    assert conv is not None
    assert conv["total_pdf_pages"] == 103
    assert conv["pages_processed"] == 50
    assert conv["pages_skipped"] == 53
    assert conv["is_partial_conversion"] is True

def test_f_user_with_0_conversions_visible():
    """
    Test F: User with 0 conversions remains visible with 0 usage.
    """
    uid = "usr-test-f-zero-conv"
    email = "zero_conv_f@example.com"
    register_user(user_id=uid, email=email, full_name="Zero Conversions User")

    res = client.get(f"/api/admin/users?search={email}", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    users = res.json()
    target = next((u for u in users if u["email"] == email), None)
    assert target is not None
    assert target["today_usage"] == 0

    res_details = client.get(f"/api/admin/users/{uid}", headers=ADMIN_HEADERS)
    assert res_details.status_code == 200
    details = res_details.json()
    assert details["total_conversions"] == 0
    assert details["today_usage"] == 0
    assert details["conversions"] == []

def test_g_suspended_user_remains_visible():
    """
    Test G: Suspended user remains visible in Admin Users with Suspended status.
    """
    uid = "usr-test-g-suspended"
    email = "suspended_g@example.com"
    register_user(user_id=uid, email=email, full_name="Suspended User G")
    
    # Suspend user
    suspend_user(uid, reason="Violation of Terms of Service", admin_by="admin@tallyxml.in")

    res = client.get(f"/api/admin/users?search={email}", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    users = res.json()
    target = next((u for u in users if u["email"] == email), None)
    assert target is not None
    assert target["is_suspended"] is True
    assert target["account_status"] == "SUSPENDED"

    res_details = client.get(f"/api/admin/users/{uid}", headers=ADMIN_HEADERS)
    assert res_details.status_code == 200
    details = res_details.json()
    assert details["is_suspended"] is True
    assert details["suspension_reason"] == "Violation of Terms of Service"

def test_h_admin_account_remains_visible():
    """
    Test H: Admin account remains visible with Admin Unlimited allowance.
    """
    res = client.get("/api/admin/users?search=admin@tallyxml.in", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    users = res.json()
    admin_u = next((u for u in users if u["email"] == "admin@tallyxml.in"), None)
    assert admin_u is not None
    assert admin_u["role"] == "ADMIN"
    assert admin_u["daily_allowance"] == "Admin Unlimited"

    res_details = client.get(f"/api/admin/users/{admin_u['id']}", headers=ADMIN_HEADERS)
    assert res_details.status_code == 200
    details = res_details.json()
    assert details["role"] == "ADMIN"
    assert details["daily_allowance"] == "Admin Unlimited"
    assert details["pages_remaining_today"] == 999999

def test_i_search_by_multiple_fields():
    """
    Test I: Search by name, username, email, mobile, and user ID filters accurately.
    """
    uid = "usr-search-target-99"
    email = "searchable_target@kangrahub.in"
    name = "Searchable Specialist"
    mobile = "+919988776655"
    username = "specialist99"

    db.upsert_user({
        "id": uid,
        "email": email,
        "full_name": name,
        "username": username,
        "mobile_number": mobile,
        "role": "USER"
    })

    # 1. Search by name
    res1 = client.get("/api/admin/users?search=Specialist", headers=ADMIN_HEADERS)
    assert any(u["id"] == uid for u in res1.json())

    # 2. Search by email
    res2 = client.get("/api/admin/users?search=searchable_target", headers=ADMIN_HEADERS)
    assert any(u["id"] == uid for u in res2.json())

    # 3. Search by mobile
    res3 = client.get("/api/admin/users?search=9988776655", headers=ADMIN_HEADERS)
    assert any(u["id"] == uid for u in res3.json())

    # 4. Search by username
    res4 = client.get("/api/admin/users?search=specialist99", headers=ADMIN_HEADERS)
    assert any(u["id"] == uid for u in res4.json())

    # 5. Search by ID
    res5 = client.get(f"/api/admin/users?search={uid}", headers=ADMIN_HEADERS)
    assert any(u["id"] == uid for u in res5.json())

def test_j_persistence_across_in_memory_state_loss():
    """
    Test J: Data persistence across server restart simulation:
    - User with conversions and usage is created.
    - In-memory data structures are cleared.
    - Database is queried via admin endpoint and all data is preserved.
    """
    import uuid
    suffix = uuid.uuid4().hex[:6]
    uid = f"usr-persist-j-{suffix}"
    email = f"persist_{suffix}@example.com"
    name = f"Persistent User {suffix}"
    job_id = f"job-persist-{suffix}"
    today = get_kolkata_today()

    db.upsert_user({
        "id": uid,
        "email": email,
        "full_name": name,
        "role": "USER",
        "is_unlimited": 0
    })
    db.record_daily_usage(uid, today, 35)
    db.save_conversion({
        "id": job_id,
        "user_id": uid,
        "user_email": email,
        "file_name": "persisted_statement.pdf",
        "bank_name": "State Bank of India",
        "statement_format": "PDF",
        "total_pdf_pages": 35,
        "pages_processed": 35,
        "pages_skipped": 0,
        "free_quota_used": 35,
        "transaction_count": 88,
        "status": "COMPLETED"
    })
    db.set_additional_pages(uid, 150)
    db.set_custom_quota(uid, 75)

    # Clear volatile in-memory caches to simulate complete restart
    _IN_MEMORY_DAILY_USAGE.clear()
    USER_CUSTOM_QUOTAS.clear()
    REGISTERED_USERS.pop(uid, None)
    IN_MEMORY_JOBS.pop(job_id, None)

    # Query admin endpoint after cache wipe
    res_details = client.get(f"/api/admin/users/{uid}", headers=ADMIN_HEADERS)
    assert res_details.status_code == 200
    details = res_details.json()

    assert details["full_name"] == name
    assert details["email"] == email
    assert details["today_usage"] == 35
    assert details["custom_daily_limit"] == 75
    assert details["effective_daily_limit"] == 75
    assert details["pages_remaining_today"] == 40  # 75 - 35 = 40
    assert details["additional_page_balance"] == 150
    assert details["total_conversions"] >= 1
    assert any(c["id"] == job_id for c in details["conversions"])
