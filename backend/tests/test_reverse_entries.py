import pytest
from datetime import date
from decimal import Decimal
from app.transactions.model import CanonicalStatement, TransactionItem
from app.accounting.reversal_detector import (
    ReversalDetector,
    detect_reversal_in_narration,
    extract_reference_numbers
)
from app.tally.xml_generator import TallyXMLGenerator
from app.tally.xml_validator import validate_tally_xml

def test_01_extract_reference_numbers():
    assert "457583" in extract_reference_numbers("REJECT:457583:FUNDS INSUFFICIENT")
    assert "457583" in extract_reference_numbers("BY INST 457583 : CTO610-1 LATENCY")
    assert "457583" in extract_reference_numbers("OW CHQ : 457583 REJ")
    assert "YESBN12025070301487305" in extract_reference_numbers("NEFT/YESBN12025070301487305/PHONEPE LIMITED")

def test_02_detect_reversal_keywords():
    hint1 = detect_reversal_in_narration("REJECT:457583:FUNDS INSUFFICIENT")
    assert hint1 is not None
    assert "Funds insufficient" in hint1[1] or "Cheque rejected" in hint1[1]

    hint2 = detect_reversal_in_narration("UPI REVERSAL TO ACC 1234")
    assert hint2 is not None
    assert "Online transfer failure" in hint2[1]

    hint3 = detect_reversal_in_narration("NORMAL PAYMENT TO VENDOR")
    assert hint3 is None

def test_03_reversal_pairing_same_date():
    tx1 = TransactionItem(
        row_index=1,
        date=date(2025, 7, 2),
        narration="BY INST 457583 : CTO610-1 LATENCY",
        credit=Decimal("13895.00"),
        debit=Decimal("0.00")
    )
    tx2 = TransactionItem(
        row_index=2,
        date=date(2025, 7, 2),
        narration="REJECT:457583:FUNDS INSUFFICIENT",
        debit=Decimal("13895.00"),
        credit=Decimal("0.00")
    )
    statement = CanonicalStatement(
        bank="Punjab National Bank",
        transactions=[tx1, tx2]
    )

    detector = ReversalDetector()
    metrics = detector.process_statement(statement)

    assert metrics["pairs_count"] == 1
    assert metrics["net_total"] == Decimal("0.00")
    assert tx1.is_reverse_entry is True
    assert tx2.is_reverse_entry is True
    assert tx1.ledger_name == "Reverse Entries"
    assert tx2.ledger_name == "Reverse Entries"
    assert tx1.reversal_pair_id == tx2.reversal_pair_id
    assert tx1.mapping_status == "Mapped"
    assert tx2.mapping_status == "Mapped"

def test_04_rejection_charges_isolation_section_11_4():
    # OW CHQ : 457583 REJ for 236.00 must go to Bank Charges, NOT Reverse Entries!
    tx_charge = TransactionItem(
        row_index=1,
        date=date(2025, 7, 2),
        narration="OW CHQ : 457583 REJ",
        debit=Decimal("236.00"),
        credit=Decimal("0.00")
    )
    tx_rev1 = TransactionItem(
        row_index=2,
        date=date(2025, 7, 2),
        narration="REJECT:457583:FUNDS INSUFFICIENT",
        debit=Decimal("13895.00"),
        credit=Decimal("0.00")
    )
    tx_rev2 = TransactionItem(
        row_index=3,
        date=date(2025, 7, 2),
        narration="BY INST 457583 : CTO610-1 LATENCY",
        credit=Decimal("13895.00"),
        debit=Decimal("0.00")
    )
    statement = CanonicalStatement(
        bank="Punjab National Bank",
        transactions=[tx_charge, tx_rev1, tx_rev2]
    )

    detector = ReversalDetector()
    metrics = detector.process_statement(statement)

    assert metrics["pairs_count"] == 1
    # Return charge MUST go to Bank Charges
    assert tx_charge.ledger_name == "Bank Charges"
    assert tx_charge.is_reverse_entry is False
    assert tx_charge.linked_reversal_ref == "457583"
    assert tx_charge.mapping_status == "Mapped"

    # Reversal pair MUST go to Reverse Entries
    assert tx_rev1.ledger_name == "Reverse Entries"
    assert tx_rev2.ledger_name == "Reverse Entries"
    assert tx_rev1.is_reverse_entry is True
    assert tx_rev2.is_reverse_entry is True
    assert tx_rev1.reversal_pair_id == tx_rev2.reversal_pair_id

