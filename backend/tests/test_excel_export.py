import io
import os
import openpyxl
import pytest
from datetime import date, datetime
from decimal import Decimal
from fastapi.testclient import TestClient

from main import app
from app.transactions.model import CanonicalStatement, TransactionItem
from app.excel.excel_generator import TallyExcelGenerator, EXCEL_COLUMNS
from app.tally.xml_generator import TallyXMLGenerator
from app.core.security import CurrentUser
from app.api.usage import _IN_MEMORY_DAILY_USAGE, get_kolkata_today
from app.api.conversions import IN_MEMORY_JOBS

client = TestClient(app)

ADMIN_HEADERS = {"Authorization": "Bearer mock-admin-token"}
USER_HEADERS = {"Authorization": "Bearer mock-user-token"}
REAL_SBI_PDF = "D:/D drive data/BANK STATEMENTS/1776150969645s6FWFsyLeycG6QGB (1).pdf"

def build_sample_statement():
    """Helper creating a valid canonical statement with diverse transaction types."""
    stmt = CanonicalStatement(
        bank="State Bank of India (SBI)",
        statement_format="Standard",
        account_number_masked="XXXX9623",
        statement_from=date(2025, 7, 1),
        statement_to=date(2025, 7, 31),
        opening_balance=Decimal("100000.00"),
        closing_balance=Decimal("99632.00"),
        total_debit=Decimal("7544.00"),
        total_credit=Decimal("7176.00"),
        bank_ledger_name="SBI Current A/C",
        cash_ledger_name="Cash"
    )
    # Row 1: Receipt with leading zeros instrument number
    tx1 = TransactionItem(
        id="tx-1",
        row_index=1,
        date=date(2025, 7, 17),
        narration="UPI SETTLEMENT -DWL508- 17/07/25",
        ledger_name="Cash",
        instrument_number="000000000000000",
        instrument_date=date(2025, 7, 17),
        debit=Decimal("0.00"),
        credit=Decimal("7176.00"),
        balance=Decimal("107176.00"),
        voucher_type="Receipt",
        validation_status="VALID"
    )
    # Row 2: Payment with cheque number
    tx2 = TransactionItem(
        id="tx-2",
        row_index=2,
        date=date(2025, 7, 18),
        narration="CHQ PAID TO ABC TRADERS",
        ledger_name="ABC Traders Pvt Ltd",
        cheque_number="004213",
        instrument_date=date(2025, 7, 18),
        debit=Decimal("7544.00"),
        credit=Decimal("0.00"),
        balance=Decimal("99632.00"),
        voucher_type="Payment",
        validation_status="VALID"
    )
    stmt.transactions = [tx1, tx2]
    return stmt


# 1. EXCEL GENERATION & MIME TYPE TESTS (PRD Items 1, 2, 3)
def test_excel_file_generation_and_mime_type():
    """Verify generator creates valid .xlsx bytes with correct structure."""
    stmt = build_sample_statement()
    generator = TallyExcelGenerator(default_bank_ledger="SBI Current A/C")
    excel_bytes = generator.generate_excel_bytes(stmt)
    assert len(excel_bytes) > 0

    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    assert "Tally Data" in wb.sheetnames


def test_excel_worksheet_name():
    """PRD Item 3: Verify single worksheet named 'Tally Data'."""
    stmt = build_sample_statement()
    generator = TallyExcelGenerator()
    wb = generator.generate_workbook(stmt)
    assert wb.active.title == "Tally Data"
    assert len(wb.sheetnames) == 1


# 2. COLUMN HEADINGS AND ORDER TESTS (PRD Items 4, 5)
def test_exact_column_names_and_order():
    """PRD Item 4 & 5: Verify exact 11 columns in exact specified order."""
    stmt = build_sample_statement()
    generator = TallyExcelGenerator()
    wb = generator.generate_workbook(stmt)
    ws = wb["Tally Data"]

    expected_columns = [
        "VOUCHER NO.",
        "VOUCHER TYPE",
        "VOUCHER DATE",
        "VOUCHER NARRATION",
        "LEDGER NAME",
        "BANK LEDGER AS TALLY",
        "INST. NUMBER",
        "INST. DATE",
        "DEBIT AMOUNT",
        "CREDIT AMOUNT",
        "BALANCE"
    ]
    actual_columns = [ws.cell(row=1, column=c).value for c in range(1, 12)]
    assert actual_columns == expected_columns
    assert len(actual_columns) == 11


