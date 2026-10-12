import io
import os
import json
import uuid
import pytest
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from reportlab.pdfgen import canvas
from PIL import Image

from main import app
from app.core import db
from app.gemini.extractor import GeminiExtractor
from app.transactions.model import CanonicalStatement, TransactionItem

client = TestClient(app)

def create_dummy_pdf(pages: int = 1) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for p in range(1, pages + 1):
        c.drawString(50, 750, f"STATE BANK OF INDIA STATEMENT OF ACCOUNT FOR PERIOD 01/01/2025 PAGE {p}")
        c.drawString(50, 730, f"Account Number: 1234567890 Branch: New Delhi IFSC: SBIN0001234 CIF: 987654321")
        c.drawString(50, 710, f"Date: 15/01/2025 Narration: UPI Payment to Merchant REF{p}123 Debit: 500.00 Credit: 0.00 Balance: 10000.00")
        c.showPage()
    c.save()
    return buf.getvalue()

def mock_pdf_extract(page_texts, file_path=None, chunk_size=2):
    txs = []
    for idx in range(1, len(page_texts) + 1):
        txs.append(
            TransactionItem(
                id=f"tx-{idx}",
                row_index=idx,
                date=date(2025, 1, 15),
                narration=f"UPI Payment Page {idx}",
                debit=Decimal("100.00"),
                credit=Decimal("0.00"),
                balance=Decimal("9900.00"),
                source_page=idx
            )
        )
    return CanonicalStatement(
        bank="State Bank of India",
        statement_format="State Bank of India",
        opening_balance=Decimal("10000.00"),
        closing_balance=Decimal("9900.00"),
        transactions=txs
    )

def create_dummy_image() -> bytes:
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

@pytest.fixture(autouse=True)
def clean_quota_state():
    """Ensure clean daily quota tables and memory before each test."""
    today = db.get_ist_today()
    from app.api.conversions import IN_MEMORY_JOBS
    from app.api.usage import _IN_MEMORY_DAILY_USAGE
    IN_MEMORY_JOBS.clear()
    _IN_MEMORY_DAILY_USAGE.clear()

    # Reset SQLite daily quota
    with db._LOCK:
        conn = db._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM daily_quota_usage")
            cursor.execute("DELETE FROM quota_reservations")
            cursor.execute("DELETE FROM job_pages")
            cursor.execute("DELETE FROM quota_exceptions")
            cursor.execute("DELETE FROM quota_audit_log")
            cursor.execute("DELETE FROM daily_usage")
            conn.commit()
        finally:
            conn.close()
    yield
    IN_MEMORY_JOBS.clear()

# ==============================================================================
# TEST 1: Ordinary user uploads PDF under limit
# ==============================================================================
def test_01_ordinary_user_pdf_under_limit(monkeypatch):
    monkeypatch.setattr(GeminiExtractor, "is_available", classmethod(lambda cls: True))
    monkeypatch.setattr(GeminiExtractor, "extract_from_pdf_pages", mock_pdf_extract)

    pdf_bytes = create_dummy_pdf(10)
    files = {"files": ("statement.pdf", pdf_bytes, "application/pdf")}
    data = {"bank_override": "State Bank of India"}
    headers = {"Authorization": "Bearer mock-user-token"}

    resp = client.post("/api/conversions/upload", files=files, data=data, headers=headers)
    assert resp.status_code == 200, resp.text
    res_data = resp.json()
    assert res_data["accepted_pages"] == 10
    assert res_data["unprocessed_pages"] == 0
    assert res_data["status"] != "QUOTA_EXHAUSTED"

    # Verify quota counter
    q_resp = client.get("/api/quota", headers=headers)
    assert q_resp.status_code == 200
    q_data = q_resp.json()
    assert q_data["pdf_pages"]["used"] == 10
    assert q_data["pdf_pages"]["remaining"] == 40
    assert q_data["images"]["remaining"] == 5

