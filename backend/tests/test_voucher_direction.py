"""
Tests for voucher direction classification and running-balance-based debit/credit resolution.

These tests verify the core accounting principles from the 32-point specification:
1. DEBIT (outgoing) → Payment
2. CREDIT (incoming) → Receipt
3. Cash Deposit (credit) → Contra
4. Cash Withdrawal / ATM (debit) → Contra
5. UPI/NEFT/IMPS/Cheques → NEVER Contra
6. Running-balance math correctly distinguishes debit vs credit
"""
import pytest
from decimal import Decimal
from datetime import date
from app.transactions.model import TransactionItem, CanonicalStatement
from app.accounting.voucher_classifier import classify_voucher_type
from app.accounting.entity_extractor import NarrationEntityExtractor
from app.transactions.validator import validate_statement_balances


class TestVoucherDirectionClassification:
    """Section 1: Debit/Credit → Payment/Receipt deterministic rules."""

    def test_debit_is_payment(self):
        """Any debit transaction must be classified as Payment."""
        tx = TransactionItem(date=date(2025, 4, 1), narration="UPI/123456/BABA BALAK NATH", debit=Decimal("5000.00"))
        result = classify_voucher_type(tx)
        assert result == "Payment", f"Debit should be Payment, got {result}"

    def test_credit_is_receipt(self):
        """Any credit transaction must be classified as Receipt."""
        tx = TransactionItem(date=date(2025, 4, 1), narration="NEFT CR/SBIN456789/CUSTOMER", credit=Decimal("10000.00"))
        result = classify_voucher_type(tx)
        assert result == "Receipt", f"Credit should be Receipt, got {result}"

    def test_upi_debit_is_payment_not_contra(self):
        """UPI debit must NEVER be Contra."""
        tx = TransactionItem(date=date(2025, 4, 1), narration="UPI/123456/PAY/user@okaxis/Party Name", debit=Decimal("1500.00"))
        result = classify_voucher_type(tx)
        assert result == "Payment", f"UPI debit should be Payment, got {result}"

    def test_neft_credit_is_receipt_not_contra(self):
        """NEFT credit must NEVER be Contra."""
        tx = TransactionItem(date=date(2025, 4, 1), narration="NEFT CR/SBIN0001234/COMPANY NAME", credit=Decimal("50000.00"))
        result = classify_voucher_type(tx)
        assert result == "Receipt", f"NEFT credit should be Receipt, got {result}"

    def test_imps_debit_is_payment_not_contra(self):
        """IMPS debit must NEVER be Contra."""
        tx = TransactionItem(date=date(2025, 4, 1), narration="IMPS/P2A/123456789012/VENDOR", debit=Decimal("3000.00"))
        result = classify_voucher_type(tx)
        assert result == "Payment", f"IMPS debit should be Payment, got {result}"

    def test_rtgs_credit_is_receipt(self):
        """RTGS credit must be Receipt."""
        tx = TransactionItem(date=date(2025, 4, 1), narration="RTGS IN : PUNBR52024 : BIG CUSTOMER", credit=Decimal("500000.00"))
        result = classify_voucher_type(tx)
        assert result == "Receipt", f"RTGS credit should be Receipt, got {result}"

    def test_cheque_debit_is_payment(self):
        """Cheque debit must be Payment, never Contra."""
        tx = TransactionItem(date=date(2025, 4, 1), narration="IZE 689744 Paid To : VENDOR NAME", debit=Decimal("25000.00"))
        result = classify_voucher_type(tx)
        assert result == "Payment", f"Cheque debit should be Payment, got {result}"

    def test_bank_charges_debit_is_payment(self):
        """Bank charges debit must be Payment."""
        tx = TransactionItem(date=date(2025, 4, 1), narration="SMS ALERT CHARGES", debit=Decimal("59.00"))
        result = classify_voucher_type(tx)
        assert result == "Payment", f"Bank charges should be Payment, got {result}"

    def test_dual_amount_net_credit_is_receipt(self):
        """When both debit and credit are non-zero, net credit should be Receipt."""
        tx = TransactionItem(date=date(2025, 4, 1), narration="Transfer", debit=Decimal("100.00"), credit=Decimal("5000.00"))
        result = classify_voucher_type(tx)
        assert result == "Receipt", f"Net credit should be Receipt, got {result}"

    def test_dual_amount_net_debit_is_payment(self):
        """When both debit and credit are non-zero, net debit should be Payment."""
        tx = TransactionItem(date=date(2025, 4, 1), narration="Transfer", debit=Decimal("5000.00"), credit=Decimal("100.00"))
        result = classify_voucher_type(tx)
        assert result == "Payment", f"Net debit should be Payment, got {result}"