# 3. TRANSACTION DATA INTEGRITY (PRD Items 6 - 18)
def test_transaction_count_and_sequential_voucher_numbering():
    """PRD Items 6 & 7: Verify transaction count and sequential voucher numbering."""
    stmt = build_sample_statement()
    generator = TallyExcelGenerator()
    wb = generator.generate_workbook(stmt)
    ws = wb["Tally Data"]

    # 2 transactions -> 2 data rows
    assert ws.max_row == 3  # Header + 2 data rows
    assert ws.cell(row=2, column=1).value == 1
    assert ws.cell(row=3, column=1).value == 2


def test_voucher_types_and_narrations():
    """PRD Items 8 & 10: Verify voucher types and cleaned narrations."""
    stmt = build_sample_statement()
    generator = TallyExcelGenerator()
    wb = generator.generate_workbook(stmt)
    ws = wb["Tally Data"]

    assert ws.cell(row=2, column=2).value == "Receipt"
    assert ws.cell(row=2, column=4).value == "UPI SETTLEMENT -DWL508- 17/07/25"

    assert ws.cell(row=3, column=2).value == "Payment"
    assert ws.cell(row=3, column=4).value == "CHQ PAID TO ABC TRADERS"


def test_ledger_names_and_bank_ledger_as_tally():
    """PRD Items 11 & 12: Verify party ledger and verbatim Bank Ledger As Tally."""
    stmt = build_sample_statement()
    generator = TallyExcelGenerator(default_bank_ledger="HDFC CC A/C 535555")
    wb = generator.generate_workbook(stmt, bank_ledger_name="HDFC CC A/C 535555")
    ws = wb["Tally Data"]

    # Row 1: Party is Cash, Bank is HDFC CC A/C 535555
    assert ws.cell(row=2, column=5).value == "Cash"
    assert ws.cell(row=2, column=6).value == "HDFC CC A/C 535555"

    # Row 2: Party is ABC Traders Pvt Ltd, Bank is HDFC CC A/C 535555
    assert ws.cell(row=3, column=5).value == "ABC Traders Pvt Ltd"
    assert ws.cell(row=3, column=6).value == "HDFC CC A/C 535555"


def test_instrument_number_preserves_leading_zeros():
    """
    PRD Items 13 & 14 (CRITICAL):
    Instrument numbers like '000000000000000' and '004213' must strictly preserve leading zeros.
    Must NOT become 0 or 0.0 or 4213.
    """
    stmt = build_sample_statement()
    generator = TallyExcelGenerator()
    wb = generator.generate_workbook(stmt)
    ws = wb["Tally Data"]

    c7_row2 = ws.cell(row=2, column=7)
    assert c7_row2.value == "000000000000000"
    assert c7_row2.data_type == "s"

    c7_row3 = ws.cell(row=3, column=7)
    assert c7_row3.value == "004213"
    assert c7_row3.data_type == "s"


def test_dates_stored_as_proper_excel_dates():
    """PRD Items 9, 15, 20: VOUCHER DATE and INST. DATE stored as date objects with DD-MMM-YY format."""
    stmt = build_sample_statement()
    generator = TallyExcelGenerator()
    wb = generator.generate_workbook(stmt)
    ws = wb["Tally Data"]

    # VOUCHER DATE
    c3 = ws.cell(row=2, column=3)
    assert isinstance(c3.value, (date, datetime))
    assert c3.value == date(2025, 7, 17)
    assert "mmm" in c3.number_format.lower()

    # INST. DATE
    c8 = ws.cell(row=2, column=8)
    assert isinstance(c8.value, (date, datetime))
    assert c8.value == date(2025, 7, 17)
    assert "mmm" in c8.number_format.lower()


