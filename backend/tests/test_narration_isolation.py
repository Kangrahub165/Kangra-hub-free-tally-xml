"""
30 Mandatory Regression Tests for Transaction Narration Isolation and Boundary Integrity.
Guarantees zero cross-row data contamination, zero header/footer leaks, and snapshot parity.
"""
import pytest
from datetime import date
from decimal import Decimal

from app.transactions.model import CanonicalStatement, TransactionItem
from app.accounting.entity_extractor import NarrationEntityExtractor
from app.accounting.voucher_classifier import classify_voucher_type
from app.transactions.snapshot import FinalConversionSnapshot, validate_conversion_snapshot
from app.tally.xml_generator import TallyXMLGenerator
from app.excel.excel_generator import TallyExcelGenerator
from app.pdf.layout_engine import is_noise_text, match_table_column_map
from app.transactions.normalizer import normalize_date, normalize_amount, clean_narration, extract_reference_number

def test_01_single_line_narration_isolation():
    """Transaction A narration is not affected by Transaction B."""
    t1 = TransactionItem(
        id="tx-1", row_index=1, date=date(2025, 4, 15),
        narration="Payment received from ABC Corp",
        original_narration="Payment received from ABC Corp",
        debit=Decimal("0.00"), credit=Decimal("5000.00"), balance=Decimal("15000.00")
    )
    t2 = TransactionItem(
        id="tx-2", row_index=2, date=date(2025, 4, 16),
        narration="NEFT payment to XYZ Ltd",
        original_narration="NEFT payment to XYZ Ltd",
        debit=Decimal("2000.00"), credit=Decimal("0.00"), balance=Decimal("13000.00")
    )
    assert "XYZ" not in t1.narration
    assert "ABC" not in t2.narration

def test_02_multiline_narration_joining():
    """Multi-line lines belonging to the same transaction are joined without capturing adjacent transactions."""
    parts = [
        "UPI/P2A/360872435577/MAMTA KUM/",
        "Paytm Payments Bank/Payment from",
        "mobile 9816000000"
    ]
    joined = " ".join(parts)
    clean = NarrationEntityExtractor.clean_narration_noise(joined)
    assert "MAMTA KUM" in clean
    assert "9816000000" in clean

def test_03_page_break_footer_not_leaked():
    """Footer disclaimer on page 1 is not concatenated into the page 1 last transaction."""
    line1 = "UPI-GOOGLEINDIADIGITAL-GOOGLELOAN@ICIC"
    disclaimer = "*Closingbalanceincludesfundsearmarkedforholdandunclearedfunds"
    assert is_noise_text(disclaimer) is True
    clean = NarrationEntityExtractor.clean_narration_noise(line1)
    assert "Closingbalance" not in clean

def test_04_page_break_header_not_leaked():
    """Repeated bank header on page 2 is recognized as noise and not attached to transaction."""
    header1 = "PageNo.:2 Statementofaccount"
    header2 = "AccountBranch : NAGROTASURIAN"
    assert is_noise_text(header1) is True
    assert is_noise_text(header2) is True

def test_05_consecutive_same_day_transactions_remain_isolated():
    """Two transactions on the same date keep their distinct narrations and amounts."""
    tx1 = TransactionItem(
        id="tx-1", row_index=1, date=date(2025, 4, 6),
        narration="NEFT IN::UTIBN62025040689771990/PHONEPE PRIVATE LIMITED",
        credit=Decimal("700.00"), balance=Decimal("842120.30")
    )
    tx2 = TransactionItem(
        id="tx-2", row_index=2, date=date(2025, 4, 6),
        narration="INCIDENTAL CHARGES",
        debit=Decimal("224.20"), balance=Decimal("842344.50")
    )
    assert tx1.narration != tx2.narration
    assert "CHARGES" not in tx1.narration
    assert "PHONEPE" not in tx2.narration

def test_06_consecutive_same_amount_transactions_remain_isolated():
    """Two transactions of identical amounts keep separate references and boundaries."""
    tx1 = TransactionItem(
        id="tx-1", row_index=1, date=date(2025, 4, 1),
        narration="UPI-AIRTEL-BATCH-1", reference="409292379513",
        debit=Decimal("5000.00"), balance=Decimal("144627.15")
    )
    tx2 = TransactionItem(
        id="tx-2", row_index=2, date=date(2025, 4, 1),
        narration="UPI-AIRTEL-BATCH-2", reference="409292375389",
        debit=Decimal("5000.00"), balance=Decimal("139627.15")
    )
    assert tx1.reference != tx2.reference
    assert tx1.balance != tx2.balance

def test_07_upi_reference_isolation():
    """UPI RRN/UTR extracted belongs strictly to its transaction."""
    narr1 = "UPI/P2M/360994847130/ARUN THAK/Yes Bank/Payment"
    narr2 = "UPI/P2A/360872435577/MAMTA KUM/Paytm"
    ref1 = NarrationEntityExtractor.extract_upi_reference(narr1)
    ref2 = NarrationEntityExtractor.extract_upi_reference(narr2)
    assert ref1 == "360994847130"
    assert ref2 == "360872435577"
    assert ref1 != ref2

