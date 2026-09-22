import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from main import app
from app.core.security import CurrentUser
from app.api.usage import _IN_MEMORY_DAILY_USAGE, get_kolkata_today
from app.api.conversions import IN_MEMORY_JOBS

client = TestClient(app)

ADMIN_HEADERS = {"Authorization": "Bearer mock-admin-token"}
USER_HEADERS = {"Authorization": "Bearer mock-user-token"}
REAL_SBI_PDF = "D:/D drive data/BANK STATEMENTS/1776150969645s6FWFsyLeycG6QGB (1).pdf"


def test_admin_can_access_converter():
    """1. Verify administrator can access the admin conversion endpoint."""
    with open(REAL_SBI_PDF, "rb") as f:
        resp = client.post(
            "/api/admin/conversions/upload",
            files={"file": ("test_admin.pdf", f, "application/pdf")},
            headers=ADMIN_HEADERS
        )
    assert resp.status_code == 200, f"Admin should access converter, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["is_admin_conversion"] is True
    assert data["quota_exempt"] is True
    assert "State Bank of India" in data["bank_name"]


def test_normal_user_cannot_access_admin_converter():
    """2. Verify normal user is strictly denied access (403 Forbidden) to admin converter."""
    with open(REAL_SBI_PDF, "rb") as f:
        resp = client.post(
            "/api/admin/conversions/upload",
            files={"file": ("test_user.pdf", f, "application/pdf")},
            headers=USER_HEADERS
        )
    assert resp.status_code == 403, f"Normal user must receive 403 Forbidden, got {resp.status_code}"


def test_admin_quota_bypass():
    """3. Verify admin converts statement without quota restriction even if past 50 pages."""
    admin_user = CurrentUser(id="test-admin-id", email="admin@tallyxml.in", role="ADMIN", is_unlimited=True)
    today = get_kolkata_today()
    _IN_MEMORY_DAILY_USAGE[f"{admin_user.id}:{today}"] = 200

    with open(REAL_SBI_PDF, "rb") as f:
        resp = client.post(
            "/api/admin/conversions/upload",
            files={"file": ("large_statement.pdf", f, "application/pdf")},
            headers=ADMIN_HEADERS
        )
    assert resp.status_code == 200, "Admin must bypass quota even when previous usage exceeds 50 pages"