class TestCashContraClassification:
    """Sections 2 & 3: Cash movements must be strictly Contra."""

    def test_cash_deposit_is_contra(self):
        """Cash deposit (credit) must be Contra."""
        tx = TransactionItem(date=date(2025, 4, 1), narration="CASH DEPOSIT BY SELF", credit=Decimal("50000.00"))
        result = classify_voucher_type(tx)
        assert result == "Contra", f"Cash deposit should be Contra, got {result}"

    def test_cash_withdrawal_is_contra(self):
        """Cash withdrawal (debit) must be Contra."""
        tx = TransactionItem(date=date(2025, 4, 1), narration="ATM CASH WITHDRAWAL", debit=Decimal("10000.00"))
        result = classify_voucher_type(tx)
        assert result == "Contra", f"Cash withdrawal should be Contra, got {result}"

    def test_atm_cash_is_contra(self):
        """ATM withdrawal must be Contra."""
        tx = TransactionItem(date=date(2025, 4, 1), narration="ATM WDL-SELF", debit=Decimal("5000.00"))
        result = classify_voucher_type(tx)
        assert result == "Contra", f"ATM WDL should be Contra, got {result}"

    def test_cdm_deposit_is_contra(self):
        """CDM (Cash Deposit Machine) deposit must be Contra."""
        tx = TransactionItem(date=date(2025, 4, 1), narration="CDM CASH DEP AT BRANCH", credit=Decimal("20000.00"))
        result = classify_voucher_type(tx)
        assert result == "Contra", f"CDM deposit should be Contra, got {result}"

    def test_self_cash_withdrawal_is_contra(self):
        """Self cash withdrawal must be Contra."""
        tx = TransactionItem(date=date(2025, 4, 1), narration="SELF CASH WITHDRAWAL CHEQUE", debit=Decimal("100000.00"))
        result = classify_voucher_type(tx)
        assert result == "Contra", f"Self cash withdrawal should be Contra, got {result}"


class TestEntityExtraction:
    """Tests for narration entity extraction — bank charges, parties, instruments."""

    def test_bank_charges_recognized(self):
        """Bank charges narrations must return Bank Charges party."""
        test_cases = [
            "SMS ALERT CHARGES",
            "A/C MAINTENANCE CHARGES",
            "BANK CHARGES",
            "SERVICE CHARGES",
            "NEFT CHARGES",
            "CONSOLIDATED CHG",
            "DEBIT CARD CHARGES",
        ]
        for narr in test_cases:
            party, category = NarrationEntityExtractor.extract_party_from_narration(narr, is_debit=True)
            assert party == "Bank Charges", f"Expected 'Bank Charges' for '{narr}', got '{party}'"
            assert category == "BANK_CHARGES", f"Expected 'BANK_CHARGES' category for '{narr}', got '{category}'"

    def test_interest_income_recognized(self):
        """Interest credit must be recognized."""
        party, cat = NarrationEntityExtractor.extract_party_from_narration("INT.COLL ON SAVINGS ACCOUNT", is_debit=False)
        assert party == "Bank Interest Income", f"Expected 'Bank Interest Income', got '{party}'"

    def test_interest_expense_recognized(self):
        """Interest debit must be recognized."""
        party, cat = NarrationEntityExtractor.extract_party_from_narration("INT.PD ON OD ACCOUNT", is_debit=True)
        assert party == "Bank Interest Expense", f"Expected 'Bank Interest Expense', got '{party}'"

    def test_upi_party_extraction(self):
        """UPI party extraction from narration."""
        party, cat = NarrationEntityExtractor.extract_party_from_narration(
            "UPI/545802695994/Maa vaishno Jener/sanyag116@oksbi/Punjab National Bank", is_debit=True
        )
        assert party is not None, "UPI party should be extracted"
        assert cat == "UPI"

    def test_rtgs_party_extraction(self):
        """RTGS party extraction."""
        party, cat = NarrationEntityExtractor.extract_party_from_narration(
            "RTGS OUT : PUNBR52024 : BABA BALAK NATH", is_debit=True
        )
        assert party == "BABA BALAK NATH", f"Expected 'BABA BALAK NATH', got '{party}'"
        assert cat == "RTGS"

    def test_cheque_number_extraction_ize(self):
        """IZE pattern cheque number extraction."""
        chq = NarrationEntityExtractor.extract_cheque_or_instrument_number("IZE 689744 Paid To VENDOR")
        assert chq == "689744", f"Expected '689744', got '{chq}'"

    def test_noise_cleaning(self):
        """PNB noise markers should be removed."""
        cleaned = NarrationEntityExtractor.clean_narration_noise("UPI -1 LAT/123456/Party Name LATENCY CTO610")
        assert "-1 LAT" not in cleaned
        assert "LATENCY" not in cleaned
        assert "CTO610" not in cleaned
        assert "UPI" in cleaned

    def test_cash_deposit_identified(self):
        """Cash deposit identification."""
        is_cash, cash_type = NarrationEntityExtractor.identify_cash_transaction("CASH DEPOSIT BY SELF", is_debit=False)
        assert is_cash is True
        assert cash_type == "CASH_DEPOSIT"

    def test_cash_withdrawal_identified(self):
        """Cash withdrawal identification."""
        is_cash, cash_type = NarrationEntityExtractor.identify_cash_transaction("ATM CASH WITHDRAWAL", is_debit=True)
        assert is_cash is True
        assert cash_type == "CASH_WITHDRAWAL"