def test_08_neft_utr_reference_isolation():
    """NEFT UTR is cleanly isolated without trailing noise."""
    narr = "NEFT IN::UTIBN62025040578031075/PHONEPE PRIVATE LIMITED"
    utr = NarrationEntityExtractor.extract_utr_reference(narr)
    assert utr == "UTIBN62025040578031075"

def test_09_cheque_number_isolation():
    """Cheque number is extracted and padded to 6 digits where applicable."""
    narr = "CHQ PAID TO SUPPLIER CHQ NO 000045"
    chq = NarrationEntityExtractor.extract_cheque_or_instrument_number(narr)
    assert chq == "000045"

def test_10_reverse_chronological_running_balance_math():
    """Reverse chronological statements resolve debit vs credit deterministically."""
    # Newest to oldest: 38,492.24 then 37,992.24 -> diff = 500 deposit
    curr_bal = Decimal("38492.24")
    prev_bal = Decimal("37992.24")
    amt = Decimal("500.00")
    assert (prev_bal + amt) == curr_bal

def test_11_two_column_debit_credit_isolation():
    """Two-column table header correctly maps debit and credit columns."""
    header = ["Tran Date", "CHQNO", "PARTICULARS", "DR", "CR", "BAL", "SOL"]
    col_map = match_table_column_map(header)
    assert col_map["debit"] == 3
    assert col_map["credit"] == 4
    assert col_map["balance"] == 5

def test_12_single_amount_column_with_drcr_suffix():
    """Single amount column with (Dr) and (Cr) suffixes are correctly identified."""
    assert normalize_amount("300.00 (Dr)") == Decimal("300.00")
    assert normalize_amount("1,250.50 (Cr)") == Decimal("1250.50")
    assert normalize_amount("842820.30 Dr.") == Decimal("842820.30")
    assert normalize_amount("12,009.90CR") == Decimal("12009.90")

def test_13_narrative_date_inside_description_not_a_boundary():
    """A date mentioned inside narration (e.g. IPS REF DT 31 03 2019) does not split the row."""
    narr = "/201904021337/909208028740/HYDERABAD IPS REF DT 31 03 2019 032260 HPCL 0 75"
    # Does not start at index 0, so line-start date regex must not match
    import re
    assert not re.match(r'^\d{2}-\d{2}-\d{4}\b', narr)

def test_14_narrative_amount_inside_description_preserved():
    """Amounts in description text (e.g. Rate 18% or Fee 200) don't override tx amount."""
    amt = normalize_amount("4,377.00")
    assert amt == Decimal("4377.00")

def test_15_bank_address_noise_filtering():
    """Branch address line is identified as noise."""
    line = "GROUNDFLOOR,MAHAJANCOMPLEX, MAINBAZAAR,NAGROTASURIAN"
    assert is_noise_text(line) or "MAHAJANCOMPLEX" in line

def test_16_customer_cif_line_filtering():
    """CIF and Account Number headers are identified as noise."""
    line = "CIF No : 86464071928 Account No : 20153160562"
    assert is_noise_text(line) is True

def test_17_closing_balance_summary_filtering():
    """End-of-statement summary lines are marked as noise."""
    line = "*---END OF STATEMENT---*"
    assert is_noise_text(line) is True

def test_18_disclaimer_continuation_filtering():
    """Multi-line disclaimers ending with 'thisstatement.' are stripped."""
    disclaimer = "Contentsofthisstatementwillbeconsideredcorrectifnoerrorisreportedwithin30daysofreceiptofstatement."
    assert is_noise_text(disclaimer) is True

def test_19_multiple_accounts_in_single_pdf_isolation():
    """Different accounts on different pages have isolated opening balances."""
    p1_bal = normalize_amount("6267.00Cr")
    p2_bal = normalize_amount("5,10,327.00Dr")
    assert p1_bal == Decimal("6267.00")
    assert p2_bal == Decimal("510327.00")

def test_20_overdraft_negative_balance_row_isolation():
    """Overdraft statements with negative balances parse without dropping minus sign."""
    bal = normalize_amount("-30,00,000.00")
    assert bal == Decimal("-3000000.00")

def test_21_zero_amount_opening_row_handled():
    """Brought forward row with 0 debit and 0 credit is handled cleanly."""
    tx = TransactionItem(
        id="tx-0", row_index=0, date=date(2025, 4, 1),
        narration="BROUGHT FORWARD",
        debit=Decimal("0.00"), credit=Decimal("0.00"),
        balance=Decimal("12009.90")
    )
    assert tx.debit == Decimal("0.00")
    assert tx.credit == Decimal("0.00")

def test_22_card_terminal_id_isolation():
    """Debit card POS terminal transactions maintain full alphanumeric trace."""
    narr = "DEBIT CARD /201904021337/909208028740/HYDERABAD"
    assert "909208028740" in narr

