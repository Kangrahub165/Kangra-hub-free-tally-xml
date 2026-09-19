"""
Union Bank of India Statement Parser.

Uses structured table extraction to ensure 100% boundary isolation across transactions.
Supports 5-column layout: Tran Id, Tran Date, Remarks, Amount (Rs.) with (Dr)/(Cr), Balance (Rs.).
"""
import logging
from decimal import Decimal
from datetime import date
from typing import List, Optional

from app.parsers.base import BaseStatementParser
from app.pdf.extractor import ExtractedDocument
from app.transactions.model import CanonicalStatement, TransactionItem
from app.transactions.normalizer import normalize_date, normalize_amount, clean_narration, extract_reference_number
from app.pdf.layout_engine import extract_structured_table_rows
from app.transactions.validator import validate_statement_balances
from app.accounting.entity_extractor import NarrationEntityExtractor

logger = logging.getLogger(__name__)

class UnionBankParser(BaseStatementParser):
    """
    Dedicated parser for Union Bank of India statements.
    Extracts structured tables with Dr/Cr amount resolution.
    Guarantees strict boundary isolation so remarks never leak across transactions.
    """

    def __init__(self):
        super().__init__(
            bank_name="Union Bank of India",
            format_name="Savings & Current Standard",
            parser_key="union_standard",
            version="2.0"
        )

    def can_parse(self, doc: ExtractedDocument) -> bool:
        first_page = doc.first_page_text.upper()
        return "UNION BANK OF INDIA" in first_page or "UBIN0" in first_page or "UNION BANK" in first_page

    def parse(self, doc: ExtractedDocument) -> CanonicalStatement:
        transactions: List[TransactionItem] = []
        statement_from: Optional[date] = None
        statement_to: Optional[date] = None
        opening_balance: Optional[Decimal] = None

        if doc.file_path:
            try:
                table_rows = extract_structured_table_rows(doc.file_path, doc.password)
                for r in table_rows:
                    tx_date = normalize_date(r.date_str)
                    if not tx_date:
                        continue

                    val_date = normalize_date(r.value_date_str) if r.value_date_str else tx_date
                    debit = normalize_amount(r.debit_str) if r.debit_str else Decimal("0.00")
                    credit = normalize_amount(r.credit_str) if r.credit_str else Decimal("0.00")
                    bal = normalize_amount(r.balance_str) if r.balance_str else None

                    clean_narr = NarrationEntityExtractor.clean_narration_noise(r.narration)
                    ref = r.reference_str or extract_reference_number(clean_narr)
                    upi_ref = NarrationEntityExtractor.extract_upi_reference(clean_narr)
                    utr = NarrationEntityExtractor.extract_utr_reference(clean_narr)
                    cheque_no = r.reference_str or NarrationEntityExtractor.extract_cheque_or_instrument_number(clean_narr)

                    is_debit = debit > Decimal("0.00")
                    voucher_type = "Payment" if is_debit else "Receipt"

                    tx = TransactionItem(
                        id=f"tx-{r.row_index}",
                        row_index=r.row_index,
                        date=tx_date,
                        value_date=val_date,
                        narration=clean_narr or "Transaction",
                        original_narration=r.narration,
                        reference=cheque_no or upi_ref or utr or ref or "",
                        cheque_number=cheque_no,
                        instrument_number=cheque_no,
                        instrument_date=tx_date if cheque_no else None,
                        upi_ref=upi_ref,
                        utr=utr,
                        debit=debit,
                        credit=credit,
                        balance=bal,
                        voucher_type=voucher_type,
                        source_page=r.page_number,
                        source_lines=r.source_lines,
                        source_row_index=r.row_index,
                        parser_name=self.parser_key,
                        boundary_confidence=1.0
                    )
                    transactions.append(tx)

                    if not statement_from or tx_date < statement_from:
                        statement_from = tx_date
                    if not statement_to or tx_date > statement_to:
                        statement_to = tx_date
            except Exception as e:
                logger.error(f"UnionBankParser failed to extract table: {e}", exc_info=True)

        if transactions and transactions[0].balance is not None:
            first_tx = transactions[0]
            if first_tx.credit > Decimal("0.00"):
                opening_balance = (first_tx.balance - first_tx.credit).quantize(Decimal("0.01"))
            elif first_tx.debit > Decimal("0.00"):
                opening_balance = (first_tx.balance + first_tx.debit).quantize(Decimal("0.01"))

        total_debit = sum(t.debit for t in transactions)
        total_credit = sum(t.credit for t in transactions)
        closing_balance = transactions[-1].balance if transactions else opening_balance

        statement = CanonicalStatement(
            bank=self.bank_name,
            statement_format=self.format_name,
            statement_from=statement_from,
            statement_to=statement_to,
            transactions=transactions,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_debit=total_debit,
            total_credit=total_credit
        )
        return validate_statement_balances(statement)
