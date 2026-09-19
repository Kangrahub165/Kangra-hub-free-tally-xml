import pytest
from fastapi.testclient import TestClient
from main import app
from app.core.config import settings
from app.core.security import CurrentUser
from app.core.user_store import (
    register_user,
    get_user_by_email,
    get_all_users,
    check_email_status,
    REGISTERED_USERS,
    PENDING_VERIFICATIONS
)
from app.core.recovery_service import recovery_service

client = TestClient(app)
ADMIN_HEADERS = {"Authorization": "Bearer mock-admin-token"}

def test_new_user_appears_in_admin_users_dashboard():
    """
    PRD Section 1 & Scope 1:
    When a new user successfully registers, that user MUST automatically appear in:
    Admin Dashboard -> Users.
    Also verifies zero sensitive secrets (passwords, hashes, OTPs) are leaked.
    """
    new_user_id = "test-new-user-prd-01"
    new_email = "newbie.accountant@example.com"

    # Register user into user store (simulating successful signup OTP verification)
    user_entry = register_user(
        user_id=new_user_id,
        email=new_email,
        full_name="Himachal Trader",
        mobile_number="+919876500001",
        role="USER",
        is_unlimited=False,
        account_status="ACTIVE",
        email_verified=True,
        mobile_verified=True
    )
    assert user_entry["id"] == new_user_id
    assert user_entry["email"] == new_email

    # Fetch users from admin API
    res = client.get("/api/admin/users", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    users = res.json()
    assert isinstance(users, list)

    # Locate user in admin response
    found = next((u for u in users if u["id"] == new_user_id or u["email"] == new_email), None)
    assert found is not None, f"Newly registered user {new_email} not found in admin users list"

    # Verify attributes
    assert found["email"] == new_email
    assert found["full_name"] == "Himachal Trader"
    assert found["account_status"] == "ACTIVE"
    assert found["email_verified"] is True
    assert found["role"] == "USER"
    assert found["quota_mode"] in ("GLOBAL", "CUSTOM", "UNLIMITED")
    assert "effective_daily_limit" in found

    # Strictly verify zero secrets are exposed
    sensitive_keys = ["password", "password_hash", "hashed_password", "otp", "otp_hash", "recovery_code", "secret"]
    for k in sensitive_keys:
        assert k not in found, f"Sensitive field '{k}' exposed in admin user response!"


def test_duplicate_verified_email_signup_blocked():
    """
    PRD Scope 6: Duplicate email signup handling.
    Verified email -> block signup, show conflict error.
    """
    existing_email = "customer@example.com"

    # 1. Pre-signup check-email API
    check_res = client.post("/api/auth/check-email", json={"email": existing_email})
    assert check_res.status_code == 200
    data = check_res.json()
    assert data["exists"] is True
    assert data["verified"] is True
    assert "already linked" in data.get("message", "").lower()

    # 2. Attempt to trigger send-otp for verified email -> HTTP 409 Conflict
    otp_res = client.post("/api/auth/signup/send-otp", json={
        "email": existing_email,
        "full_name": "Duplicate Impostor",
        "channel": "EMAIL"
    })
    assert otp_res.status_code == 409
    assert "already linked to an account" in otp_res.json().get("detail", "").lower()


def test_duplicate_unverified_email_signup_resend_allowed():
    """
    PRD Scope 6: Duplicate email signup handling.
    Unverified email -> allow resending verification code without creating duplicate profiles.
    """
    unverified_email = "pending.signup.tester@example.com"
    # Ensure clean slate
    PENDING_VERIFICATIONS.pop(unverified_email, None)
    REGISTERED_USERS.pop("pending-user-id", None)

    # 1. Initial check-email: does not exist
    check1 = client.post("/api/auth/check-email", json={"email": unverified_email})
    assert check1.status_code == 200
    assert check1.json()["exists"] is False

    # 2. First send-otp: initiates pending signup
    send1 = client.post("/api/auth/signup/send-otp", json={
        "email": unverified_email,
        "full_name": "Pending Trader",
        "channel": "EMAIL"
    })
    assert send1.status_code == 200
    assert send1.json()["success"] is True

    # 3. Second check-email: reports exists=True, verified=False
    check2 = client.post("/api/auth/check-email", json={"email": unverified_email})
    assert check2.status_code == 200
    assert check2.json()["exists"] is True
    assert check2.json()["verified"] is False

    # 4. User requests resend: must NOT be blocked with 409
    send2 = client.post("/api/auth/signup/send-otp", json={
        "email": unverified_email,
        "full_name": "Pending Trader",
        "channel": "EMAIL"
    })
    # Will either succeed or be rate-limited by cooldown, but NOT HTTP 409 Conflict!
    assert send2.status_code in (200, 429)
    if send2.status_code == 429:
        assert "wait" in str(send2.json().get("detail", "")).lower()


def test_two_step_account_recovery_full_lifecycle():
    """
    PRD Sections 24-30 & Scope 8:
    Two-Step Account Recovery:
      - Step 1: Admin ownership cross-check (signup date, statement conversions, usage patterns).
      - Step 2: Proposed new email OTP verification (OTP sent to new email; code verified before email update).
      - Complete recovery commits the email change only when BOTH Step 1 is PASSED and Step 2 is VERIFIED.
    """
    target_user_id = "usr-demo-1"
    original_email = REGISTERED_USERS[target_user_id]["email"]
    proposed_email = "rajesh.newaddress2026@example.com"

    # 1. Create a recovery request
    req = recovery_service.submit_request(
        account_identifier=original_email,
        user_id=target_user_id,
        known_email=original_email,
        requested_new_email=proposed_email,
        reason="Lost company email domain access. Recovering to personal domain.",
        identity_verification_info="Account holder Rajesh Sharma with SBI and HDFC bank statement imports.",
        account_history={"total_conversions": 14, "verified_user": True}
    )
    req_id = req.id
    assert req.status == "Pending"
    assert req.step1_status == "PENDING"
    assert req.step2_status == "PENDING"

    # 2. Step 2 dispatch BEFORE Step 1 PASSED must be rejected
    early_step2_res = client.post(
        f"/api/admin/recovery/requests/{req_id}/step2/send-code",
        json={"proposed_new_email": proposed_email},
        headers=ADMIN_HEADERS
    )
    assert early_step2_res.status_code == 400
    assert "step 1" in early_step2_res.json()["detail"].lower()

    # 3. Completion BEFORE Step 1 PASSED must be rejected
    early_complete_res = client.post(
        f"/api/admin/recovery/requests/{req_id}/complete",
        headers=ADMIN_HEADERS
    )
    assert early_complete_res.status_code == 400
    assert "step 1" in early_complete_res.json()["detail"].lower()

    # 4. Admin performs Step 1 review: PASSED
    step1_res = client.post(
        f"/api/admin/recovery/requests/{req_id}/step1",
        json={"result": "PASSED", "notes": "Cross-checked statement conversion timestamps and bank records."},
        headers=ADMIN_HEADERS
    )
    assert step1_res.status_code == 200
    updated_req = step1_res.json()["request"]
    assert updated_req["step1_status"] == "PASSED"
    assert updated_req["status"] == "Under Review"

    # 5. Completion BEFORE Step 2 VERIFIED must be rejected
    mid_complete_res = client.post(
        f"/api/admin/recovery/requests/{req_id}/complete",
        headers=ADMIN_HEADERS
    )
    assert mid_complete_res.status_code == 400
    assert "step 2" in mid_complete_res.json()["detail"].lower()

    # 6. Admin initiates Step 2: sends verification code to proposed new email
    step2_send_res = client.post(
        f"/api/admin/recovery/requests/{req_id}/step2/send-code",
        json={"proposed_new_email": proposed_email},
        headers=ADMIN_HEADERS
    )
    assert step2_send_res.status_code == 200
    step2_data = step2_send_res.json()
    assert step2_data["success"] is True

    # Retrieve dev OTP code for verification
    dev_code = step2_data.get("dev_code")
    assert dev_code is not None and len(dev_code) == 6

    # 7. Step 2 verify with INVALID code must fail
    bad_verify_res = client.post(
        f"/api/admin/recovery/requests/{req_id}/step2/verify-code",
        json={"otp": "000000"},
        headers=ADMIN_HEADERS
    )
    assert bad_verify_res.status_code == 400
    assert "incorrect" in bad_verify_res.json()["detail"].lower()

    # 8. Step 2 verify with VALID code
    good_verify_res = client.post(
        f"/api/admin/recovery/requests/{req_id}/step2/verify-code",
        json={"otp": dev_code},
        headers=ADMIN_HEADERS
    )
    assert good_verify_res.status_code == 200
    verify_req = good_verify_res.json()["request"]
    assert verify_req["step2_status"] == "VERIFIED"
    assert verify_req["status"] == "Approved"

    # 9. Complete recovery: commits new email
    complete_res = client.post(
        f"/api/admin/recovery/requests/{req_id}/complete",
        headers=ADMIN_HEADERS
    )
    assert complete_res.status_code == 200
    final_req = complete_res.json()["request"]
    assert final_req["status"] == "Completed"

    # Verify user profile email is updated in the user store
    updated_user = REGISTERED_USERS.get(target_user_id)
    assert updated_user is not None
    assert updated_user["email"] == proposed_email

    # Subsequent lookup by new email succeeds
    user_by_email = get_user_by_email(proposed_email)
    assert user_by_email is not None
    assert user_by_email["id"] == target_user_id


def test_recovery_rejection_flow():
    """
    PRD Scope 8:
    Admin can reject an unverified or fraudulent recovery request with a mandatory explanation.
    """
    req = recovery_service.submit_request(
        account_identifier="fraud.attempt@example.com",
        reason="Suspicious recovery claim",
        identity_verification_info="No verifiable documents provided"
    )
    req_id = req.id

    # Rejection without reason fails validation
    res_empty = client.post(
        f"/api/admin/recovery/requests/{req_id}/reject",
        json={"reason": "  "},
        headers=ADMIN_HEADERS
    )
    assert res_empty.status_code == 400

    # Rejection with valid reason
    res_valid = client.post(
        f"/api/admin/recovery/requests/{req_id}/reject",
        json={"reason": "Identity documents do not match registered company account."},
        headers=ADMIN_HEADERS
    )
    assert res_valid.status_code == 200
    rej_req = res_valid.json()["request"]
    assert rej_req["status"] == "Rejected"
    assert rej_req["decision_reason"] == "Identity documents do not match registered company account."


def test_admin_endpoints_require_admin_authorization():
    """
    PRD Section 10 & Scope 10: Secure Admin Authorization.
    Admin endpoints must strictly reject unauthenticated or non-admin requests.
    """
    # 1. Unauthenticated request to /api/admin/users
    res_unauth = client.get("/api/admin/users")
    assert res_unauth.status_code == 401

    # 2. Unauthenticated request to /api/admin/recovery/requests
    res_rec_unauth = client.get("/api/admin/recovery/requests")
    assert res_rec_unauth.status_code == 401

    # 3. Regular user attempting admin action
    user_headers = {"Authorization": "Bearer mock-regular-user-token"}
    from unittest.mock import patch
    with patch("app.core.security.get_current_user", return_value=CurrentUser(
        id="reg-user-1", email="reg@example.com", role="USER", is_unlimited=False
    )):
        res_forbidden = client.get("/api/admin/users", headers=user_headers)
        assert res_forbidden.status_code == 403
        assert "administrator privileges required" in res_forbidden.json()["detail"].lower()
