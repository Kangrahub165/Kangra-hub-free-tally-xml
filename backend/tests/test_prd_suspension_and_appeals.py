import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from main import app
from app.core.config import settings
from app.core.user_store import (
    register_user,
    suspend_user,
    recover_user,
    get_user_suspension_info,
    calculate_deletion_date,
    is_deletion_eligible,
    REGISTERED_USERS,
)
from app.api.admin import USER_ACCOUNT_STATUSES
from app.api.appeals import APPEALS_STORE, _APPEALS_LOCK

client = TestClient(app)
ADMIN_HEADERS = {"Authorization": "Bearer mock-admin-token"}

@pytest.fixture(autouse=True)
def clean_appeals():
    """Ensure clean appeals store for each test."""
    with _APPEALS_LOCK:
        APPEALS_STORE.clear()
    yield
    with _APPEALS_LOCK:
        APPEALS_STORE.clear()


def test_scenario_1_admin_suspends_user_with_reason():
    """
    Scenario 1 (PRD Section 26):
    Admin suspends an active user.
    User status changes to SUSPENDED with suspension reason and scheduled deletion date.
    """
    user_id = "test-scenario-1-user"
    email = "scenario1@example.com"

    register_user(
        user_id=user_id,
        email=email,
        full_name="Scenario One User",
        role="USER",
        account_status="ACTIVE"
    )

    # Admin calls status update endpoint
    reason_text = "Violation of fair-use statement conversion policy"
    res = client.patch(
        f"/api/admin/users/{user_id}/status",
        json={"account_status": "SUSPENDED", "suspension_reason": reason_text},
        headers=ADMIN_HEADERS
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

    # Verify suspension info recorded
    s_info = get_user_suspension_info(user_id)
    assert s_info["is_suspended"] is True
    assert s_info["suspension_reason"] == reason_text
    assert s_info["suspended_at"] is not None
    assert s_info["suspension_delete_at"] is not None
    assert s_info["is_eligible_for_deletion"] is False


def test_scenario_2_suspended_user_login_denied_with_structured_payload():
    """
    Scenario 2 (PRD Section 26):
    Suspended user enters email and password on login.
    System strictly rejects authentication with HTTP 403 ACCOUNT_SUSPENDED
    and returns full suspension metadata.
    """
    user_id = "test-scenario-2-user"
    email = "scenario2.suspended@example.com"
    pwd = "SecurePassword123!"

    register_user(
        user_id=user_id,
        email=email,
        full_name="Suspended Accountant",
        role="USER",
        account_status="ACTIVE"
    )

    # Suspend user
    suspend_user(user_id, reason="Account flagged for unusual batch activity")

    # Attempt login
    login_res = client.post("/api/auth/login", json={"email": email, "password": pwd})
    assert login_res.status_code == 403
    err = login_res.json().get("detail", {})

    assert err.get("error") == "ACCOUNT_SUSPENDED"
    assert err.get("code") == "ACCOUNT_SUSPENDED"
    assert err.get("email") == email
    assert err.get("suspension_reason") == "Account flagged for unusual batch activity"
    assert err.get("suspended_at") is not None
    assert err.get("suspension_delete_at") is not None


def test_scenario_3_suspended_user_protected_api_denied():
    """
    Scenario 3 (PRD Section 26):
    Suspended user with an existing valid session calls a protected API endpoint.
    System denies access with HTTP 403 ACCOUNT_SUSPENDED.
    """
    user_id = "test-user-id"
    email = "user@example.com"

    # Suspend mock standard user
    suspend_user(user_id, reason="Security review in progress")

    try:
        user_headers = {"Authorization": "Bearer mock-user-token"}
        res = client.get("/api/auth/me", headers=user_headers)
        assert res.status_code == 403
        err = res.json().get("detail", {})
        assert err.get("error") == "ACCOUNT_SUSPENDED"
        assert err.get("code") == "ACCOUNT_SUSPENDED"
        assert err.get("suspension_reason") == "Security review in progress"
    finally:
        # Recover mock user
        recover_user(user_id)


def test_scenario_4_deletion_date_calculation_and_eligibility():
    """
    Scenario 4 (PRD Section 26):
    Verify 90-day deletion calculation and deletion eligibility flag.
    Account deletion is non-destructive (never deletes automatically;
    merely flags as eligible after 90 days / 3 months).
    """
    # 1. Fresh suspension today: not eligible
    now = datetime.now(timezone.utc)
    delete_date_str = calculate_deletion_date(now)
    assert delete_date_str is not None
    assert is_deletion_eligible(delete_date_str) is False

    # 2. Suspension from 95 days ago: eligible
    past_date = now - timedelta(days=95)
    past_delete_date_str = calculate_deletion_date(past_date)
    assert is_deletion_eligible(past_delete_date_str) is True


def test_scenario_5_suspended_user_submits_appeal():
    """
    Scenario 5 (PRD Section 26):
    Suspended user visits appeal portal and submits review request.
    System validates input, generates request ID, and sets status to pending.
    """
    user_id = "test-scenario-5-user"
    email = "scenario5.appeal@example.com"

    register_user(
        user_id=user_id,
        email=email,
        full_name="Appeal Submitter",
        role="USER",
        account_status="SUSPENDED"
    )
    suspend_user(user_id, reason="Terms review")

    appeal_body = {
        "email": email,
        "user_name": "Appeal Submitter",
        "subject": "Request to review my suspended account",
        "message": "Hello Administrator, I was converting standard bank statements for my firm. Please kindly restore my access."
    }

    res = client.post("/api/appeals/submit", json=appeal_body)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] == "pending"
    assert "request_id" in data

    # Check status endpoint for this user
    status_res = client.get(f"/api/appeals/status?email={email}")
    assert status_res.status_code == 200
    s_data = status_res.json()
    assert s_data["has_appeal"] is True
    assert s_data["appeal"]["status"] == "pending"
    assert s_data["appeal"]["user_email"] == email