def test_numeric_amount_cells_for_sum_and_filter():
    """
    PRD Items 16, 17, 18, 19:
    DEBIT AMOUNT, CREDIT AMOUNT, BALANCE stored as actual numeric float values, not strings.
    Users can SUM, FILTER, SORT without text-to-number conversion.
    """
    stmt = build_sample_statement()
    generator = TallyExcelGenerator()
    wb = generator.generate_workbook(stmt)
    ws = wb["Tally Data"]

    # Row 2 (Receipt): Debit is None/blank, Credit is 7176.00 (numeric float)
    debit_cell = ws.cell(row=2, column=9)
    credit_cell = ws.cell(row=2, column=10)
    bal_cell = ws.cell(row=2, column=11)

    assert debit_cell.value is None
    assert isinstance(credit_cell.value, (float, int))
    assert credit_cell.value == 7176.00
    assert credit_cell.number_format == "#,##0.00"

    assert isinstance(bal_cell.value, (float, int))
    assert bal_cell.value == 107176.00
    assert bal_cell.number_format == "#,##0.00"

    # Row 3 (Payment): Debit is 7544.00 (numeric float), Credit is None/blank
    debit_cell3 = ws.cell(row=3, column=9)
    credit_cell3 = ws.cell(row=3, column=10)
    assert isinstance(debit_cell3.value, (float, int))
    assert debit_cell3.value == 7544.00
    assert credit_cell3.value is None


def test_freeze_panes_and_autofilter():
    """PRD Item 11: Header row is frozen at A2 and Excel filters enabled on header row."""
    stmt = build_sample_statement()
    generator = TallyExcelGenerator()
    wb = generator.generate_workbook(stmt)
    ws = wb["Tally Data"]

    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref == "A1:K3"


def test_filename_sanitization():
    """PRD Item 10: Clean filename e.g. SBI_Statement_01-Jul-25_to_31-Jul-25.xlsx."""
    stmt = build_sample_statement()
    generator = TallyExcelGenerator()
    fn = generator.generate_filename(stmt, bank_name="State Bank of India (SBI)")
    assert fn == "State_Statement_01-Jul-25_to_31-Jul-25.xlsx" or "SBI_Statement" in fn


# 4. ENDPOINT TESTS (PRD Items 21, 22, 23, 24, 25)
def test_user_excel_export_endpoint():
    """Verify user can generate and download Excel via API."""
    with open(REAL_SBI_PDF, "rb") as f:
        resp = client.post(
            "/api/conversions/upload",
            files={"file": ("test_user_excel.pdf", f, "application/pdf")},
            headers=USER_HEADERS
        )
    assert resp.status_code == 200
    job_id = resp.json()["id"]

    # Generate Excel
    gen_resp = client.post(
        f"/api/conversions/{job_id}/generate-excel",
        json={"bank_ledger_name": "SBI Current A/C", "cash_ledger_name": "Cash"},
        headers=USER_HEADERS
    )
    assert gen_resp.status_code == 200, f"Excel generation failed: {gen_resp.text}"
    gen_data = gen_resp.json()
    assert gen_data["success"] is True
    assert gen_data["filename"].endswith(".xlsx")

    # Download Excel
    dl_resp = client.get(
        f"/api/conversions/{job_id}/download-excel",
        headers=USER_HEADERS
    )
    assert dl_resp.status_code == 200
    assert dl_resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    wb = openpyxl.load_workbook(io.BytesIO(dl_resp.content))
    ws = wb["Tally Data"]
    assert ws.max_row == 129  # Header + 128 transactions