class TestRunningBalanceValidation:
    """Tests for the validator's severity-based classification."""

    def _make_statement(self, transactions, opening=None):
        return CanonicalStatement(
            bank="Test Bank",
            opening_balance=opening,
            transactions=transactions
        )

    def test_valid_balance_chain(self):
        """Perfectly balanced transactions should all be VALID."""
        txs = [
            TransactionItem(date=date(2025, 4, 1), narration="TX1", debit=Decimal("1000.00"), balance=Decimal("9000.00")),
            TransactionItem(date=date(2025, 4, 2), narration="TX2", credit=Decimal("500.00"), balance=Decimal("9500.00")),
            TransactionItem(date=date(2025, 4, 3), narration="TX3", debit=Decimal("200.00"), balance=Decimal("9300.00")),
        ]
        stmt = self._make_statement(txs, opening=Decimal("10000.00"))
        result = validate_statement_balances(stmt)
        for tx in result.transactions:
            assert tx.validation_status == "VALID", f"TX {tx.row_index} should be VALID, got {tx.validation_status}"

    def test_small_discrepancy_is_warning(self):
        """Discrepancy < 1.00 should be WARNING, not ERROR."""
        txs = [
            TransactionItem(date=date(2025, 4, 1), narration="TX1", debit=Decimal("1000.00"), balance=Decimal("9000.50")),
        ]
        stmt = self._make_statement(txs, opening=Decimal("10000.00"))
        result = validate_statement_balances(stmt)
        assert result.transactions[0].validation_status == "WARNING"

    def test_large_discrepancy_is_error(self):
        """Discrepancy >= 1.00 should be ERROR."""
        txs = [
            TransactionItem(date=date(2025, 4, 1), narration="TX1", debit=Decimal("1000.00"), balance=Decimal("11000.00")),
        ]
        stmt = self._make_statement(txs, opening=Decimal("10000.00"))
        result = validate_statement_balances(stmt)
        assert result.transactions[0].validation_status == "ERROR"

    def test_no_balance_is_valid(self):
        """Transactions without balance data should be VALID (not warned)."""
        txs = [
            TransactionItem(date=date(2025, 4, 1), narration="TX1", debit=Decimal("1000.00"), balance=None),
        ]
        stmt = self._make_statement(txs, opening=None)
        result = validate_statement_balances(stmt)
        assert result.transactions[0].validation_status == "VALID"

    def test_confidence_score(self):
        """Overall confidence should reflect discrepancy ratio."""
        txs = [
            TransactionItem(date=date(2025, 4, 1), narration="TX1", debit=Decimal("1000.00"), balance=Decimal("9000.00")),
            TransactionItem(date=date(2025, 4, 2), narration="TX2", credit=Decimal("500.00"), balance=Decimal("9500.00")),
        ]
        stmt = self._make_statement(txs, opening=Decimal("10000.00"))
        result = validate_statement_balances(stmt)
        assert result.confidence_score == 100.0
