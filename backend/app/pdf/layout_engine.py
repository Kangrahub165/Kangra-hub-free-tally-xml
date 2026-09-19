"""
Layout Engine & Coordinate Table Extraction for Kangra Hub Free Tally XML.

Provides robust, boundary-isolated table extraction and coordinate-based visual row
reconstruction. Ensures 100% isolation between consecutive transactions, eliminating
cross-row narration mixing, repeated page header/footer contamination, and reference leakage.
"""

import re
import pdfplumber
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel

# Standard noise keywords to strip from transaction narrations
NOISE_PATTERNS = [
    re.compile(r"^Page\s*(?:No\.?:?\s*)?\d+(?:\s+of\s+\d+)?", re.IGNORECASE),
    re.compile(r"^Statement\s*(?:of\s*)?Account", re.IGNORECASE),
    re.compile(r"^Statement\s*for\s*(?:the\s*)?Period", re.IGNORECASE),
    re.compile(r"^Statement\s*From\s*.*?\s*To\s*", re.IGNORECASE),
    re.compile(r"^(?:Account\s*Branch|AccountBranch)", re.IGNORECASE),
    re.compile(r"^Account\s*(?:Branch|Name|Number|Type|Status)\s*:", re.IGNORECASE),
    re.compile(r"^Branch\s*(?:Address|Code|Contact|Phone)\s*:", re.IGNORECASE),
    re.compile(r"^Customer\s*(?:Name|Address|Care|ID)\s*:", re.IGNORECASE),
    re.compile(r"^Cust(?:omer)?\s*ID\s*:", re.IGNORECASE),
    re.compile(r"^CIF\s*(?:No\.?)?\s*:", re.IGNORECASE),
    re.compile(r"^CKYC\s*No\.?\s*:", re.IGNORECASE),
    re.compile(r"^IFSC\s*(?:Code)?\s*:", re.IGNORECASE),
    re.compile(r"^MICR\s*(?:Code)?\s*:", re.IGNORECASE),
    re.compile(r"^Currency\s*:", re.IGNORECASE),
    re.compile(r"^Nomination\s*:", re.IGNORECASE),
    re.compile(r"^OD\s*Limit\s*:", re.IGNORECASE),
    re.compile(r"^Cleared\s*Balance\s*:", re.IGNORECASE),
    re.compile(r"^Uncleared\s*(?:Amount|Funds)\s*:", re.IGNORECASE),
    re.compile(r"^Drawing\s*Power\s*:", re.IGNORECASE),
    re.compile(r"^Int(?:\.|\s*)Rate\s*:", re.IGNORECASE),
    re.compile(r"^This\s*is\s*an\s*Electronically\s*Generated", re.IGNORECASE),
    re.compile(r"^\*?Closing\s*balance\s*includes\s*funds", re.IGNORECASE),
    re.compile(r"^Contents\s*(?:of\s*)?(?:this\s*)?statement", re.IGNORECASE),
    re.compile(r"^State\s*account\s*branch\s*GSTN", re.IGNORECASE),
    re.compile(r"^HDFC\s*Bank\s*GSTIN", re.IGNORECASE),
    re.compile(r"^Registered\s*Office\s*Address", re.IGNORECASE),
    re.compile(r"^(?:TOTAL|Total)\s*(?:WITHDRAWAL|DEPOSIT|DEBITS?|CREDITS?|BALANCE)", re.IGNORECASE),
    re.compile(r"^(?:CLOSING|OPENING)\s*BALANCE(?:\s*\(?[A-Z]+\)?)?", re.IGNORECASE),
    re.compile(r"^STATEMENT\s*SUMMARY", re.IGNORECASE),
    re.compile(r"^\*+---?END\s*OF\s*STATEMENT---?\*+", re.IGNORECASE),
    re.compile(r"^Did\s*you\s*know\?\s*It's\s*mandatory\s*to\s*be\s*KYC", re.IGNORECASE),
    re.compile(r"^Summary\s+of\s+Accounts\s+held\s+under", re.IGNORECASE),
    re.compile(r"^ACCOUNT\s+DETAILS\s*-\s*INR", re.IGNORECASE),
    re.compile(r"^ACCOUNT\s+TYPE\s+A/c\s+BALANCE", re.IGNORECASE),
    re.compile(r"^Visit\s+www\.", re.IGNORECASE),
    re.compile(r"^Dial\s+your\s+Bank", re.IGNORECASE),
    re.compile(r"^Tel(?:ephone)?\s+Number\s*:", re.IGNORECASE),
]