def test_05_owner_pnb_finacle_sample_regression_section_11_6():
    """
    PRD Section 11.6 exact regression test for PNB Finacle sample:
    7 rows from 01-07-2025 to 03-07-2025.
    """
    rows = [
        TransactionItem(
            row_index=1,
            date=date(2025, 7, 3),
            narration="NEFT/YESBN12025070301487305/PHONEPE LIMITED FOR PH",
            debit=Decimal("3997.00"),
            credit=Decimal("0.00"),
            balance=Decimal("1453239.36")
        ),
        TransactionItem(
            row_index=2,
            date=date(2025, 7, 2),
            narration="OW CHQ : 457583 REJ",
            debit=Decimal("236.00"),
            credit=Decimal("0.00"),
            balance=Decimal("1457236.36")
        ),
        TransactionItem(
            row_index=3,
            date=date(2025, 7, 2),
            narration="REJECT:457583:FUNDS INSUFFICIENT",
            debit=Decimal("13895.00"),
            credit=Decimal("0.00"),
            balance=Decimal("1457000.36")
        ),
        TransactionItem(
            row_index=4,
            date=date(2025, 7, 2),
            narration="BY INST 457583 : CTO610-1 LATENCY",
            debit=Decimal("0.00"),
            credit=Decimal("13895.00"),
            balance=Decimal("1443105.36")
        ),
        TransactionItem(
            row_index=5,
            date=date(2025, 7, 2),
            narration="BY INST 306332 : CTO610-1 LATENCY",
            debit=Decimal("0.00"),
            credit=Decimal("6055.00"),
            balance=Decimal("1457000.36")
        ),
        TransactionItem(
            row_index=6,
            date=date(2025, 7, 2),
            narration="NEFT/YESBN12025070200964418/PHONEPE LIMITED FOR PH",
            debit=Decimal("11202.18"),
            credit=Decimal("0.00"),
            balance=Decimal("1463055.36")
        ),
        TransactionItem(
            row_index=7,
            date=date(2025, 7, 1),
            narration="BY INST 53010 : CTO610-1 LATENCY",
            debit=Decimal("0.00"),
            credit=Decimal("18490.00"),
            balance=Decimal("1474257.54")
        )
    ]
    statement = CanonicalStatement(
        bank="Punjab National Bank",
        statement_format="PNB_Finacle",
        transactions=rows
    )

    detector = ReversalDetector()
    summary = detector.process_statement(statement)

    # 1. Verification of reversal pair
    assert summary["pairs_count"] == 1
    assert rows[2].is_reverse_entry is True
    assert rows[3].is_reverse_entry is True
    assert rows[2].ledger_name == "Reverse Entries"
    assert rows[3].ledger_name == "Reverse Entries"
    assert rows[2].reversal_pair_id == rows[3].reversal_pair_id
    assert summary["net_total"] == Decimal("0.00")

    # 2. Verification of return charge mapping to Bank Charges
    assert rows[1].ledger_name == "Bank Charges"
    assert rows[1].is_reverse_entry is False
    assert rows[1].linked_reversal_ref == "457583"
    assert rows[1].mapping_status == "Mapped"

    # 3. Non-reversal rows remain clean
    assert rows[0].is_reverse_entry is False
    assert rows[4].is_reverse_entry is False
    assert rows[5].is_reverse_entry is False
    assert rows[6].is_reverse_entry is False

def test_06_unpaired_reversal_row_section_11_3():
    tx_unpaired = TransactionItem(
        row_index=1,
        date=date(2025, 7, 2),
        narration="NEFT RETURN UTR 999888777 BENEFICIARY ACCOUNT CLOSED",
        debit=Decimal("0.00"),
        credit=Decimal("5000.00")
    )
    statement = CanonicalStatement(
        bank="HDFC Bank",
        transactions=[tx_unpaired]
    )

    detector = ReversalDetector()
    summary = detector.process_statement(statement)

    assert summary["pairs_count"] == 0
    assert summary["unmatched_count"] == 1
    assert tx_unpaired.is_reverse_entry is True
    assert tx_unpaired.ledger_name == "Reverse Entries"
    assert tx_unpaired.mapping_status == "Requires Review"
    assert "original entry not in this statement" in tx_unpaired.validation_notes

def test_07_tally_xml_auto_creates_reverse_entries_ledger():
    tx1 = TransactionItem(
        row_index=1,
        date=date(2025, 7, 2),
        narration="BY INST 457583 : CTO610-1 LATENCY",
        credit=Decimal("13895.00"),
        debit=Decimal("0.00")
    )
    tx2 = TransactionItem(
        row_index=2,
        date=date(2025, 7, 2),
        narration="REJECT:457583:FUNDS INSUFFICIENT",
        debit=Decimal("13895.00"),
        credit=Decimal("0.00")
    )
    statement = CanonicalStatement(
        bank="Punjab National Bank",
        transactions=[tx1, tx2]
    )

    detector = ReversalDetector()
    detector.process_statement(statement)

    xml_gen = TallyXMLGenerator(default_bank_ledger="PNB Current A/c")
    xml_output = xml_gen.generate_xml(statement)

    # Verify that ledger master for Reverse Entries is auto-generated under Suspense A/c
    assert '<LEDGER NAME="Reverse Entries" ACTION="Create">' in xml_output
    assert '<NAME>Reverse Entries</NAME>' in xml_output
    assert '<PARENT>Suspense A/c</PARENT>' in xml_output

    # Validate generated XML syntax and double-entry balancing
    is_valid, errors = validate_tally_xml(xml_output)
    assert is_valid is True, f"XML validation failed: {errors}"
    assert len(errors) == 0
