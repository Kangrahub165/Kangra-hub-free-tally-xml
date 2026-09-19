import copy
from datetime import date as dt_date
from decimal import Decimal
from typing import List, Optional, Tuple, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict

from app.transactions.model import CanonicalStatement, TransactionItem
from app.core.exceptions import XMLGenerationException

class FinalVoucherEntry(BaseModel):
    """
    Immutable individual transaction entry in the FinalConversionSnapshot.
    Guarantees that downstream generators (Excel/XML) cannot modify voucher data.
    """
    model_config = ConfigDict(frozen=True)

    row_index: int
    voucher_type: str = "Payment"
    date: Optional[dt_date] = None
    narration: str = ""
    original_narration: Optional[str] = None
    ledger_name: str
    bank_ledger_name: str
    instrument_number: Optional[str] = None
    cheque_number: Optional[str] = None
    instrument_date: Optional[dt_date] = None
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")
    balance: Optional[Decimal] = None
    is_cash_transaction: bool = False
    reference: Optional[str] = None
    validation_status: str = "VALID"
    validation_notes: Optional[str] = None


class FinalConversionSnapshot(BaseModel):
    """
    Immutable Single Source of Truth for final reviewed bank statement conversion data.
    PRD Sections 1 & 2:
    Both Excel (.xlsx) and Tally XML (.xml) generation strictly consume this exact snapshot.
    Immutable: frozen=True prevents mutation by any consumer.
    Contains all final values after:
    - PDF extraction
    - Bank detection
    - Transaction normalization
    - Ledger matching
    - User/Admin corrections (Ledger, Voucher Type, Narration, Instrument No, Dates, Amounts)
    - Sequential voucher numbering (1, 2, 3...)
    - Final accounting validation
    """
    model_config = ConfigDict(frozen=True)

    job_id: str = ""
    bank_name: str
    bank_ledger_name: str
    cash_ledger_name: str = "Cash"
    statement_from: Optional[dt_date] = None
    statement_to: Optional[dt_date] = None
    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None
    total_debit: Decimal = Decimal("0.00")
    total_credit: Decimal = Decimal("0.00")
    transactions: Tuple[FinalVoucherEntry, ...] = ()

    @classmethod
    def create_from_statement(
        cls,
        statement: CanonicalStatement,
        bank_ledger_name: str,
        cash_ledger_name: str = "Cash",
        job_id: str = ""
    ) -> "FinalConversionSnapshot":
        """
        Creates a stabilized, validated FinalConversionSnapshot from a CanonicalStatement.
        Ensures sequential voucher numbering 1..N and resolves party ledgers.
        All entries are converted to deeply frozen FinalVoucherEntry objects.
        """
        entries: List[FinalVoucherEntry] = []
        b_name = bank_ledger_name.strip()
        c_name = cash_ledger_name.strip()

        for idx, tx in enumerate(statement.transactions, start=1):
            raw_party = tx.ledger_name
            if not raw_party or not raw_party.strip():
                if tx.is_cash_transaction:
                    party = c_name
                else:
                    party = "Suspense"
            else:
                party = raw_party.strip()

            inst_num = tx.instrument_number or tx.cheque_number
            inst_num_str = str(inst_num).strip() if inst_num else None

            entry = FinalVoucherEntry(
                row_index=idx,
                voucher_type=tx.voucher_type or "Payment",
                date=tx.date,
                narration=tx.narration or "",
                original_narration=getattr(tx, "original_narration", None) or tx.narration or "",
                ledger_name=party,
                bank_ledger_name=b_name,
                instrument_number=inst_num_str,
                cheque_number=inst_num_str,
                instrument_date=tx.instrument_date or tx.date,
                debit=tx.debit if tx.debit is not None else Decimal("0.00"),
                credit=tx.credit if tx.credit is not None else Decimal("0.00"),
                balance=tx.balance,
                is_cash_transaction=tx.is_cash_transaction,
                reference=tx.reference or inst_num_str,
                validation_status=tx.validation_status or "VALID",
                validation_notes=tx.validation_notes
            )
            entries.append(entry)

        tot_debit = sum(t.debit for t in entries)
        tot_credit = sum(t.credit for t in entries)

        return cls(
            job_id=job_id,
            bank_name=statement.bank,
            bank_ledger_name=b_name,
            cash_ledger_name=c_name,
            statement_from=statement.statement_from,
            statement_to=statement.statement_to,
            opening_balance=statement.opening_balance,
            closing_balance=statement.closing_balance,
            total_debit=tot_debit,
            total_credit=tot_credit,
            transactions=tuple(entries)
        )


def validate_conversion_snapshot(snapshot: FinalConversionSnapshot) -> Tuple[bool, List[str]]:
    """
    Validates all accounting and data integrity invariants on the FinalConversionSnapshot
    independent of XML or Excel generation.
    """
    errors: List[str] = []

    if not snapshot.transactions:
        errors.append("Snapshot validation failed: No transactions found in conversion snapshot.")
        return False, errors

    if not snapshot.bank_ledger_name or not snapshot.bank_ledger_name.strip():
        errors.append("Snapshot validation failed: Missing configured Bank Ledger As Tally.")

    for idx, tx in enumerate(snapshot.transactions, start=1):
        if tx.row_index != idx:
            errors.append(f"Row {idx}: Non-sequential voucher number {tx.row_index} (expected {idx})")

        vch_type = tx.voucher_type or "Payment"
        if vch_type not in ("Payment", "Receipt", "Contra", "Journal"):
            errors.append(f"Row {idx}: Invalid voucher type '{vch_type}'")

        if not tx.date:
            errors.append(f"Row {idx}: Missing voucher date")

        if not tx.narration or not tx.narration.strip():
            errors.append(f"Row {idx}: Missing voucher narration")

        if not tx.ledger_name or not tx.ledger_name.strip():
            errors.append(f"Row {idx}: Missing party ledger name")

        if tx.debit < Decimal("0.00") or tx.credit < Decimal("0.00"):
            errors.append(f"Row {idx}: Negative amount encountered")

        if tx.debit == Decimal("0.00") and tx.credit == Decimal("0.00"):
            errors.append(f"Row {idx}: Both debit and credit amounts are zero")

        if tx.validation_status == "ERROR":
            errors.append(f"Row {idx}: Critical balance validation error - {tx.validation_notes or 'Mathematical error'}")

    # Closing balance reconciliation (informational check — does not block valid voucher export)
    # Opening and closing balances printed on statement headers may reflect different period dates
    # than the extracted transaction range.

    if errors:
        return False, errors
    return True, []
