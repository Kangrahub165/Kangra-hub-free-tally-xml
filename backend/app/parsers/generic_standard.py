import re
from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple
from app.parsers.base import BaseStatementParser
from app.pdf.extractor import ExtractedDocument
from app.transactions.model import CanonicalStatement, TransactionItem
from app.transactions.normalizer import (
    normalize_date,
    normalize_amount,
    clean_narration,
    extract_reference_number
)
from app.transactions.validator import validate_statement_balances
from app.pdf.layout_engine import extract_structured_table_rows, is_noise_text
from app.accounting.entity_extractor import NarrationEntityExtractor

class GenericStandardParser(BaseStatementParser):
    """
    Robust columnar & regex bank parser handling Indian bank statement layouts.
    Detects transaction boundaries, joins multi-line narrations, and normalizes amounts.
    """

    # Matches lines starting with a date e.g. 01/04/2024 or 01-04-2024 or S58764812 17/02/2022
    DATE_START_REGEX = re.compile(
        r'^(?:(?:[A-Za-z]*\d+[A-Za-z0-9_\-]*|\d+)\s+)?(\d{1,2}[/\-\.](?:\d{1,2}|[A-Za-z]{3})[/\-\.]\d{2,4})\b'
    )
    
    # Matches amounts at the end of lines e.g. "5,000.00 45,000.00 Cr" or "100.00 0.00 100.00"
    AMOUNT_PATTERN = re.compile(r'([0-9,]+\.[0-9]{2}(?:\s*(?:Cr|Dr))?|[0-9,]+(?:\.[0-9]{2})?)')

    def can_parse(self, doc: ExtractedDocument) -> bool:
        # Generic parser acts as universal standard fallback
        return True

    def parse(self, doc: ExtractedDocument) -> CanonicalStatement:
        # 1. Try structured vector table extraction first
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
                    transactions: List[TransactionItem] = []
                    statement_from: Optional[date] = None
                    statement_to: Optional[date] = None
                    opening_balance: Optional[Decimal] = None

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
                        voucher = "Payment" if debit > Decimal("0.00") else "Receipt"

                        tx = TransactionItem(
                            id=f"tx-{r.row_index}",
                            row_index=r.row_index,
                            date=tx_date,
                            value_date=val_date,
                            narration=clean_narr or "Transaction",
                            original_narration=r.narration,
                            reference=ref or "",
                            cheque_number=ref,
                            instrument_number=ref,
                            instrument_date=tx_date if ref else None,
                            debit=debit,
                            credit=credit,
                            balance=bal,
                            voucher_type=voucher,
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

                    if transactions:
                        if transactions[0].balance is not None:
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
            except Exception:
                pass

        raw_rows: List[dict] = []
        current_tx: Optional[dict] = None

        all_lines: List[Tuple[int, str]] = []
        for page in doc.pages:
            for line in page.lines:
                all_lines.append((page.page_number, line))

        in_transactions_table = False
        table_headers = ["DATE", "PARTICULARS", "NARRATION", "DESCRIPTION", "WITHDRAWAL", "DEPOSIT", "BALANCE", "CHQ"]

        for page_num, line in all_lines:
            upper_line = line.upper()
            
            # Check for table header row
            if not in_transactions_table:
                header_matches = sum(1 for h in table_headers if h in upper_line)
                if header_matches >= 2:
                    in_transactions_table = True
                    continue
                # Or if we encounter a line starting with a date directly
                if self.DATE_START_REGEX.match(line):
                    in_transactions_table = True

            if not in_transactions_table:
                continue

            # Check if line indicates end of statement or summary
            if any(term in upper_line for term in ["TOTAL WITHDRAWAL", "TOTAL DEPOSIT", "CLOSING BALANCE:", "STATEMENT SUMMARY", "PAGE "]):
                if current_tx:
                    raw_rows.append(current_tx)
                    current_tx = None
                continue

            # Check if this line begins a new transaction
            date_match = self.DATE_START_REGEX.match(line)
            if date_match:
                if current_tx:
                    raw_rows.append(current_tx)
                
                raw_date_str = date_match.group(1)
                tx_date = normalize_date(raw_date_str)
                remainder = line[date_match.end():].strip()
                
                current_tx = {
                    "date": tx_date,
                    "raw_date": raw_date_str,
                    "page": page_num,
                    "narration_parts": [remainder],
                    "amounts": [],
                    "source_lines": [line]
                }
            elif current_tx:
                # Continuation line for the current transaction's narration or amounts
                current_tx["narration_parts"].append(line)
                current_tx["source_lines"].append(line)

        # Append last transaction
        if current_tx:
            raw_rows.append(current_tx)

        # Now process the raw rows into canonical transactions
        transactions: List[TransactionItem] = []
        statement_from: Optional[date] = None
        statement_to: Optional[date] = None
        previous_balance: Optional[Decimal] = None
        quant = Decimal("0.01")

        for idx, row in enumerate(raw_rows):
            if not row["date"]:
                continue
            
            full_line_text = " ".join(row["narration_parts"])
            # Extract numbers that look like currency amounts
            tokens = full_line_text.split()
            amounts_found = []
            non_amount_tokens = []
            
            for t in tokens:
                cleaned_t = t.replace(',', '').replace('Cr', '').replace('Dr', '').replace('CR', '').replace('DR', '')
                try:
                    # Check if float convertible with digits
                    if any(c.isdigit() for c in cleaned_t):
                        # Avoid standalone integers that look like cheque numbers or phone numbers unless formatted as amount
                        if '.' in cleaned_t or ',' in t:
                            val = Decimal(cleaned_t)
                            amounts_found.append(val)
                            continue
                except Exception:
                    pass
                non_amount_tokens.append(t)

            raw_narration = " ".join(non_amount_tokens)
            narration = clean_narration(raw_narration)
            ref_no = extract_reference_number(full_line_text)

            debit = Decimal("0.00")
            credit = Decimal("0.00")
            balance = None

            # Standard 3 amounts found: [Debit or Credit, Balance] or [Debit, Credit, Balance]
            if len(amounts_found) >= 3:
                # [Debit, Credit, Balance]
                raw_debit = amounts_found[0].quantize(quant)
                raw_credit = amounts_found[1].quantize(quant)
                balance = amounts_found[-1].quantize(quant)
                
                # In proper bank statements, one of debit/credit should be 0.
                # If both are non-zero, it's likely a parsing artifact from amount extraction.
                if raw_debit > Decimal("0.00") and raw_credit > Decimal("0.00"):
                    # Use running-balance math to disambiguate
                    net = raw_credit - raw_debit
                    if previous_balance is not None:
                        expected_after_credit = (previous_balance + raw_credit).quantize(quant)
                        expected_after_debit = (previous_balance - raw_debit).quantize(quant)
                        expected_net = (previous_balance + net).quantize(quant)
                        if expected_after_credit == balance:
                            credit = raw_credit
                        elif expected_after_debit == balance:
                            debit = raw_debit
                        elif expected_net == balance:
                            if net > Decimal("0.00"):
                                credit = net
                            else:
                                debit = abs(net)
                        else:
                            # Can't resolve — keep the larger as the transaction, zero the smaller
                            if raw_debit >= raw_credit:
                                debit = raw_debit
                            else:
                                credit = raw_credit
                    else:
                        # No previous balance — keep the larger as the transaction
                        if raw_debit >= raw_credit:
                            debit = raw_debit
                        else:
                            credit = raw_credit
                else:
                    debit = raw_debit
                    credit = raw_credit
            elif len(amounts_found) == 2:
                # [Transaction Amount, Balance]
                amt = amounts_found[0].quantize(quant)
                balance = amounts_found[1].quantize(quant)
                
                # Check explicit (Dr) / (Cr) indicators first (e.g. Union Bank, Canara Bank)
                upper_narr = full_line_text.upper()
                if re.search(r'\(\s*DR\s*\)', upper_narr):
                    debit = amt
                elif re.search(r'\(\s*CR\s*\)', upper_narr):
                    credit = amt
                elif previous_balance is not None:
                    # PRIMARY: Use running-balance math when previous balance is available
                    # prev_bal - amt == bal → DEBIT, prev_bal + amt == bal → CREDIT
                    expected_debit = (previous_balance - amt).quantize(quant)
                    expected_credit = (previous_balance + amt).quantize(quant)
                    if expected_debit == balance:
                        debit = amt
                    elif expected_credit == balance:
                        credit = amt
                    else:
                        # Running balance math failed — use narration fallback
                        if any(w in upper_narr for w in ["CREDIT", "DEPOSIT", "BY TRANSFER", "SALARY", "REFUND", "INTEREST RECEIVED", "INT RECD"]):
                            credit = amt
                        else:
                            debit = amt
                else:
                    # No previous balance available — use narration heuristic (EXCLUDING bare "CR")
                    if any(w in upper_narr for w in ["CREDIT", "DEPOSIT", "BY TRANSFER", "SALARY", "REFUND", "INTEREST RECEIVED", "INT RECD"]):
                        credit = amt
                    else:
                        debit = amt
            elif len(amounts_found) == 1:
                amt = amounts_found[0].quantize(quant)
                debit = amt

            # Track running balance for next iteration
            if balance is not None:
                previous_balance = balance
            elif previous_balance is not None:
                previous_balance = previous_balance + credit - debit

            if not statement_from or row["date"] < statement_from:
                statement_from = row["date"]
            if not statement_to or row["date"] > statement_to:
                statement_to = row["date"]

            tx_item = TransactionItem(
                id=f"tx-{idx+1}",
                row_index=idx+1,
                date=row["date"],
                value_date=row["date"],
                narration=narration or "Transaction",
                reference=ref_no,
                debit=debit,
                credit=credit,
                balance=balance,
                voucher_type="Payment" if debit > 0 else "Receipt",
                source_page=row.get("page", 1),
                source_lines=row.get("source_lines", []),
                source_row_index=idx+1,
                parser_name=self.parser_key
            )
            transactions.append(tx_item)

        statement = CanonicalStatement(
            bank=self.bank_name,
            statement_format=self.format_name,
            statement_from=statement_from,
            statement_to=statement_to,
            transactions=transactions
        )

        # Run running balance validation & confidence scoring
        return validate_statement_balances(statement)
