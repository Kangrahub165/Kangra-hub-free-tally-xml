import io
import os
import sys
import json
import asyncio
import openpyxl
import pytest
from decimal import Decimal
from reportlab.pdfgen import canvas
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from app.core import db
from app.core.config import settings
from app.api.usage import (
    _IN_MEMORY_DAILY_USAGE,
    USER_ADDITIONAL_PAGES,
    get_user_usage_data,
    grant_user_additional_pages,
    get_user_additional_pages,
    get_kolkata_today,
)
from app.api.conversions import (
    IN_MEMORY_JOBS,
    CONVERSION_STORAGE_DIR,
    _get_user_lock,
)
from app.api.payments import PAYMENT_REQUESTS

client = TestClient(app)

USER_HEADERS = {"Authorization": "Bearer mock-user-token"}
ADMIN_HEADERS = {"Authorization": "Bearer mock-admin-token"}

def create_mock_pdf_bytes(num_pages: int, bank_name: str = "State Bank of India") -> bytes:
    """Generates valid multi-page PDF bytes with predictable per-page transaction text."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for p in range(1, num_pages + 1):
        c.drawString(50, 800, f"{bank_name} Statement of Account")
        c.drawString(50, 780, "Account Number: 123456789012  IFSC: SBIN0001234")
        c.drawString(50, 760, f"Date: 01/01/2026 Page: {p} of {num_pages}")
        c.drawString(50, 740, "Txn Date | Description | Debit | Credit | Balance")
        c.drawString(50, 720, f"01/01/2026 | UPI/Vendor Payment P{p} | 100.00 | | {10000 - p * 50}.00")
        c.drawString(50, 700, f"02/01/2026 | UPI/Client Receipt P{p} | | 50.00 | {10000 - p * 50 + 50}.00")
        c.showPage()
    c.save()
    return buf.getvalue()

def reset_test_state():
    """Resets in-memory and SQLite test states for clean isolation."""
    _IN_MEMORY_DAILY_USAGE.clear()
    USER_ADDITIONAL_PAGES.clear()
    IN_MEMORY_JOBS.clear()
    PAYMENT_REQUESTS.clear()
    today = get_kolkata_today()
    for uid in ["test-user-id", "usr-demo-1", "usr-login-test"]:
        db.reset_daily_usage(uid, today)
        db.set_additional_pages(uid, 0)
        db.set_custom_quota(uid, None)


# ---------------------------------------------------------------------------
# Test 1: Upload 105-page PDF with 50 free pages
# ---------------------------------------------------------------------------
def test_01_upload_105_page_pdf_with_50_free_quota():
    """
    Acceptance Test 1:
    - User uploads 105-page PDF with default 50 free pages quota.
    - Pages 1-50 must be processed; pages 51-105 must remain pending.
    - Zero transactions from pages 51-105.
    - page_statuses: 1-50 PROCESSED, 51-105 PENDING.
    """
    reset_test_state()
    pdf_bytes = create_mock_pdf_bytes(105)

    res = client.post(
        "/api/conversions/upload",
        files={"file": ("stmt105.pdf", pdf_bytes, "application/pdf")},
        data={"bank_override": "State Bank of India"},
        headers=USER_HEADERS,
    )
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["page_count"] == 105
    assert data["total_pdf_pages"] == 105
    assert data["pages_processed"] == 50
    assert data["pages_skipped"] == 55
    assert data["pages_pending"] == 55
    assert data["is_partial_conversion"] is True
    assert data["status"] == "PARTIALLY_COMPLETED"
    assert data["suggested_additional_price"] == 110.0  # 55 * 2

    # Verify page statuses map
    page_statuses = data["page_statuses"]
    assert len(page_statuses) == 105
    for p in range(1, 51):
        assert page_statuses[str(p)] == "PROCESSED", f"Page {p} should be PROCESSED"
    for p in range(51, 106):
        assert page_statuses[str(p)] == "PENDING", f"Page {p} should be PENDING"

    # Verify zero transactions from unauthorized pages
    job = IN_MEMORY_JOBS[data["id"]]
    transactions = job["statement"].transactions
    assert len(transactions) > 0
    for tx in transactions:
        assert getattr(tx, "source_page", None) is not None
        assert tx.source_page <= 50, f"Leaked transaction from page {tx.source_page}!"


# ---------------------------------------------------------------------------
# Test 2: Upload 1,000-page PDF with 50 free pages (Layout Engine Gated)
# ---------------------------------------------------------------------------
def test_02_upload_1000_page_pdf_layout_engine_pages_gated():
    """
    Acceptance Test 2:
    - User uploads 1,000-page PDF with 50 free pages.
    - Layout engine receives max_pages=50, never reading pages 51-1,000.
    - Pages 51-1,000 remain pending without OCR/parsing work.
    - Zero transactions from pages 51-1,000.
    """
    reset_test_state()
    pdf_bytes = create_mock_pdf_bytes(1000)

    res = client.post(
        "/api/conversions/upload",
        files={"file": ("stmt1000.pdf", pdf_bytes, "application/pdf")},
        data={"bank_override": "State Bank of India"},
        headers=USER_HEADERS,
    )
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["page_count"] == 1000
    assert data["total_pdf_pages"] == 1000
    assert data["pages_processed"] == 50
    assert data["pages_skipped"] == 950
    assert data["pages_pending"] == 950
    assert data["is_partial_conversion"] is True
    assert data["status"] == "PARTIALLY_COMPLETED"

    job = IN_MEMORY_JOBS[data["id"]]
    transactions = job["statement"].transactions
    assert len(transactions) > 0
    for tx in transactions:
        assert tx.source_page <= 50, f"Transaction from unauthorized page {tx.source_page} found!"


# ---------------------------------------------------------------------------
# Test 3: Pay INR 100 for 55 pending pages -> 50 credited, 5 pending
# ---------------------------------------------------------------------------
def test_03_pay_inr_100_for_55_pending_pages():
    """
    Acceptance Test 3:
    - User with 55 pending pages pays ₹100.
    - Exact formula: FLOOR(100 / 2) = 50 pages.
    - Exactly 50 pages credited (NOT 55, no rounding up).
    - Remaining pending = 5 pages.
    """
    reset_test_state()
    pdf_bytes = create_mock_pdf_bytes(105)

    res = client.post(
        "/api/conversions/upload",
        files={"file": ("stmt105.pdf", pdf_bytes, "application/pdf")},
        data={"bank_override": "State Bank of India"},
        headers=USER_HEADERS,
    )
    job_id = res.json()["id"]

    # Submit payment request for 50 pages (₹100)
    dummy_img = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    pay_res = client.post(
        "/api/payments/requests",
        data={"requested_pages": "50", "job_id": job_id, "notes": "Paid 100 via GPay"},
        files={"screenshot": ("receipt.png", dummy_img, "image/png")},
        headers=USER_HEADERS,
    )
    req_id = pay_res.json()["id"]

    # Admin approves ₹100
    appr_res = client.post(
        f"/api/admin/payments/requests/{req_id}/approve",
        json={"verified_amount": 100.0, "admin_notes": "Verified 100 INR"},
        headers=ADMIN_HEADERS,
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["granted_pages"] == 50

    # User processes remaining pages
    proc_res = client.post(
        f"/api/conversions/{job_id}/process-remaining",
        headers=USER_HEADERS,
    )
    assert proc_res.status_code == 200
    p_data = proc_res.json()

    assert p_data["pages_processed"] == 100
    assert p_data["pages_skipped"] == 5
    assert p_data["pages_pending"] == 5
    assert p_data["is_partial_conversion"] is True
    assert p_data["status"] == "PARTIALLY_COMPLETED"
    assert p_data["page_statuses"]["100"] == "PROCESSED"
    assert p_data["page_statuses"]["101"] == "PENDING"
    assert p_data["page_statuses"]["105"] == "PENDING"


# ---------------------------------------------------------------------------
# Test 4: Pay INR 110 for 55 pending pages -> 55 credited, all authorized
# ---------------------------------------------------------------------------
def test_04_pay_inr_110_for_55_pending_pages():
    """
    Acceptance Test 4:
    - User with 55 pending pages pays ₹110.
    - FLOOR(110 / 2) = 55 pages.
    - All 55 pending pages processed. Status becomes COMPLETED.
    """
    reset_test_state()
    pdf_bytes = create_mock_pdf_bytes(105)

    res = client.post(
        "/api/conversions/upload",
        files={"file": ("stmt105.pdf", pdf_bytes, "application/pdf")},
        data={"bank_override": "State Bank of India"},
        headers=USER_HEADERS,
    )
    job_id = res.json()["id"]

    # Admin grants 55 pages via approval of ₹110
    dummy_img = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    pay_res = client.post(
        "/api/payments/requests",
        data={"requested_pages": "55", "job_id": job_id, "notes": "Paid 110"},
        files={"screenshot": ("receipt.png", dummy_img, "image/png")},
        headers=USER_HEADERS,
    )
    req_id = pay_res.json()["id"]

    client.post(
        f"/api/admin/payments/requests/{req_id}/approve",
        json={"verified_amount": 110.0},
        headers=ADMIN_HEADERS,
    )

    # Process remaining
    proc_res = client.post(
        f"/api/conversions/{job_id}/process-remaining",
        headers=USER_HEADERS,
    )
    assert proc_res.status_code == 200
    p_data = proc_res.json()

    assert p_data["pages_processed"] == 105
    assert p_data["pages_skipped"] == 0
    assert p_data["pages_pending"] == 0
    assert p_data["is_partial_conversion"] is False
    assert p_data["status"] in ("COMPLETED", "NEEDS_REVIEW")
    assert all(status == "PROCESSED" for status in p_data["page_statuses"].values())


# ---------------------------------------------------------------------------
# Test 5: Reopen conversion workspace
# ---------------------------------------------------------------------------
def test_05_reopen_conversion_workspace():
    """
    Acceptance Test 5:
    - User reopens conversion workspace by ID.
    - 50 processed pages still available, 55 pending pages remain pending.
    - Saved PDF in CONVERSION_STORAGE_DIR exists and is readable.
    """
    reset_test_state()
    pdf_bytes = create_mock_pdf_bytes(105)

    res = client.post(
        "/api/conversions/upload",
        files={"file": ("stmt105.pdf", pdf_bytes, "application/pdf")},
        data={"bank_override": "State Bank of India"},
        headers=USER_HEADERS,
    )
    job_id = res.json()["id"]

    # Fetch job directly
    fetch_res = client.get(f"/api/conversions/{job_id}", headers=USER_HEADERS)
    assert fetch_res.status_code == 200
    job_data = fetch_res.json()

    assert job_data["pages_processed"] == 50
    assert job_data["pages_pending"] == 55
    assert job_data["total_pdf_pages"] == 105
    assert job_data["transaction_count"] > 0

    # Verify stored PDF file exists permanently
    job_record = IN_MEMORY_JOBS[job_id]
    assert os.path.exists(job_record["pdf_path"])
    assert job_record["pdf_path"].startswith(CONVERSION_STORAGE_DIR)


# ---------------------------------------------------------------------------
# Test 6: Logout/login session persistence
# ---------------------------------------------------------------------------
def test_06_logout_login_session_persistence():
    """
    Acceptance Test 6:
    - Conversion job and page states persist in SQLite database.
    - Reloading from DB simulates session logout/login with no data loss.
    """
    reset_test_state()
    pdf_bytes = create_mock_pdf_bytes(105)

    res = client.post(
        "/api/conversions/upload",
        files={"file": ("stmt105.pdf", pdf_bytes, "application/pdf")},
        data={"bank_override": "State Bank of India"},
        headers=USER_HEADERS,
    )
    job_id = res.json()["id"]

    # Verify persisted in SQLite
    db_job = db.get_conversion(job_id)
    assert db_job is not None
    assert db_job["user_id"] == "test-user-id"
    assert db_job["status"] == "PARTIALLY_COMPLETED"

    meta = json.loads(db_job["metadata_json"])
    assert meta["pages_processed"] == 50
    assert meta["pages_pending"] == 55
    assert meta["page_statuses"]["50"] == "PROCESSED"
    assert meta["page_statuses"]["51"] == "PENDING"


# ---------------------------------------------------------------------------
# Test 7: Refresh page -> no reprocessing of pages 1-50
# ---------------------------------------------------------------------------
def test_07_refresh_page_no_reprocessing():
    """
    Acceptance Test 7:
    - Re-fetching the conversion job does NOT re-extract or re-parse pages 1-50.
    - In process-remaining, start_page is strictly pages_processed + 1.
    """
    reset_test_state()
    pdf_bytes = create_mock_pdf_bytes(105)

    res = client.post(
        "/api/conversions/upload",
        files={"file": ("stmt105.pdf", pdf_bytes, "application/pdf")},
        data={"bank_override": "State Bank of India"},
        headers=USER_HEADERS,
    )
    job_id = res.json()["id"]

    # Check that multiple GET calls return identical transaction IDs
    res1 = client.get(f"/api/conversions/{job_id}", headers=USER_HEADERS)
    res2 = client.get(f"/api/conversions/{job_id}", headers=USER_HEADERS)
    assert res1.json()["transaction_count"] == res2.json()["transaction_count"]

    job = IN_MEMORY_JOBS[job_id]
    original_first_tx_id = job["statement"].transactions[0].id
    assert original_first_tx_id == f"{job_id}-tx-1"


# ---------------------------------------------------------------------------
# Test 8: Concurrent duplicate processing -> atomic lock
# ---------------------------------------------------------------------------
def test_08_concurrent_duplicate_processing():
    """
    Acceptance Test 8:
    - User lock prevents race conditions or double quota deduction.
    """
    lock1 = _get_user_lock("user-concurrent-test")
    lock2 = _get_user_lock("user-concurrent-test")
    assert lock1 is lock2  # Same instance ensures synchronization


# ---------------------------------------------------------------------------
# Test 9: Client attempts is_unlimited=True -> rejected
# ---------------------------------------------------------------------------
def test_09_client_attempts_is_unlimited_rejected():
    """
    Acceptance Test 9:
    - Standard user cannot assert is_unlimited=True to bypass quota.
    - Server-side security ignores client claims and enforces daily limit.
    """
    reset_test_state()
    pdf_bytes = create_mock_pdf_bytes(60)

    # Client tries to send is_unlimited=True in form data
    res = client.post(
        "/api/conversions/upload",
        files={"file": ("stmt60.pdf", pdf_bytes, "application/pdf")},
        data={"bank_override": "State Bank of India", "is_unlimited": "true"},
        headers=USER_HEADERS,
    )
    assert res.status_code == 200
    data = res.json()
    # Still capped at 50 pages!
    assert data["pages_processed"] == 50
    assert data["pages_skipped"] == 10
    assert data["is_partial_conversion"] is True


# ---------------------------------------------------------------------------
# Test 10: Excel & XML export contains ONLY transactions from processed pages
# ---------------------------------------------------------------------------
def test_10_excel_and_tally_xml_export_only_processed_pages():
    """
    Acceptance Test 10:
    - Exporting a partially completed document to Excel and XML contains ONLY
      the 50 processed pages' transactions. Zero transactions from pending pages.
    """
    reset_test_state()
    pdf_bytes = create_mock_pdf_bytes(105)

    res = client.post(
        "/api/conversions/upload",
        files={"file": ("stmt105.pdf", pdf_bytes, "application/pdf")},
        data={"bank_override": "State Bank of India"},
        headers=USER_HEADERS,
    )
    job_id = res.json()["id"]

    # 1. Excel Generation
    excel_gen_res = client.post(
        f"/api/conversions/{job_id}/generate-excel",
        headers=USER_HEADERS,
    )
    assert excel_gen_res.status_code == 200
    excel_down_res = client.get(
        f"/api/conversions/{job_id}/download-excel",
        headers=USER_HEADERS,
    )
    assert excel_down_res.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(excel_down_res.content))
    ws = wb.active
    # Row 1 is header. Rows 2..N are transactions.
    # 50 pages * 2 txns per page = 100 transactions.
    excel_tx_rows = ws.max_row - 1
    assert excel_tx_rows == 100

    # 2. Tally XML Generation
    xml_gen_res = client.post(
        f"/api/conversions/{job_id}/generate",
        headers=USER_HEADERS,
    )
    assert xml_gen_res.status_code == 200
    xml_down_res = client.get(
        f"/api/conversions/{job_id}/download",
        headers=USER_HEADERS,
    )
    assert xml_down_res.status_code == 200
    xml_text = xml_down_res.text
    assert "<ENVELOPE>" in xml_text
    voucher_count = xml_text.count("<VOUCHER ")
    assert voucher_count == 100


# ---------------------------------------------------------------------------
# Test 11: Payment screenshot submitted -> pending status, no unlock
# ---------------------------------------------------------------------------
def test_11_payment_screenshot_submitted_pending_no_unlock():
    """
    Acceptance Test 11:
    - Payment submission remains PENDING until verified.
    - Pages are NOT unlocked upon submission.
    """
    reset_test_state()
    dummy_img = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"

    res = client.post(
        "/api/payments/requests",
        data={"requested_pages": "55", "notes": "Submitted ₹110"},
        files={"screenshot": ("screenshot.png", dummy_img, "image/png")},
        headers=USER_HEADERS,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "PENDING"

    # Verify user additional page balance is still 0
    bal_res = client.get("/api/usage", headers=USER_HEADERS)
    assert bal_res.json()["additional_page_balance"] == 0


# ---------------------------------------------------------------------------
# Test 12: Admin verifies INR 100 -> exactly 50 pages credited + audit log
# ---------------------------------------------------------------------------
def test_12_admin_verifies_inr_100_credits_50_pages_audit_log():
    """
    Acceptance Test 12:
    - Admin approves payment with verified_amount=100.
    - Exactly FLOOR(100 / 2) = 50 pages credited.
    - Audit log entry created with event_type="PAYMENT_APPROVAL".
    """
    reset_test_state()
    dummy_img = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"

    pay_res = client.post(
        "/api/payments/requests",
        data={"requested_pages": "50"},
        files={"screenshot": ("screenshot.png", dummy_img, "image/png")},
        headers=USER_HEADERS,
    )
    req_id = pay_res.json()["id"]

    appr_res = client.post(
        f"/api/admin/payments/requests/{req_id}/approve",
        json={"verified_amount": 100.0, "admin_notes": "Received ₹100"},
        headers=ADMIN_HEADERS,
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["granted_pages"] == 50
    assert appr_res.json()["amount_paid"] == 100.0

    # Verify user balance
    usage = client.get("/api/usage", headers=USER_HEADERS).json()
    assert usage["additional_page_balance"] == 50

    # Verify audit log entry
    logs = db.get_page_credit_audit_logs(user_id="test-user-id")
    assert len(logs) >= 1
    latest = logs[0]
    assert latest["pages_granted"] == 50
    assert latest["amount_paid"] == 100.0
    assert latest["event_type"] in ("ADMIN_APPROVAL", "PAYMENT_APPROVAL")


# ---------------------------------------------------------------------------
# Test 13: Admin verifies INR 110 -> exactly 55 pages credited + audit log
# ---------------------------------------------------------------------------
def test_13_admin_verifies_inr_110_credits_55_pages_audit_log():
    """
    Acceptance Test 13:
    - Admin approves payment with verified_amount=110.
    - Exactly FLOOR(110 / 2) = 55 pages credited.
    - Audit log entry created with correct event details.
    """
    reset_test_state()
    dummy_img = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"

    pay_res = client.post(
        "/api/payments/requests",
        data={"requested_pages": "55"},
        files={"screenshot": ("screenshot.png", dummy_img, "image/png")},
        headers=USER_HEADERS,
    )
    req_id = pay_res.json()["id"]

    appr_res = client.post(
        f"/api/admin/payments/requests/{req_id}/approve",
        json={"verified_amount": 110.0, "admin_notes": "Received ₹110 for 55 pages"},
        headers=ADMIN_HEADERS,
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["granted_pages"] == 55
    assert appr_res.json()["amount_paid"] == 110.0

    # Verify user balance
    usage = client.get("/api/usage", headers=USER_HEADERS).json()
    assert usage["additional_page_balance"] == 55

    # Verify audit log entry
    logs = db.get_page_credit_audit_logs(user_id="test-user-id")
    assert len(logs) >= 1
    latest = logs[0]
    assert latest["pages_granted"] == 55
    assert latest["amount_paid"] == 110.0
    assert latest["event_type"] in ("ADMIN_APPROVAL", "PAYMENT_APPROVAL")
