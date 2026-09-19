import pytest
from datetime import date
from decimal import Decimal
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.pdf.extractor import ExtractedDocument, ExtractedPage
from app.detector.bank_detector import detect_bank_from_document
from app.transactions.model import CanonicalStatement, TransactionItem
from app.transactions.validator import validate_statement_balances
from app.accounting.voucher_classifier import classify_voucher_type

def test_bank_detector_matches_pnb():
    page = ExtractedPage(
        page_number=1,
        text="PUNJAB NATIONAL BANK\nBranch: NAGROTA SURIAN\nAccount Number : 0033000100123456\nCustomer Name: Kangra Hub",
        lines=["PUNJAB NATIONAL BANK", "Account Number : 0033000100123456"]
    )
    doc = ExtractedDocument(pages=[page])
    result = detect_bank_from_document(doc)
    assert "Punjab National Bank" in result.bank_name
    assert result.parser_key == "pnb_standard"
    assert result.confidence >= 80.0
    assert result.account_number_masked == "XXXX3456"

def test_bank_detector_matches_sbi():
    page = ExtractedPage(
        page_number=1,
        text="STATE BANK OF INDIA\ne-Statement for Account Number: 12345678901\nIFS Code: SBIN0001234",
        lines=["STATE BANK OF INDIA", "Account Number: 12345678901"]
    )
    doc = ExtractedDocument(pages=[page])
    result = detect_bank_from_document(doc)
    assert "State Bank of India" in result.bank_name
    assert result.parser_key == "sbi_standard"

def test_running_balance_validation_pass():
    statement = CanonicalStatement(
        bank="PNB",
        opening_balance=Decimal("50000.00"),
        transactions=[
            TransactionItem(
                date=date(2026, 4, 1),
                narration="Debit purchase",
                debit=Decimal("5000.00"),
                credit=Decimal("0.00"),
                balance=Decimal("45000.00")
            ),
            TransactionItem(
                date=date(2026, 4, 2),
                narration="Salary credit",
                debit=Decimal("0.00"),
                credit=Decimal("10000.00"),
                balance=Decimal("55000.00")
            )
        ]
    )
    validated = validate_statement_balances(statement)
    assert validated.confidence_score == 100.0
    assert all(tx.validation_status == "VALID" for tx in validated.transactions)

def test_running_balance_validation_mismatch():
    statement = CanonicalStatement(
        bank="PNB",
        opening_balance=Decimal("50000.00"),
        transactions=[
            TransactionItem(
                date=date(2026, 4, 1),
                narration="Incorrect math row",
                debit=Decimal("5000.00"),
                credit=Decimal("0.00"),
                balance=Decimal("40000.00")  # Should be 45,000!
            )
        ]
    )
    validated = validate_statement_balances(statement)
    assert validated.confidence_score < 100.0
    assert validated.transactions[0].validation_status in ["WARNING", "ERROR"]

def test_voucher_classification():
    cash_dep_tx = TransactionItem(
        date=date(2026, 4, 1),
        narration="Cash Deposit At Branch",
        credit=Decimal("5000.00"),
        ledger_name="Cash",
        is_cash_transaction=True
    )
    # Cash deposit to bank is Contra
    assert classify_voucher_type(cash_dep_tx) == "Contra"

    internal_transfer_tx = TransactionItem(
        date=date(2026, 4, 1),
        narration="Internal Transfer between accounts",
        credit=Decimal("5000.00"),
        ledger_name="SBI Current A/C"
    )
    # Internal transfer -> Contra
    assert classify_voucher_type(internal_transfer_tx) == "Contra"

    payment_tx = TransactionItem(
        date=date(2026, 4, 1),
        narration="UPI to Vendor ABC",
        debit=Decimal("1200.00"),
        ledger_name="Vendor ABC"
    )
    assert classify_voucher_type(payment_tx) == "Payment"

    receipt_tx = TransactionItem(
        date=date(2026, 4, 1),
        narration="Client NEFT Payment Received",
        credit=Decimal("8000.00"),
        ledger_name="Client Corp"
    )
    assert classify_voucher_type(receipt_tx) == "Receipt"