# ==============================================================================
# TEST 2: Ordinary user uploads PDF over limit with slicing
# ==============================================================================
def test_02_ordinary_user_pdf_over_limit_slicing(monkeypatch):
    monkeypatch.setattr(GeminiExtractor, "is_available", classmethod(lambda cls: True))
    monkeypatch.setattr(GeminiExtractor, "extract_from_pdf_pages", mock_pdf_extract)
    today = db.get_ist_today()
    headers = {"Authorization": "Bearer mock-user-token"}

    # Simulate 40 pages already used today
    with db._LOCK:
        conn = db._get_connection()
        try:
            conn.cursor().execute(
                "INSERT INTO daily_quota_usage (id, user_id, quota_date, type, used) VALUES (?, ?, ?, ?, ?)",
                (f"dqu-{uuid.uuid4().hex[:8]}", "test-user-id", today, "PDF_PAGE", 40)
            )
            conn.commit()
        finally:
            conn.close()

    pdf_bytes = create_dummy_pdf(45)
    files = {"files": ("statement.pdf", pdf_bytes, "application/pdf")}
    data = {"bank_override": "State Bank of India"}

    resp = client.post("/api/conversions/upload", files=files, data=data, headers=headers)
    assert resp.status_code == 200, resp.text
    res_data = resp.json()

    # Only remaining 10 pages are accepted, 35 are unprocessed
    assert res_data["accepted_pages"] == 10
    assert res_data["unprocessed_pages"] == 35
    assert res_data["is_partial_conversion"] is True

    # Verify quota counter is exhausted
    q_resp = client.get("/api/quota", headers=headers)
    q_data = q_resp.json()
    assert q_data["pdf_pages"]["used"] == 50
    assert q_data["pdf_pages"]["remaining"] == 0

    # Verify job_pages tracked in order
    job_id = res_data["id"]
    pages_resp = client.get(f"/api/conversions/{job_id}/pages", headers=headers)
    assert pages_resp.status_code == 200
    pages_data = pages_resp.json()["pages"]
    assert len(pages_data) == 45
    # First 10 pages accepted
    for p in pages_data[:10]:
        assert p["status"] in ("PROCESSED", "PROCESSED_WITH_WARNINGS", "QUEUED")
    # Remaining 35 pages marked NOT_PROCESSED_QUOTA
    for p in pages_data[10:]:
        assert p["status"] == "NOT_PROCESSED_QUOTA"

# ==============================================================================
# TEST 3: Ordinary user uploads PDF with zero quota remaining
# ==============================================================================
def test_03_ordinary_user_pdf_zero_quota(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "gemini_enabled", False)
    today = db.get_ist_today()
    headers = {"Authorization": "Bearer mock-user-token"}

    # Simulate 50 pages used today
    with db._LOCK:
        conn = db._get_connection()
        try:
            conn.cursor().execute(
                "INSERT INTO daily_quota_usage (id, user_id, quota_date, type, used) VALUES (?, ?, ?, ?, ?)",
                (f"dqu-{uuid.uuid4().hex[:8]}", "test-user-id", today, "PDF_PAGE", 50)
            )
            conn.commit()
        finally:
            conn.close()

    pdf_bytes = create_dummy_pdf(5)
    files = {"files": ("statement.pdf", pdf_bytes, "application/pdf")}
    data = {"bank_override": "State Bank of India"}

    resp = client.post("/api/conversions/upload", files=files, data=data, headers=headers)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["status"] == "QUOTA_EXHAUSTED"
    assert res_data["accepted_pages"] == 0
    assert res_data["unprocessed_pages"] == 5
    assert "free daily limit for today" in res_data["quota_message"]
    assert "12:00 AM IST" in res_data["quota_message"]

