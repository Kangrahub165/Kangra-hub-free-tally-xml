import io
import os
import sys
import pytest
from reportlab.pdfgen import canvas
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from app.core import db
from app.core.security import CurrentUser
from app.api.usage import (
    _IN_MEMORY_DAILY_USAGE,
    USER_ADDITIONAL_PAGES,
    get_user_usage_data,
    grant_user_additional_pages,
    deduct_user_additional_pages,
    get_user_additional_pages,
    get_kolkata_today,
)
from app.api.conversions import IN_MEMORY_JOBS
from app.api.payments import PAYMENT_REQUESTS

client = TestClient(app)

def create_mock_pdf_bytes(num_pages: int, bank_name: str = "State Bank of India") -> bytes:
    """Generates valid multi-page PDF bytes with readable text for parser extraction."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for p in range(1, num_pages + 1):
        c.drawString(50, 800, f"{bank_name} Statement of Account")
        c.drawString(50, 780, "Account Number: 123456789012  IFSC: SBIN0001234")
        c.drawString(50, 760, f"Date: 01/01/2026 Page: {p} of {num_pages}")
        c.drawString(50, 740, "Txn Date | Description | Debit | Credit | Balance")
        c.drawString(50, 720, f"01/01/2026 | UPI/Vendor Payment P{p} | 100.00 | | 9900.00")
        c.drawString(50, 700, f"02/01/2026 | UPI/Client Receipt P{p} | | 500.00 | 10400.00")
        c.showPage()
    c.save()
    return buf.getvalue()

def reset_test_state():
    from app.core import db
    from app.api.usage import get_kolkata_today
    _IN_MEMORY_DAILY_USAGE.clear()
    USER_ADDITIONAL_PAGES.clear()
    IN_MEMORY_JOBS.clear()
    PAYMENT_REQUESTS.clear()
    today = get_kolkata_today()
    for uid in ["test-user-id", "usr-demo-1"]:
        db.reset_daily_usage(uid, today)
        db.set_additional_pages(uid, 0)
        db.set_custom_quota(uid, None)

def test_case_a_20_pages_under_quota():
    """Case A: 20-page PDF with 50 pages quota -> 20 processed, 0 skipped, 30 remaining quota."""
    reset_test_state()
    pdf_bytes = create_mock_pdf_bytes(20)

    res = client.post(
        "/api/conversions/upload",
        files={"file": ("stmt20.pdf", pdf_bytes, "application/pdf")},
        data={"bank_override": "State Bank of India"},
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["page_count"] == 20
    assert data["pages_processed"] == 20
    assert data["pages_skipped"] == 0
    assert data["is_partial_conversion"] is False
    assert data["status"] in ("COMPLETED", "NEEDS_REVIEW")

    # Check usage remaining is 30
    usage_res = client.get("/api/usage", headers={"Authorization": "Bearer mock-user-token"})
    assert usage_res.status_code == 200
    u_data = usage_res.json()
    assert u_data["pages_used_today"] == 20
    assert u_data["pages_remaining_today"] == 30

def test_case_b_exact_50_pages_quota():
    """Case B: 50-page PDF with 50 pages quota -> 50 processed, 0 skipped, 0 remaining quota."""
    reset_test_state()
    pdf_bytes = create_mock_pdf_bytes(50)

    res = client.post(
        "/api/conversions/upload",
        files={"file": ("stmt50.pdf", pdf_bytes, "application/pdf")},
        data={"bank_override": "State Bank of India"},
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["page_count"] == 50
    assert data["pages_processed"] == 50
    assert data["pages_skipped"] == 0
    assert data["is_partial_conversion"] is False

    usage_res = client.get("/api/usage", headers={"Authorization": "Bearer mock-user-token"})
    u_data = usage_res.json()
    assert u_data["pages_used_today"] == 50
    assert u_data["pages_remaining_today"] == 0

def test_case_c_103_pages_with_50_quota_partial_processing():
    """
    Case C: 103-page PDF with 50 pages quota:
    - Pages 1-50 MUST be processed
    - Pages 51-103 MUST NOT be processed
    - Conversion must complete with PARTIALLY_COMPLETED
    - 50 processed, 53 skipped, suggested price = 53 * 2 = 106.0
    - Remaining daily free quota becomes 0
    """
    reset_test_state()
    pdf_bytes = create_mock_pdf_bytes(103)

    res = client.post(
        "/api/conversions/upload",
        files={"file": ("stmt103.pdf", pdf_bytes, "application/pdf")},
        data={"bank_override": "State Bank of India"},
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["page_count"] == 103
    assert data["total_pdf_pages"] == 103
    assert data["pages_processed"] == 50
    assert data["pages_skipped"] == 53
    assert data["is_partial_conversion"] is True
    assert data["remaining_pages"] == 53
    assert data["suggested_additional_price"] == 106.0  # 53 * 2.0
    assert data["status"] == "PARTIALLY_COMPLETED"

    usage_res = client.get("/api/usage", headers={"Authorization": "Bearer mock-user-token"})
    u_data = usage_res.json()
    assert u_data["pages_used_today"] == 50
    assert u_data["pages_remaining_today"] == 0

def test_case_d_500_pages_partial_processing():
    """Case D: 500-page PDF with 50 quota -> 50 processed, 450 skipped, PARTIALLY_COMPLETED."""
    reset_test_state()
    pdf_bytes = create_mock_pdf_bytes(500)

    res = client.post(
        "/api/conversions/upload",
        files={"file": ("stmt500.pdf", pdf_bytes, "application/pdf")},
        data={"bank_override": "State Bank of India"},
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["page_count"] == 500
    assert data["pages_processed"] == 50
    assert data["pages_skipped"] == 450
    assert data["is_partial_conversion"] is True
    assert data["status"] == "PARTIALLY_COMPLETED"
    assert data["suggested_additional_price"] == 900.0

def test_case_e_zero_quota_exhausted_no_crash():
    """Case E: User has 0 quota left -> 0 processed, all skipped, QUOTA_EXHAUSTED status, does NOT crash with 403."""
    reset_test_state()
    today = get_kolkata_today()
    _IN_MEMORY_DAILY_USAGE[f"test-user-id:{today}"] = 50
    db.increment_daily_quota_usage("test-user-id", today, 50)

    pdf_bytes = create_mock_pdf_bytes(25)
    res = client.post(
        "/api/conversions/upload",
        files={"file": ("stmt25.pdf", pdf_bytes, "application/pdf")},
        data={"bank_override": "State Bank of India"},
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "QUOTA_EXHAUSTED"
    assert data["pages_processed"] == 0
    assert data["pages_skipped"] == 25
    assert data["is_partial_conversion"] is True
    assert data["suggested_additional_price"] == 50.0

def test_case_f_quota_priority_20_free_and_100_additional():
    """
    Case F: User has 20 free left + 100 additional balance (120 total).
    Uploads 103-page PDF:
    - 20 free used first (0 free left)
    - 83 additional used (17 additional balance left)
    - All 103 pages processed, 0 skipped, status="COMPLETED"
    """
    reset_test_state()
    today = get_kolkata_today()
    # 30 free pages already used today -> 20 free remaining
    db.record_daily_usage("test-user-id", today, 30)
    _IN_MEMORY_DAILY_USAGE[f"test-user-id:{today}"] = 30
    # 100 additional balance
    grant_user_additional_pages("test-user-id", 100)

    pdf_bytes = create_mock_pdf_bytes(103)
    res = client.post(
        "/api/conversions/upload",
        files={"file": ("stmt103.pdf", pdf_bytes, "application/pdf")},
        data={"bank_override": "State Bank of India"},
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["page_count"] == 103
    assert data["pages_processed"] == 103
    assert data["pages_skipped"] == 0
    assert data["is_partial_conversion"] is False
    assert data["free_quota_used"] == 20
    assert data["additional_quota_used"] == 83

    # Check remaining additional balance is 100 - 83 = 17
    assert USER_ADDITIONAL_PAGES["test-user-id"] == 17

    # Check free quota is 50 used (30 previous + 20 from this job)
    usage_res = client.get("/api/usage", headers={"Authorization": "Bearer mock-user-token"})
    u_data = usage_res.json()
    assert u_data["pages_remaining_today"] == 0
    assert u_data["additional_page_balance"] == 17
    assert u_data["total_allowed_pages"] == 17

def test_payments_config_and_manual_upi_flow():
    """Tests payment config, request submission, and admin approval lifecycle."""
    reset_test_state()

    # 1. Get Payment Config
    cfg_res = client.get("/api/payments/config")
    assert cfg_res.status_code == 200
    cfg = cfg_res.json()
    assert cfg["price_per_page"] == 2.0
    assert cfg["upi_id"] == "9418250639@ybl"
    assert "/buy-a-coffee/googlepay_qr.png" in cfg["qr_path"]

    # 2. Submit payment request with screenshot (e.g. 53 pages = ₹106)
    dummy_screenshot = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    pay_res = client.post(
        "/api/payments/requests",
        data={"requested_pages": "53", "notes": "UPI Txn ID: 1234567890"},
        files={"screenshot": ("screenshot.png", dummy_screenshot, "image/png")},
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert pay_res.status_code == 200
    p_data = pay_res.json()
    req_id = p_data["id"]
    assert p_data["requested_pages"] == 53
    assert p_data["amount_paid"] == 106.0
    assert p_data["status"] == "PENDING"

    # 3. User lists their payment requests
    my_res = client.get("/api/payments/requests/me", headers={"Authorization": "Bearer mock-user-token"})
    assert my_res.status_code == 200
    assert len(my_res.json()) >= 1

    # 4. View screenshot
    shot_res = client.get(f"/api/payments/requests/{req_id}/screenshot", headers={"Authorization": "Bearer mock-user-token"})
    assert shot_res.status_code == 200

    # 5. Admin lists requests
    admin_list_res = client.get("/api/admin/payments/requests", headers={"Authorization": "Bearer mock-admin-token"})
    assert admin_list_res.status_code == 200
    assert any(r["id"] == req_id for r in admin_list_res.json())

    # 6. Admin approves payment request
    approve_res = client.post(
        f"/api/admin/payments/requests/{req_id}/approve",
        json={"granted_pages": 53, "admin_notes": "Verified in Google Pay"},
        headers={"Authorization": "Bearer mock-admin-token"}
    )
    assert approve_res.status_code == 200
    app_data = approve_res.json()
    assert app_data["success"] is True
    assert app_data["new_balance"] == 53

    # Check user balance is now 53
    assert get_user_additional_pages("test-user-id") == 53

def test_process_remaining_pages_endpoint():
    """
    Tests process-remaining flow:
    - User has 50 free quota, uploads 103-page PDF -> 50 processed, 53 skipped.
    - Admin approves 53 extra pages for user.
    - User calls POST /api/conversions/{job_id}/process-remaining.
    - System processes pages 51-103 without re-processing pages 1-50.
    - Status transitions to COMPLETED.
    """
    reset_test_state()
    pdf_bytes = create_mock_pdf_bytes(103)

    # Initial partial conversion
    res = client.post(
        "/api/conversions/upload",
        files={"file": ("stmt103.pdf", pdf_bytes, "application/pdf")},
        data={"bank_override": "State Bank of India"},
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert res.status_code == 200
    data = res.json()
    job_id = data["id"]
    assert data["pages_processed"] == 50
    assert data["pages_skipped"] == 53
    assert data["status"] == "PARTIALLY_COMPLETED"
    initial_tx_count = data["transaction_count"]

    # Try process-remaining before paying -> should fail with 400 (quota exhausted)
    fail_res = client.post(
        f"/api/conversions/{job_id}/process-remaining",
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert fail_res.status_code in (400, 403)

    # Admin grants 60 pages
    grant_user_additional_pages("test-user-id", 60)

    # Now process-remaining
    resume_res = client.post(
        f"/api/conversions/{job_id}/process-remaining",
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert resume_res.status_code == 200
    r_data = resume_res.json()
    assert r_data["pages_processed"] == 103
    assert r_data["pages_skipped"] == 0
    assert r_data["status"] == "COMPLETED"
    assert r_data["is_partial_conversion"] is False
    # Verified additional transactions were appended
    assert r_data["transaction_count"] > initial_tx_count
    # Verified remaining additional balance: 60 - 53 = 7
    assert get_user_additional_pages("test-user-id") == 7

def test_purchased_balance_never_resets_at_midnight():
    """Verifies that purchased additional pages persist across daily resets."""
    reset_test_state()
    grant_user_additional_pages("usr-demo-1", 100)

    # Set daily free quota to 50 used on day 1
    _IN_MEMORY_DAILY_USAGE["usr-demo-1:2026-09-18"] = 50

    # On new day (2026-09-19), free quota resets to 0 used, but additional balance stays 100
    user = CurrentUser(id="usr-demo-1", email="user@demo.com", role="USER", is_unlimited=False)
    usage = get_user_usage_data(user)
    assert usage.pages_used_today == 0
    assert usage.pages_remaining_today == 50
    assert usage.additional_page_balance == 100
    assert usage.total_allowed_pages == 150