def test_user_edited_values_reflected_in_excel_and_xml_parity():
    """
    PRD Items 21 & 23:
    When user updates a ledger and voucher type during review,
    both Excel and XML outputs MUST reflect the exact same final reviewed values.
    """
    with open(REAL_SBI_PDF, "rb") as f:
        resp = client.post(
            "/api/conversions/upload",
            files={"file": ("test_parity.pdf", f, "application/pdf")},
            headers=USER_HEADERS
        )
    assert resp.status_code == 200
    job_id = resp.json()["id"]

    # Update Row 1: Change ledger to 'Super Supplies Pvt Ltd' and voucher_type to 'Payment'
    update_resp = client.post(
        f"/api/conversions/{job_id}/update-row",
        json={
            "row_index": 1,
            "ledger_name": "Super Supplies Pvt Ltd",
            "voucher_type": "Payment"
        },
        headers=USER_HEADERS
    )
    assert update_resp.status_code == 200

    # Generate XML
    xml_resp = client.post(
        f"/api/conversions/{job_id}/generate",
        json={"bank_ledger_name": "State Bank of India A/C"},
        headers=USER_HEADERS
    )
    assert xml_resp.status_code == 200

    # Generate Excel
    excel_resp = client.post(
        f"/api/conversions/{job_id}/generate-excel",
        json={"bank_ledger_name": "State Bank of India A/C"},
        headers=USER_HEADERS
    )
    assert excel_resp.status_code == 200

    # Inspect Excel content
    dl_excel = client.get(f"/api/conversions/{job_id}/download-excel", headers=USER_HEADERS)
    wb = openpyxl.load_workbook(io.BytesIO(dl_excel.content))
    ws = wb["Tally Data"]

    # Row 1 (row 2 in excel) must have the edited ledger and voucher type
    assert ws.cell(row=2, column=5).value == "Super Supplies Pvt Ltd"
    assert ws.cell(row=2, column=2).value == "Payment"

    # Inspect XML content
    dl_xml = client.get(f"/api/conversions/{job_id}/download", headers=USER_HEADERS)
    xml_text = dl_xml.text
    assert "Super Supplies Pvt Ltd" in xml_text


def test_excel_export_does_not_consume_quota():
    """PRD Item 24: Verify generating Excel does NOT deduct any user daily page quota."""
    user = CurrentUser(id="test-user-id", email="user@example.com", role="USER")
    today = get_kolkata_today()
    
    with open(REAL_SBI_PDF, "rb") as f:
        resp = client.post(
            "/api/conversions/upload",
            files={"file": ("test_quota.pdf", f, "application/pdf")},
            headers=USER_HEADERS
        )
    job_id = resp.json()["id"]
    usage_after_upload = _IN_MEMORY_DAILY_USAGE.get(f"{user.id}:{today}", 0)

    # Generate Excel
    client.post(
        f"/api/conversions/{job_id}/generate-excel",
        headers=USER_HEADERS
    )
    usage_after_excel = _IN_MEMORY_DAILY_USAGE.get(f"{user.id}:{today}", 0)
    assert usage_after_excel == usage_after_upload, "Excel generation must not deduct user quota"

    # Download Excel
    client.get(f"/api/conversions/{job_id}/download-excel", headers=USER_HEADERS)
    usage_after_dl = _IN_MEMORY_DAILY_USAGE.get(f"{user.id}:{today}", 0)
    assert usage_after_dl == usage_after_upload, "Excel download must not deduct user quota"


def test_export_blocked_when_critical_validation_fails():
    """PRD Item 25: Excel generation must strictly fail/block when transactions have validation errors."""
    stmt = build_sample_statement()
    # Mark row 1 as error
    stmt.transactions[0].validation_status = "ERROR"
    stmt.transactions[0].validation_notes = "Debit/Credit math discrepancy"

    job_id = "test-failing-job"
    IN_MEMORY_JOBS[job_id] = {
        "id": job_id,
        "user_id": "test-user-id",
        "bank_name": "State Bank of India (SBI)",
        "statement": stmt,
        "raw_transaction_count": 2,
        "status": "NEEDS_REVIEW"
    }

    resp = client.post(
        f"/api/conversions/{job_id}/generate-excel",
        headers=USER_HEADERS
    )
    assert resp.status_code == 400
    assert "ERR_MATH_VALIDATION_FAILED" in resp.text or "failed balance verification" in resp.text