# ==============================================================================
# TEST 4: Ordinary user uploads images under limit
# ==============================================================================
def test_04_ordinary_user_images_under_limit(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "gemini_enabled", False)
    headers = {"Authorization": "Bearer mock-user-token"}

    # Mock Gemini extractor to return valid statement from dummy image
    def mock_extract(img_bytes, mime_type="image/jpeg"):
        return CanonicalStatement(
            bank="HDFC Bank",
            transactions=[
                TransactionItem(
                    id="tx-1",
                    row_index=1,
                    date=date(2025, 1, 15),
                    narration="Test Deposit",
                    debit=Decimal("0.00"),
                    credit=Decimal("500.00"),
                    balance=Decimal("1500.00"),
                    source_page=1
                )
            ]
        )
    monkeypatch.setattr(GeminiExtractor, "extract_from_image_bytes", mock_extract)
    monkeypatch.setattr(GeminiExtractor, "is_available", classmethod(lambda cls: True))

    img1 = create_dummy_image()
    img2 = create_dummy_image()
    img3 = create_dummy_image()

    files = [
        ("files", ("page1.jpg", img1, "image/jpeg")),
        ("files", ("page2.jpg", img2, "image/jpeg")),
        ("files", ("page3.jpg", img3, "image/jpeg")),
    ]

    resp = client.post("/api/conversions/upload", files=files, headers=headers)
    assert resp.status_code == 200, resp.text
    res_data = resp.json()
    assert res_data["accepted_pages"] == 3
    assert res_data["unprocessed_pages"] == 0

    # Quota check
    q_resp = client.get("/api/quota", headers=headers)
    q_data = q_resp.json()
    assert q_data["images"]["used"] == 3
    assert q_data["images"]["remaining"] == 2
    assert q_data["pdf_pages"]["remaining"] == 50  # Independent counter!

# ==============================================================================
# TEST 5: Ordinary user image upload slicing
# ==============================================================================
def test_05_ordinary_user_images_over_limit_slicing(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "gemini_enabled", False)
    headers = {"Authorization": "Bearer mock-user-token"}
    today = db.get_ist_today()

    # Pre-use 3 images
    with db._LOCK:
        conn = db._get_connection()
        try:
            conn.cursor().execute(
                "INSERT INTO daily_quota_usage (id, user_id, quota_date, type, used) VALUES (?, ?, ?, ?, ?)",
                (f"dqu-{uuid.uuid4().hex[:8]}", "test-user-id", today, "IMAGE", 3)
            )
            conn.commit()
        finally:
            conn.close()

    def mock_extract_multiple(images_data, mime_type="image/jpeg"):
        txs = []
        for idx, (fname, b) in enumerate(images_data, start=1):
            txs.append(
                TransactionItem(
                    id=f"tx-{idx}",
                    row_index=idx,
                    date=date(2025, 1, 15),
                    narration=f"Tx from {fname}",
                    debit=Decimal("100.00"),
                    credit=Decimal("0.00"),
                    balance=Decimal("900.00"),
                    source_page=idx
                )
            )
        return CanonicalStatement(bank="HDFC Bank", transactions=txs)
    monkeypatch.setattr(GeminiExtractor, "extract_from_multiple_image_bytes", mock_extract_multiple)
    monkeypatch.setattr(GeminiExtractor, "is_available", classmethod(lambda cls: True))

    img_bytes = create_dummy_image()
    files = [
        ("files", (f"img_{i}.jpg", img_bytes, "image/jpeg"))
        for i in range(1, 5)  # 4 images uploaded, only 2 should be accepted
    ]

    resp = client.post("/api/conversions/upload", files=files, headers=headers)
    assert resp.status_code == 200, resp.text
    res_data = resp.json()
    assert res_data["accepted_pages"] == 2
    assert res_data["unprocessed_pages"] == 2

    # Quota check
    q_resp = client.get("/api/quota", headers=headers)
    q_data = q_resp.json()
    assert q_data["images"]["used"] == 5
    assert q_data["images"]["remaining"] == 0

# ==============================================================================
# TEST 6: Independent PDF and Image counters
# ==============================================================================
def test_06_independent_counters():
    today = db.get_ist_today()
    headers = {"Authorization": "Bearer mock-user-token"}

    # Exhaust all 50 PDF pages
    with db._LOCK:
        conn = db._get_connection()
        try:
            conn.cursor().execute(
                "INSERT INTO daily_quota_usage (id, user_id, quota_date, type, used) VALUES (?, ?, ?, ?, ?)",
                (f"dqu-{uuid.uuid4().hex[:8]}", "test-user-id", today, "PDF_PAGE", 50)
            )
            conn.commit()
        finally:
            conn.close()

    q_resp = client.get("/api/quota", headers=headers)
    q_data = q_resp.json()
    assert q_data["pdf_pages"]["remaining"] == 0
    # Image quota is unaffected
    assert q_data["images"]["remaining"] == 5

