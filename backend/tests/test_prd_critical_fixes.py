import os
import re
import time
import pytest
from datetime import date, datetime
from decimal import Decimal
from openpyxl import load_workbook
import io
import xml.etree.ElementTree as ET

from app.core.otp_service import otp_service, OTPRecord
from app.accounting.ledger_importer import UserLedgerStore, import_ledgers_from_text
from app.transactions.model import CanonicalStatement, TransactionItem
from app.transactions.snapshot import FinalConversionSnapshot
from app.excel.excel_generator import TallyExcelGenerator
from app.tally.xml_generator import TallyXMLGenerator

# ---------------------------------------------------------------------------
# TEST 1: Admin Login Security & Hardcoded Credential Scrubbing
# ---------------------------------------------------------------------------
def test_admin_login_page_no_hardcoded_credentials():
    """Verify that the frontend admin login page contains no exposed admin passwords or bypass banners."""
    frontend_login_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "app", "admin", "login", "page.tsx")
    )
    assert os.path.exists(frontend_login_path), f"File not found: {frontend_login_path}"
    with open(frontend_login_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Must NOT contain hardcoded test/dev password
    assert "admin123" not in content, "CRITICAL SECURITY RISK: 'admin123' found in admin login page"
    assert "Local Dev / Staff Login" not in content, "CRITICAL: 'Local Dev / Staff Login' banner still present"
    assert "admin@tallyxml.in" not in content, "CRITICAL: 'admin@tallyxml.in' hardcoded credential banner still present"

    # Inputs must use generic placeholders
    assert 'placeholder="Enter your admin email"' in content
    assert 'placeholder="Enter your password"' in content


# ---------------------------------------------------------------------------
# TEST 2: OTP Service (Cryptographic Hash, Cooldown, Rate Limit, Lockout, Masking)
# ---------------------------------------------------------------------------
def test_otp_service_lifecycle_and_security():
    """Verify OTP generation, salted hash storage, cooldown, rate-limiting, lockout, and verification."""
    phone = "+919876543210"

    # Reset any previous state for test isolation
    otp_service._active_otps.pop(phone.lower(), None)
    otp_service._rate_limits.pop(phone.lower(), None)

    # 1. Request OTP
    success, msg, cooldown, ref_id = otp_service.generate_and_send_otp(phone, channel="SMS")
    assert success is True, f"Failed to request OTP: {msg}"
    assert cooldown == 60

    record = otp_service._active_otps.get(phone.lower())
    assert record is not None
    # Verify hashed_otp exists and plain OTP is never stored
    assert hasattr(record, "hashed_otp")
    assert hasattr(record, "salt")
    assert not hasattr(record, "plain_otp")
    assert record.attempts_remaining == 5

    # 2. Cooldown check: request again immediately -> must be rejected
    success2, msg2, remaining_cd, _ = otp_service.generate_and_send_otp(phone, channel="SMS")
    assert success2 is False
    assert "wait" in msg2.lower() or "cooldown" in msg2.lower()
    assert remaining_cd > 0

    # 3. Test failed attempts and brute force lockout
    for i in range(4):
        valid, _ = otp_service.verify_otp(phone, "000000")
        assert valid is False

    # 5th failed attempt should trigger lockout and remove record
    valid5, msg5 = otp_service.verify_otp(phone, "000000")
    assert valid5 is False
    assert "exceeded" in msg5.lower() or "invalidated" in msg5.lower()
    assert phone.lower() not in otp_service._active_otps

    # 4. Telemetry check: ensure plain OTP is never in telemetry and phone is masked
    telemetry = otp_service.get_telemetry_logs()
    assert len(telemetry) > 0
    latest = [t for t in telemetry if t.masked_destination == "+91******3210"]
    assert len(latest) > 0, "Destination must be masked in audit telemetry"
    for item in telemetry:
        assert not hasattr(item, "plain_otp")
        assert not hasattr(item, "otp")


def test_otp_verification_success():
    """Verify that correct OTP hashes match and verify successfully."""
    email = "newuser@example.com"
    otp_service._active_otps.pop(email.lower(), None)
    otp_service._rate_limits.pop(email.lower(), None)

    # Simulate generating an OTP where we know the plain value for verification
    salt = "testsalt123456"
    test_plain_otp = "482915"
    hashed_otp = otp_service._hash_otp(test_plain_otp, salt)

    otp_service._active_otps[email.lower()] = OTPRecord(
        destination=email.lower(),
        hashed_otp=hashed_otp,
        salt=salt,
        created_at=time.time(),
        expires_at=time.time() + 600,
        attempts_remaining=5,
        reference_id="TEST-REF-1"
    )

    # Verify with correct OTP
    valid, msg = otp_service.verify_otp(email, test_plain_otp)
    assert valid is True
    assert "successful" in msg.lower()

    # Verification should invalidate/clear the pending OTP
    assert email.lower() not in otp_service._active_otps


# ---------------------------------------------------------------------------
# TEST 3: Complete Narration Preservation (Zero Truncation in Excel & Tally XML)
# ---------------------------------------------------------------------------
def test_long_narration_preservation_excel_and_xml():
    """Verify that long narrations (250+ characters with special chars) are preserved without truncation."""
    long_narration = (
        "UPI/CR/526019283746/MR JOHN DOE & PARTNERS/HDFC0001234/INVOICE #9872 "
        "SETTLEMENT FOR CONSULTING SERVICES & SOFTWARE LICENSES <CONFIDENTIAL> "
        "REF/TXN/2026/03/15/ABC-XYZ-998877/TRANSFER FROM ACC ************4321 "
        "FINAL BALANCE ADJUSTMENT PER AGREEMENT DATED 01/01/2026"
    )
    assert len(long_narration) > 250

    tx = TransactionItem(
        id="tx-narr-1",
        row_index=1,
        date=date(2026, 3, 15),
        narration=long_narration,
        original_narration=long_narration,
        full_narration=long_narration,
        ledger_name="Consulting Expense",
        voucher_type="Payment",
        debit=Decimal("15420.50"),
        credit=Decimal("0.00"),
        balance=Decimal("84579.50"),
        validation_status="VALID"
    )

    stmt = CanonicalStatement(
        bank="HDFC Bank",
        statement_format="Standard",
        opening_balance=Decimal("100000.00"),
        closing_balance=Decimal("84579.50"),
        total_debit=Decimal("15420.50"),
        total_credit=Decimal("0.00"),
        transactions=[tx],
        bank_ledger_name="HDFC Bank C/A 139528"
    )

    snapshot = FinalConversionSnapshot.create_from_statement(
        statement=stmt,
        bank_ledger_name="HDFC Bank C/A 139528",
        cash_ledger_name="Cash"
    )

    # A. Test Excel Export Preservation & Wrapping
    excel_generator = TallyExcelGenerator()
    excel_bytes = excel_generator.generate_excel_bytes(snapshot)
    wb = load_workbook(io.BytesIO(excel_bytes))
    ws = wb.active

    # Column 4 is Voucher Narration in our layout
    narration_cell = ws.cell(row=2, column=4)
    assert narration_cell.value == long_narration, "Excel narration was truncated or altered"
    assert narration_cell.alignment.wrap_text is True, "Excel narration cell must have wrap_text=True"

    # B. Test Tally XML Export Preservation & XML Entity Escaping
    xml_generator = TallyXMLGenerator()
    xml_str = xml_generator.generate_xml(snapshot)

    # Validate XML is well-formed
    root = ET.fromstring(xml_str)
    assert root is not None

    # Verify narration is present verbatim in the parsed XML
    vouchers = root.findall(".//VOUCHER")
    assert len(vouchers) == 1
    narr_element = vouchers[0].find("NARRATION")
    assert narr_element is not None
    assert narr_element.text == long_narration, "Tally XML narration was truncated or entity-corrupted"


# ---------------------------------------------------------------------------
# TEST 4: Master XML Bank Account Extraction & Ledger Mapping
# ---------------------------------------------------------------------------
def test_master_xml_bank_accounts_extraction_and_mapping():
    """Verify Master XML parses bank ledgers and applies selected bank ledger verbatim to XML and Excel."""
    sample_master_xml = """<ENVELOPE>
      <BODY>
        <IMPORTDATA>
          <REQUESTDATA>
            <TALLYMESSAGE>
              <GROUP NAME="Bank Accounts" RESERVEDNAME="Bank Accounts">
                <PARENT>Current Assets</PARENT>
              </GROUP>
              <GROUP NAME="Bank OCC A/c" RESERVEDNAME="Bank OCC A/c">
                <PARENT>Loans (Liability)</PARENT>
              </GROUP>
              <GROUP NAME="Sundry Creditors" RESERVEDNAME="Sundry Creditors">
                <PARENT>Current Liabilities</PARENT>
              </GROUP>
              <LEDGER NAME="HDFC C/A-139528" RESERVEDNAME="">
                <PARENT>Bank Accounts</PARENT>
                <OPENINGBALANCE>-50000.00</OPENINGBALANCE>
              </LEDGER>
              <LEDGER NAME="SBI A/c 322092276053" RESERVEDNAME="">
                <PARENT>Bank Accounts</PARENT>
                <OPENINGBALANCE>-125000.00</OPENINGBALANCE>
              </LEDGER>
              <LEDGER NAME="PNB OD Account" RESERVEDNAME="">
                <PARENT>Bank OCC A/c</PARENT>
                <OPENINGBALANCE>25000.00</OPENINGBALANCE>
              </LEDGER>
              <LEDGER NAME="Alpha Traders" RESERVEDNAME="">
                <PARENT>Sundry Creditors</PARENT>
              </LEDGER>
            </TALLYMESSAGE>
          </REQUESTDATA>
        </IMPORTDATA>
      </BODY>
    </ENVELOPE>"""

    # Parse ledgers
    result = import_ledgers_from_text(sample_master_xml, filename="Master.xml")
    assert len(result.ledgers) == 4
    assert len(result.groups) == 3

    # Store in UserLedgerStore with user_id
    user_id = "test-user-master-check"
    store = UserLedgerStore()
    store.add_ledgers(user_id, result.ledgers)
    store.add_groups(user_id, result.groups)

    # Verify get_bank_ledgers() extracts ONLY the 3 bank accounts
    bank_ledgers = store.get_bank_ledgers(user_id)
    bank_names = [b.name for b in bank_ledgers]
    assert len(bank_ledgers) == 3
    assert "HDFC C/A-139528" in bank_names
    assert "SBI A/c 322092276053" in bank_names
    assert "PNB OD Account" in bank_names
    assert "Alpha Traders" not in bank_names

    # User selects "SBI A/c 322092276053" as their target bank ledger
    selected_bank_ledger = "SBI A/c 322092276053"
    tx = TransactionItem(
        id="tx-bank-1",
        row_index=1,
        date=date(2026, 3, 10),
        narration="NEFT RCV FROM CUSTOMER ABC",
        original_narration="NEFT RCV FROM CUSTOMER ABC",
        ledger_name="Customer ABC",
        voucher_type="Receipt",
        debit=Decimal("0.00"),
        credit=Decimal("50000.00"),
        balance=Decimal("150000.00"),
        validation_status="VALID"
    )

    stmt = CanonicalStatement(
        bank="State Bank of India",
        statement_format="Standard",
        opening_balance=Decimal("100000.00"),
        closing_balance=Decimal("150000.00"),
        total_debit=Decimal("0.00"),
        total_credit=Decimal("50000.00"),
        transactions=[tx],
        bank_ledger_name=selected_bank_ledger
    )

    snapshot = FinalConversionSnapshot.create_from_statement(
        statement=stmt,
        bank_ledger_name=selected_bank_ledger,
        cash_ledger_name="Cash"
    )

    # 1. Verify snapshot holds the selected ledger
    assert snapshot.bank_ledger_name == selected_bank_ledger
    assert snapshot.transactions[0].bank_ledger_name == selected_bank_ledger

    # 2. Verify XML export writes the selected ledger verbatim
    xml_generator = TallyXMLGenerator()
    xml_output = xml_generator.generate_xml(snapshot)
    assert f"<LEDGERNAME>{selected_bank_ledger}</LEDGERNAME>" in xml_output

    # 3. Verify Excel export writes the selected ledger verbatim
    excel_generator = TallyExcelGenerator()
    excel_data = excel_generator.generate_excel_bytes(snapshot)
    wb = load_workbook(io.BytesIO(excel_data))
    ws = wb.active
    # Column 6 is Bank Ledger Name in Excel export
    assert ws.cell(row=2, column=6).value == selected_bank_ledger


def test_otp_api_strictly_excludes_plaintext_and_dev_otp():
    """Verify that send-otp and resend-otp API responses never expose dev_otp or plain OTP."""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    test_email = f"secure_user_{int(time.time())}@example.com"

    # 1. Test Send OTP via Email
    res = client.post("/api/auth/signup/send-otp", json={
        "email": test_email,
        "mobile_number": "9876543210",
        "full_name": "Security Test User",
        "password": "Password123!",
        "channel": "EMAIL"
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert data.get("success") is True
    assert "dev_otp" not in data, "CRITICAL: dev_otp must never be returned in API response"
    assert "otp" not in data, "CRITICAL: plain otp must never be returned in API response"
    assert "destination_masked" in data
    assert "@" in data["destination_masked"]
    # Check that email is masked
    assert data["destination_masked"].startswith("s")
    assert "*" in data["destination_masked"]

