from decimal import Decimal
from typing import Optional
from app.transactions.model import TransactionItem
from app.accounting.entity_extractor import NarrationEntityExtractor

def classify_voucher_type(tx: TransactionItem) -> str:
    """
    Determines the appropriate Tally Voucher Type based on PRD Specifications (Sections 1, 2, 3):
    - Physical Cash Movement (Bank <-> Cash): STRICTLY "Contra"
      * Cash Deposit into Bank (Credit): "Contra", Ledger = Cash
      * Cash Withdrawal / ATM from Bank (Debit): "Contra", Ledger = Cash
    - Normal Outgoing / Debit (UPI, NEFT, IMPS, Cheque, Charges, Vendor, Expense): STRICTLY "Payment"
    - Normal Incoming / Credit (UPI, NEFT, IMPS, Cheque, Customer, Refund, Interest): STRICTLY "Receipt"
    - Internal Bank-to-Bank Transfer: "Contra"
    
    IMPORTANT: Ordinary electronic third-party transactions (UPI, NEFT, IMPS, Cheques)
    must NEVER be classified as Contra.
    """
    # 1. If user has already explicitly edited or confirmed the voucher type, preserve it!
    if tx.original_voucher_type and tx.voucher_type != tx.original_voucher_type:
        return tx.voucher_type

    is_debit = tx.debit > Decimal("0.00")
    upper_narration = tx.narration.upper()

    # 2. Check for explicit internal Bank-to-Bank Transfer
    if "INTERNAL TRANSFER" in upper_narration or "OWN ACCOUNT TRANSFER" in upper_narration:
        tx.original_voucher_type = "Contra"
        return "Contra"

    # 3. Check for Physical Cash Transactions (Section 2 & 3: Bank <-> Cash movement strictly Contra)
    is_cash, cash_type = NarrationEntityExtractor.identify_cash_transaction(tx.narration, is_debit)
    if is_cash:
        tx.is_cash_transaction = True
        tx.cash_transaction_type = cash_type
        tx.original_voucher_type = "Contra"
        return "Contra"

    # 4. Deterministic Directional Voucher Classification (Section 1)
    # DEBIT (outgoing) MUST be Payment
    # CREDIT (incoming) MUST be Receipt
    # Edge case: If BOTH debit and credit have non-zero values (e.g., some bank formats
    # produce 3-amount rows), use the NET direction to classify.
    has_debit = tx.debit > Decimal("0.00")
    has_credit = tx.credit > Decimal("0.00")

    if has_debit and has_credit:
        # Both populated — use net direction
        if tx.debit > tx.credit:
            vch = "Payment"
        else:
            vch = "Receipt"
    elif has_debit:
        vch = "Payment"
    elif has_credit:
        vch = "Receipt"
    else:
        # Both zero — safe fallback to Payment
        vch = "Payment"

    tx.original_voucher_type = vch
    return vch

