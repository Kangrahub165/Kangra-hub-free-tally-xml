import os
import io
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from main import app
from app.core import db
from app.core.config import settings
from app.core.user_store import register_user, create_user_session, REGISTERED_USERS, ACTIVE_SESSIONS
from app.invoices.model import (
    FinalInvoiceSnapshot,
    InvoiceDocument,
    InvoiceItem,
    PartyInfo,
    LedgerMappingConfig
)

client = TestClient(app)
ADMIN_HEADERS = {"Authorization": "Bearer mock-admin-token"}

def _create_sample_invoice_doc(inv_num="INV-TEST-001", inv_type="PURCHASE"):
    from decimal import Decimal
    return InvoiceDocument(
        invoice_number=inv_num,
        invoice_type=inv_type,
        supplier=PartyInfo(name="Acme Supplier", gstin="07AAAAA0000A1Z5", state="Delhi"),
        buyer=PartyInfo(name="Buyer Co", gstin="02BBBBB1111B1Z6", state="Himachal Pradesh"),
        items=[
            InvoiceItem(
                item_name="Widget A",
                description="Widget A",
                quantity=Decimal("2.0"),
                uom="PCS",
                rate=Decimal("100.0"),
                gross_amount=Decimal("200.0"),
                taxable_amount=Decimal("200.0"),
                gst_rate=Decimal("18.0"),
                cgst_amount=Decimal("18.0"),
                sgst_amount=Decimal("18.0"),
                total_amount=Decimal("236.0"),
                matched_stock_item="Widget A"
            )
        ],
        taxable_total=Decimal("200.0"),
        cgst_total=Decimal("18.0"),
        sgst_total=Decimal("18.0"),
        grand_total=Decimal("236.0"),
        source_filename="test_invoice.pdf",
        source_page_count=1
    )