# ==============================================================================
# TEST 7: Reset at 00:00 IST
# ==============================================================================
def test_07_midnight_ist_reset():
    # Insert usage on yesterday
    yesterday = "2026-10-11"
    today = db.get_ist_today()

    with db._LOCK:
        conn = db._get_connection()
        try:
            conn.cursor().execute(
                "INSERT INTO daily_quota_usage (id, user_id, quota_date, type, used) VALUES (?, ?, ?, ?, ?)",
                (f"dqu-{uuid.uuid4().hex[:8]}", "test-user-id", yesterday, "PDF_PAGE", 50)
            )
            conn.commit()
        finally:
            conn.close()

    # Query quota for today
    used_today = db.get_daily_quota_used("test-user-id", today, "PDF_PAGE")
    assert used_today == 0

# ==============================================================================
# TEST 8: Corrupt file rejected without consuming quota
# ==============================================================================
def test_08_corrupt_file_rejection_no_quota_deducted():
    headers = {"Authorization": "Bearer mock-user-token"}
    corrupt_bytes = b"NOT_A_VALID_PDF_STREAM_12345"
    files = {"files": ("corrupt.pdf", corrupt_bytes, "application/pdf")}

    resp = client.post("/api/conversions/upload", files=files, headers=headers)
    assert resp.status_code == 400

    q_resp = client.get("/api/quota", headers=headers)
    q_data = q_resp.json()
    assert q_data["pdf_pages"]["used"] == 0
    assert q_data["pdf_pages"]["remaining"] == 50

# ==============================================================================
# TEST 9: Encrypted PDF without password rejected without consuming quota
# ==============================================================================
def test_09_encrypted_file_wrong_password_no_quota_deducted():
    headers = {"Authorization": "Bearer mock-user-token"}

    # Create encrypted PDF
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("SecretPass123")
    buf = io.BytesIO()
    writer.write(buf)
    encrypted_bytes = buf.getvalue()

    files = {"files": ("locked.pdf", encrypted_bytes, "application/pdf")}
    resp = client.post("/api/conversions/upload", files=files, headers=headers)
    assert resp.status_code in (400, 401)

    q_resp = client.get("/api/quota", headers=headers)
    q_data = q_resp.json()
    assert q_data["pdf_pages"]["used"] == 0

# ==============================================================================
# TEST 10: Chunked extraction completeness
# ==============================================================================
def test_10_chunked_extraction_completeness(monkeypatch):
    """Verifies chunked extraction calls Gemini per chunk without single-prompt truncation."""
    called_chunks = []

    def mock_call(contents, timeout_seconds=45.0, model_name=None):
        text_prompt = contents[0]["parts"][0]["text"]
        called_chunks.append(text_prompt)
        # Mock structured response
        return json.dumps({
            "bank_name": "State Bank of India",
            "transactions": [
                {
                    "page": 1,
                    "date": "2026-10-12",
                    "narration": "UPI Transfer",
                    "debit": 250.00,
                    "credit": 0.00,
                    "balance": 1000.00
                }
            ]
        })

    monkeypatch.setattr(GeminiExtractor, "_call_gemini_api", mock_call)
    monkeypatch.setattr(GeminiExtractor, "is_available", classmethod(lambda cls: True))

    pages = [f"Page {i} statement text with transactions" for i in range(1, 6)]
    stmt = GeminiExtractor.extract_from_pdf_pages(pages, chunk_size=2)
    assert stmt is not None
    # 5 pages with chunk_size 2 should make 3 chunks: [1,2], [3,4], [5]
    assert len(called_chunks) == 3
    assert len(stmt.transactions) == 3

# ==============================================================================
# TEST 11: Transaction source page tagging
# ==============================================================================
def test_11_transaction_source_page_tagging(monkeypatch):
    def mock_call(contents, timeout_seconds=45.0, model_name=None):
        return json.dumps({
            "bank_name": "HDFC Bank",
            "transactions": [
                {"page": 2, "date": "2026-10-12", "narration": "Salary Credit", "debit": 0, "credit": 50000, "balance": 60000}
            ]
        })

    monkeypatch.setattr(GeminiExtractor, "_call_gemini_api", mock_call)
    monkeypatch.setattr(GeminiExtractor, "is_available", classmethod(lambda cls: True))

    pages = ["Page 1 text", "Page 2 text"]
    stmt = GeminiExtractor.extract_from_pdf_pages(pages, chunk_size=2)
    assert stmt is not None
    assert stmt.transactions[0].source_page == 2

