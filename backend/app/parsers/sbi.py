import re
import pdfplumber
from decimal import Decimal
from datetime import date
from typing import List, Optional, Tuple, Dict, Any
from app.parsers.base import BaseStatementParser
from app.pdf.extractor import ExtractedDocument
from app.transactions.model import CanonicalStatement, TransactionItem
from app.transactions.normalizer import normalize_date, normalize_amount, clean_narration, extract_reference_number
from app.pdf.layout_engine import extract_structured_table_rows

class SBIParser(BaseStatementParser):
    """
    Dedicated parser for State Bank of India (SBI) statements.
    Supports both structured vector table extraction (standard online banking PDFs)
    and columnar text extraction (synthetic / borderless statements).
    Extracts all 8 SBI columns with mathematical running balance reconciliation.
    """

    def __init__(self):
        super().__init__(
            bank_name="State Bank of India (SBI)",
            format_name="Savings & Current Standard",
            parser_key="sbi_standard",
            version="1.2"
        )

    def can_parse(self, doc: ExtractedDocument) -> bool:
        first_page = doc.first_page_text.upper()
        return "STATE BANK" in first_page or "SBIN0" in first_page or "ONLINESBI" in first_page or "EB-MSME-CC" in first_page

    def parse(self, doc: ExtractedDocument) -> CanonicalStatement:
        transactions: List[TransactionItem] = []
        statement_from: Optional[date] = None
        statement_to: Optional[date] = None
        opening_balance: Optional[Decimal] = None

        # 1. Extract opening balance from header if present
        open_match = re.search(
            r'Balance\s+as\s+on\s+[^\n:]+:\s*(?:(?:\(?cid:9\)?|INR|Rs\.?)\s*)?([0-9,\.\-]+)',
            doc.first_page_text,
            re.IGNORECASE
        )
        if open_match:
            try:
                opening_balance = Decimal(open_match.group(1).replace(',', '').strip())
            except Exception:
                pass

        # 2. Try structured vector table extraction first
        if doc.file_path:
            try:
                raw_rows = extract_structured_table_rows(
                    doc.file_path,
                    doc.password,
                    start_page=getattr(doc, "start_page", 1),
                    max_pages=getattr(doc, "max_pages", None),
                    allowed_page_numbers=getattr(doc, "page_numbers", None)
                )
                if raw_rows:
                    for r in raw_rows:
                        tx_date = normalize_date(r.date_str)
                        if not tx_date:
                            continue
                        val_date = normalize_date(r.value_date_str) if r.value_date_str else tx_date
                        debit = normalize_amount(r.debit_str) if r.debit_str else Decimal("0.00")
                        credit = normalize_amount(r.credit_str) if r.credit_str else Decimal("0.00")
                        bal = normalize_amount(r.balance_str) if r.balance_str else None
                        clean_narr = clean_narration(r.narration)
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
            except Exception:
                transactions = []

        if not transactions:
            # Fallback to line-based parsing for text-only synthetic PDFs
            transactions, statement_from, statement_to = self._parse_text_lines(doc)

        # 3. Mathematical Running Balance Validation
        validated_transactions = self._validate_running_balances(transactions, opening_balance)

        total_debit = sum(t.debit for t in validated_transactions)
        total_credit = sum(t.credit for t in validated_transactions)
        calc_closing = None
        if opening_balance is not None:
            calc_closing = (opening_balance + total_credit - total_debit).quantize(Decimal("0.01"))

        stmt = CanonicalStatement(
            bank=self.bank_name,
            statement_format=self.format_name,
            statement_from=statement_from,
            statement_to=statement_to,
            transactions=validated_transactions,
            opening_balance=opening_balance,
            closing_balance=validated_transactions[-1].balance if validated_transactions else opening_balance,
            calculated_closing_balance=calc_closing,
            total_debit=total_debit,
            total_credit=total_credit
        )

        # 4. Calculate statement confidence
        if validated_transactions:
            valid_count = sum(1 for t in validated_transactions if t.validation_status == "VALID")
            stmt.confidence_score = round((valid_count / len(validated_transactions)) * 100.0, 2)
        else:
            stmt.confidence_score = 0.0

        return stmt

    def _map_columns(self, header_row) -> Optional[Dict[str, int]]:
        col_map: Dict[str, int] = {}
        for idx, col in enumerate(header_row):
            if not col:
                continue
            clean = str(col).replace('\n', ' ').strip().upper()
            if "TXN DATE" in clean or clean == "DATE":
                col_map["date"] = idx
            elif "VALUE DATE" in clean or "VAL DATE" in clean:
                col_map["value_date"] = idx
            elif "DESCRIPTION" in clean or "PARTICULARS" in clean:
                col_map["description"] = idx
            elif "REF" in clean or "CHEQUE" in clean or "CHQ" in clean:
                col_map["reference"] = idx
            elif "BRANCH" in clean:
                col_map["branch"] = idx
            elif "DEBIT" in clean or "WITHDRAWAL" in clean:
                col_map["debit"] = idx
            elif "CREDIT" in clean or "DEPOSIT" in clean:
                col_map["credit"] = idx
            elif "BALANCE" in clean:
                col_map["balance"] = idx

        if "date" in col_map and ("debit" in col_map or "credit" in col_map) and "balance" in col_map:
            return col_map
        return None

    def _parse_table_row(self, row, col_map: Dict[str, int]) -> Optional[TransactionItem]:
        date_idx = col_map.get("date")
        if date_idx is None or date_idx >= len(row) or not row[date_idx]:
            return None
        
        raw_date = " ".join(str(row[date_idx]).split())
        m_date = re.search(r'(\d{1,2}(?:[/\-\.]|\s+)(?:\d{1,2}|[A-Za-z]{3,9})(?:[/\-\.]|\s+)\d{2,4})', raw_date)
        parsed_date = normalize_date(m_date.group(1)) if m_date else normalize_date(raw_date)
        if not parsed_date:
            return None

        # Value date
        val_date = parsed_date
        val_idx = col_map.get("value_date")
        if val_idx is not None and val_idx < len(row) and row[val_idx]:
            raw_val = " ".join(str(row[val_idx]).split())
            m_val = re.search(r'(\d{1,2}(?:[/\-\.]|\s+)(?:\d{1,2}|[A-Za-z]{3,9})(?:[/\-\.]|\s+)\d{2,4})', raw_val)
            val_date = normalize_date(m_val.group(1)) if m_val else (normalize_date(raw_val) or parsed_date)

        # Description
        desc = ""
        desc_idx = col_map.get("description")
        if desc_idx is not None and desc_idx < len(row) and row[desc_idx]:
            desc = " ".join(str(row[desc_idx]).split())

        # Reference
        ref = ""
        ref_idx = col_map.get("reference")
        if ref_idx is not None and ref_idx < len(row) and row[ref_idx]:
            ref = " ".join(str(row[ref_idx]).split())
        if not ref or ref.upper() in ["TRANSFER FROM", "-", ""]:
            ref = extract_reference_number(desc) or ref

        # Debit
        debit = Decimal("0.00")
        dr_idx = col_map.get("debit")
        if dr_idx is not None and dr_idx < len(row) and row[dr_idx]:
            val_str = str(row[dr_idx]).replace(',', '').strip()
            if val_str:
                try:
                    debit = Decimal(val_str).quantize(Decimal("0.01"))
                except Exception:
                    pass

        # Credit
        credit = Decimal("0.00")
        cr_idx = col_map.get("credit")
        if cr_idx is not None and cr_idx < len(row) and row[cr_idx]:
            val_str = str(row[cr_idx]).replace(',', '').strip()
            if val_str:
                try:
                    credit = Decimal(val_str).quantize(Decimal("0.01"))
                except Exception:
                    pass

        # Balance (supports negative overdraft/CC balances e.g. -7,38,460.86)
        balance = None
        bal_idx = col_map.get("balance")
        if bal_idx is not None and bal_idx < len(row) and row[bal_idx]:
            val_str = str(row[bal_idx]).replace(',', '').replace('Cr', '').replace('Dr', '').strip()
            if val_str:
                try:
                    balance = Decimal(val_str).quantize(Decimal("0.01"))
                except Exception:
                    pass

        # Disambiguate if both debit and credit extracted (table artifact)
        if debit > Decimal("0.00") and credit > Decimal("0.00"):
            if debit >= credit:
                credit = Decimal("0.00")
            else:
                debit = Decimal("0.00")

        # Skip rows with no financial movement
        if debit == Decimal("0.00") and credit == Decimal("0.00"):
            return None

        # Voucher Classification (directional per PRD: cash withdrawals -> Payment, cash deposits -> Receipt)
        if debit > Decimal("0.00"):
            voucher_type = "Payment"
        else:
            voucher_type = "Receipt"

        return TransactionItem(
            date=parsed_date,
            value_date=val_date,
            narration=clean_narration(desc) or "SBI Transaction",
            reference=ref or None,
            cheque_number=ref if (ref and ref.isdigit() and len(ref) <= 8) else None,
            instrument_number=ref if (ref and ref.isdigit() and len(ref) <= 8) else None,
            debit=debit,
            credit=credit,
            balance=balance,
            voucher_type=voucher_type,
            validation_status="VALID"
        )

    def _parse_text_lines(self, doc: ExtractedDocument) -> Tuple[List[TransactionItem], Optional[date], Optional[date]]:
        transactions: List[TransactionItem] = []
        statement_from: Optional[date] = None
        statement_to: Optional[date] = None
        previous_balance: Optional[Decimal] = None

        all_line_entries: List[Tuple[str, int]] = []
        for page in doc.pages:
            p_num = getattr(page, "page_number", 1)
            for line in page.lines:
                all_line_entries.append((line, p_num))

        in_table = False
        date_pattern = re.compile(r'^(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\b')

        current_tx = None
        for line, p_num in all_line_entries:
            upper = line.upper()
            if not in_table:
                if "DATE" in upper and ("WITHDRAWAL" in upper or "DEPOSIT" in upper or "PARTICULARS" in upper):
                    in_table = True
                    continue
                if date_pattern.match(line):
                    in_table = True

            if not in_table:
                continue

            # Skip statement summary and footer lines
            if any(term in upper for term in ["STATEMENT SUMMARY", "BROUGHT FORWARD", "*---END OF STATEMENT---*", "TOTAL DEBITS", "TOTAL CREDITS", "CLOSING BALANCE CR", "CLOSING BALANCE DR"]):
                if current_tx:
                    item, previous_balance = self._process_text_tx(current_tx, previous_balance)
                    if item:
                        transactions.append(item)
                        if not statement_from or item.date < statement_from:
                            statement_from = item.date
                        if not statement_to or item.date > statement_to:
                            statement_to = item.date
                    current_tx = None
                continue

            m = date_pattern.match(line)
            if m:
                if current_tx:
                    item, previous_balance = self._process_text_tx(current_tx, previous_balance)
                    if item:
                        transactions.append(item)
                        if not statement_from or item.date < statement_from:
                            statement_from = item.date
                        if not statement_to or item.date > statement_to:
                            statement_to = item.date
                current_tx = {
                    "raw_date": m.group(1),
                    "lines": [line[m.end():].strip()],
                    "source_page": p_num
                }
            elif current_tx:
                current_tx["lines"].append(line)

        if current_tx:
            item, previous_balance = self._process_text_tx(current_tx, previous_balance)
            if item:
                transactions.append(item)
                if not statement_from or item.date < statement_from:
                    statement_from = item.date
                if not statement_to or item.date > statement_to:
                    statement_to = item.date

        return transactions, statement_from, statement_to

    def _process_text_tx(self, tx_dict: dict, previous_balance: Optional[Decimal] = None) -> tuple:
        """
        Process a single text-based transaction row.
        Returns: (TransactionItem or None, updated_previous_balance)
        """
        parsed_date = normalize_date(tx_dict["raw_date"])
        if not parsed_date:
            return None, previous_balance

        full_text = " ".join(tx_dict["lines"])
        amounts = re.findall(r'([0-9,]+\.[0-9]{2})', full_text)
        debit = Decimal("0.00")
        credit = Decimal("0.00")
        balance = None
        quant = Decimal("0.01")

        if len(amounts) >= 3:
            raw_d = Decimal(amounts[-3].replace(',', ''))
            raw_c = Decimal(amounts[-2].replace(',', ''))
            balance = Decimal(amounts[-1].replace(',', ''))

            # Disambiguate if both debit and credit extracted (text parsing artifact)
            if raw_d > Decimal("0.00") and raw_c > Decimal("0.00"):
                if previous_balance is not None:
                    if (previous_balance - raw_d).quantize(quant) == balance:
                        debit = raw_d
                        credit = Decimal("0.00")
                    elif (previous_balance + raw_c).quantize(quant) == balance:
                        credit = raw_c
                        debit = Decimal("0.00")
                    else:
                        if raw_d >= raw_c:
                            debit = raw_d
                            credit = Decimal("0.00")
                        else:
                            credit = raw_c
                            debit = Decimal("0.00")
                else:
                    if raw_d >= raw_c:
                        debit = raw_d
                        credit = Decimal("0.00")
                    else:
                        credit = raw_c
                        debit = Decimal("0.00")
            else:
                debit = raw_d
                credit = raw_c
        elif len(amounts) == 2:
            amt = Decimal(amounts[-2].replace(',', ''))
            balance = Decimal(amounts[-1].replace(',', ''))
            # PRIMARY: Use running-balance math when previous balance is available
            if previous_balance is not None:
                expected_debit = (previous_balance - amt).quantize(quant)
                expected_credit = (previous_balance + amt).quantize(quant)
                if expected_debit == balance.quantize(quant):
                    debit = amt
                elif expected_credit == balance.quantize(quant):
                    credit = amt
                else:
                    # Fallback to narration heuristic (excluding bare "CR")
                    upper = full_text.upper()
                    if any(w in upper for w in ["CREDIT", "DEPOSIT", "BY TRANSFER", "SALARY", "REFUND", "INTEREST RECEIVED", "INT RECD"]):
                        credit = amt
                    else:
                        debit = amt
            else:
                # No previous balance — narration heuristic (excluding bare "CR")
                upper = full_text.upper()
                if any(w in upper for w in ["CREDIT", "DEPOSIT", "BY TRANSFER", "SALARY", "REFUND", "INTEREST RECEIVED", "INT RECD"]):
                    credit = amt
                else:
                    debit = amt

        narration = full_text
        for a in amounts:
            narration = narration.replace(a, "")
        narration = clean_narration(narration)

        updated_balance = balance if balance is not None else previous_balance
        voucher_type = "Payment" if debit > Decimal("0.00") else "Receipt"
        tx = TransactionItem(
            date=parsed_date,
            value_date=parsed_date,
            narration=narration or "SBI Transaction",
            reference=extract_reference_number(full_text) or None,
            debit=debit,
            credit=credit,
            balance=balance,
            voucher_type=voucher_type,
            source_page=tx_dict.get("source_page"),
            validation_status="VALID"
        )
        return tx, updated_balance

    def _validate_running_balances(
        self,
        transactions: List[TransactionItem],
        opening_balance: Optional[Decimal]
    ) -> List[TransactionItem]:
        curr_bal = opening_balance
        for idx, tx in enumerate(transactions):
            if curr_bal is not None:
                expected_bal = (curr_bal + tx.credit - tx.debit).quantize(Decimal("0.01"))
                if tx.balance is not None:
                    actual_bal = tx.balance.quantize(Decimal("0.01"))
                    if expected_bal != actual_bal:
                        tx.validation_status = "WARNING"
                        tx.validation_notes = f"Balance mismatch at row {idx+1}: Expected {expected_bal}, reported {actual_bal}"
                    else:
                        tx.validation_status = "VALID"
                        tx.validation_notes = None
                    curr_bal = actual_bal
                else:
                    tx.balance = expected_bal
                    tx.validation_status = "VALID"
                    curr_bal = expected_bal
            else:
                if tx.balance is not None:
                    curr_bal = tx.balance.quantize(Decimal("0.01"))
                tx.validation_status = "VALID"

        return transactions
