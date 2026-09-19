"""
Kangra Central Co-operative Bank (KCCB) Statement Parser.

Features:
- Borderless dual-date anchor extraction (Post Date, Value Date, Details, Chq No, Debit, Credit, Balance).
- Strict multi-line party and UTR continuation collection without cross-row leakage.
- Chronological running-balance resolution with exact debit/credit count and total verification.
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

# Matches: PostDate ValueDate Details [Chq] Amount Balance
_KANGRA_TX_RX = re.compile(
    r'^(\d{2}/\d{2}/\d{2,4})\s+(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2}(?:Cr|Dr)?)$'
)

_KANGRA_STOP_KEYWORDS = (
    "CLOSING BALANCE",
    "Statement Summary",
    "*---END OF STATEMENT---*"
)

class KangraCoopParser(BaseStatementParser):
    """
    Dedicated parser for Kangra Central Co-operative Bank (KCCB) statements.
    """

    def __init__(self):
        super().__init__(
            bank_name="Kangra Central Co-operative Bank",
            format_name="Savings & Current Standard",
            parser_key="kccb_standard",
            version="2.0"
        )

    def can_parse(self, doc: ExtractedDocument) -> bool:
        first_page = doc.first_page_text.upper()
        return (
            "KANGRA CENTRAL CO-OP BANK" in first_page or
            "KCCB" in first_page or
            "KANGRA CO OPERATIVE" in first_page or
            "KANGRA CO-OPERATIVE" in first_page
        )

    def parse(self, doc: ExtractedDocument) -> CanonicalStatement:
        raw_txns = []
        curr = None
        global_row_index = 0
        opening_balance: Optional[Decimal] = None

        in_table = False
        curr_section_opening = None

        for page in doc.pages:
            lines = page.lines
            for line in lines:
                line_s = line.strip()
                if not line_s:
                    continue

                if not in_table:
                    if "Post Value Details" in line_s or "Date Date" in line_s:
                        in_table = True
                        continue
                    if "BROUGHT FORWARD" in line_s:
                        in_table = True
                        amt_m = re.search(r'([\d,]+\.\d{2}(?:Cr|Dr)?)', line_s)
                        if amt_m:
                            curr_section_opening = normalize_amount(amt_m.group(1))
                            if opening_balance is None:
                                opening_balance = curr_section_opening
                        continue
                    continue

                if any(k in line_s for k in _KANGRA_STOP_KEYWORDS):
                    in_table = False
                    continue

                if "BROUGHT FORWARD" in line_s:
                    amt_m = re.search(r'([\d,]+\.\d{2}(?:Cr|Dr)?)', line_s)
                    if amt_m:
                        curr_section_opening = normalize_amount(amt_m.group(1))
                        if opening_balance is None:
                            opening_balance = curr_section_opening
                    continue

                # Sanitize OCR and font artifacts (e.g. O.OODr -> 0.00Dr, \ufffd, and broken spaces in numbers)
                clean_line = re.sub(r'[\ufffd\xa0]', '', line_s)
                clean_line = re.sub(r'\b[O0]\.[O0]{2}(Cr|Dr)?\b', r'0.00\1', clean_line)
                clean_line = re.sub(r'(\d+)\s*,\s*(\d+)', r'\1,\2', clean_line)
                clean_line = re.sub(r'(\d+)\s*\.\s*(\d{2})\b', r'\1.\2', clean_line)

                m = _KANGRA_TX_RX.match(clean_line)
                if m:
                    if curr:
                        raw_txns.append(curr)
                    global_row_index += 1
                    curr = {
                        "row_index": global_row_index,
                        "page": page.page_number,
                        "post_date_str": m.group(1),
                        "val_date_str": m.group(2),
                        "details": [m.group(3)],
                        "amt": normalize_amount(m.group(4)),
                        "bal": normalize_amount(m.group(5)),
                        "section_opening": curr_section_opening,
                        "source_lines": [line_s]
                    }
                    curr_section_opening = None
                elif curr:
                    if not any(hdr in line_s for hdr in ("Date Date", "Post Value Details", "Post Date", "Value Date")):
                        curr["details"].append(line_s)
                        curr["source_lines"].append(line_s)

        if curr:
            raw_txns.append(curr)

        transactions: List[TransactionItem] = []
        statement_from: Optional[date] = None
        statement_to: Optional[date] = None

        if raw_txns:
            prev_bal = opening_balance
            quant = Decimal("0.01")

            for t in raw_txns:
                if t.get("section_opening") is not None:
                    prev_bal = t["section_opening"]

                amt = t["amt"]
                bal = t["bal"]
                debit = Decimal("0.00")
                credit = Decimal("0.00")

                if prev_bal is not None:
                    if (prev_bal + amt).quantize(quant) == bal:
                        credit = amt
                    elif (prev_bal - amt).quantize(quant) == bal:
                        debit = amt
                    elif bal > prev_bal:
                        credit = amt
                    else:
                        debit = amt
                else:
                    raw_upper = " ".join(t["details"]).upper()
                    if "INTEREST CREDIT" in raw_upper or "TRF FR" in raw_upper:
                        credit = amt
                    else:
                        debit = amt

                prev_bal = bal

                raw_narr = " ".join(t["details"])
                clean_narr = NarrationEntityExtractor.clean_narration_noise(raw_narr)

                ref = extract_reference_number(clean_narr)
                upi_ref = NarrationEntityExtractor.extract_upi_reference(clean_narr)
                utr = NarrationEntityExtractor.extract_utr_reference(clean_narr)
                cheque_no = NarrationEntityExtractor.extract_cheque_or_instrument_number(clean_narr)

                tx_date = normalize_date(t["post_date_str"]) or date.today()
                val_date = normalize_date(t["val_date_str"]) if t.get("val_date_str") else tx_date

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