def test_admin_converter_excel_export():
    """PRD Item 22: Admin converter generates Excel from reviewed data with unlimited quota."""
    with open(REAL_SBI_PDF, "rb") as f:
        upload_resp = client.post(
            "/api/admin/conversions/upload",
            files={"file": ("admin_excel_test.pdf", f, "application/pdf")},
            headers=ADMIN_HEADERS
        )
    assert upload_resp.status_code == 200
    job_id = upload_resp.json()["id"]

    # Admin generate Excel
    gen_resp = client.post(
        f"/api/admin/conversions/{job_id}/generate-excel",
        json={"bank_ledger_name": "State Bank of India A/C", "cash_ledger_name": "Cash"},
        headers=ADMIN_HEADERS
    )
    assert gen_resp.status_code == 200, f"Admin Excel generation failed: {gen_resp.text}"
    gen_data = gen_resp.json()
    assert gen_data["status"] == "COMPLETED"
    assert gen_data["voucher_count"] == 128
    assert gen_data["filename"].endswith(".xlsx")

    # Download Excel
    dl_resp = client.get(
        f"/api/conversions/{job_id}/download-excel",
        headers=ADMIN_HEADERS
    )
    assert dl_resp.status_code == 200
    assert len(dl_resp.content) > 0

def test_excel_generation_independent_of_xml():
    """
    PRD Correction Item 1:
    Verify Excel generation works completely independently even if XML has NOT been generated.
    """
    _IN_MEMORY_DAILY_USAGE.clear()
    with open(REAL_SBI_PDF, "rb") as f:
        resp = client.post(
            "/api/conversions/upload",
            files={"file": ("test_independent.pdf", f, "application/pdf")},
            headers=USER_HEADERS
        )
    assert resp.status_code == 200
    job_id = resp.json()["id"]

    # Verify XML has not been generated
    job = IN_MEMORY_JOBS[job_id]
    assert job.get("xml_content") is None
    assert job.get("xml_path") is None

    # Generate Excel directly
    gen_resp = client.post(
        f"/api/conversions/{job_id}/generate-excel",
        json={"bank_ledger_name": "State Bank of India A/C"},
        headers=USER_HEADERS
    )
    assert gen_resp.status_code == 200
    assert gen_resp.json()["success"] is True

    # Confirm XML was NOT secretly created during Excel generation
    assert job.get("xml_content") is None
    assert job.get("xml_path") is None


def test_real_statement_all_fields_modified_excel_xml_parity():
    """
    PRD Correction Item 18:
    Use a real statement sample and intentionally modify:
    1. Ledger Name
    2. Bank Ledger As Tally
    3. Voucher Type
    4. Narration
    5. Instrument Number
    Then generate both Excel and XML and verify that every modified value appears identically in both outputs.
    """
    _IN_MEMORY_DAILY_USAGE.clear()
    with open(REAL_SBI_PDF, "rb") as f:
        resp = client.post(
            "/api/conversions/upload",
            files={"file": ("test_all_modifications.pdf", f, "application/pdf")},
            headers=USER_HEADERS
        )
    assert resp.status_code == 200
    job_id = resp.json()["id"]

    # Intentionally modify all required fields on row 1
    custom_ledger = "ABC Traders Pvt Ltd"
    custom_bank_ledger = "HDFC CC A/C 535555"
    custom_voucher_type = "Contra"
    custom_narration = "Cleaned Custom Narration For Field Parity Verification"
    custom_inst_no = "000000000000000"

    update_resp = client.post(
        f"/api/conversions/{job_id}/update-row",
        json={
            "row_index": 1,
            "ledger_name": custom_ledger,
            "voucher_type": custom_voucher_type,
            "narration": custom_narration,
            "instrument_number": custom_inst_no
        },
        headers=USER_HEADERS
    )
    assert update_resp.status_code == 200

    # 1. Generate Excel from snapshot
    excel_resp = client.post(
        f"/api/conversions/{job_id}/generate-excel",
        json={"bank_ledger_name": custom_bank_ledger},
        headers=USER_HEADERS
    )
    assert excel_resp.status_code == 200

    # 2. Generate XML from the same snapshot
    xml_resp = client.post(
        f"/api/conversions/{job_id}/generate",
        json={"bank_ledger_name": custom_bank_ledger},
        headers=USER_HEADERS
    )
    assert xml_resp.status_code == 200

    # Inspect Excel output
    dl_excel = client.get(f"/api/conversions/{job_id}/download-excel", headers=USER_HEADERS)
    wb = openpyxl.load_workbook(io.BytesIO(dl_excel.content))
    ws = wb["Tally Data"]

    # Verify Row 2 (the first transaction row)
    excel_voucher_no = ws.cell(row=2, column=1).value
    excel_voucher_type = ws.cell(row=2, column=2).value
    excel_narration = ws.cell(row=2, column=4).value
    excel_ledger = ws.cell(row=2, column=5).value
    excel_bank_ledger = ws.cell(row=2, column=6).value
    excel_inst_no_cell = ws.cell(row=2, column=7)

    assert excel_voucher_no == 1
    assert excel_voucher_type == custom_voucher_type
    assert excel_narration == custom_narration
    assert excel_ledger == custom_ledger
    assert excel_bank_ledger == custom_bank_ledger
    assert excel_inst_no_cell.value == custom_inst_no
    assert excel_inst_no_cell.data_type == "s"

    # Inspect XML output
    dl_xml = client.get(f"/api/conversions/{job_id}/download", headers=USER_HEADERS)
    xml_text = dl_xml.text

    assert f'VCHTYPE="{custom_voucher_type}"' in xml_text
    assert f"<NARRATION>{custom_narration}</NARRATION>" in xml_text
    assert f"<LEDGERNAME>{custom_ledger}</LEDGERNAME>" in xml_text
    assert f"<LEDGERNAME>{custom_bank_ledger}</LEDGERNAME>" in xml_text
    assert f"<INSTRUMENTNUMBER>{custom_inst_no}</INSTRUMENTNUMBER>" in xml_text


