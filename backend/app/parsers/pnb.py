"""
Punjab National Bank (PNB) Statement Parser.

PNB Format Characteristics:
- Each transaction line: DD-MM-YYYY <Amount> <Balance> Cr. <Narration...>
- 'Cr.' appears on EVERY line (marks the balance type, not the tx direction)
- Amount is either Withdrawal or Deposit — can ONLY be distinguished by
  running-balance math: prev_bal - amt == bal → DEBIT, prev_bal + amt == bal → CREDIT
- Multi-line narrations: first line has date/amount/balance/partial narration,
  following non-date lines are continuation narration lines
"""
import re
import logging
from datetime import date
from decimal import Decimal
from typing import List, Optional

from app.parsers.base import BaseStatementParser
from app.pdf.extractor import ExtractedDocument
from app.transactions.model import CanonicalStatement, TransactionItem
from app.transactions.normalizer import normalize_date, normalize_amount
from app.accounting.entity_extractor import NarrationEntityExtractor
from app.transactions.validator import validate_statement_balances
from app.pdf.layout_engine import extract_structured_table_rows

logger = logging.getLogger(__name__)

# Matches PNB transaction lines: DD-MM-YYYY Amount Balance Cr./Dr. [Narration...]
_TX_LINE_PATTERN = re.compile(
    r"^(\d{2}[-/]\d{2}[-/]\d{4})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+(?:Cr|Dr)\.?(.*)",
    re.IGNORECASE
)

# Matches standard 5-column PNB lines: Date Particulars Withdrawal Deposit Balance
_TX_5COL_PATTERN = re.compile(
    r"^(\d{2}[-/]\d{2}[-/]\d{4})\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$",
    re.IGNORECASE
)

# Lines to skip (headers, footers, page markers)
_SKIP_KEYWORDS = (
    "Statement of Account No:",
    "Printed By:",
    "Customer Name:",
    "Statement for Period",
    "Tran Date Withdrawal",
    "Tran Date",
    "Branch Address:",
    "Account Name:",
    "Product Type:",
    "Address:",
    "Currency :",
    "Nomination :",
    "Disclaimer:",
    "This is an Electronically Generated",
    "Total Withdrawal",
    "Total Deposit",
    "Closing Balance",
    "Opening Balance",
    "Statement Summary",
)