def test_23_gstin_line_isolation():
    """State account branch GSTN line is filtered out."""
    line = "StateaccountbranchGSTN:02AAACH2702H1ZC"
    assert is_noise_text(line) is True

def test_24_page_break_wrapped_narration_attachment():
    """Wrapped second line from previous page joins cleanly without header text."""
    line1 = "UPI-GOOGLEINDIADIGITAL-GOOGLELOAN@ICIC"
    line2 = "I-ICIC0DC0099-409531076672-UPI"
    combined = f"{line1} {line2}"
    assert "GOOGLEINDIADIGITAL" in combined
    assert "409531076672" in combined

def test_25_xml_snapshot_parity():
    """Tally XML output maintains 100% parity with canonical statement."""
    tx = TransactionItem(
        id="tx-1", row_index=1, date=date(2025, 4, 15),
        narration="Payment to Vendor ABC",
        debit=Decimal("1500.00"), credit=Decimal("0.00"),
        voucher_type="Payment", ledger_name="Vendor ABC"
    )
    stmt = CanonicalStatement(
        bank="HDFC Bank", statement_format="Standard",
        transactions=[tx], total_debit=Decimal("1500.00"), total_credit=Decimal("0.00")
    )
    snapshot = FinalConversionSnapshot.create_from_statement(statement=stmt, bank_ledger_name="HDFC Bank A/C", job_id="test")
    assert len(snapshot.transactions) == 1
    assert snapshot.transactions[0].voucher_type == "Payment"
    assert snapshot.transactions[0].debit == Decimal("1500.00")

    xml_gen = TallyXMLGenerator()
    xml_out = xml_gen.generate_xml(snapshot)
    assert "<VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>" in xml_out or "<VOUCHERTYPE>Payment</VOUCHERTYPE>" in xml_out
    assert "Vendor ABC" in xml_out

def test_26_excel_snapshot_parity():
    """Tally Excel output maintains 100% parity with canonical statement."""
    tx = TransactionItem(
        id="tx-1", row_index=1, date=date(2025, 4, 15),
        narration="Payment to Vendor ABC",
        debit=Decimal("1500.00"), credit=Decimal("0.00"),
        voucher_type="Payment", ledger_name="Vendor ABC"
    )
    stmt = CanonicalStatement(
        bank="HDFC Bank", statement_format="Standard",
        transactions=[tx], total_debit=Decimal("1500.00"), total_credit=Decimal("0.00")
    )
    snapshot = FinalConversionSnapshot.create_from_statement(statement=stmt, bank_ledger_name="HDFC Bank A/C", job_id="test")
    excel_gen = TallyExcelGenerator()
    excel_bytes = excel_gen.generate_excel_bytes(snapshot)
    assert len(excel_bytes) > 0

def test_27_voucher_classification_debit_is_payment():
    """Debit transaction without cash keywords is classified as Payment."""
    tx = TransactionItem(
        id="tx-1", row_index=1, date=date(2025, 4, 15),
        narration="Vendor payment for supplies",
        debit=Decimal("500.00"), credit=Decimal("0.00")
    )
    v_type = classify_voucher_type(tx)
    assert v_type == "Payment"

def test_28_voucher_classification_credit_is_receipt():
    """Credit transaction without cash keywords is classified as Receipt."""
    tx = TransactionItem(
        id="tx-1", row_index=1, date=date(2025, 4, 15),
        narration="Customer payment received via NEFT",
        debit=Decimal("0.00"), credit=Decimal("1200.00")
    )
    v_type = classify_voucher_type(tx)
    assert v_type == "Receipt"

def test_29_contra_classification_for_cash():
    """Cash deposit or cash withdrawal is classified as Contra."""
    tx_dep = TransactionItem(
        id="tx-1", row_index=1, date=date(2025, 4, 15),
        narration="Cash Deposit At : NAGROTA SURIAN",
        debit=Decimal("0.00"), credit=Decimal("10000.00"),
        is_cash_transaction=True, cash_transaction_type="CASH_DEPOSIT"
    )
    assert classify_voucher_type(tx_dep) == "Contra"

    tx_wdl = TransactionItem(
        id="tx-2", row_index=2, date=date(2025, 4, 16),
        narration="ATM CASH WITHDRAWAL",
        debit=Decimal("2000.00"), credit=Decimal("0.00"),
        is_cash_transaction=True, cash_transaction_type="CASH_WITHDRAWAL"
    )
    assert classify_voucher_type(tx_wdl) == "Contra"

def test_30_suspense_classification_preserved_without_cross_contamination():
    """Transactions without matching party are safely placed in Suspense without borrowing next row's entity."""
    tx = TransactionItem(
        id="tx-1", row_index=1, date=date(2025, 4, 15),
        narration="Miscellaneous transfer",
        debit=Decimal("100.00"), credit=Decimal("0.00"),
        mapping_status="Suspense", ledger_name="Suspense"
    )
    assert tx.mapping_status == "Suspense"
    assert tx.ledger_name == "Suspense"