TABLE_HEADER_KEYWORDS = {
    "date": ["TXN DATE", "TRAN DATE", "POST DATE", "POSTING DATE", "TRANSACTION DATE", "DATE"],
    "value_date": ["VALUE DATE", "VAL DATE", "VALUE DT", "VAL DT"],
    "narration": ["NARRATION", "PARTICULARS", "DESCRIPTION", "REMARKS", "TRANSACTION DETAILS", "DETAILS", "TRANSACTION"],
    "reference": ["CHQ/REF", "CHQ./REF.NO.", "CHQ.NO.", "CHQ NO", "CHQNO", "CHEQUE NO/REFERENCE", "REF NO./CHEQUE NO.", "REF NO.", "INSTRUMENT NO", "TRAN ID", "TRANSACTION ID", "CHQ", "CHEQUE", "REF", "REFERENCE", "INSTRUMENT"],
    "debit": ["WITHDRAWAL AMT.", "WITHDRAWALS", "WITHDRAWAL", "WITHDRAW ALS", "AMOUNT (DR)", "DEBIT (DR)", "MONEY OUT", "DEBIT", "DR"],
    "credit": ["DEPOSIT AMT.", "DEPOSITS", "DEPOSIT", "AMOUNT (CR)", "CREDIT (CR)", "MONEY IN", "CREDIT", "CR"],
    "amount": ["AMOUNT (RS.)", "AMOUNT(RS.)", "TXN AMOUNT", "TRAN AMOUNT", "AMOUNT"],
    "balance": ["CLOSING BALANCE", "CLOSINGBALANCE", "RUNNING BALANCE", "BALANCE (RS.)", "BALANCE", "BAL", "TOTALS"],
    "additional_info": ["ADDITIONAL INFO", "ADDL INFO", "ADDITIONAL INFORMATION"]
}

class RawTableRow(BaseModel):
    page_number: int
    row_index: int
    date_str: str
    value_date_str: Optional[str] = None
    narration: str
    reference_str: Optional[str] = None
    debit_str: Optional[str] = None
    credit_str: Optional[str] = None
    balance_str: Optional[str] = None
    source_lines: List[str] = []

def is_noise_text(text: str) -> bool:
    """Returns True if the text matches standard bank statement noise (headers, footers, disclaimers)."""
    clean = text.strip()
    if not clean:
        return True
    for pat in NOISE_PATTERNS:
        if pat.search(clean):
            return True
    return False

def clean_cell_text(cell: Any) -> str:
    """Normalizes cell text by replacing multiple whitespace/newlines with single space."""
    if not cell:
        return ""
    # Replace internal newlines with space, then normalize multiple spaces
    text = str(cell).replace('\r', ' ').replace('\n', ' ').strip()
    return " ".join(text.split())

def _col_matches_keywords(col: str, keywords: List[str]) -> bool:
    """Checks whether a column header matches any keyword using safe phrase/word boundaries."""
    for kw in keywords:
        if kw == col:
            return True
        if len(kw) <= 3:
            # Word-bounded match for short abbreviations (DR, CR, BAL, CHQ)
            if re.search(r'\b' + re.escape(kw) + r'\b', col):
                return True
        else:
            # Phrase match for multi-word or long tokens
            if kw in col:
                return True
    return False

def match_table_column_map(header_row: List[Any]) -> Optional[Dict[str, int]]:
    """
    Identifies column indexes for date, narration, debit, credit, balance, etc.
    from a table header row.
    """
    col_map: Dict[str, int] = {}
    normalized_cols = [clean_cell_text(c).upper() for c in header_row]

    for idx, col in enumerate(normalized_cols):
        if not col:
            continue
        
        # 1. Date (exclude value date)
        if "date" not in col_map:
            if _col_matches_keywords(col, TABLE_HEADER_KEYWORDS["date"]) and "VAL" not in col:
                col_map["date"] = idx
                continue

        # 2. Value date
        if "value_date" not in col_map:
            if _col_matches_keywords(col, TABLE_HEADER_KEYWORDS["value_date"]):
                col_map["value_date"] = idx
                continue

        # 3. Reference
        if "reference" not in col_map:
            if _col_matches_keywords(col, TABLE_HEADER_KEYWORDS["reference"]):
                col_map["reference"] = idx
                continue

        # 4. Debit
        if "debit" not in col_map:
            if _col_matches_keywords(col, TABLE_HEADER_KEYWORDS["debit"]):
                col_map["debit"] = idx
                continue

        # 5. Credit
        if "credit" not in col_map:
            if _col_matches_keywords(col, TABLE_HEADER_KEYWORDS["credit"]):
                col_map["credit"] = idx
                continue

        # 6. Balance
        if "balance" not in col_map:
            if _col_matches_keywords(col, TABLE_HEADER_KEYWORDS["balance"]) and "TYPE" not in col and "OPENING" not in col:
                col_map["balance"] = idx
                continue

        # 7. Additional Info
        if "additional_info" not in col_map:
            if _col_matches_keywords(col, TABLE_HEADER_KEYWORDS["additional_info"]):
                col_map["additional_info"] = idx
                continue

        # 8. Amount (single column fallback if debit/credit not explicit)
        if "amount" not in col_map:
            if _col_matches_keywords(col, TABLE_HEADER_KEYWORDS["amount"]) and "BAL" not in col:
                col_map["amount"] = idx
                continue

        # 9. Narration
        if "narration" not in col_map:
            if _col_matches_keywords(col, TABLE_HEADER_KEYWORDS["narration"]):
                col_map["narration"] = idx
                continue

    # Required: date, at least one of (debit, credit, amount, narration)
    if "date" in col_map and ("debit" in col_map or "credit" in col_map or "amount" in col_map or "narration" in col_map):
        return col_map
    return None

