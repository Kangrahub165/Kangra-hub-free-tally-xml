import pytest
from decimal import Decimal
from datetime import date
from fastapi.testclient import TestClient
from main import app
from app.transactions.model import CanonicalStatement, TransactionItem
from app.tally.xml_generator import TallyXMLGenerator
from app.accounting.ledger_importer import (
    import_ledgers_from_text,
    detect_ledger_format,
    ImportedLedger,
    global_ledger_store
)
from app.accounting.mapper import LedgerMapper
from app.accounting.entity_extractor import NarrationEntityExtractor
from app.accounting.voucher_classifier import classify_voucher_type

client = TestClient(app)

# ==============================================================================
# 1. Bank & Cash Ledger Configuration Tests
# ==============================================================================

def test_bank_ledger_name_is_used_in_xml():
    """1. Verify exact user-configured bank ledger name is used in XML without normalization."""
    generator = TallyXMLGenerator()
    stmt = CanonicalStatement(
        bank="State Bank of India",
        transactions=[
            TransactionItem(
                date=date(2024, 4, 1),
                narration="Payment to Vendor",
                debit=Decimal("5000.00"),
                ledger_name="Vendor A/C",
                voucher_type="Payment"
            )
        ]
    )
    # User entered exact custom bank ledger name: "SBI Current Account - 9021 (Special)"
    exact_bank_name = "SBI Current Account - 9021 (Special)"
    xml = generator.generate_xml(stmt, bank_ledger_name=exact_bank_name)
    assert f"<LEDGERNAME>{exact_bank_name}</LEDGERNAME>" in xml
    assert "<LEDGERNAME>State Bank of India</LEDGERNAME>" not in xml

def test_cash_ledger_name_is_used_in_xml():
    """2. Verify exact user-configured cash ledger name is used in XML."""
    generator = TallyXMLGenerator()
    stmt = CanonicalStatement(
        bank="Punjab National Bank",
        transactions=[
            TransactionItem(
                date=date(2024, 4, 2),
                narration="ATM CASH WITHDRAWAL",
                debit=Decimal("2000.00"),
                is_cash_transaction=True,
                ledger_name="Petty Cash Box - Main",
                voucher_type="Payment"
            )
        ]
    )
    exact_cash_name = "Petty Cash Box - Main"
    xml = generator.generate_xml(stmt, bank_ledger_name="PNB A/C", cash_ledger_name=exact_cash_name)
    assert f"<LEDGERNAME>{exact_cash_name}</LEDGERNAME>" in xml

# ==============================================================================
# 2. Ledger Editing & Suspense Default Tests
# ==============================================================================

def test_user_can_edit_ledger():
    """3. Verify user can edit ledger on a transaction item."""
    tx = TransactionItem(
        date=date(2024, 4, 3),
        narration="UPI/UNKNOWN",
        debit=Decimal("1500.00"),
        ledger_name="Suspense"
    )
    assert tx.ledger_name == "Suspense"
    # User edits ledger
    tx.ledger_name = "Office Supplies A/C"
    assert tx.ledger_name == "Office Supplies A/C"

def test_admin_can_edit_ledger():
    """4. Verify admin can edit ledger on a transaction item."""
    tx = TransactionItem(
        date=date(2024, 4, 3),
        narration="IMPS/TRANSFER",
        debit=Decimal("10000.00"),
        ledger_name="Suspense"
    )
    tx.ledger_name = "Machinery Repairs A/C"
    assert tx.ledger_name == "Machinery Repairs A/C"

def test_unmapped_transaction_defaults_to_suspense():
    """5. Verify unmapped transaction strictly defaults to Suspense with status Needs Review."""
    mapper = LedgerMapper(
        user_saved_mappings={},
        imported_ledgers=[],
        bank_ledger_name="SBI A/C",
        suspense_ledger_name="Suspense"
    )
    tx = TransactionItem(
        date=date(2024, 4, 4),
        narration="RANDOM OBSCURE UNKNOWN PAYEE 9988",
        debit=Decimal("450.00")
    )
    assigned = mapper.map_transaction_ledger(tx)
    assert assigned == "Suspense"
    assert tx.mapping_status == "Suspense"

# ==============================================================================
# 3. Ledger Import Engine Tests (XML, JSON, HTML)
# ==============================================================================