# ==============================================================================
# TEST 12: Running balance verification
# ==============================================================================
def test_12_running_balance_verification():
    raw_json = json.dumps({
        "bank_name": "Axis Bank",
        "opening_balance": 1000.00,
        "transactions": [
            {"date": "2026-10-10", "narration": "Tx 1", "debit": 200, "credit": 0, "balance": 800.00},
            {"date": "2026-10-11", "narration": "Tx 2 with bad balance", "debit": 100, "credit": 0, "balance": 950.00}
        ]
    })
    stmt = GeminiExtractor._parse_and_validate_gemini_response(raw_json)
    assert stmt is not None
    assert stmt.transactions[0].validation_status == "VALID"
    assert stmt.transactions[1].validation_status == "WARNING"
    assert "Running balance mismatch" in stmt.transactions[1].validation_notes

# ==============================================================================
# TEST 13: Strict job isolation (no cross-job data mixing)
# ==============================================================================
def test_13_strict_job_isolation_no_data_mixing(monkeypatch):
    monkeypatch.setattr(GeminiExtractor, "is_available", classmethod(lambda cls: True))
    monkeypatch.setattr(GeminiExtractor, "extract_from_pdf_pages", mock_pdf_extract)
    headers = {"Authorization": "Bearer mock-user-token"}

    pdf1 = create_dummy_pdf(2)
    resp1 = client.post("/api/conversions/upload", files={"files": ("file1.pdf", pdf1, "application/pdf")}, data={"bank_override": "State Bank of India"}, headers=headers)
    assert resp1.status_code == 200
    job1_id = resp1.json()["id"]

    pdf2 = create_dummy_pdf(3)
    resp2 = client.post("/api/conversions/upload", files={"files": ("file2.pdf", pdf2, "application/pdf")}, data={"bank_override": "State Bank of India"}, headers=headers)
    assert resp2.status_code == 200
    job2_id = resp2.json()["id"]

    assert job1_id != job2_id

# ==============================================================================
# TEST 14: Job ID required for review and download
# ==============================================================================
def test_14_job_id_required_for_review_and_download():
    headers = {"Authorization": "Bearer mock-user-token"}

    # Reviewing unknown job returns 404
    resp = client.post("/api/conversions/job-nonexistent-1234/review", json={"transactions": []}, headers=headers)
    assert resp.status_code == 404

    # Downloading unknown job returns 404
    resp2 = client.get("/api/conversions/job-nonexistent-1234/download", headers=headers)
    assert resp2.status_code == 404

# ==============================================================================
# TEST 15: System failure quota reimbursement
# ==============================================================================
def test_15_system_failure_quota_reimbursement():
    today = db.get_ist_today()
    user_id = "test-refund-user"

    # Reserve 10 pages
    res = db.reserve_quota_atomic("job-fail-1", user_id, today, "PDF_PAGE", 10, 50, is_unlimited=False)
    assert res["reserved_count"] == 10
    assert db.get_daily_quota_used(user_id, today, "PDF_PAGE") == 10

    # System crash occurs: reconcile with failure
    db.reconcile_quota_reservation(res["reservation_id"], consumed_count=0, failed_system_count=10)

    # Quota is reimbursed
    assert db.get_daily_quota_used(user_id, today, "PDF_PAGE") == 0

# ==============================================================================
# TEST 16: Admin unlimited bypass
# ==============================================================================
def test_16_admin_unlimited_bypass(monkeypatch):
    monkeypatch.setattr(GeminiExtractor, "is_available", classmethod(lambda cls: True))
    monkeypatch.setattr(GeminiExtractor, "extract_from_pdf_pages", mock_pdf_extract)
    headers = {"Authorization": "Bearer mock-admin-token"}

    pdf_bytes = create_dummy_pdf(60)
    resp = client.post("/api/conversions/upload", files={"files": ("huge.pdf", pdf_bytes, "application/pdf")}, data={"bank_override": "State Bank of India"}, headers=headers)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["accepted_pages"] == 60
    assert res_data["unprocessed_pages"] == 0