def test_admin_large_statement_conversion():
    """4. Verify admin can process statements without page count block."""
    with open(REAL_SBI_PDF, "rb") as f:
        resp = client.post(
            "/api/admin/conversions/upload",
            files={"file": ("multi_page.pdf", f, "application/pdf")},
            headers=ADMIN_HEADERS
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["page_count"] == 8
    assert data["transaction_count"] == 128


def test_admin_conversion_does_not_consume_daily_quota():
    """5. Verify admin conversion does NOT consume normal daily usage quota."""
    admin_user = CurrentUser(id="test-admin-id", email="admin@tallyxml.in", role="ADMIN", is_unlimited=True)
    today = get_kolkata_today()
    initial_usage = _IN_MEMORY_DAILY_USAGE.get(f"{admin_user.id}:{today}", 0)

    with open(REAL_SBI_PDF, "rb") as f:
        resp = client.post(
            "/api/admin/conversions/upload",
            files={"file": ("quota_test.pdf", f, "application/pdf")},
            headers=ADMIN_HEADERS
        )
    assert resp.status_code == 200
    after_usage = _IN_MEMORY_DAILY_USAGE.get(f"{admin_user.id}:{today}", 0)
    assert after_usage == initial_usage, "Admin conversion must not increment daily usage"


def test_admin_xml_generation():
    """6. Verify admin can generate Tally XML from Admin Converter."""
    with open(REAL_SBI_PDF, "rb") as f:
        upload_resp = client.post(
            "/api/admin/conversions/upload",
            files={"file": ("xml_test.pdf", f, "application/pdf")},
            headers=ADMIN_HEADERS
        )
    assert upload_resp.status_code == 200
    job_id = upload_resp.json()["id"]

    gen_resp = client.post(
        f"/api/admin/conversions/{job_id}/generate",
        json={"bank_ledger_name": "State Bank of India A/C", "suspense_ledger_name": "Suspense A/C"},
        headers=ADMIN_HEADERS
    )
    assert gen_resp.status_code == 200, f"XML generation failed: {gen_resp.text}"
    gen_data = gen_resp.json()
    assert gen_data["status"] == "COMPLETED"
    assert gen_data["voucher_count"] == 128


def test_admin_xml_validation():
    """7. Verify admin XML follows standard double-entry format and downloads cleanly."""
    with open(REAL_SBI_PDF, "rb") as f:
        upload_resp = client.post(
            "/api/admin/conversions/upload",
            files={"file": ("val_test.pdf", f, "application/pdf")},
            headers=ADMIN_HEADERS
        )
    job_id = upload_resp.json()["id"]

    client.post(
        f"/api/admin/conversions/{job_id}/generate",
        json={"bank_ledger_name": "SBI Bank A/c"},
        headers=ADMIN_HEADERS
    )

    down_resp = client.get(f"/api/conversions/{job_id}/download", headers=ADMIN_HEADERS)
    assert down_resp.status_code == 200
    assert "<ENVELOPE>" in down_resp.text
    assert "<TALLYMESSAGE" in down_resp.text
    assert "<VOUCHER" in down_resp.text


def test_admin_manual_bank_override():
    """8. Verify admin manual bank override changes parser and displays explicit warning."""
    with open(REAL_SBI_PDF, "rb") as f:
        upload_resp = client.post(
            "/api/admin/conversions/upload",
            files={"file": ("override_test.pdf", f, "application/pdf")},
            headers=ADMIN_HEADERS
        )
    job_id = upload_resp.json()["id"]

    # Override to Punjab National Bank
    override_resp = client.post(
        f"/api/admin/conversions/{job_id}/override-bank",
        json={"bank_name": "Punjab National Bank (PNB)"},
        headers=ADMIN_HEADERS
    )
    assert override_resp.status_code == 200
    data = override_resp.json()
    assert data["bank_name"] == "Punjab National Bank (PNB)"
    assert "Automatic detection selected" in data["override_warning"]
    assert "You manually selected Punjab National Bank" in data["override_warning"]


def test_admin_diagnostics_access():
    """9. Verify admin diagnostics endpoint provides candidate scores, signatures, and duration."""
    with open(REAL_SBI_PDF, "rb") as f:
        upload_resp = client.post(
            "/api/admin/conversions/upload",
            files={"file": ("diag_test.pdf", f, "application/pdf")},
            headers=ADMIN_HEADERS
        )
    data = upload_resp.json()
    assert "candidates" in data
    assert "duration_ms" in data
    assert data["duration_ms"] >= 0
    assert "detection_reasons" in data
    assert len(data["detection_reasons"]) > 0


def test_normal_user_quota_still_enforced():
    """10. Verify normal user quota is strictly enforced server-side when limit is exceeded."""
    user = CurrentUser(id="test-user-id", email="user@example.com", role="USER", is_unlimited=False)
    today = get_kolkata_today()
    # Exhaust normal user quota
    _IN_MEMORY_DAILY_USAGE[f"{user.id}:{today}"] = 48  # Only 2 pages remaining

    with open(REAL_SBI_PDF, "rb") as f:  # 8 pages > 2 pages remaining
        resp = client.post(
            "/api/conversions/upload",
            files={"file": ("quota_block.pdf", f, "application/pdf")},
            headers=USER_HEADERS
        )
    # Under PRD partial processing, quota is strictly enforced: only remaining quota is processed, 6 pages skipped
    assert resp.status_code == 200
    q_data = resp.json()
    assert q_data.get("is_partial_conversion") is True or q_data.get("pages_skipped") > 0
    assert q_data.get("pages_processed") <= 2
    _IN_MEMORY_DAILY_USAGE[f"{user.id}:{today}"] = 0
    from app.core import db
    db.reset_daily_usage(user.id, today)


def test_unlimited_user_quota_bypass():
    """11. Verify unlimited approved user also bypasses the 50-page daily quota."""
    unlim_user = CurrentUser(
        id="test-unlimited-id",
        email="unlimited@example.com",
        role="USER",
        is_unlimited=True
    )
    today = get_kolkata_today()
    _IN_MEMORY_DAILY_USAGE[f"{unlim_user.id}:{today}"] = 250

    with open(REAL_SBI_PDF, "rb") as f:
        resp = client.post(
            "/api/conversions/upload",
            files={"file": ("unlim_test.pdf", f, "application/pdf")},
            headers={"Authorization": "Bearer mock-unlimited-token"}
        )
    assert resp.status_code == 200, f"Unlimited user should convert without 429, got {resp.status_code}"


def test_admin_unlimited_on_production_configuration():
    """12. Verify admin unlimited status is based on role, not hostname or environment."""
    prod_admin = CurrentUser(
        id="prod-admin-uuid",
        email="owner@production-domain.in",
        role="ADMIN",
        is_unlimited=True
    )
    assert prod_admin.is_admin is True
    assert prod_admin.has_quota_bypass is True

    from app.api.usage import get_user_usage_data
    usage = get_user_usage_data(prod_admin)
    assert usage.is_unlimited is True
    assert usage.pages_remaining_today >= 999999
    assert usage.account_status == "Admin Unlimited"