# 7. SNAPSHOT IMMUTABILITY & CACHE INVALIDATION TESTS
from pydantic import ValidationError
from app.transactions.snapshot import FinalConversionSnapshot, FinalVoucherEntry
from app.excel.consistency_validator import validate_complete_11_field_parity
from tests.test_bank_detection_regression import create_synthetic_pnb_pdf
from app.pdf.extractor import extract_pdf_data
from app.detector.bank_detector import detect_bank_from_document
from app.parsers.registry import parser_registry

REAL_HDFC_PDF = r"D:/D drive data/BANK STATEMENTS/GULERIA CLOTH/Acct_Statement_XXXXXXXX3431_30072026_unlocked.pdf"

def test_snapshot_deep_immutability():
    """
    CRITICAL ARCHITECTURAL CHECK:
    Verifies that FinalConversionSnapshot and FinalVoucherEntry are strictly frozen.
    Downstream Excel/XML generators CANNOT mutate the snapshot.
    Attempted attribute reassignment raises ValidationError.
    """
    stmt = build_sample_statement()
    snapshot = FinalConversionSnapshot.create_from_statement(
        statement=stmt,
        bank_ledger_name="SBI Current A/C",
        cash_ledger_name="Cash"
    )

    # 1. Verify snapshot root model is frozen
    with pytest.raises(ValidationError):
        snapshot.bank_name = "Mutated Bank Name"

    with pytest.raises(ValidationError):
        snapshot.bank_ledger_name = "Mutated Ledger"

    # 2. Verify transactions container is an immutable tuple
    assert isinstance(snapshot.transactions, tuple)
    with pytest.raises(AttributeError):
        snapshot.transactions.append("foo")
    with pytest.raises(TypeError):
        snapshot.transactions[0] = "foo"

    # 3. Verify individual voucher entries inside transactions are frozen
    entry = snapshot.transactions[0]
    assert isinstance(entry, FinalVoucherEntry)
    with pytest.raises(ValidationError):
        entry.ledger_name = "Mutated Party"

    with pytest.raises(ValidationError):
        entry.voucher_type = "Contra"

    with pytest.raises(ValidationError):
        entry.debit = Decimal("999999.99")