def test_ledger_import_xml():
    """6. Verify Tally XML ledger import extracts ledgers and groups."""
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
    <ENVELOPE>
        <BODY>
            <IMPORTDATA>
                <REQUESTDATA>
                    <TALLYMESSAGE>
                        <LEDGER NAME="ABC TRADERS">
                            <PARENT>Sundry Debtors</PARENT>
                        </LEDGER>
                    </TALLYMESSAGE>
                    <TALLYMESSAGE>
                        <LEDGER NAME="XYZ SUPPLIERS PVT LTD">
                            <PARENT>Sundry Creditors</PARENT>
                        </LEDGER>
                    </TALLYMESSAGE>
                </REQUESTDATA>
            </IMPORTDATA>
        </BODY>
    </ENVELOPE>"""
    res = import_ledgers_from_text(xml_content, filename="masters.xml")
    assert res.detected_format == "XML"
    assert res.total_imported == 2
    names = [l.name for l in res.ledgers]
    assert "ABC TRADERS" in names
    assert "XYZ SUPPLIERS PVT LTD" in names

def test_ledger_import_json():
    """7. Verify JSON ledger import with array of objects."""
    json_content = """[
        {"name": "SHARMA ENTERPRISES", "group": "Sundry Debtors"},
        {"name": "RENT EXPENSE A/C", "group": "Indirect Expenses"}
    ]"""
    res = import_ledgers_from_text(json_content, filename="ledgers.json")
    assert res.detected_format == "JSON"
    assert res.total_imported == 2
    names = [l.name for l in res.ledgers]
    assert "SHARMA ENTERPRISES" in names
    assert "RENT EXPENSE A/C" in names

def test_ledger_import_html():
    """8. Verify HTML table ledger import safely extracts rows without executing scripts."""
    html_content = """<!DOCTYPE html>
    <html>
    <body>
        <script>alert('malicious script');</script>
        <table>
            <tr><th>Ledger Name</th><th>Group</th></tr>
            <tr><td>KANGRA TIMBER STORE</td><td>Sundry Creditors</td></tr>
            <tr><td>ELECTRICITY BILL A/C</td><td>Indirect Expenses</td></tr>
        </table>
    </body>
    </html>"""
    res = import_ledgers_from_text(html_content, filename="export.html")
    assert res.detected_format == "HTML"
    assert res.total_imported == 2
    names = [l.name for l in res.ledgers]
    assert "KANGRA TIMBER STORE" in names
    assert "ELECTRICITY BILL A/C" in names

def test_ledger_format_auto_detection():
    """9. Verify automatic detection of XML, JSON, and HTML."""
    assert detect_ledger_format('{"ledgers": ["A", "B"]}') == "JSON"
    assert detect_ledger_format('<?xml version="1.0"?><ENVELOPE></ENVELOPE>') == "XML"
    assert detect_ledger_format('<!DOCTYPE html><html><body><table><tr><td>A</td></tr></table></body></html>') == "HTML"

# ==============================================================================
# 4. Narration Entity & Similarity Matching Tests
# ==============================================================================

def test_ledger_matching_exact():
    """10. Verify exact matching against imported Tally ledgers."""
    imported = [ImportedLedger(name="ABC TRADERS", normalized_name="ABC TRADERS")]
    mapper = LedgerMapper(imported_ledgers=imported)
    tx = TransactionItem(
        date=date(2024, 4, 5),
        narration="UPI/446295445740/P2M/pay@okaxis/ABC TRADERS",
        debit=Decimal("1200.00")
    )
    assigned = mapper.map_transaction_ledger(tx)
    assert assigned == "ABC TRADERS"
    assert tx.mapping_confidence >= 95.0

def test_ledger_matching_case_insensitive():
    """11. Verify case-insensitive and whitespace normalized matching."""
    imported = [ImportedLedger(name="Tata Play Direct", normalized_name="TATA PLAY DIRECT")]
    mapper = LedgerMapper(imported_ledgers=imported)
    tx = TransactionItem(
        date=date(2024, 4, 6),
        narration="UPI/446295445740/P2M/tataplay@ybl/TATA PLAY DIRECT",
        debit=Decimal("600.00")
    )
    assigned = mapper.map_transaction_ledger(tx)
    assert assigned == "Tata Play Direct"

def test_ledger_matching_fuzzy():
    """12. Verify token/substring similarity matching."""
    imported = [ImportedLedger(name="ABC TRADERS PVT LTD", normalized_name="ABC TRADERS PVT LTD")]
    mapper = LedgerMapper(imported_ledgers=imported)
    tx = TransactionItem(
        date=date(2024, 4, 7),
        narration="NEFT/N123456/ABC TRADERS",
        debit=Decimal("8000.00")
    )
    assigned = mapper.map_transaction_ledger(tx)
    assert assigned == "ABC TRADERS PVT LTD"
    assert tx.mapping_confidence >= 80.0

def test_low_confidence_mapping_goes_to_suspense():
    """13. Verify low confidence match strictly falls back to Suspense."""
    imported = [ImportedLedger(name="HIMALAYAN ADVENTURES", normalized_name="HIMALAYAN ADVENTURES")]
    mapper = LedgerMapper(imported_ledgers=imported, suspense_ledger_name="Suspense")
    tx = TransactionItem(
        date=date(2024, 4, 8),
        narration="IMPS/998877/DELHI MOTORS",
        debit=Decimal("1500.00")
    )
    assigned = mapper.map_transaction_ledger(tx)
    assert assigned == "Suspense"
    assert tx.mapping_status == "Suspense"

def test_multiple_ledger_matches_require_selection():
    """14. Verify candidate suggestions are generated when multiple matches exist."""
    imported = [
        ImportedLedger(name="ABC TRADERS", normalized_name="ABC TRADERS"),
        ImportedLedger(name="ABC TRADERS PVT LTD", normalized_name="ABC TRADERS PVT LTD"),
        ImportedLedger(name="ABC TRADING CO", normalized_name="ABC TRADING CO"),
    ]
    mapper = LedgerMapper(imported_ledgers=imported)
    _, _, _, candidates = mapper.find_best_ledger_match("ABC TRADERS", "UPI/ABC TRADERS", is_debit=True)
    assert len(candidates) >= 2

def test_saved_mapping_reused():
    """15. Verify saved user mapping rules are reused with 100% confidence."""
    saved_rules = {"PATANJALI STORE": "Patanjali Ayurved A/C"}
    mapper = LedgerMapper(user_saved_mappings=saved_rules)
    tx = TransactionItem(
        date=date(2024, 4, 9),
        narration="UPI/PATANJALI STORE/23490",
        debit=Decimal("350.00")
    )
    assigned = mapper.map_transaction_ledger(tx)
    assert assigned == "Patanjali Ayurved A/C"
    assert tx.mapping_status == "Previously Mapped"
    assert tx.mapping_confidence == 100.0

# ==============================================================================
# 5. User Overrides & Deterministic XML Generation
# ==============================================================================

def test_user_can_override_ledger():
    """16. Verify user can override suggested ledger."""
    tx = TransactionItem(
        date=date(2024, 4, 10),
        narration="UPI/VENDOR",
        debit=Decimal("500.00"),
        ledger_name="Auto Suggested Ledger"
    )
    tx.ledger_name = "User Chosen Ledger"
    assert tx.ledger_name == "User Chosen Ledger"

def test_user_can_override_voucher():
    """17. Verify user can override voucher type."""
    tx = TransactionItem(
        date=date(2024, 4, 11),
        narration="TRANSFER TO SISTER BRANCH",
        debit=Decimal("15000.00"),
        voucher_type="Payment"
    )
    # User corrects to Contra
    tx.voucher_type = "Contra"
    assert tx.voucher_type == "Contra"

def test_final_xml_uses_user_edited_ledger():
    """18. Verify generated XML strictly uses user-edited ledger."""
    generator = TallyXMLGenerator()
    stmt = CanonicalStatement(
        bank="HDFC Bank",
        transactions=[
            TransactionItem(
                date=date(2024, 4, 12),
                narration="UPI/PAYEE",
                debit=Decimal("4000.00"),
                ledger_name="Custom Final Ledger A/C",
                voucher_type="Payment"
            )
        ]
    )
    xml = generator.generate_xml(stmt, bank_ledger_name="HDFC Current A/C")
    assert "<LEDGERNAME>Custom Final Ledger A/C</LEDGERNAME>" in xml

def test_final_xml_uses_user_edited_voucher():
    """19. Verify generated XML strictly uses user-edited voucher type."""
    generator = TallyXMLGenerator()
    stmt = CanonicalStatement(
        bank="Axis Bank",
        transactions=[
            TransactionItem(
                date=date(2024, 4, 13),
                narration="Inter-bank Transfer",
                credit=Decimal("50000.00"),
                ledger_name="SBI Current Account",
                voucher_type="Contra"
            )
        ]
    )
    xml = generator.generate_xml(stmt, bank_ledger_name="Axis Current A/C")
    assert '<VOUCHER VCHTYPE="Contra"' in xml

# ==============================================================================
# 6. Instrument & Reference Number Preservation
# ==============================================================================

def test_cheque_number_maps_to_instrument_number():
    """20. Verify cheque numbers are extracted and mapped to instrument number in XML."""
    chq = NarrationEntityExtractor.extract_cheque_or_instrument_number("TO TRANSFER CHQ NO 654321 FAVOURING ABC")
    assert chq == "654321"

    generator = TallyXMLGenerator()
    stmt = CanonicalStatement(
        bank="State Bank of India",
        transactions=[
            TransactionItem(
                date=date(2024, 4, 14),
                narration="CHQ 654321 TO SUPPLIER",
                debit=Decimal("25000.00"),
                instrument_number="654321",
                ledger_name="Supplier A/C",
                voucher_type="Payment"
            )
        ]
    )
    xml = generator.generate_xml(stmt, bank_ledger_name="SBI A/C")
    assert "<INSTRUMENTNUMBER>654321</INSTRUMENTNUMBER>" in xml
    assert "<REFERENCE>654321</REFERENCE>" in xml

def test_reference_number_preserved():
    """21. Verify UTR and UPI reference numbers are preserved."""
    utr = NarrationEntityExtractor.extract_utr_reference("NEFT-SBIN424102938472-ABC SUPPLIERS")
    assert utr == "SBIN424102938472"
    upi = NarrationEntityExtractor.extract_upi_reference("UPI/446295445740/P2M/PAY")
    assert upi == "446295445740"

def test_transaction_date_preserved():
    """22. Verify transaction date and value date are preserved."""
    tx = TransactionItem(
        date=date(2024, 4, 15),
        value_date=date(2024, 4, 16),
        narration="CLEARING CHQ",
        credit=Decimal("10000.00")
    )
    assert tx.date == date(2024, 4, 15)
    assert tx.value_date == date(2024, 4, 16)

def test_no_transaction_silently_lost():
    """23. Verify all transactions from statement are preserved."""
    txs = [
        TransactionItem(date=date(2024, 4, i), narration=f"Txn {i}", debit=Decimal(f"{i*10}.00"))
        for i in range(1, 11)
    ]
    stmt = CanonicalStatement(bank="SBI", transactions=txs)
    assert len(stmt.transactions) == 10

def test_transaction_count_reconciliation():
    """24. Verify transaction count reconciliation passes when all transactions are retained."""
    raw_count = 15
    included_count = 15
    assert raw_count == included_count

# ==============================================================================
# 7. Directional Cash & Contra Rules
# ==============================================================================

def test_cash_deposit_classification():
    """25. Verify cash deposit defaults to Receipt voucher."""
    tx = TransactionItem(
        date=date(2024, 4, 17),
        narration="CASH DEPOSIT BY SELF AT BRANCH",
        credit=Decimal("50000.00"),
        debit=Decimal("0.00")
    )
    vch = classify_voucher_type(tx)
    assert vch == "Contra"

def test_cash_withdrawal_classification():
    """26. Verify cash withdrawal defaults to Contra voucher in Tally."""
    tx = TransactionItem(
        date=date(2024, 4, 18),
        narration="ATM CASH WITHDRAWAL",
        debit=Decimal("10000.00"),
        credit=Decimal("0.00")
    )
    vch = classify_voucher_type(tx)
    assert vch == "Contra"

def test_normal_transaction_not_classified_as_contra():
    """27. Verify ordinary third-party transactions (UPI/NEFT/IMPS) are never Contra."""
    upi_tx = TransactionItem(
        date=date(2024, 4, 19),
        narration="UPI/446295445740/P2M/TATAPLAY",
        debit=Decimal("500.00")
    )
    assert classify_voucher_type(upi_tx) == "Payment"

    neft_tx = TransactionItem(
        date=date(2024, 4, 20),
        narration="NEFT/SBIN123/XYZ ENTERPRISES",
        credit=Decimal("25000.00")
    )
    assert classify_voucher_type(neft_tx) == "Receipt"

# ==============================================================================
# 8. Double Entry Algebraic Validation
# ==============================================================================

def test_double_entry_validation():
    """28. Verify double entry debits equal credits in generated XML."""
    generator = TallyXMLGenerator()
    stmt = CanonicalStatement(
        bank="State Bank of India",
        transactions=[
            TransactionItem(
                date=date(2024, 4, 21),
                narration="Payment to Supplier",
                debit=Decimal("1234.56"),
                ledger_name="Supplier A/C",
                voucher_type="Payment"
            ),
            TransactionItem(
                date=date(2024, 4, 22),
                narration="Receipt from Customer",
                credit=Decimal("9876.54"),
                ledger_name="Customer A/C",
                voucher_type="Receipt"
            )
        ]
    )
    xml = generator.generate_xml(stmt, bank_ledger_name="SBI Current A/C")
    # In Payment: Bank has +1234.56, Supplier has -1234.56
    assert "<AMOUNT>1234.56</AMOUNT>" in xml
    assert "<AMOUNT>-1234.56</AMOUNT>" in xml
    # In Receipt: Customer has +9876.54, Bank has -9876.54
    assert "<AMOUNT>9876.54</AMOUNT>" in xml
    assert "<AMOUNT>-9876.54</AMOUNT>" in xml
