import pytest
from datetime import date
from decimal import Decimal
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.transactions.model import CanonicalStatement, TransactionItem
from app.tally.xml_generator import TallyXMLGenerator
from app.tally.xml_validator import validate_tally_xml

def test_tally_xml_matches_sample_spec():
    statement = CanonicalStatement(
        bank="Punjab National Bank (PNB)",
        statement_from=date(2024, 4, 2),
        statement_to=date(2024, 4, 4),
        transactions=[
            TransactionItem(
                date=date(2024, 4, 2),
                narration="APY CONTRI:01-04-2024 to 30-06-2024",
                debit=Decimal("3928.00"),
                credit=Decimal("0.00"),
                ledger_name="Cash",
                voucher_type="Payment"
            ),
            TransactionItem(
                date=date(2024, 4, 4),
                narration="UPI/446130236270/P2V/9418250639@ybl/RAKESH KUMAR S",
                debit=Decimal("0.00"),
                credit=Decimal("3500.00"),
                ledger_name="Cash",
                voucher_type="Receipt"
            ),
            TransactionItem(
                date=date(2024, 6, 26),
                narration="Cash Deposit At : NAGROTA SURIAN(DISTT. KANGRA)",
                debit=Decimal("0.00"),
                credit=Decimal("5500.00"),
                ledger_name="Cash",
                voucher_type="Contra"
            )
        ]
    )

    generator = TallyXMLGenerator(default_bank_ledger="PNB SAVING A/C 0033")
    xml_output = generator.generate_xml(statement)

    # 1. Structural tags check
    assert '<?xml version="1.0" encoding="utf-8"?>' in xml_output
    assert '<ENVELOPE>' in xml_output
    assert '<TALLYREQUEST>Import Data</TALLYREQUEST>' in xml_output
    assert '<REPORTNAME>All Masters</REPORTNAME>' in xml_output
    assert '<REQUESTDATA>' in xml_output

    # 2. Date format check YYYYMMDD
    assert '<DATE>20240402</DATE>' in xml_output
    assert '<DATE>20240404</DATE>' in xml_output

    # 3. Voucher tags & ledger signs check
    assert '<VOUCHER VCHTYPE="Payment" ACTION="Create" OBJVIEW="Accounting Voucher View">' in xml_output
    assert '<VOUCHER VCHTYPE="Receipt" ACTION="Create" OBJVIEW="Accounting Voucher View">' in xml_output
    assert '<VOUCHER VCHTYPE="Contra" ACTION="Create" OBJVIEW="Accounting Voucher View">' in xml_output

    # 4. XML validation check
    is_valid, errors = validate_tally_xml(xml_output)
    assert is_valid is True, f"XML validation errors: {errors}"
    assert len(errors) == 0

def test_xml_escaping_special_chars():
    statement = CanonicalStatement(
        bank="HDFC Bank",
        transactions=[
            TransactionItem(
                date=date(2026, 4, 1),
                narration="Payment for M/S ABC & Sons <Electronics> 'Discount' \"Special\"",
                debit=Decimal("1500.00"),
                ledger_name="ABC & Sons",
                voucher_type="Payment"
            )
        ]
    )
    generator = TallyXMLGenerator(default_bank_ledger="HDFC Bank")
    xml_output = generator.generate_xml(statement)

    # Must be escaped
    assert "ABC &amp; Sons" in xml_output
    assert "&lt;Electronics&gt;" in xml_output

    is_valid, errors = validate_tally_xml(xml_output)
    assert is_valid is True, f"XML escaping broke validation: {errors}"