def test_cache_invalidation_on_data_edit():
    """
    CRITICAL CHECK:
    When a user/admin edits data after a snapshot has been created,
    the cached snapshot and export files are invalidated so that the next
    export creates a fresh FinalConversionSnapshot reflecting the edits.
    """
    _IN_MEMORY_DAILY_USAGE.clear()
    with open(REAL_SBI_PDF, "rb") as f:
        resp = client.post(
            "/api/conversions/upload",
            files={"file": ("test_cache_inval.pdf", f, "application/pdf")},
            headers=USER_HEADERS
        )
    assert resp.status_code == 200
    job_id = resp.json()["id"]

    # Generate initial Excel (builds snapshot and stores excel_path)
    excel_resp = client.post(
        f"/api/conversions/{job_id}/generate-excel",
        headers=USER_HEADERS
    )
    assert excel_resp.status_code == 200
    job = IN_MEMORY_JOBS[job_id]
    assert "snapshot" in job
    assert "excel_path" in job

    # Edit a row
    edit_resp = client.post(
        f"/api/conversions/{job_id}/update-row",
        json={
            "row_index": 1,
            "ledger_name": "Newly Updated Vendor Ltd",
            "narration": "Newly Updated Narration After Snapshot Creation"
        },
        headers=USER_HEADERS
    )
    assert edit_resp.status_code == 200

    # Verify cached snapshot and export path were invalidated
    assert "snapshot" not in job
    assert "excel_path" not in job
    assert "xml_path" not in job

    # Re-generate Excel -> Fresh snapshot built with updated data
    re_gen = client.post(
        f"/api/conversions/{job_id}/generate-excel",
        headers=USER_HEADERS
    )
    assert re_gen.status_code == 200

    # Download Excel and verify updated value is present
    dl = client.get(f"/api/conversions/{job_id}/download-excel", headers=USER_HEADERS)
    wb = openpyxl.load_workbook(io.BytesIO(dl.content))
    ws = wb["Tally Data"]
    assert ws.cell(row=2, column=5).value == "Newly Updated Vendor Ltd"
    assert ws.cell(row=2, column=4).value == "Newly Updated Narration After Snapshot Creation"


# 8. COMPLETE 11-FIELD PARITY TEST ACROSS ALL TRANSACTIONS
def test_complete_11_field_parity_real_sbi_statement():
    """
    CRITICAL CHECK 2:
    Compares EVERY exportable field across all 128 transactions of the real SBI statement:
    - VOUCHER NO.
    - VOUCHER TYPE
    - VOUCHER DATE
    - VOUCHER NARRATION
    - LEDGER NAME
    - BANK LEDGER AS TALLY
    - INST. NUMBER (including leading zeros)
    - INST. DATE
    - DEBIT AMOUNT
    - CREDIT AMOUNT
    - BALANCE
    """
    _IN_MEMORY_DAILY_USAGE.clear()
    with open(REAL_SBI_PDF, "rb") as f:
        resp = client.post(
            "/api/conversions/upload",
            files={"file": ("test_complete_parity.pdf", f, "application/pdf")},
            headers=USER_HEADERS
        )
    assert resp.status_code == 200
    job_id = resp.json()["id"]

    # Modify row 1 with leading zero instrument number and custom ledger
    client.post(
        f"/api/conversions/{job_id}/update-row",
        json={
            "row_index": 1,
            "ledger_name": "Special Party A/C",
            "voucher_type": "Contra",
            "instrument_number": "000000000000000",
            "narration": "Narration with leading zeros instrument"
        },
        headers=USER_HEADERS
    )

    # Generate both Excel and XML
    bank_ledger = "State Bank of India A/C"
    e_res = client.post(f"/api/conversions/{job_id}/generate-excel", json={"bank_ledger_name": bank_ledger}, headers=USER_HEADERS)
    assert e_res.status_code == 200

    x_res = client.post(f"/api/conversions/{job_id}/generate", json={"bank_ledger_name": bank_ledger}, headers=USER_HEADERS)
    assert x_res.status_code == 200

    dl_excel = client.get(f"/api/conversions/{job_id}/download-excel", headers=USER_HEADERS)
    dl_xml = client.get(f"/api/conversions/{job_id}/download", headers=USER_HEADERS)

    job = IN_MEMORY_JOBS[job_id]
    snapshot: FinalConversionSnapshot = job["snapshot"]

    is_parity_valid, errors = validate_complete_11_field_parity(
        snapshot=snapshot,
        excel_bytes=dl_excel.content,
        xml_content=dl_xml.text
    )
    assert is_parity_valid, f"Complete 11-field parity failed: {errors[:5]}"