def test_prd_admin_staff_profiles_suite():
    """
    Comprehensive verification of PRD - Admin Controls, Staff Management,
    User Profiles, and Conversion History Persistence.
    Criteria A through J.
    """
    test_user_id = "usr-test-prd-staff-001"
    test_email = "staff_member_test@example.com"
    test_name = "Staff Candidate"

    # Register baseline user
    register_user(
        user_id=test_user_id,
        email=test_email,
        full_name=test_name,
        role="USER",
        is_unlimited=False
    )
    sess_token = create_user_session(test_user_id, test_email)["token"]
    user_headers = {"Authorization": f"Bearer {sess_token}"}

    # -------------------------------------------------------------------------
    # Criterion A: Admin manually adds user to Staff
    # -------------------------------------------------------------------------
    res_add = client.post(
        "/api/staff/add",
        json={"user_id_or_email": test_email, "is_gold": True, "notes": "Granted for staff testing"},
        headers=ADMIN_HEADERS
    )
    assert res_add.status_code == 200, f"Failed to add staff: {res_add.text}"
    add_data = res_add.json()
    assert add_data["success"] is True
    assert add_data["role"] == "STAFF"

    # Verify SQLite DB authoritative records
    db_u = db.get_user_by_id_or_email(test_user_id)
    assert db_u is not None
    assert db_u["role"] == "STAFF"
    assert db_u["is_unlimited"] == 1
    assert db_u["is_gold"] == 1

    membership = db.get_staff_membership(test_user_id)
    assert membership is not None
    assert membership["staff_status"] == "ACTIVE"

    # Check user self-inspection immediately reflects Staff status
    res_me = client.get("/api/auth/me", headers=user_headers)
    assert res_me.status_code == 200
    me_data = res_me.json()
    assert me_data["role"] == "STAFF"
    assert me_data["is_unlimited"] is True
    assert me_data["is_staff"] is True

    # -------------------------------------------------------------------------
    # Criterion B: Admin manually removes user from Staff
    # -------------------------------------------------------------------------
    res_rem = client.post(
        "/api/staff/remove",
        json={"user_id_or_email": test_email, "reason": "Demoting back to user"},
        headers=ADMIN_HEADERS
    )
    assert res_rem.status_code == 200, f"Failed to remove staff: {res_rem.text}"
    assert res_rem.json()["success"] is True

    # Verify SQLite DB reverted
    db_u = db.get_user_by_id_or_email(test_user_id)
    assert db_u["role"] == "USER"
    assert db_u["is_unlimited"] == 0
    rem_membership = db.get_staff_membership(test_user_id)
    assert rem_membership is None or rem_membership["staff_status"] == "CANCELLED"

    # User self-inspection immediately reflects demotion
    res_me = client.get("/api/auth/me", headers=user_headers)
    assert res_me.status_code == 200
    me_data = res_me.json()
    assert me_data["role"] == "USER"
    assert me_data["is_staff"] is False

    # -------------------------------------------------------------------------
    # Criterion C: User uploads profile picture
    # -------------------------------------------------------------------------
    sample_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    res_upload = client.post(
        "/api/auth/profile/picture",
        files={"file": ("profile.png", sample_png, "image/png")},
        headers=user_headers
    )
    assert res_upload.status_code == 200, f"Failed upload avatar: {res_upload.text}"
    up_data = res_upload.json()
    assert up_data["success"] is True
    avatar_url = up_data["avatar_url"]
    assert avatar_url.startswith("/api/auth/profile/picture/")

    # User's profile must show new avatar_url
    res_me = client.get("/api/auth/me", headers=user_headers)
    assert res_me.status_code == 200
    assert res_me.json().get("avatar_url") == avatar_url

    # -------------------------------------------------------------------------
    # Criterion D: Profile picture served/streamed safely
    # -------------------------------------------------------------------------
    res_img = client.get(avatar_url)
    assert res_img.status_code == 200
    assert res_img.headers.get("content-type") == "image/png"
    assert res_img.content == sample_png

    # -------------------------------------------------------------------------
    # Criterion E: User updates/replaces profile picture
    # -------------------------------------------------------------------------
    sample_png_2 = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02\x08\x06\x00\x00\x00\x72\xb6\r$\x00\x00\x00\x0bIDATx\x9cc\xf8\x0f\x00\x01\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
    res_upload_2 = client.post(
        "/api/auth/profile/picture",
        files={"file": ("new_avatar.png", sample_png_2, "image/png")},
        headers=user_headers
    )
    assert res_upload_2.status_code == 200
    new_avatar_url = res_upload_2.json()["avatar_url"]
    assert new_avatar_url != avatar_url

    # Old avatar URL should now 404
    res_old = client.get(avatar_url)
    assert res_old.status_code == 404

    # New avatar URL should 200 with new bytes
    res_new = client.get(new_avatar_url)
    assert res_new.status_code == 200
    assert res_new.content == sample_png_2

    # -------------------------------------------------------------------------
    # Criterion F: User removes profile picture
    # -------------------------------------------------------------------------
    res_del = client.delete("/api/auth/profile/picture", headers=user_headers)
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

    # Profile now has avatar_url as None
    res_me = client.get("/api/auth/me", headers=user_headers)
    assert res_me.json().get("avatar_url") is None

    # Deleted image now returns 404
    res_check_del = client.get(new_avatar_url)
    assert res_check_del.status_code == 404

    # -------------------------------------------------------------------------
    # Criterion G: Staff conversion history persistence
    # -------------------------------------------------------------------------
    # Re-promote to Staff
    client.post(
        "/api/staff/add",
        json={"user_id_or_email": test_email, "is_gold": True},
        headers=ADMIN_HEADERS
    )

    doc_staff = _create_sample_invoice_doc("STAFF-INV-001", "PURCHASE")
    snapshot_staff = FinalInvoiceSnapshot(
        invoices=[doc_staff],
        ledger_mapping=LedgerMappingConfig()
    )

    res_xml_staff = client.post(
        "/api/invoices/generate-xml",
        json=snapshot_staff.model_dump(mode="json"),
        headers=user_headers
    )
    assert res_xml_staff.status_code == 200
    staff_gen_data = res_xml_staff.json()
    assert staff_gen_data["success"] is True
    staff_job_id = staff_gen_data["job_id"]
    assert staff_job_id is not None

    # Conversion record MUST exist in SQLite conversions table
    staff_db_conv = db.get_conversion_by_id(staff_job_id)
    assert staff_db_conv is not None
    assert staff_db_conv["user_id"] == test_user_id
    assert staff_db_conv["status"] == "COMPLETED"

    # XML export file MUST exist on disk
    from app.core.db import DATA_DIR
    xml_path = os.path.join(DATA_DIR, "xml_exports", f"{staff_job_id}.xml")
    assert os.path.exists(xml_path)

    # Conversion MUST be listed in GET /api/conversions for this staff user
    res_conv_list = client.get("/api/conversions", headers=user_headers)
    assert res_conv_list.status_code == 200
    staff_conv_jobs = res_conv_list.json()
    assert any(c["id"] == staff_job_id for c in staff_conv_jobs)

    # XML file can be downloaded via GET /api/conversions/{job_id}/download
    res_dl = client.get(f"/api/conversions/{staff_job_id}/download", headers=user_headers)
    assert res_dl.status_code == 200
    assert "TALLYMESSAGE" in res_dl.text

    # -------------------------------------------------------------------------
    # Criterion H: Admin conversion history persistence
    # -------------------------------------------------------------------------
    doc_admin = _create_sample_invoice_doc("ADMIN-INV-999", "SALES")
    snapshot_admin = FinalInvoiceSnapshot(
        invoices=[doc_admin],
        ledger_mapping=LedgerMappingConfig()
    )

    res_xml_admin = client.post(
        "/api/invoices/generate-xml",
        json=snapshot_admin.model_dump(mode="json"),
        headers=ADMIN_HEADERS
    )
    assert res_xml_admin.status_code == 200
    admin_gen_data = res_xml_admin.json()
    assert admin_gen_data["success"] is True
    admin_job_id = admin_gen_data["job_id"]
    assert admin_job_id is not None

    admin_db_conv = db.get_conversion_by_id(admin_job_id)
    assert admin_db_conv is not None
    assert admin_db_conv["status"] == "COMPLETED"

    res_admin_convs = client.get("/api/conversions", headers=ADMIN_HEADERS)
    assert res_admin_convs.status_code == 200
    assert any(c["id"] == admin_job_id for c in res_admin_convs.json())

    # -------------------------------------------------------------------------
    # Criterion I: Free user conversion history is NOT permanently saved
    # -------------------------------------------------------------------------
    free_user_id = "usr-free-user-non-persistent"
    free_email = "free_user@example.com"
    register_user(
        user_id=free_user_id,
        email=free_email,
        full_name="Free Tester",
        role="USER",
        is_unlimited=False
    )
    free_token = create_user_session(free_user_id, free_email)["token"]
    free_headers = {"Authorization": f"Bearer {free_token}"}

    doc_free = _create_sample_invoice_doc("FREE-INV-111", "PURCHASE")
    snapshot_free = FinalInvoiceSnapshot(
        invoices=[doc_free],
        ledger_mapping=LedgerMappingConfig()
    )

    res_xml_free = client.post(
        "/api/invoices/generate-xml",
        json=snapshot_free.model_dump(mode="json"),
        headers=free_headers
    )
    assert res_xml_free.status_code == 200
    free_gen_data = res_xml_free.json()
    assert free_gen_data["success"] is True
    assert free_gen_data["job_id"] is None

    # SQLite conversions table must have 0 rows for free_user_id
    assert db.get_user_conversions(free_user_id) == []

    # GET /api/conversions for free user must return empty list []
    res_free_convs = client.get("/api/conversions", headers=free_headers)
    assert res_free_convs.status_code == 200
    assert res_free_convs.json() == []

    # -------------------------------------------------------------------------
    # Criterion J: Persistence across simulated restarts / DB authoritative
    # -------------------------------------------------------------------------
    # Clear in-memory user cache and sessions
    with patch.dict(REGISTERED_USERS, {}, clear=True), patch.dict(ACTIVE_SESSIONS, {}, clear=True):
        # Database holds the persistent source of truth
        user_reloaded = db.get_user_by_id_or_email(test_user_id)
        assert user_reloaded is not None
        assert user_reloaded["role"] == "STAFF"
        assert user_reloaded["is_unlimited"] == 1
        assert user_reloaded["is_gold"] == 1

        # Staff conversion record remains in SQLite
        conv_reloaded = db.get_conversion_by_id(staff_job_id)
        assert conv_reloaded is not None
        assert conv_reloaded["user_id"] == test_user_id

        # Free user remains normal user without conversion records
        free_reloaded = db.get_user_by_id_or_email(free_user_id)
        assert free_reloaded is not None
        assert free_reloaded["role"] == "USER"
        assert db.get_user_conversions(free_user_id) == []