# ==============================================================================
# TEST 17: Admin exception grant
# ==============================================================================
def test_17_admin_exception_grant():
    admin_headers = {"Authorization": "Bearer mock-admin-token"}
    user_headers = {"Authorization": "Bearer mock-user-token"}

    payload = {
        "user_id": "test-user-id",
        "scope": "PDF_PAGE",
        "limit_type": "DAILY_LIMIT",
        "limit_value": 150,
        "reason": "Special tax filing project"
    }
    resp = client.post("/api/admin/exceptions", json=payload, headers=admin_headers)
    assert resp.status_code == 200
    exc_id = resp.json()["exception"]["id"]

    # User queries quota and receives 150 limit
    q_resp = client.get("/api/quota", headers=user_headers)
    q_data = q_resp.json()
    assert q_data["pdf_pages"]["limit"] == 150
    assert q_data["pdf_pages"]["remaining"] == 150

    # Audit log entry exists
    audit_resp = client.get("/api/admin/quota-audit-logs", headers=admin_headers)
    assert audit_resp.status_code == 200
    assert any(log["action"] == "GRANT_EXCEPTION" for log in audit_resp.json()["logs"])

# ==============================================================================
# TEST 18: Admin exception revoke
# ==============================================================================
def test_18_admin_exception_revoke():
    admin_headers = {"Authorization": "Bearer mock-admin-token"}
    user_headers = {"Authorization": "Bearer mock-user-token"}

    # Grant exception
    payload = {
        "user_id": "test-user-id",
        "scope": "PDF_PAGE",
        "limit_type": "DAILY_LIMIT",
        "limit_value": 200,
        "reason": "Temporary expansion"
    }
    resp = client.post("/api/admin/exceptions", json=payload, headers=admin_headers)
    exc_id = resp.json()["exception"]["id"]

    # Revoke exception
    rev_resp = client.delete(f"/api/admin/exceptions/{exc_id}", headers=admin_headers)
    assert rev_resp.status_code == 200

    # Quota returns to default 50
    q_resp = client.get("/api/quota", headers=user_headers)
    assert q_resp.json()["pdf_pages"]["limit"] == 50

# ==============================================================================
# TEST 19: Concurrent upload atomic reservation
# ==============================================================================
def test_19_concurrent_uploads_atomic_reservation():
    import threading
    today = db.get_ist_today()
    user_id = "test-concurrent-user"

    # Pre-use 47 pages (3 remaining)
    with db._LOCK:
        conn = db._get_connection()
        try:
            conn.cursor().execute(
                "INSERT INTO daily_quota_usage (id, user_id, quota_date, type, used) VALUES (?, ?, ?, ?, ?)",
                (f"dqu-{uuid.uuid4().hex[:8]}", user_id, today, "PDF_PAGE", 47)
            )
            conn.commit()
        finally:
            conn.close()

    results = []
    def do_reserve(job_id):
        r = db.reserve_quota_atomic(job_id, user_id, today, "PDF_PAGE", 10, 50, is_unlimited=False)
        results.append(r["reserved_count"])

    t1 = threading.Thread(target=do_reserve, args=("job-c-1",))
    t2 = threading.Thread(target=do_reserve, args=("job-c-2",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Total reserved across both threads cannot exceed the 3 remaining pages
    assert sum(results) <= 3

# ==============================================================================
# TEST 20: GET /api/quota endpoint schema
# ==============================================================================
def test_20_get_quota_endpoint_schema():
    headers = {"Authorization": "Bearer mock-user-token"}
    resp = client.get("/api/quota", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "pdf_pages" in data
    assert "images" in data
    assert "limit" in data["pdf_pages"]
    assert "used" in data["pdf_pages"]
    assert "remaining" in data["pdf_pages"]
    assert "limit" in data["images"]
    assert "used" in data["images"]
    assert "remaining" in data["images"]
    assert data["reset_time_ist"] == "12:00 AM IST"
    assert "date_ist" in data
    assert "is_admin" in data
    assert "is_unlimited" in data
    assert "is_paid" in data
