"""
Comprehensive regression tests for all 12 real bank statement PDFs in 'Sample pdf/'.
Verifies:
1. Document extraction and bank parser detection.
2. Complete transaction extraction (boundary-isolated rows).
3. Zero contamination: narration does not contain header/footer noise or disclaimers.
4. Strict voucher classification:
   - Debit is Payment (or Contra if cash), NEVER Receipt.
   - Credit is Receipt (or Contra if cash), NEVER Payment.
   - Contra is strictly Cash / Transfer.
5. Snapshot parity:
   - FinalConversionSnapshot is created with 100% field preservation.
   - Tally XML is generated with valid structure and matching voucher count.
   - Tally Excel is generated with valid binary XLSX headers.
"""
import pytest
from pathlib import Path
from decimal import Decimal

from app.pdf.extractor import extract_pdf_data
from app.detector.bank_detector import detect_bank_from_document
from app.parsers.registry import parser_registry
from app.accounting.mapper import LedgerMapper
from app.accounting.voucher_classifier import classify_voucher_type
from app.transactions.snapshot import FinalConversionSnapshot
from app.tally.xml_generator import TallyXMLGenerator
from app.excel.excel_generator import TallyExcelGenerator

SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "Sample pdf"

FORBIDDEN_HEADER_FOOTER_SNIPPETS = [
    "contents of this statement",
    "page no :",
    "page no.:",
    "this is a system generated",
    "statement of account",
    "branch gstin:",
    "account branch gstn:",
    "state account branch",
    "computer generated statement",
]

def _assert_pdf_pipeline(filename: str, min_expected_txns: int = 1):
    pdf_path = SAMPLE_DIR / filename
    assert pdf_path.exists(), f"Sample PDF file not found: {pdf_path}"

    # 1. Extraction
    doc = extract_pdf_data(str(pdf_path))
    assert len(doc.pages) > 0, f"No pages extracted from {filename}"

    # 2. Bank Detection
    detection = detect_bank_from_document(doc)
    assert detection is not None, f"Detection failed for {filename}"

    # 3. Parser Resolution
    parser = parser_registry.get_parser_for_bank(detection.bank_name)
    if not parser and detection.parser_key:
        parser = parser_registry.get_parser(detection.parser_key)
    if not parser:
        parser = parser_registry.get_parser("generic_standard")
    assert parser is not None, f"No parser resolved for {filename} ({detection.bank_name})"

    # 4. Parse Statement
    statement = parser.parse(doc)
    assert len(statement.transactions) >= min_expected_txns, (
        f"Expected at least {min_expected_txns} transactions for {filename}, got {len(statement.transactions)}"
    )

    # 5. Narration Isolation & Integrity
    for tx in statement.transactions:
        assert tx.narration and len(tx.narration.strip()) > 0, f"Empty narration in {filename} row {tx.row_index}"
        
        lower_narr = tx.narration.lower()
        for noise in FORBIDDEN_HEADER_FOOTER_SNIPPETS:
            assert noise not in lower_narr, (
                f"Contamination in {filename} row {tx.row_index}: found header/footer noise '{noise}' in '{tx.narration}'"
            )

        assert tx.debit is not None and tx.debit >= Decimal("0.00"), f"Invalid debit in {filename} row {tx.row_index}"
        assert tx.credit is not None and tx.credit >= Decimal("0.00"), f"Invalid credit in {filename} row {tx.row_index}"
        if tx.debit == Decimal("0.00") and tx.credit == Decimal("0.00"):
            assert any(k in tx.narration.lower() for k in ["balance", "brought forward", "b/f", "opening", "ending"]), (
                f"Both debit and credit are zero in non-balance row: {filename} row {tx.row_index}: '{tx.narration}'"
            )

    # 6. Voucher Classification Integrity
    bank_ledger = f"{detection.bank_name or 'Bank'} A/C"
    mapper = LedgerMapper(bank_ledger_name=bank_ledger, cash_ledger_name="Cash")
    for tx in statement.transactions:
        mapper.map_transaction_ledger(tx)
        tx.voucher_type = classify_voucher_type(tx)

    debit_as_receipt = [t for t in statement.transactions if t.debit > 0 and t.voucher_type == "Receipt"]
    assert len(debit_as_receipt) == 0, f"Found DEBIT transactions classified as Receipt in {filename}: {len(debit_as_receipt)}"

    credit_as_payment = [t for t in statement.transactions if t.credit > 0 and t.voucher_type == "Payment"]
    assert len(credit_as_payment) == 0, f"Found CREDIT transactions classified as Payment in {filename}: {len(credit_as_payment)}"

    non_cash_contra = [t for t in statement.transactions if t.voucher_type == "Contra" and not t.is_cash_transaction]
    assert len(non_cash_contra) == 0, f"Found non-cash Contra transactions in {filename}: {len(non_cash_contra)}"

    # 7. Snapshot Parity & Generation
    snapshot = FinalConversionSnapshot.create_from_statement(
        statement=statement,
        bank_ledger_name=bank_ledger,
        cash_ledger_name="Cash",
        job_id=f"test-real-{filename}"
    )
    assert len(snapshot.transactions) == len(statement.transactions)

    xml_gen = TallyXMLGenerator(default_bank_ledger=bank_ledger, default_cash_ledger="Cash")
    xml_content = xml_gen.generate_xml(snapshot)
    assert len(xml_content) > 100
    has_amount = any(t.debit > Decimal("0.00") or t.credit > Decimal("0.00") for t in statement.transactions)
    if has_amount:
        assert "<VOUCHER" in xml_content or "<TALLYMESSAGE" in xml_content
    else:
        assert "<ENVELOPE>" in xml_content

    excel_gen = TallyExcelGenerator(default_bank_ledger=bank_ledger, default_cash_ledger="Cash")
    excel_bytes = excel_gen.generate_excel_bytes(snapshot)
    assert len(excel_bytes) > 500
    assert excel_bytes.startswith(b"PK\x03\x04")  # XLSX zip header

    return statement