def test_scenario_6_duplicate_pending_appeal_blocked():
    """
    Scenario 6 (PRD Section 19 & 26):
    User with pending appeal attempts to submit another appeal.
    System rejects duplicate submission with HTTP 400.
    """
    user_id = "test-scenario-6-user"
    email = "scenario6.duplicate@example.com"

    register_user(
        user_id=user_id,
        email=email,
        full_name="Duplicate Tester",
        role="USER",
        account_status="SUSPENDED"
    )

    # First submission -> succeeds
    res1 = client.post("/api/appeals/submit", json={
        "email": email,
        "message": "First appeal submission for account review."
    })
    assert res1.status_code == 200

    # Second submission -> blocked with 400
    res2 = client.post("/api/appeals/submit", json={
        "email": email,
        "message": "Second appeal submission attempt."
    })
    assert res2.status_code == 400
    assert "already have an appeal under review" in res2.json()["detail"].lower()


def test_scenario_7_admin_inspects_appeals_list_and_details():
    """
    Scenario 7 (PRD Section 26):
    Admin opens appeals dashboard, lists pending appeals, and inspects details.
    """
    email = "scenario7.inspection@example.com"
    sub_res = client.post("/api/appeals/submit", json={
        "email": email,
        "user_name": "Inspection User",
        "message": "Detailed explanation of legitimate accounting usage."
    })
    assert sub_res.status_code == 200
    appeal_id = sub_res.json()["request_id"]

    # Admin lists appeals
    list_res = client.get("/api/admin/appeals", headers=ADMIN_HEADERS)
    assert list_res.status_code == 200
    appeals = list_res.json()
    assert any(a["id"] == appeal_id for a in appeals)

    # Filter by status
    pending_res = client.get("/api/admin/appeals?status=pending", headers=ADMIN_HEADERS)
    assert pending_res.status_code == 200
    assert all(a["status"] == "pending" for a in pending_res.json())

    # Get specific appeal details
    detail_res = client.get(f"/api/admin/appeals/{appeal_id}", headers=ADMIN_HEADERS)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == appeal_id
    assert detail["user_email"] == email


