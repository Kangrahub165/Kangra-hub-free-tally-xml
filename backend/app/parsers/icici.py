"""
ICICI Bank Statement Parser.

Features:
- Table-header exclusion zone: completely ignores customer address lines (e.g. 13-1-55)
  so they are never misparsed as year 2055 dates.
- Multi-line card transaction and merchant description reconstruction.
- Mathematical running-balance verification to determine debit vs credit direction.
- Strict boundary isolation across transactions.
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
from app.transactions.validator import validate_statement_balances
from app.accounting.entity_extractor import NarrationEntityExtractor

logger = logging.getLogger(__name__)

_DATE_ANCHOR_RX = re.compile(r'^(\d{2}-\d{2}-\d{4})\b')
_AMOUNT_RX = re.compile(r'([\d,]+\.\d{2})')

_TABLE_START_KEYWORDS = (
    "DATE MODE",
    "PARTICULARS DEPOSITS",
    "DATE PARTICULARS"
)

_TABLE_STOP_KEYWORDS = (
    "Total:",
    "STAMP & SIGNATURE",
    "Page "
)

class ICICIBankParser(BaseStatementParser):
    """
    Dedicated parser for ICICI Bank savings and current account statements.
    Ensures addresses are excluded and multi-line descriptions stay strictly isolated.
    """

    def __init__(self):
        super().__init__(
            bank_name="ICICI Bank",
            format_name="Savings & Current Standard",
            parser_key="icici_standard",
            version="2.0"
        )

    def can_parse(self, doc: ExtractedDocument) -> bool:
        first_page = doc.first_page_text.upper()
        return "ICICI BANK" in first_page or "ICIC0" in first_page or "ICICIBANK.COM" in first_page

    def parse(self, doc: ExtractedDocument) -> CanonicalStatement:
        raw_txns = []
        curr = None
        global_row_index = 0

        for page in doc.pages:
            lines = page.lines
            in_table = False

            for line in lines:
                line_s = line.strip()
                if not line_s:
                    continue

                if not in_table:
                    if any(k in line_s for k in _TABLE_START_KEYWORDS):
                        in_table = True
                    continue

                if any(k in line_s for k in _TABLE_STOP_KEYWORDS):
                    in_table = False
                    continue

                m = _DATE_ANCHOR_RX.match(line_s)
                if m:
                    if curr:
                        raw_txns.append(curr)
                    global_row_index += 1
                    date_str = m.group(1)
                    rem = line_s[m.end():].strip()
                    curr = {
                        "row_index": global_row_index,
                        "page": page.page_number,
                        "date_str": date_str,
                        "line": rem,
                        "continuations": [],
                        "source_lines": [line_s]
                    }
                elif curr:
                    curr["continuations"].append(line_s)
                    curr["source_lines"].append(line_s)

        if curr:
            raw_txns.append(curr)

        transactions: List[TransactionItem] = []
        statement_from: Optional[date] = None
        statement_to: Optional[date] = None
        opening_balance: Optional[Decimal] = None

        if raw_txns:
            prev_bal = None
            quant = Decimal("0.01")

            for t in raw_txns:
                full_text = " ".join([t["line"]] + t["continuations"])

                # Check if this is a B/F (Brought Forward / Opening) row
                if re.search(r'\bB/F\b|\bBROUGHT\s+FORWARD\b', full_text, re.IGNORECASE):
                    amounts = _AMOUNT_RX.findall(full_text)
                    if amounts:
                        opening_balance = normalize_amount(amounts[-1])
                        prev_bal = opening_balance
                    continue

                # Extract amounts: ICICI row typically ends with Amount and Balance, or just Balance
                amounts = _AMOUNT_RX.findall(full_text)
                if not amounts:
                    continue

                amt = Decimal("0.00")
                bal = None

                if len(amounts) >= 2:
                    amt = normalize_amount(amounts[-2])
                    bal = normalize_amount(amounts[-1])
                elif len(amounts) == 1:
                    amt = normalize_amount(amounts[0])

                debit = Decimal("0.00")
                credit = Decimal("0.00")

                if prev_bal is not None and bal is not None:
                    if (prev_bal - amt).quantize(quant) == bal:
                        debit = amt
                    elif (prev_bal + amt).quantize(quant) == bal:
                        credit = amt
                    elif bal < prev_bal:
                        debit = amt
                    else:
                        credit = amt
                else:
                    # Fallback check narration for mode clues
                    if any(k in full_text.upper() for k in ("DEBIT", "WDL", "ATM", "PAYMENT", "CHARGES")):
                        debit = amt
                    else:
                        credit = amt

                if bal is not None:
                    prev_bal = bal
                elif prev_bal is not None:
                    prev_bal = (prev_bal + credit - debit).quantize(quant)
                    bal = prev_bal

                clean_narr = NarrationEntityExtractor.clean_narration_noise(full_text)
                # Remove balance & amount fragments from clean narration
                for a_str in amounts:
                    clean_narr = clean_narr.replace(a_str, "").strip()

                ref = extract_reference_number(clean_narr)
                upi_ref = NarrationEntityExtractor.extract_upi_reference(clean_narr)
                utr = NarrationEntityExtractor.extract_utr_reference(clean_narr)
                cheque_no = NarrationEntityExtractor.extract_cheque_or_instrument_number(clean_narr)

                tx_date = normalize_date(t["date_str"]) or date.today()
                is_debit = debit > Decimal("0.00")
                voucher_type = "Payment" if is_debit else "Receipt"

                tx = TransactionItem(
                    id=f"tx-{t['row_index']}",
                    row_index=t["row_index"],
                    date=tx_date,
                    value_date=tx_date,
                    narration=clean_narr or "Transaction",
                    original_narration=full_text,
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
                    source_lines=t["source_lines"],
                    source_row_index=t["row_index"],
                    parser_name=self.parser_key,
                    boundary_confidence=1.0
                )
                transactions.append(tx)

                if not statement_from or tx_date < statement_from:
                    statement_from = tx_date
                if not statement_to or tx_date > statement_to:
                    statement_to = tx_date

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