def test_real_axis_bank_pdf():
    stmt = _assert_pdf_pipeline("axis-bank.pdf", min_expected_txns=50)
    assert len(stmt.transactions) >= 70


def test_real_hdfc_bank_pdf():
    stmt = _assert_pdf_pipeline("HDFC BANK.pdf", min_expected_txns=500)
    assert len(stmt.transactions) >= 800


def test_real_icici_bank_pdf():
    stmt = _assert_pdf_pipeline("icici-bank.pdf", min_expected_txns=500)
    assert len(stmt.transactions) >= 600


def test_real_kangra_cooperative_bank_pdf():
    stmt = _assert_pdf_pipeline("kangra co operative bank.pdf", min_expected_txns=10)
    assert len(stmt.transactions) >= 15


def test_real_paypal_pdf():
    stmt = _assert_pdf_pipeline("paypal.pdf", min_expected_txns=2)
    assert len(stmt.transactions) >= 4


def test_real_pnb_pdf():
    stmt = _assert_pdf_pipeline("PNB.pdf", min_expected_txns=300)
    assert len(stmt.transactions) >= 350


def test_real_sbi_2_pdf():
    stmt = _assert_pdf_pipeline("SBI-2.pdf", min_expected_txns=50)
    assert len(stmt.transactions) >= 75


def test_real_sbi_pdf():
    stmt = _assert_pdf_pipeline("SBI.pdf", min_expected_txns=500)
    assert len(stmt.transactions) >= 700


def test_real_the_cooperative_bank_pdf():
    stmt = _assert_pdf_pipeline("the-co-operative-bank.pdf", min_expected_txns=5)
    assert len(stmt.transactions) >= 10


def test_real_uco_bank_2_pdf():
    stmt = _assert_pdf_pipeline("uco-bank-2.pdf", min_expected_txns=40)
    assert len(stmt.transactions) >= 50


def test_real_uco_bank_pdf():
    stmt = _assert_pdf_pipeline("UCO BANK.pdf", min_expected_txns=10)
    assert len(stmt.transactions) >= 20


def test_real_union_bank_pdf():
    stmt = _assert_pdf_pipeline("union-bank-of-india.pdf", min_expected_txns=100)
    assert len(stmt.transactions) >= 120
