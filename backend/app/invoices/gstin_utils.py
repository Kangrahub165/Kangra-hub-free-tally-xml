"""
GSTIN checksum and OCR repair, Indian amount parsing, and validation helpers.
Conforms strictly to PRD Appendix C.
"""
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from itertools import product
from typing import Optional, List, Tuple, Dict, Any

# ---------- GSTIN ----------
CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_RE = re.compile(
    r'^(0[1-9]|[12][0-9]|3[0-8]|9[79])[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$'
)

def gstin_check_char(first14: str) -> str:
    """Calculates the Mod-36 check character for the first 14 characters of a GSTIN."""
    total = 0
    for i, ch in enumerate(first14):
        prod = CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += prod // 36 + prod % 36
    return CHARS[(36 - total % 36) % 36]

def gstin_valid(g: str) -> bool:
    """Returns True if the GSTIN matches the format and has a valid checksum."""
    if not g:
        return False
    g = g.strip().upper()
    return bool(GSTIN_RE.match(g)) and gstin_check_char(g[:14]) == g[14]

TO_DIGIT  = {'O': '0', 'Q': '0', 'I': '1', 'L': '1', 'Z': '2', 'S': '5', 'G': '6', 'B': '8'}
TO_LETTER = {'0': 'O', '1': 'I', '2': 'Z', '5': 'S', '6': 'G', '8': 'B'}

def gstin_repair(raw: str) -> Optional[str]:
    """Fix OCR letter/digit confusions by position. Accept ONLY if checksum passes."""
    if not raw:
        return None
    g = re.sub(r'[^0-9A-Za-z]', '', raw).upper()
    if len(g) != 15:
        return None
    kinds = "DD" + "LLLLL" + "DDDD" + "L" + "A" + "Z" + "A"  # D digit, L letter, A any
    options = []
    for ch, k in zip(g, kinds):
        if k == "D":
            options.append([TO_DIGIT.get(ch, ch)])
        elif k == "L":
            options.append([TO_LETTER.get(ch, ch)])
        elif k == "Z":
            options.append(["Z"])
        else:
            options.append(sorted({ch, TO_DIGIT.get(ch, ch), TO_LETTER.get(ch, ch)}))
    for combo in product(*options):
        cand = "".join(combo)
        if gstin_valid(cand):
            return cand
    return None

# ---------- Indian amounts ----------
def parse_amount(s: Any) -> Optional[Decimal]:
    """
    Parses Indian amount representations into Decimal.
    Handles Indian commas (1,23,456.50), rupee symbols, and brackets for negatives (1,200.00).
    """
    if s is None:
        return None
    if isinstance(s, Decimal):
        return s
    t = str(s).strip()
    if not t:
        return None
    neg = (t.startswith('(') and t.endswith(')')) or t.startswith('-')
    t = re.sub(r'(?i)(rs\.?|inr|₹|/-)', '', t)
    t = re.sub(r'[,\s()\-]', '', t)  # 1,23,456.50 -> 123456.50
    try:
        d = Decimal(t)
    except InvalidOperation:
        return None
    res = -d if neg else d
    return res.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

# ---------- Validation helpers ----------
def close(a: Any, b: Any, abs_tol: Decimal = Decimal("1.00"), rel_tol: Decimal = Decimal("0.005")) -> bool:
    """Checks if two decimal values are close within tolerance (max(abs_tol, abs(b) * rel_tol))."""
    if a is None or b is None:
        return False
    a_dec, b_dec = Decimal(str(a)), Decimal(str(b))
    return abs(a_dec - b_dec) <= max(abs_tol, abs(b_dec) * rel_tol)

def check_line(item: Dict[str, Any]) -> List[Tuple[str, str]]:
    """item values are Decimals. Returns a list of rule failures for one row."""
    errs = []
    qty = item.get("qty") or Decimal("0.00")
    rate = item.get("rate") or Decimal("0.00")
    gross = qty * rate
    disc = item.get("discount_amount")
    if disc is None:
        disc_pct = item.get("discount_pct") or Decimal("0.00")
        disc = gross * disc_pct / Decimal("100")
    
    taxable = item.get("taxable") or Decimal("0.00")
    if not close(gross - disc, taxable):
        errs.append(("V09", "qty*rate-discount != taxable"))
        
    gst_rate = item.get("gst_rate") or Decimal("0.00")
    exp_tax = taxable * gst_rate / Decimal("100")
    got_tax = sum(item.get(k) or Decimal("0.00") for k in ("cgst", "sgst", "igst"))
    if got_tax > Decimal("0.00") and not close(exp_tax, got_tax):
        errs.append(("V10", "tax amount != taxable*rate"))
    return errs

def exclusive_from_inclusive(amount_incl: Decimal, gst_rate: Decimal) -> Decimal:
    """Computes exclusive value from inclusive: amount_incl * 100 / (100 + gst_rate)."""
    if gst_rate <= Decimal("0.00"):
        return amount_incl.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return (amount_incl * Decimal("100") / (Decimal("100") + gst_rate)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