class PNBParser(BaseStatementParser):
    """
    Specialized parser for Punjab National Bank (PNB) savings and current account statements.
    
    Uses mathematical running-balance resolution (not narration heuristics) to determine
    whether each transaction is a debit or credit. This is the ONLY reliable method for
    PNB statements where 'Cr.' appears on every line.
    """

    def __init__(self):
        super().__init__(
            bank_name="Punjab National Bank (PNB)",
            format_name="Savings & Current Standard",
            parser_key="pnb_standard",
            version="2.0"
        )

    def can_parse(self, doc: ExtractedDocument) -> bool:
        first_page = doc.first_page_text.upper()
        return "PUNJAB NATIONAL BANK" in first_page or "PNB" in first_page or "PUNB0" in first_page

    def parse(self, doc: ExtractedDocument) -> CanonicalStatement:
        """
        Full PNB parse pipeline:
        1. Extract raw blocks (date-anchored transaction groups with multi-line narration)
        2. Apply running-balance math to determine debit vs credit
        3. Clean narrations and extract metadata
        4. Build CanonicalStatement
        5. Run balance validation
        """
        transactions: List[TransactionItem] = []
        opening_balance: Optional[Decimal] = None

        # Try structured vector table extraction first (100% boundary isolated)
        table_rows = []
        if doc.file_path:
            try:
                table_rows = extract_structured_table_rows(
                    doc.file_path,
                    doc.password,
                    start_page=getattr(doc, "start_page", 1),
                    max_pages=getattr(doc, "max_pages", None),
                    allowed_page_numbers=getattr(doc, "page_numbers", None)
                )
            except Exception as e:
                logger.warning(f"Structured table extraction failed for PNB, falling back: {e}")
                table_rows = []

        if table_rows:
            logger.info(f"PNB parser: extracted {len(table_rows)} structured table rows")
            for idx, r in enumerate(table_rows):
                tx_date = normalize_date(r.date_str) or date.today()
                clean_narr = NarrationEntityExtractor.clean_narration_noise(r.narration)
                cheque_no = r.reference_str or NarrationEntityExtractor.extract_cheque_or_instrument_number(clean_narr)
                upi_ref = NarrationEntityExtractor.extract_upi_reference(clean_narr)
                utr = NarrationEntityExtractor.extract_utr_reference(clean_narr)

                debit = normalize_amount(r.debit_str) if r.debit_str else Decimal("0.00")
                credit = normalize_amount(r.credit_str) if r.credit_str else Decimal("0.00")
                bal = normalize_amount(r.balance_str) if r.balance_str else None

                is_debit = debit > Decimal("0.00")
                voucher_type = "Payment" if is_debit else "Receipt"

                tx = TransactionItem(
                    id=f"tx-{idx + 1}",
                    row_index=idx + 1,
                    date=tx_date,
                    value_date=normalize_date(r.value_date_str) if r.value_date_str else tx_date,
                    narration=clean_narr or "Transaction",
                    original_narration=r.narration,
                    reference=cheque_no or upi_ref or utr or "",
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

            # Determine opening balance respecting direction
            if transactions and transactions[0].balance is not None:
                is_desc = (len(transactions) >= 2 and transactions[0].date > transactions[-1].date)
                if not is_desc:
                    first_tx = transactions[0]
                    if first_tx.credit > Decimal("0.00"):
                        opening_balance = (first_tx.balance - first_tx.credit).quantize(Decimal("0.01"))
                    elif first_tx.debit > Decimal("0.00"):
                        opening_balance = (first_tx.balance + first_tx.debit).quantize(Decimal("0.01"))
                else:
                    # Defer to validate_statement_balances after reversal
                    opening_balance = None
        else:
            raw_blocks = self._extract_raw_blocks(doc)
            logger.info(f"PNB parser fallback: extracted {len(raw_blocks)} raw transaction blocks")

            if not raw_blocks:
                return CanonicalStatement(
                    bank=self.bank_name,
                    statement_format=self.format_name,
                    transactions=[],
                    confidence_score=0.0
                )

            # Resolve debit/credit using running-balance math
            transactions, opening_balance = self._resolve_directions(raw_blocks)

        # Determine date range
        statement_from = min((tx.date for tx in transactions), default=None) if transactions else None
        statement_to = max((tx.date for tx in transactions), default=None) if transactions else None
        closing_balance = transactions[-1].balance if transactions else None

        total_debit = sum(tx.debit for tx in transactions)
        total_credit = sum(tx.credit for tx in transactions)

        statement = CanonicalStatement(
            bank=self.bank_name,
            statement_format=self.format_name,
            statement_from=statement_from,
            statement_to=statement_to,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_debit=total_debit,
            total_credit=total_credit,
            transactions=transactions
        )

        # Run running balance validation & confidence scoring
        return validate_statement_balances(statement)

    def _extract_raw_blocks(self, doc: ExtractedDocument) -> List[dict]:
        """
        Phase 1: Extract raw transaction blocks from all pages.
        Each block has: date_str, amt (Decimal), bal (Decimal), narr_parts (list of strings)
        Multi-line narrations are joined by collecting non-date lines after each transaction anchor.
        """
        raw_blocks: List[dict] = []
        current_block: Optional[dict] = None

        for page in doc.pages:
            for line in page.lines:
                line_s = line.strip()
                if not line_s:
                    continue

                # Skip header/footer/page lines
                if any(skip in line_s for skip in _SKIP_KEYWORDS):
                    continue
                if re.match(r"^Page\s+\d+", line_s, re.IGNORECASE):
                    continue

                # Try to match a new transaction line
                m = _TX_LINE_PATTERN.match(line_s)
                m5 = _TX_5COL_PATTERN.match(line_s) if not m else None
                if m:
                    # Save previous block
                    if current_block:
                        raw_blocks.append(current_block)

                    current_block = {
                        "date_str": m.group(1),
                        "amt": Decimal(m.group(2).replace(',', '')),
                        "bal": Decimal(m.group(3).replace(',', '')),
                        "narr_parts": [m.group(4).strip()] if m.group(4).strip() else []
                    }
                elif m5:
                    if current_block:
                        raw_blocks.append(current_block)

                    dr_val = Decimal(m5.group(3).replace(',', ''))
                    cr_val = Decimal(m5.group(4).replace(',', ''))
                    bal_val = Decimal(m5.group(5).replace(',', ''))
                    amt_val = dr_val if dr_val > Decimal("0.00") else cr_val

                    current_block = {
                        "date_str": m5.group(1),
                        "amt": amt_val,
                        "bal": bal_val,
                        "narr_parts": [m5.group(2).strip()] if m5.group(2).strip() else [],
                        "is_debit": (dr_val > Decimal("0.00")),
                        "explicit_direction": True
                    }
                elif current_block:
                    # Continuation narration line for the current transaction
                    current_block["narr_parts"].append(line_s)

        # Append last block
        if current_block:
            raw_blocks.append(current_block)

        return raw_blocks

    def _resolve_directions(self, raw_blocks: List[dict]) -> tuple:
        """
        Phase 2: Use running-balance math to determine debit vs credit for each transaction.
        
        Algorithm:
        - For the first transaction, we need to infer the opening balance.
          We try both assumptions (credit and debit) and check which one is consistent
          with the second transaction's balance math.
        - For subsequent transactions:
          if (prev_bal - amt) == bal → DEBIT
          if (prev_bal + amt) == bal → CREDIT
          else → fallback heuristic (check narration for cash/ATM/withdrawal keywords)
        
        Returns: (transactions_list, opening_balance)
        """
        transactions: List[TransactionItem] = []
        quant = Decimal("0.01")

        # --- Resolve first transaction direction ---
        first = raw_blocks[0]
        first_amt = first["amt"]
        first_bal = first["bal"]

        # Default assumption: first transaction is credit (deposit)
        first_is_debit = False

        if first.get("explicit_direction"):
            first_is_debit = first["is_debit"]
        elif len(raw_blocks) > 1:
            second = raw_blocks[1]
            second_amt = second["amt"]
            second_bal = second["bal"]

            # If first was credit: opening = first_bal - first_amt, prev for second = first_bal
            # Check if second math works with first_bal as prev
            if (first_bal - second_amt).quantize(quant) == second_bal:
                # Second is debit. First was credit is consistent.
                first_is_debit = False
            elif (first_bal + second_amt).quantize(quant) == second_bal:
                # Second is credit. First was credit is consistent.
                first_is_debit = False
            else:
                # Try first as debit: opening = first_bal + first_amt
                first_is_debit = True
        else:
            # Single transaction — use narration heuristic
            narr_upper = " ".join(first.get("narr_parts", [])).upper()
            if any(k in narr_upper for k in ("ATM", "WITHDRAWAL", "CASH WDL", "PAYMENT", "CHARGES")):
                first_is_debit = True

        if first_is_debit:
            opening_balance = (first_bal + first_amt).quantize(quant)
        else:
            opening_balance = (first_bal - first_amt).quantize(quant)

        # --- Process all transactions ---
        prev_bal = opening_balance

        for idx, b in enumerate(raw_blocks):
            amt = b["amt"]
            bal = b["bal"]
            debit = Decimal("0.00")
            credit = Decimal("0.00")

            if b.get("explicit_direction"):
                if b["is_debit"]:
                    debit = amt
                else:
                    credit = amt
            elif idx == 0:
                if first_is_debit:
                    debit = amt
                else:
                    credit = amt
            else:
                if (prev_bal - amt).quantize(quant) == bal:
                    debit = amt
                elif (prev_bal + amt).quantize(quant) == bal:
                    credit = amt
                else:
                    # Fallback: check narration for directional clues
                    narr_upper = " ".join(b.get("narr_parts", [])).upper()
                    if any(k in narr_upper for k in ("ATM", "WITHDRAWAL", "CASH WDL", "CHARGES", "PAYMENT")):
                        debit = amt
                    else:
                        credit = amt
                    logger.warning(
                        f"PNB parser row {idx+1}: balance math inconclusive. "
                        f"prev={prev_bal}, amt={amt}, expected_debit={prev_bal - amt}, "
                        f"expected_credit={prev_bal + amt}, actual_bal={bal}. "
                        f"Using narration fallback."
                    )

            prev_bal = bal

            # Join multi-line narration and clean noise
            raw_narr = " ".join(b["narr_parts"])
            clean_narr = NarrationEntityExtractor.clean_narration_noise(raw_narr)

            # Extract metadata
            cheque_no = NarrationEntityExtractor.extract_cheque_or_instrument_number(clean_narr)
            upi_ref = NarrationEntityExtractor.extract_upi_reference(clean_narr)
            utr = NarrationEntityExtractor.extract_utr_reference(clean_narr)

            tx_date = normalize_date(b["date_str"]) or date.today()

            is_debit = debit > Decimal("0.00")
            voucher_type = "Payment" if is_debit else "Receipt"

            tx = TransactionItem(
                id=f"tx-{idx + 1}",
                row_index=idx + 1,
                date=tx_date,
                value_date=tx_date,
                narration=clean_narr or "Transaction",
                original_narration=raw_narr,
                reference=cheque_no or upi_ref or utr or "",
                cheque_number=cheque_no,
                instrument_number=cheque_no,
                instrument_date=tx_date if cheque_no else None,
                upi_ref=upi_ref,
                utr=utr,
                debit=debit,
                credit=credit,
                balance=bal,
                voucher_type=voucher_type
            )
            transactions.append(tx)

        return transactions, opening_balance