def test_scenario_8_admin_approves_appeal_and_recovers_account():
    """
    Scenario 8 (PRD Section 13, 14, 26):
    Admin approves appeal and clicks 'Recover Account'.
    User status returns to ACTIVE, appeal marked 'approved', recovery email sent.
    """
    user_id = "test-scenario-8-user"
    email = "scenario8.recover@example.com"

    register_user(
        user_id=user_id,
        email=email,
        full_name="Recovered User",
        role="USER",
        account_status="SUSPENDED"
    )
    suspend_user(user_id, reason="Temporary investigation")

    # Submit appeal
    sub_res = client.post("/api/appeals/submit", json={
        "email": email,
        "message": "Please recover my account, I have verified my details."
    })
    appeal_id = sub_res.json()["request_id"]

    # Admin recovers account via appeal endpoint
    recover_res = client.post(f"/api/admin/appeals/{appeal_id}/recover", headers=ADMIN_HEADERS)
    assert recover_res.status_code == 200
    rec_data = recover_res.json()
    assert rec_data["success"] is True
    assert rec_data["status"] == "approved"

    # Verify user state is now ACTIVE
    s_info = get_user_suspension_info(user_id)
    assert s_info["is_suspended"] is False
    assert s_info["account_status"] == "ACTIVE"


def test_scenario_9_recovered_user_can_login_and_access_api():
    """
    Scenario 9 (PRD Section 26):
    Recovered user logs in again. Login succeeds and returns 200 OK with session data.
    """
    user_id = "test-scenario-9-user"
    email = "scenario9.login@example.com"
    pwd = "RecoveredPassword123!"

    register_user(
        user_id=user_id,
        email=email,
        full_name="Reactivated User",
        role="USER",
        account_status="ACTIVE"
    )

    # First suspend
    suspend_user(user_id, reason="Routine check")
    # Verify login blocked
    blocked_res = client.post("/api/auth/login", json={"email": email, "password": pwd})
    assert blocked_res.status_code == 403

    # Recover account
    recover_user(user_id)

    # Login now succeeds
    success_res = client.post("/api/auth/login", json={"email": email, "password": pwd})
    assert success_res.status_code == 200
    data = success_res.json()
    assert "token" in data
    assert data["user"]["email"] == email


def test_scenario_10_admin_rejects_appeal_and_maintains_suspension():
    """
    Scenario 10 (PRD Section 15, 17, 26):
    Admin rejects appeal and clicks 'Keep Suspended'.
    Appeal status changes to 'rejected' with admin response note.
    User remains SUSPENDED and cannot log in.
    """
    user_id = "test-scenario-10-user"
    email = "scenario10.reject@example.com"
    pwd = "StaySuspendedPassword123!"

    register_user(
        user_id=user_id,
        email=email,
        full_name="Persistently Suspended User",
        role="USER",
        account_status="ACTIVE"
    )
    suspend_user(user_id, reason="Repeated terms violations")

    # Submit appeal
    sub_res = client.post("/api/appeals/submit", json={
        "email": email,
        "message": "Appeal requesting restoration."
    })
    appeal_id = sub_res.json()["request_id"]

    # Admin rejects appeal
    reject_reason = "Account flagged for commercial reselling without authorization. Appeal denied."
    reject_res = client.post(
        f"/api/admin/appeals/{appeal_id}/reject",
        json={"admin_response": reject_reason},
        headers=ADMIN_HEADERS
    )
    assert reject_res.status_code == 200
    rej_data = reject_res.json()
    assert rej_data["success"] is True
    assert rej_data["status"] == "rejected"

    # Verify appeal status
    status_res = client.get(f"/api/appeals/status?email={email}")
    assert status_res.status_code == 200
    assert status_res.json()["appeal"]["status"] == "rejected"
    assert status_res.json()["appeal"]["admin_response"] == reject_reason

    # User must still be suspended
    s_info = get_user_suspension_info(user_id)
    assert s_info["is_suspended"] is True

    # User login must still be denied
    login_res = client.post("/api/auth/login", json={"email": email, "password": pwd})
    assert login_res.status_code == 403
    assert login_res.json()["detail"]["error"] == "ACCOUNT_SUSPENDED"
