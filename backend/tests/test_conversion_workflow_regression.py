import os
import uuid
from decimal import Decimal
from datetime import date
from fastapi.testclient import TestClient
from main import app
from app.core import db
from app.api.conversions import IN_MEMORY_JOBS
from app.transactions.model import CanonicalStatement, TransactionItem

client = TestClient(app)

def create_sample_job(job_id: str, user_id: str = "test-user-id", email: str = "user@example.com"):
    tx1 = TransactionItem(
        row_index=1,
        date=date(2025, 1, 15),
        narration="UPI/REF123/SUPPLIER PAYMENT",
        cheque_number=None,
        debit=Decimal("1500.00"),
        credit=Decimal("0.00"),
        balance=Decimal("8500.00"),
        voucher_type="Payment",
        ledger_name="Sundry Creditors",
        source_page=1
    )
    tx2 = TransactionItem(
        row_index=2,
        date=date(2025, 1, 16),
        narration="NEFT/REF456/CUSTOMER RECEIPT",
        cheque_number=None,
        debit=Decimal("0.00"),
        credit=Decimal("5000.00"),
        balance=Decimal("13500.00"),
        voucher_type="Receipt",
        ledger_name="Sundry Debtors",
        source_page=1
    )
    statement = CanonicalStatement(
        bank="State Bank of India",
        statement_format="State Bank of India",
        statement_from=date(2025, 1, 1),
        statement_to=date(2025, 1, 31),
        opening_balance=Decimal("10000.00"),
        closing_balance=Decimal("13500.00"),
        transactions=[tx1, tx2],
        confidence_score=99.0
    )
    job = {
        "id": job_id,
        "user_id": user_id,
        "user_email": email,
        "file_name": "test_statement.pdf",
        "bank_name": "State Bank of India",
        "statement_format": "State Bank of India",
        "statement": statement,
        "transactions": [tx1, tx2],
        "page_count": 1,
        "total_pdf_pages": 1,
        "pages_processed": 1,
        "pages_skipped": 0,
        "free_quota_used": 1,
        "additional_quota_used": 0,
        "is_partial_conversion": False,
        "status": "COMPLETED",
        "transaction_count": 2,
        "raw_transaction_count": 2,
        "suspense_count": 0,
        "mapped_count": 2,
        "duplicate_count": 0,
        "warning_count": 0,
        "error_count": 0,
        "ready_for_export": True,
        "bank_ledger_name": "State Bank of India",
        "cash_ledger_name": "Cash",
        "total_debit": Decimal("1500.00"),
        "total_credit": Decimal("5000.00"),
        "opening_balance": Decimal("10000.00"),
        "closing_balance": Decimal("13500.00")
    }
    return job

def test_active_recent_returns_null_when_empty():
    # Calling active/recent when no jobs exist should return 200 with null (not 500)
    res = client.get("/api/conversions/active/recent", headers={"Authorization": "Bearer mock-user-token"})
    assert res.status_code == 200

def test_active_recent_restores_from_sqlite():
    job_id = f"job-recent-{uuid.uuid4().hex[:8]}"
    job = create_sample_job(job_id)
    job["created_at"] = "2099-01-01T00:00:00Z"
    # Save directly to SQLite
    db.save_conversion(job)

    # Evict from in-memory cache to verify restoration
    IN_MEMORY_JOBS.pop(job_id, None)

    res = client.get("/api/conversions/active/recent", headers={"Authorization": "Bearer mock-user-token"})
    assert res.status_code == 200
    data = res.json()
    assert data is not None
    assert data["id"] == job_id
    assert data["bank_name"] == "State Bank of India"
    assert data["transaction_count"] == 2

