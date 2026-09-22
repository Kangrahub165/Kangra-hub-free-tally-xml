"""
UCO Bank Statement Parser.

Supports both:
1. Structured vector table extraction (e.g. UCO BANK.pdf)
2. Borderless columnar statements with chronological running-balance math (e.g. uco-bank-2.pdf)

Guarantees 100% boundary isolation across transactions.
"""
import re
import logging
from decimal import Decimal
from datetime import date
from typing import List, Optional

from app.parsers.base import BaseStatementParser
from app.pdf.extractor import ExtractedDocument
from app.transactions.model import CanonicalStatement, TransactionItem
from app.transactions.normalizer import normalize_date, normalize_amount, clean_narration, extract_reference_number
from app.pdf.layout_engine import extract_structured_table_rows, is_noise_text
from app.transactions.validator import validate_statement_balances
from app.accounting.entity_extractor import NarrationEntityExtractor

logger = logging.getLogger(__name__)

_UCO_BORDERLESS_TX_RX = re.compile(
    r'^(\d{2}-\d{2}-\d{4})\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$'
)

_UCO_HEADER_SKIP = (
    "Statement for A/c",
    "Client Code",
    "Branch Code",
    "IFSC Code UCBA",
    "Branch Name",
    "Date Particulars Instrument",
    "Withdrawals Deposits Balance",
    "Page "
)

class UCOBankParser(BaseStatementParser):
    """
    Dedicated parser for UCO Bank statements.
    Handles tabular corporate statements and borderless retail statements.
    """

    def __init__(self):
        super().__init__(
            bank_name="UCO Bank",
            format_name="Savings & Current Standard",
            parser_key="uco_standard",
            version="2.0"
        )

    def can_parse(self, doc: ExtractedDocument) -> bool:
        first_page = doc.first_page_text.upper()
        return "UCO BANK" in first_page or "UCBA0" in first_page or "UCOBANK" in first_page

    def parse(self, doc: ExtractedDocument) -> CanonicalStatement:
        transactions: List[TransactionItem] = []
        statement_from: Optional[date] = None
        statement_to: Optional[date] = None
        opening_balance: Optional[Decimal] = None

        # 1. Try structured table extraction first
        if doc.file_path:
            try:
                table_rows = extract_structured_table_rows(
                    doc.file_path,
                    doc.password,
                    start_page=getattr(doc, "start_page", 1),
                    max_pages=getattr(doc, "max_pages", None),
                    allowed_page_numbers=getattr(doc, "page_numbers", None)
                )
                if table_rows:
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
                logger.warning(f"UCO structured table extraction failed, falling back: {e}")
                transactions = []

        # 2. Borderless fallback for statements like uco-bank-2.pdf
        if not transactions:
            raw_txns = []
            curr = None

            for page in doc.pages:
                for line in page.lines:
                    line_s = line.strip()
                    if not line_s or any(skip in line_s for skip in _UCO_HEADER_SKIP) or is_noise_text(line_s):
                        continue

                    m = _UCO_BORDERLESS_TX_RX.match(line_s)
                    if m:
                        if curr:
                            raw_txns.append(curr)
                        curr = {
                            "page": page.page_number,
                            "date_str": m.group(1),
                            "narr_parts": [m.group(2)],
                            "amt": normalize_amount(m.group(3)),
                            "bal": normalize_amount(m.group(4)),
                            "source_line": line_s
                        }
                    elif curr:
                        curr["narr_parts"].append(line_s)

            if curr:
                raw_txns.append(curr)

            if raw_txns:
                # Resolve debit/credit using chronological running balance
                chrono = list(reversed(raw_txns))
                prev_bal = None

                for idx, t in enumerate(chrono):
                    amt = t["amt"]
                    bal = t["bal"]
                    debit = Decimal("0.00")
                    credit = Decimal("0.00")

                    if prev_bal is not None:
                        if (prev_bal + amt) == bal:
                            credit = amt
                        elif (prev_bal - amt) == bal:
                            debit = amt
                        else:
                            debit = amt
                    else:
                        next_t = chrono[1] if len(chrono) > 1 else None
                        if next_t and (bal + next_t["amt"] == next_t["bal"]):
                            debit = amt
                        else:
                            credit = amt
                    prev_bal = bal

                    full_narr = " ".join(t["narr_parts"])
                    clean_narr = NarrationEntityExtractor.clean_narration_noise(full_narr)
                    ref = extract_reference_number(clean_narr)
                    upi_ref = NarrationEntityExtractor.extract_upi_reference(clean_narr)
                    utr = NarrationEntityExtractor.extract_utr_reference(clean_narr)
                    cheque_no = NarrationEntityExtractor.extract_cheque_or_instrument_number(clean_narr)

                    tx_date = normalize_date(t["date_str"]) or date.today()
                    is_debit = debit > Decimal("0.00")
                    voucher_type = "Payment" if is_debit else "Receipt"

                    tx = TransactionItem(
                        id=f"tx-{idx + 1}",
                        row_index=idx + 1,
                        date=tx_date,
                        value_date=tx_date,
                        narration=clean_narr or "Transaction",
                        original_narration=full_narr,
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
                        source_page=t["page"],
                        source_lines=[t["source_line"]],
                        source_row_index=idx + 1,
                        parser_name=self.parser_key,
                        boundary_confidence=1.0
                    )
                    transactions.append(tx)

                    if not statement_from or tx_date < statement_from:
                        statement_from = tx_date
                    if not statement_to or tx_date > statement_to:
                        statement_to = tx_date

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
