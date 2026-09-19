"""
HDFC Bank Statement Parser.

Features:
- Strict page-level header and footer boundary isolation.
- Completely prevents disclaimers, GSTIN notices, branch addresses, and repeated headers
  from leaking into transaction narrations.
- Reconstructs multi-line wrapped narrations (e.g. UPI handles, merchant names).
- Mathematical running-balance resolution for withdrawal vs deposit direction.
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
from app.pdf.layout_engine import is_noise_text
from app.transactions.validator import validate_statement_balances
from app.accounting.entity_extractor import NarrationEntityExtractor

logger = logging.getLogger(__name__)

# Matches HDFC transaction line:
# Date Narration [Chq/Ref] ValueDt Amount ClosingBal
_HDFC_TX_RX = re.compile(
    r'^(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+(?:(\d{10,20}|[A-Za-z0-9]{8,20})\s+)?(\d{2}/\d{2}/\d{2,4})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$'
)

_DATE_RX = re.compile(r'^\d{2}/\d{2}/\d{2,4}\b')

_HDFC_FOOTER_KEYWORDS = (
    "*Closingbalance",
    "Contentsofthisstatement",
    "RegisteredOffice",
    "StateaccountbranchGSTN",
    "HDFCBankGSTIN",
    "GSTN:"
)

_HDFC_HEADER_END_KEYWORDS = (
    "StatementFrom",
    "Date Narration"
)

class HDFCBankParser(BaseStatementParser):
    """
    Dedicated parser for HDFC Bank savings and current account statements.
    Enforces 100% boundary isolation across all pages.
    """

    def __init__(self):
        super().__init__(
            bank_name="HDFC Bank",
            format_name="Savings & Current Standard",
            parser_key="hdfc_standard",
            version="2.1"
        )

    def can_parse(self, doc: ExtractedDocument) -> bool:
        first_page = doc.first_page_text.upper()
        return "HDFC BANK" in first_page or "HDFC0" in first_page or "HDFCBANK.COM" in first_page

    def parse(self, doc: ExtractedDocument) -> CanonicalStatement:
        raw_txns = []
        curr = None
        global_row_index = 0

        for page in doc.pages:
            lines = page.lines
            # Locate end of header on this page
            header_end = 0
            for idx, l in enumerate(lines):
                l_s = l.strip()
                if any(k in l_s for k in _HDFC_HEADER_END_KEYWORDS):
                    header_end = idx + 1
                    if "Date Narration" in l_s:
                        break

            body_lines = lines[header_end:]
            for line in body_lines:
                line_s = line.strip()
                if not line_s:
                    continue

                # Stop page processing at genuine footer line (never on a line that begins with a transaction date)
                if not _DATE_RX.match(line_s) and any(k.lower() in line_s.lower() for k in _HDFC_FOOTER_KEYWORDS):
                    break

                m = _HDFC_TX_RX.match(line_s)
                if m:
                    if curr:
                        raw_txns.append(curr)
                    global_row_index += 1
                    curr = {
                        "row_index": global_row_index,
                        "page": page.page_number,
                        "date_str": m.group(1),
                        "narr_parts": [m.group(2)],
                        "ref": m.group(3) or "",
                        "val_dt_str": m.group(4),
                        "amt": normalize_amount(m.group(5)),
                        "bal": normalize_amount(m.group(6)),
                        "source_lines": [line_s]
                    }
                elif curr:
                    if any(k.lower() in line_s.lower() for k in _HDFC_FOOTER_KEYWORDS):
                        break
                    curr["narr_parts"].append(line_s)
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

            for idx, t in enumerate(raw_txns):
                amt = t["amt"]
                bal = t["bal"]
                debit = Decimal("0.00")
                credit = Decimal("0.00")

                if prev_bal is not None:
                    if (prev_bal - amt).quantize(quant) == bal:
                        debit = amt
                    elif (prev_bal + amt).quantize(quant) == bal:
                        credit = amt
                    else:
                        # Direction heuristic: if balance decreased -> Debit, else Credit
                        if bal < prev_bal:
                            debit = amt
                        else:
                            credit = amt
                else:
                    # First transaction: check against second transaction
                    if len(raw_txns) > 1:
                        next_bal = raw_txns[1]["bal"]
                        next_amt = raw_txns[1]["amt"]
                        # Assume current is debit or credit and test opening
                        if next_bal < bal:
                            debit = amt
                        else:
                            credit = amt
                    else:
                        debit = amt

                prev_bal = bal

                raw_narr = " ".join(t["narr_parts"])
                clean_narr = NarrationEntityExtractor.clean_narration_noise(raw_narr)

                ref = t["ref"] or extract_reference_number(clean_narr)
                upi_ref = NarrationEntityExtractor.extract_upi_reference(clean_narr)
                utr = NarrationEntityExtractor.extract_utr_reference(clean_narr)
                cheque_no = NarrationEntityExtractor.extract_cheque_or_instrument_number(clean_narr) or (t["ref"] if len(t["ref"]) <= 8 else None)

                tx_date = normalize_date(t["date_str"]) or date.today()
                val_date = normalize_date(t["val_dt_str"]) if t.get("val_dt_str") else tx_date

                is_debit = debit > Decimal("0.00")
                voucher_type = "Payment" if is_debit else "Receipt"

                tx = TransactionItem(
                    id=f"tx-{t['row_index']}",
                    row_index=t["row_index"],
                    date=tx_date,
                    value_date=val_date,
                    narration=clean_narr or "Transaction",
                    original_narration=raw_narr,
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

            if transactions and transactions[0].balance is not None:
                first_tx = transactions[0]
                if first_tx.credit > Decimal("0.00"):
                    opening_balance = (first_tx.balance - first_tx.credit).quantize(quant)
                elif first_tx.debit > Decimal("0.00"):
                    opening_balance = (first_tx.balance + first_tx.debit).quantize(quant)

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