def test_review_endpoint_restores_from_sqlite():
    job_id = f"job-review-{uuid.uuid4().hex[:8]}"
    job = create_sample_job(job_id)
    db.save_conversion(job)

    # Evict from in-memory cache
    IN_MEMORY_JOBS.pop(job_id, None)

    # POST to review endpoint
    review_payload = {
        "transactions": [
            {
                "row_index": 1,
                "date": "2025-01-15",
                "narration": "UPDATED NARRATION",
                "cheque_number": None,
                "debit": 1500.0,
                "credit": 0.0,
                "balance": 8500.0,
                "voucher_type": "Payment",
                "ledger_name": "Office Expenses"
            },
            {
                "row_index": 2,
                "date": "2025-01-16",
                "narration": "NEFT/REF456/CUSTOMER RECEIPT",
                "cheque_number": None,
                "debit": 0.0,
                "credit": 5000.0,
                "balance": 13500.0,
                "voucher_type": "Receipt",
                "ledger_name": "Sales Account"
            }
        ],
        "bank_ledger_name": "State Bank of India Ledger",
        "cash_ledger_name": "Cash In Hand"
    }
    res = client.post(
        f"/api/conversions/{job_id}/review",
        json=review_payload,
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == job_id
    assert data["transaction_count"] == 2
    assert data["bank_ledger_name"] == "State Bank of India Ledger"

def test_generate_xml_and_download_flow():
    job_id = f"job-xml-{uuid.uuid4().hex[:8]}"
    job = create_sample_job(job_id)
    db.save_conversion(job)

    # Evict from memory
    IN_MEMORY_JOBS.pop(job_id, None)

    # 1. Generate XML
    gen_res = client.post(
        f"/api/conversions/{job_id}/generate-xml",
        json={"bank_ledger_name": "State Bank of India", "cash_ledger_name": "Cash", "confirm_suspense": True},
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert gen_data["success"] is True
    assert "download_url" in gen_data

    # 2. Download XML
    dl_res = client.get(f"/api/conversions/{job_id}/download", headers={"Authorization": "Bearer mock-user-token"})
    assert dl_res.status_code == 200
    assert "ENVELOPE" in dl_res.text or "<VOUCHER" in dl_res.text

    # 3. Test route aliases
    dl_alias_1 = client.get(f"/api/conversions/{job_id}/download-xml", headers={"Authorization": "Bearer mock-user-token"})
    assert dl_alias_1.status_code == 200
    dl_alias_2 = client.get(f"/api/conversions/{job_id}/xml", headers={"Authorization": "Bearer mock-user-token"})
    assert dl_alias_2.status_code == 200

def test_generate_excel_and_download_flow():
    job_id = f"job-excel-{uuid.uuid4().hex[:8]}"
    job = create_sample_job(job_id)
    db.save_conversion(job)

    IN_MEMORY_JOBS.pop(job_id, None)

    # 1. Generate Excel
    gen_res = client.post(
        f"/api/conversions/{job_id}/generate-excel",
        json={"bank_ledger_name": "State Bank of India", "cash_ledger_name": "Cash"},
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert gen_data["success"] is True

    # 2. Download Excel
    dl_res = client.get(f"/api/conversions/{job_id}/download-excel", headers={"Authorization": "Bearer mock-user-token"})
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # 3. Test alias /excel
    dl_alias = client.get(f"/api/conversions/{job_id}/excel", headers={"Authorization": "Bearer mock-user-token"})
    assert dl_alias.status_code == 200

def test_download_regenerates_when_disk_file_is_missing():
    job_id = f"job-regen-{uuid.uuid4().hex[:8]}"
    job = create_sample_job(job_id)
    # Give non-existent file paths
    job["xml_path"] = "/tmp/non_existent_file_123.xml"
    job["excel_path"] = "/tmp/non_existent_file_123.xlsx"
    db.save_conversion(job)

    # Clear in-memory
    IN_MEMORY_JOBS.pop(job_id, None)

    # Download XML directly without explicit generate -> should regenerate on the fly!
    xml_res = client.get(f"/api/conversions/{job_id}/download", headers={"Authorization": "Bearer mock-user-token"})
    assert xml_res.status_code == 200
    assert len(xml_res.content) > 0

    # Download Excel directly without explicit generate -> should regenerate on the fly!
    excel_res = client.get(f"/api/conversions/{job_id}/download-excel", headers={"Authorization": "Bearer mock-user-token"})
    assert excel_res.status_code == 200
    assert len(excel_res.content) > 0

def test_authorization_checks_user_isolation_and_admin_bypass():
    job_id = f"job-auth-{uuid.uuid4().hex[:8]}"
    job = create_sample_job(job_id, user_id="different-user-id", email="different@example.com")
    db.save_conversion(job)
    IN_MEMORY_JOBS.pop(job_id, None)

    # 1. Normal user (test-user-id) trying to access different-user-id's job -> 403 Forbidden
    res_user = client.get(f"/api/conversions/{job_id}/download", headers={"Authorization": "Bearer mock-user-token"})
    assert res_user.status_code == 403

    # 2. Admin accessing different-user-id's job -> 200 OK
    res_admin = client.get(f"/api/conversions/{job_id}/download", headers={"Authorization": "Bearer mock-admin-token"})
    assert res_admin.status_code == 200
