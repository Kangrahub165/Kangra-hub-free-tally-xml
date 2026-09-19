import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Optional
from dateutil import parser as date_parser

ISO_DATE_REGEX = re.compile(r'^\b(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})\b')

def normalize_date(raw_date_str: str) -> Optional[date]:
    """
    Parses dates in Indian and international formats into a standard date object.
    Handles DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, DD-Mon-YYYY, DD Mon YYYY, YYYY-MM-DD.
    """
    if not raw_date_str:
        return None
    cleaned = raw_date_str.strip()

    # Check ISO format YYYY-MM-DD first
    iso_match = ISO_DATE_REGEX.match(cleaned)
    if iso_match:
        try:
            return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        except ValueError:
            pass
    
    # Day-first parsing for Indian formats (DD/MM/YYYY, DD-MM-YYYY, DD Mon YYYY)
    try:
        dt = date_parser.parse(cleaned, dayfirst=True)
        return dt.date()
    except Exception:
        pass

    return None

def normalize_amount(raw_amount_str: str) -> Decimal:
    """
    Normalizes amounts into precise 2-decimal Decimals.
    Handles:
    - Commas (e.g. 1,50,000.00)
    - Currency symbols (₹, Rs, Rs., INR)
    - Suffixes like Cr / Dr
    - Parentheses (negative)
    - Negative minus signs
    """
    if not raw_amount_str:
        return Decimal("0.00")
    
    cleaned = raw_amount_str.strip()
    
    # Strip currency symbols and text (including Rs.)
    cleaned = re.sub(r'[₹$€£]', '', cleaned)
    cleaned = re.sub(r'Rs\.?', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\b(?:INR|Overdraft)\b', '', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(',', '').strip()

    is_negative = False
    if cleaned.startswith('(') and cleaned.endswith(')'):
        is_negative = True
        cleaned = cleaned[1:-1]
    
    # Strip trailing Dr/Cr, (Dr)/(Cr), Dr., Cr.
    cleaned = re.sub(r'(?i)\(?\s*(?:CR|DR)\.?\)?$', '', cleaned).strip()

    if not cleaned:
        return Decimal("0.00")

    try:
        val = Decimal(cleaned)
        if is_negative:
            val = -abs(val)
        return val.quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0.00")

def clean_narration(raw_narration: str) -> str:
    """Cleans up multi-line, redundant whitespace, and excessive special characters from narration."""
    if not raw_narration:
        return ""
    cleaned = re.sub(r'[\r\n\t]+', ' ', raw_narration)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    return cleaned.strip()

def extract_reference_number(narration: str) -> str:
    """Extracts UPI, IMPS, NEFT, RTGS or Cheque reference number if present."""
    patterns = [
        r'\bUPI/(?:CR|DR)?/?(\d{10,14})\b',
        r'\bIMPS/P2A/(\d{10,14})\b',
        r'\bNEFT/([A-Z0-9]{10,18})\b',
        r'\bRTGS/([A-Z0-9]{10,18})\b',
        r'\b(?:CHQ|CHEQUE|REF)[\s\.:#]+([A-Za-z0-9]+)\b'
    ]
    for p in patterns:
        m = re.search(p, narration, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""
