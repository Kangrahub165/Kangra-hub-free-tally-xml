import pytest
import os
import sys
from decimal import Decimal
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from app.pdf.extractor import extract_pdf_data
from app.detector.bank_detector import detect_bank_from_document
from app.parsers.registry import parser_registry
from app.tally.xml_generator import TallyXMLGenerator
from app.tally.xml_validator import validate_tally_xml

client = TestClient(app)

REAL_SBI_PDF_PATH = r"D:/D drive data/BANK STATEMENTS/1776150969645s6FWFsyLeycG6QGB (1).pdf"

@pytest.mark.skipif(not os.path.exists(REAL_SBI_PDF_PATH), reason="Real user SBI PDF not found at path")
def test_real_sbi_statement_detection_and_reconciliation():
    """
    CRITICAL REGRESSION TEST:
    Verifies that the user's actual 8-page SBI statement:
    1. Is detected as State Bank of India with >= 95% HIGH confidence.
    2. Does NOT trigger false positive PNB despite counterparty NEFT/UPI PUNB narrations.
    3. Selects 'sbi_standard' parser.
    4. Extracts all 128 transactions cleanly.
    5. Has 0 balance mismatches and 100% reconciled running balance.
    6. Produces valid, balanced Tally XML.
    """
    # 1. Extract document
    doc = extract_pdf_data(REAL_SBI_PDF_PATH)
    assert doc.total_pages == 8

    # 2. Bank Detection
    det = detect_bank_from_document(doc)
    assert "State Bank of India" in det.bank_name
    assert det.confidence >= 95.0
    assert det.confidence_tier == "HIGH"
    assert det.is_ambiguous is False
    assert det.parser_key == "sbi_standard"
    assert det.detected_ifsc == "SBIN0003248"
    assert det.account_number_masked == "XXXX9623"

    # Counterparty transfer safety: PNB must not win
    assert "Punjab" not in det.bank_name

    # 3. Parser Selection
    parser = parser_registry.get_parser(det.parser_key)
    assert parser is not None
    assert parser.bank_name == "State Bank of India (SBI)"

    # 4. Transaction Extraction & Balance Validation
    statement = parser.parse(doc)
    assert len(statement.transactions) == 128

    # All 128 transactions must be VALID
    invalid_txs = [t for t in statement.transactions if t.validation_status != "VALID"]
    assert len(invalid_txs) == 0, f"Found {len(invalid_txs)} transactions with balance mismatches: {[t.validation_notes for t in invalid_txs]}"

    # Opening & Closing Balance Reconciliation
    assert statement.opening_balance == Decimal("-838460.86")
    assert statement.closing_balance == Decimal("-870432.26")
    
    calc_closing = statement.opening_balance + statement.total_credit - statement.total_debit
    assert calc_closing == statement.closing_balance

    # 5. Tally XML Generation & Validation
    generator = TallyXMLGenerator(default_bank_ledger="State Bank of India A/C")
    xml_content = generator.generate_xml(statement, bank_ledger_name="State Bank of India A/C")
    is_valid, errors = validate_tally_xml(xml_content)
    assert is_valid, f"Tally XML validation failed: {errors}"
    assert "<VOUCHER" in xml_content

