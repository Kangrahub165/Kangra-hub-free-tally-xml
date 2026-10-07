import unittest
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient

from main import app
from app.core import db
from app.core.security import CurrentUser
from app.invoices.model import InvoiceDocument, InvoiceItem, PartyInfo, FinalInvoiceSnapshot
from app.invoices.bill_identity import (
    normalize_bill_number,
    normalize_bill_date,
    normalize_company_name,
    company_similarity,
    are_same_company,
    compute_bill_fingerprint,
    group_and_merge_invoice_documents
)

class TestPrdFeatures(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_01_mandatory_login_gating(self):
        """Unauthenticated requests to Sales & Purchase APIs must return 401 Unauthorized."""
        res_upload = self.client.post("/api/invoices/upload")
        self.assertEqual(res_upload.status_code, 401, "Upload endpoint must reject unauthenticated requests with 401")

        res_generate = self.client.post("/api/invoices/generate-xml", json={"invoices": []})
        self.assertEqual(res_generate.status_code, 401, "Generate XML endpoint must reject unauthenticated requests with 401")

        res_download = self.client.post("/api/invoices/download-xml", json={"invoices": []})
        self.assertEqual(res_download.status_code, 401, "Download XML endpoint must reject unauthenticated requests with 401")

    def test_02_bill_identity_normalization(self):
        """Bill identity normalization must handle punctuation, leading zeroes, date formats, and company suffixes."""
        # Bill numbers
        self.assertEqual(normalize_bill_number("INV-00123"), "123")
        self.assertEqual(normalize_bill_number("SI/2026/045"), "si2026045")
        self.assertEqual(normalize_bill_number(" #9988 "), "9988")

        # Dates
        self.assertEqual(normalize_bill_date("05/10/2026"), "2026-10-05")
        self.assertEqual(normalize_bill_date("2026-10-05"), "2026-10-05")
        self.assertEqual(normalize_bill_date("05-10-2026"), "2026-10-05")

        # Company Names
        self.assertEqual(normalize_company_name("Hindustan Unilever Pvt. Ltd."), "hindustan unilever")
        self.assertEqual(normalize_company_name("ITC LIMITED"), "itc")
        self.assertEqual(normalize_company_name("Sharma Enterprises LLP"), "sharma")

        # Company Fuzzy Match >= 90%
        self.assertTrue(are_same_company("Hindustan Unilever Limited", "Hindustan Unilever Ltd"))
        self.assertTrue(are_same_company("Nestle India Pvt Ltd", "Nestle India Limited"))

    def test_03_multi_page_bill_consolidation(self):
        """Pages with identical (Bill Number + Date + Company) must merge into 1 single bill with 1 credit."""
        doc_page1 = InvoiceDocument(
            invoice_number="INV-2026-99",
            invoice_date="2026-10-05",
            supplier=PartyInfo(name="Britannia Industries Limited", gstin="02AAACB1234F1Z1"),
            items=[
                InvoiceItem(item_name="Good Day Butter 100g", quantity=Decimal("10"), rate=Decimal("25"), taxable_amount=Decimal("250"))
            ],
            source_filename="page1.pdf",
            source_page_count=1
        )

        doc_page2 = InvoiceDocument(
            invoice_number="INV-2026-99",
            invoice_date="2026-10-05",
            supplier=PartyInfo(name="Britannia Industries Ltd", gstin="02AAACB1234F1Z1"),
            items=[
                InvoiceItem(item_name="Marie Gold 200g", quantity=Decimal("20"), rate=Decimal("30"), taxable_amount=Decimal("600"))
            ],
            source_filename="page2.pdf",
            source_page_count=1
        )

        merged = group_and_merge_invoice_documents([doc_page1, doc_page2], user_id="test_user_1")
        self.assertEqual(len(merged), 1, "2 pages of the same bill must consolidate into 1 single bill")
        self.assertEqual(len(merged[0].items), 2, "Consolidated bill must contain line items from both pages")
        self.assertTrue(merged[0].has_page_continuation, "Consolidated bill must be flagged with continuation")
        self.assertIn("page1.pdf", merged[0].source_filename)
        self.assertIn("page2.pdf", merged[0].source_filename)

    def test_04_fingerprint_and_zero_credit_reconversion(self):
        """Re-uploading an already converted bill today must cost 0 credits."""
        user_id = f"test_user_fp_{uuid.uuid4().hex[:8]}"
        today_ist = "2026-10-05"
        fp = compute_bill_fingerprint(
            user_id=user_id,
            bill_number="INV-TEST-001",
            bill_date=today_ist,
            company_name="Test Supplier Co",
            total_amount=1500.00
        )

        # Before recording: not converted
        self.assertFalse(db.is_bill_already_converted_today(user_id, fp, today_ist))

        # Record conversion
        db.record_converted_bill(
            user_id=user_id,
            bill_number="INV-TEST-001",
            bill_date=today_ist,
            company_name="Test Supplier Co",
            total_amount=1500.00,
            fingerprint_hash=fp,
            page_count=1,
            date_ist=today_ist
        )

        # After recording: recognized as already converted today (0 credits)
        self.assertTrue(db.is_bill_already_converted_today(user_id, fp, today_ist))

    def test_05_staff_security_model(self):
        """Staff users have unlimited bill conversion but ZERO admin powers (is_admin == False)."""
        staff_user = CurrentUser(
            id="staff_123",
            email="staff@example.com",
            role="STAFF",
            staff_source="ADMIN",
            is_gold=False
        )

        self.assertTrue(staff_user.is_staff, "Staff user must have is_staff == True")
        self.assertTrue(staff_user.has_quota_bypass, "Staff user must bypass bill quota limits")
        self.assertFalse(staff_user.is_admin, "Staff user MUST NEVER have admin authorization")

        admin_user = CurrentUser(
            id="admin_123",
            email="admin@example.com",
            role="ADMIN"
        )
        self.assertTrue(admin_user.is_admin, "Admin user must have is_admin == True")
        self.assertTrue(admin_user.is_staff, "Admin user has all staff privileges")
        self.assertTrue(admin_user.has_quota_bypass, "Admin user bypasses bill quota")

    def test_06_gold_tick_distinction(self):
        """Admin-created staff does not get Gold Tick by default; Paid subscriber gets Gold Tick."""
        admin_staff = CurrentUser(
            id="staff_admin",
            email="adminstaff@example.com",
            role="STAFF",
            staff_source="ADMIN",
            is_gold=False
        )
        self.assertFalse(admin_staff.is_gold, "Staff added manually by admin must not have Gold Tick by default")

        paid_staff = CurrentUser(
            id="staff_paid",
            email="paidstaff@example.com",
            role="STAFF",
            staff_source="SUBSCRIPTION",
            is_gold=True
        )
        self.assertTrue(paid_staff.is_gold, "Paid subscriber must have is_gold == True")

    def test_07_device_tracking_and_pool(self):
        """Device tracking must record devices and aggregate multi-account usage."""
        test_suffix = uuid.uuid4().hex[:8]
        dev_id = f"test_dev_{test_suffix}"
        u1 = f"user_pool_1_{test_suffix}"
        u2 = f"user_pool_2_{test_suffix}"

        db.record_device_activity(dev_id, u1, "127.0.0.1", "Mozilla/5.0")
        db.record_device_activity(dev_id, u2, "127.0.0.1", "Mozilla/5.0")

        users = db.get_device_users(dev_id)
        self.assertIn(u1, users)
        self.assertIn(u2, users)

        # Non-whitelisted device tracks daily usage
        db.record_daily_usage(u1, "2026-10-05", 3)
        dev_usage = db.get_device_daily_usage(dev_id, "2026-10-05")
        self.assertGreaterEqual(dev_usage, 3)

        # Admin whitelist toggle
        db.set_device_whitelist(dev_id, True)
        self.assertTrue(db.is_device_whitelisted(dev_id))

if __name__ == "__main__":
    unittest.main()