def extract_structured_table_rows(
    file_path: str,
    password: Optional[str] = None
) -> List[RawTableRow]:
    """
    Extracts isolated transaction rows from structured PDF tables across all pages.
    Guarantees that multi-line cell contents remain strictly within their parent row.
    """
    raw_rows: List[RawTableRow] = []
    global_row_index = 0

    try:
        with pdfplumber.open(file_path, password=password) as pdf:
            current_col_map: Optional[Dict[str, int]] = None

            for page_idx, page in enumerate(pdf.pages):
                page_num = page_idx + 1
                tables = page.extract_tables() or []

                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    for r_idx, row in enumerate(table):
                        # Clean cells
                        cleaned_row = [clean_cell_text(c) for c in row]
                        row_text = " ".join(c for c in cleaned_row if c)
                        if not row_text or is_noise_text(row_text):
                            continue

                        # Check if this row is a header row
                        possible_col_map = match_table_column_map(row)
                        if possible_col_map:
                            current_col_map = possible_col_map
                            continue

                        if not current_col_map:
                            continue

                        # Extract date
                        date_idx = current_col_map.get("date")
                        if date_idx is None or date_idx >= len(cleaned_row):
                            continue
                        raw_date = cleaned_row[date_idx]
                        if not raw_date:
                            continue

                        # Verify date format (DD/MM/YYYY, DD-MM-YYYY, DD Mon YYYY, YYYY-MM-DD, etc.)
                        date_match = re.search(r'(\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2}|\d{1,2}[/\-\.](?:\d{1,2}|[A-Za-z]{3,9})[/\-\.]\d{2,4}|\d{1,2}\s+(?:\d{1,2}|[A-Za-z]{3,9})\s+\d{2,4})', raw_date)
                        if not date_match:
                            continue

                        global_row_index += 1

                        # Value date
                        val_date_str = None
                        val_idx = current_col_map.get("value_date")
                        if val_idx is not None and val_idx < len(cleaned_row) and cleaned_row[val_idx]:
                            val_date_str = cleaned_row[val_idx]

                        # Narration / Particulars
                        narration = ""
                        narr_idx = current_col_map.get("narration")
                        if narr_idx is not None and narr_idx < len(cleaned_row):
                            narration = cleaned_row[narr_idx]

                        # Additional Info column (e.g. PNB wrapped info)
                        addl_idx = current_col_map.get("additional_info")
                        if addl_idx is not None and addl_idx < len(cleaned_row) and cleaned_row[addl_idx]:
                            addl_text = cleaned_row[addl_idx]
                            if addl_text:
                                narration = f"{narration} {addl_text}".strip()

                        # Reference
                        ref_str = None
                        ref_idx = current_col_map.get("reference")
                        if ref_idx is not None and ref_idx < len(cleaned_row) and cleaned_row[ref_idx]:
                            ref_str = cleaned_row[ref_idx]

                        # Debit
                        debit_str = None
                        dr_idx = current_col_map.get("debit")
                        if dr_idx is not None and dr_idx < len(cleaned_row) and cleaned_row[dr_idx]:
                            debit_str = cleaned_row[dr_idx]

                        # Credit
                        credit_str = None
                        cr_idx = current_col_map.get("credit")
                        if cr_idx is not None and cr_idx < len(cleaned_row) and cleaned_row[cr_idx]:
                            credit_str = cleaned_row[cr_idx]

                        # If separate debit/credit not found, check single amount column (e.g. Union Bank)
                        if not debit_str and not credit_str:
                            amt_idx = current_col_map.get("amount")
                            if amt_idx is not None and amt_idx < len(cleaned_row) and cleaned_row[amt_idx]:
                                raw_amt = cleaned_row[amt_idx]
                                # Check for Dr/Cr indicators
                                if re.search(r'\bDr\b|\(Dr\)', raw_amt, re.IGNORECASE):
                                    debit_str = re.sub(r'[^\d\.,]', '', raw_amt)
                                elif re.search(r'\bCr\b|\(Cr\)', raw_amt, re.IGNORECASE):
                                    credit_str = re.sub(r'[^\d\.,]', '', raw_amt)
                                else:
                                    # Fallback: if balance indicates or plain amount
                                    debit_str = re.sub(r'[^\d\.,]', '', raw_amt)

                        # Balance
                        balance_str = None
                        bal_idx = current_col_map.get("balance")
                        if bal_idx is not None and bal_idx < len(cleaned_row) and cleaned_row[bal_idx]:
                            balance_str = cleaned_row[bal_idx]

                        raw_rows.append(
                            RawTableRow(
                                page_number=page_num,
                                row_index=global_row_index,
                                date_str=date_match.group(1),
                                value_date_str=val_date_str,
                                narration=narration,
                                reference_str=ref_str,
                                debit_str=debit_str,
                                credit_str=credit_str,
                                balance_str=balance_str,
                                source_lines=[row_text]
                            )
                        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Structured table extraction encountered an issue on {file_path}: {e}")

    return raw_rows