@pytest.mark.skipif(not os.path.exists(REAL_SBI_PDF_PATH), reason="Real user SBI PDF not found at path")
def test_real_sbi_upload_api_endpoint():
    """Tests the full upload API endpoint with the user's actual SBI statement."""
    with open(REAL_SBI_PDF_PATH, "rb") as f:
        pdf_bytes = f.read()

    files = {"file": ("sbi_statement.pdf", pdf_bytes, "application/pdf")}
    res = client.post(
        "/api/conversions/upload",
        files=files,
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert res.status_code == 200, f"Upload failed: {res.text}"
    data = res.json()

    assert data["bank_name"] == "State Bank of India (SBI)"
    assert data["confidence_tier"] == "HIGH"
    assert data["confidence_score"] >= 95.0
    assert data["is_ambiguous"] is False
    assert data["transaction_count"] == 128
    assert data["balance_status"] == "VALID"
    assert data["status"] == "COMPLETED"

    # Generate XML via API
    job_id = data["id"]
    gen_res = client.post(
        f"/api/conversions/{job_id}/generate",
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert gen_data["success"] is True
    assert gen_data["status"] == "COMPLETED"

def create_synthetic_pnb_pdf() -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "PUNJAB NATIONAL BANK")
    c.setFont("Helvetica", 9)
    c.drawString(50, 735, "Branch: NAGROTA SURIAN")
    c.drawString(50, 720, "IFS Code: PUNB0080800")
    c.drawString(50, 705, "Account Number : 0033000100123456")
    c.drawString(50, 660, "Date")
    c.drawString(120, 660, "Particulars")
    c.drawString(420, 660, "Withdrawal")
    c.drawString(490, 660, "Deposit")
    c.drawString(540, 660, "Balance")
    c.line(50, 655, 590, 655)
    c.drawString(50, 640, "01/05/2024")
    c.drawString(120, 640, "Salary Credited")
    c.drawString(420, 640, "0.00")
    c.drawString(490, 640, "50,000.00")
    c.drawString(540, 640, "50,000.00")
    c.showPage()
    c.save()
    return buffer.getvalue()

def test_pnb_statement_detection_and_parser_selection():
    """Verifies that PNB statements detect PNB and NEVER select SBI parser."""
    pnb_bytes = create_synthetic_pnb_pdf()
    files = {"file": ("pnb.pdf", pnb_bytes, "application/pdf")}
    res = client.post(
        "/api/conversions/upload",
        files=files,
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "Punjab National Bank" in data["bank_name"]
    assert "State Bank" not in data["bank_name"]
    assert data["confidence_score"] >= 80.0
    assert data["confidence_tier"] in ("HIGH", "MEDIUM")

def create_synthetic_ambiguous_pdf() -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 750, "ACCOUNT STATEMENT")
    c.setFont("Helvetica", 9)
    c.drawString(50, 735, "Customer ID: 12345678")
    c.drawString(50, 720, "Period: 01/01/2024 to 31/01/2024")
    c.drawString(50, 660, "Date")
    c.drawString(120, 660, "Particulars")
    c.drawString(420, 660, "Debit")
    c.drawString(490, 660, "Credit")
    c.drawString(540, 660, "Balance")
    c.line(50, 655, 590, 655)
    c.drawString(50, 640, "01/01/2024")
    c.drawString(120, 640, "Opening Balance")
    c.drawString(420, 640, "0.00")
    c.drawString(490, 640, "10,000.00")
    c.drawString(540, 640, "10,000.00")
    c.showPage()
    c.save()
    return buffer.getvalue()

def test_ambiguous_bank_requires_confirmation_and_select_bank_endpoint():
    """Verifies that an ambiguous statement returns AMBIGUOUS_BANK and requires manual confirmation."""
    amb_bytes = create_synthetic_ambiguous_pdf()
    files = {"file": ("unknown_statement.pdf", amb_bytes, "application/pdf")}
    res = client.post(
        "/api/conversions/upload",
        files=files,
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "AMBIGUOUS_BANK"
    assert data["is_ambiguous"] is True
    job_id = data["id"]

    # User confirms bank as State Bank of India
    confirm_res = client.post(
        f"/api/conversions/{job_id}/select-bank",
        json={"bank_name": "State Bank of India (SBI)"},
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert confirm_res.status_code == 200
    conf_data = confirm_res.json()
    assert conf_data["bank_name"] == "State Bank of India (SBI)"
    assert conf_data["is_ambiguous"] is False
    assert conf_data["confidence_tier"] == "HIGH"

def test_xml_generation_blocked_on_mathematical_mismatch():
    """CRITICAL SECURITY TEST: Blocks XML generation if any transaction is unbalanced."""
    pnb_bytes = create_synthetic_pnb_pdf()
    files = {"file": ("pnb.pdf", pnb_bytes, "application/pdf")}
    res = client.post(
        "/api/conversions/upload",
        files=files,
        headers={"Authorization": "Bearer mock-user-token"}
    )
    job_id = res.json()["id"]

    # Corrupt a transaction in review to induce a mathematical error
    corrupted_txs = res.json()["transactions"]
    corrupted_txs[0]["validation_status"] = "ERROR"
    corrupted_txs[0]["validation_notes"] = "Forced mismatch test"

    client.post(
        f"/api/conversions/{job_id}/review",
        json={"transactions": corrupted_txs},
        headers={"Authorization": "Bearer mock-user-token"}
    )

    # Attempt XML generation -> Must be rejected with HTTP 400 and ERR_MATH_VALIDATION_FAILED
    gen_res = client.post(
        f"/api/conversions/{job_id}/generate",
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert gen_res.status_code == 400
    err_detail = gen_res.json()["detail"]
    assert err_detail["error_code"] == "ERR_MATH_VALIDATION_FAILED"