# 9. REAL-WORLD MULTI-BANK INTEGRATION TESTS
@pytest.mark.skipif(not os.path.exists(REAL_HDFC_PDF), reason="Real HDFC PDF not available")
def test_multi_bank_pipeline_hdfc_bank_statement():
    """
    CRITICAL CHECK 3:
    Executes end-to-end pipeline on real HDFC statement:
    PDF -> Detection -> Parser -> Review/Mapping -> FinalConversionSnapshot -> Excel & XML.
    Verifies that Excel generator is 100% bank-agnostic and maintains 11-field parity.
    """
    doc = extract_pdf_data(REAL_HDFC_PDF)
    det = detect_bank_from_document(doc)
    assert "HDFC" in det.bank_name

    parser = parser_registry.get_parser_for_bank(det.bank_name)
    stmt = parser.parse(doc)
    assert len(stmt.transactions) == 25

    # Mark validation status as VALID for conversion review
    for tx in stmt.transactions:
        tx.validation_status = "VALID"
        tx.validation_notes = None

    snapshot = FinalConversionSnapshot.create_from_statement(
        statement=stmt,
        bank_ledger_name="HDFC Bank CC A/C",
        cash_ledger_name="Cash"
    )
    assert len(snapshot.transactions) == 25

    excel_gen = TallyExcelGenerator()
    excel_bytes = excel_gen.generate_excel_bytes(snapshot)
    assert len(excel_bytes) > 0

    xml_gen = TallyXMLGenerator()
    xml_content = xml_gen.generate_xml(snapshot)
    assert "<VOUCHER" in xml_content

    # Validate complete 11-field parity on HDFC statement
    is_valid, errors = validate_complete_11_field_parity(snapshot, excel_bytes, xml_content)
    assert is_valid, f"HDFC 11-field parity failed: {errors}"


def test_multi_bank_pipeline_pnb_statement():
    """
    CRITICAL CHECK 3:
    Executes end-to-end pipeline on PNB statement:
    PDF -> Detection -> Parser -> Review/Mapping -> FinalConversionSnapshot -> Excel & XML.
    Verifies that Excel generator is 100% bank-agnostic and maintains 11-field parity.
    """
    pnb_bytes = create_synthetic_pnb_pdf()
    _IN_MEMORY_DAILY_USAGE.clear()
    IN_MEMORY_JOBS.clear()
    from app.core import db
    today = get_kolkata_today()
    for uid in ["test-user-id", "user@example.com"]:
        db.reset_daily_usage(uid, today)
        db.set_additional_pages(uid, 0)
    upload_res = client.post(
        "/api/conversions/upload",
        files={"file": ("pnb_pipeline.pdf", pnb_bytes, "application/pdf")},
        headers=USER_HEADERS
    )
    assert upload_res.status_code == 200
    data = upload_res.json()
    assert "Punjab National Bank" in data["bank_name"]
    job_id = data["id"]

    # Generate Excel and XML
    bank_ledger = "PNB Saving A/C 0033"
    e_res = client.post(f"/api/conversions/{job_id}/generate-excel", json={"bank_ledger_name": bank_ledger}, headers=USER_HEADERS)
    assert e_res.status_code == 200

    x_res = client.post(f"/api/conversions/{job_id}/generate", json={"bank_ledger_name": bank_ledger}, headers=USER_HEADERS)
    assert x_res.status_code == 200

    dl_excel = client.get(f"/api/conversions/{job_id}/download-excel", headers=USER_HEADERS)
    dl_xml = client.get(f"/api/conversions/{job_id}/download", headers=USER_HEADERS)

    job = IN_MEMORY_JOBS[job_id]
    snapshot: FinalConversionSnapshot = job["snapshot"]

    is_valid, errors = validate_complete_11_field_parity(snapshot, dl_excel.content, dl_xml.text)
    assert is_valid, f"PNB 11-field parity failed: {errors}"
