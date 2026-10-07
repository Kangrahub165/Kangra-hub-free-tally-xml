"""
Table Engine and Arithmetic Column Resolver for Indian Invoices (PRD v1.1 / Addendum 1).
Implements:
1. Header-driven column mapping with extensive synonyms (AD3, AD10)
2. Qty, unit, pack size, and MRP separation rules (AD4)
3. Arithmetic Column Solver (AD3, AD10)
4. Date-dependent GST rate resolution (AD5)
5. Arithmetic Tax-Inclusive vs Exclusive detection (AD6)
6. Canonical conversion to tax-exclusive model (AD6, AD10)
"""

import re
import itertools
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal as D, InvalidOperation, ROUND_HALF_UP
from difflib import SequenceMatcher
from typing import List, Dict, Tuple, Optional, Any, Set
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

# =====================================================================
# 1. Header text -> canonical role (Configurable synonyms dictionary)
# =====================================================================
HEADER_SYNONYMS: Dict[str, List[str]] = {
    "serial":       ["sr", "sr no", "sr. no.", "s no", "s. no.", "sno", "sl no", "sl. no.", "no", "no.", "#", "item no", "sl"],
    "description":  ["description", "description of goods", "particulars", "item", "item name",
                     "product", "product name", "goods", "name of item", "item description", "material description", "item details"],
    "hsn":          ["hsn", "hsn code", "hsn/sac", "hsn sac", "sac", "hsn sac code", "commodity code", "hsn/sac code"],
    "mrp":          ["mrp", "m r p", "m.r.p.", "max retail price", "list price", "retail price", "m.r.p",
                     "mrp (rs.)", "m.r.p. (rs.)", "mrp(rs)", "m.r.p.(rs)", "max price"],
    "pack_size":    ["pack", "pack size", "pkg", "size", "net wt", "net weight", "weight", "content", "packing", "pk size"],
    "billed_qty":   ["billed qty", "bill qty", "billed quantity", "billed", "inv qty", "invoice qty", "invoiced qty", "billed qnty"],
    "shipped_qty":  ["shipped qty", "ship qty", "shipped quantity", "dispatched qty", "disp qty", "dispatch qty", "despatched qty", "chalan qty", "challan qty", "supply qty", "delivered qty", "shipped", "dispatched"],
    "total_units":  ["total units", "total unit", "tot units", "tot unit", "total pieces", "total pcs", "tot pieces", "tot pcs", "tot. units", "tot units.", "tot. unit"],
    "qty":          ["qty", "quantity", "qnty", "qnty.", "nos", "no of units", "no. of units",
                     "qty.", "qty (nos)", "qty(nos)", "qty in nos", "quantity (nos)", "quantity (pcs)",
                     "qty / pcs", "qty/pcs", "units", "total qty", "pack qty",
                     "order qty", "accepted qty", "rec qty", "received qty", "quant"],
    "free_qty":     ["free", "free qty", "scheme qty", "sch qty", "bonus", "free item"],
    "unit":         ["unit", "uom", "u o m", "u.o.m.", "per", "unit of measure", "uqc", "unit/uom", "trade unit", "base unit"],
    "rate":         ["rate", "price", "unit price", "net rate", "basic rate", "ptr", "pts", "rate (rs.)",
                     "rate/unit", "unit rate", "rate/pcs", "rate/nos", "item rate", "price/unit", "rate (inr)"],
    "discount_pct": ["disc", "disc %", "discount %", "dis %", "scheme %", "disc. %", "trade disc %", "sch %"],
    "discount_amt": ["disc amt", "discount amt", "discount", "scheme amt", "disc amount", "trade discount"],
    "taxable":      ["taxable value", "taxable amt", "taxable amount", "taxable", "basic amount",
                     "amount before tax", "net amount", "assessable value", "taxable val"],
    "amount":       ["amount", "amt", "value", "total", "line total", "amount (rs.)", "net value", "item total"],
    "cgst_rate":    ["cgst %", "cgst rate", "cgst percentage", "central tax %", "central tax rate", "cgst", "cgst(%)", "cgst (%)"],
    "cgst_amt":     ["cgst amt", "cgst amount", "central tax amt", "central tax amount"],
    "sgst_rate":    ["sgst %", "sgst rate", "utgst %", "utgst rate", "state tax %", "state tax rate", "sgst", "sgst(%)", "sgst (%)", "utgst", "utgst(%)"],
    "sgst_amt":     ["sgst amt", "sgst amount", "utgst amt", "utgst amount", "state tax amt", "state tax amount"],
    "igst_rate":    ["igst %", "igst rate", "integrated tax %", "integrated tax rate", "igst", "igst(%)", "igst (%)"],
    "igst_amt":     ["igst amt", "igst amount", "integrated tax amt", "integrated tax amount"],
    "gst_rate":     ["gst %", "gst rate", "tax %", "tax rate", "total tax %"],
    "cess_amt":     ["cess", "cess amt", "cess amount", "compensation cess"],
}

def _norm_header(s: str) -> str:
    s = s.lower().replace("%", " % ")
    s = re.sub(r"[^a-z0-9%# ]+", " ", s)
    toks = [t for t in s.split() if t not in ("rs", "inr", "cr", "dr")]
    return " ".join(toks)

_LOOKUP: Dict[str, str] = {
    _norm_header(syn): role for role, syns in HEADER_SYNONYMS.items() for syn in syns
}

def map_header(text: str, fuzzy_cutoff: float = 0.88) -> str:
    """
    Maps column header text to canonical role.
    Grouped headers: pass 'CGST Rate' (group + sub header joined).
    Unknown -> 'other' (never forced into qty/rate).
    """
    n = _norm_header(text)
    if n in _LOOKUP:
        return _LOOKUP[n]
    best, best_score = None, 0.0
    for key, role in _LOOKUP.items():
        sc = SequenceMatcher(None, n, key).ratio()
        if sc > best_score:
            best, best_score = role, sc
    return best if best_score >= fuzzy_cutoff else "other"

# =====================================================================
# 2. Qty / Unit / Pack Size
# =====================================================================
UNIT_CANON: Dict[str, str] = {
    "NOS": "Nos", "NO": "Nos", "PCS": "Pcs", "PC": "Pcs", "PIECE": "Pcs", "PIECES": "Pcs",
    "KG": "Kg", "KGS": "Kg", "KILOGRAM": "Kg", "KILOGRAMS": "Kg",
    "GM": "Gm", "GMS": "Gm", "G": "Gm", "GRAM": "Gm", "GRAMS": "Gm",
    "LTR": "Ltr", "LTRS": "Ltr", "L": "Ltr", "LITRE": "Ltr", "LITRES": "Ltr", "LITER": "Ltr", "LT": "Ltr",
    "ML": "Ml", "MLT": "Ml",
    "MTR": "Mtr", "MTRS": "Mtr", "M": "Mtr", "METER": "Mtr", "METERS": "Mtr",
    "BOX": "Box", "BOXES": "Box", "BX": "Box",
    "SET": "Set", "SETS": "Set",
    "PKT": "Pkt", "PKTS": "Pkt", "PACKET": "Pkt", "PACKETS": "Pkt", "PACK": "Pkt",
    "DOZ": "Doz", "DOZEN": "Doz", "DOZENS": "Doz", "DZN": "Doz", "DZ": "Doz",
    "BAG": "Bag", "BAGS": "Bag", "BG": "Bag",
    "CTN": "Ctn", "CARTON": "Ctn", "CARTONS": "Ctn",
    "CASE": "Case", "CASES": "Case", "CS": "Case",
    "PAIR": "Pair", "PAIRS": "Pair", "PR": "Pair",
    "ROLL": "Roll", "ROLLS": "Roll",
    "BTL": "Btl", "BOTTLE": "Btl", "BOTTLES": "Btl",
    "STRIP": "Strip", "STRIPS": "Strip", "TIN": "Tin", "CAN": "Can", "CANS": "Can"
}

PACK_RE = re.compile(
    r"(?i)\b(\d+(?:\.\d+)?)\s*(ml|m\.l\.|ltr|litre|litres|l|gm|gms|g|gram|grams|kg|kgs|kilogram|mg|mtr|cm|mm|oz|sqmm|sqft|w|watt|v|volt|ah|mah)\b"
)

def pack_size_from_description(desc: str) -> Optional[str]:
    """
    Extracts pack size embedded in description.
    'Sunsilk Shampoo 340ml' -> '340 ml'.
    This is PACK SIZE / WEIGHT / VOLUME.
    It stays in the description and is NEVER the invoice quantity.
    """
    m = PACK_RE.search(desc or "")
    return f"{m.group(1)} {m.group(2).lower()}" if m else None

def strip_pack_sizes_from_text(text: str) -> Tuple[str, List[str]]:
    """
    Masks out pack sizes, weight, volume, and electrical specs from text
    so that numbers like '10' in '10ml' or '100' in '100gm' are not accidentally
    picked up as invoice quantity or rates.
    """
    found = []
    def repl(m):
        found.append(m.group(0))
        return " __PACK_SPEC__ "
    masked = PACK_RE.sub(repl, text or "")
    return masked, found

def merge_size_into_item_name(item_name: str, size: Optional[str]) -> str:
    """
    Merges item size/weight into item name without duplicate inputs or duplicate values.
    Example:
    item_name: 'C2 AMLA HAIR OIL', size: '51 ML' -> 'C2 AMLA HAIR OIL 51ML'
    Applies to all units (ML, L, GM, KG, etc.), preserving original values accurately.
    """
    if not item_name:
        return ""
    if not size or not str(size).strip() or str(size).strip() in ("0", "null", "None"):
        return item_name.strip()
    
    clean_sz = str(size).strip()
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([a-zA-Z]+)$", clean_sz)
    if m:
        num_part = m.group(1)
        unit_part = m.group(2).upper()
        formatted_size = f"{num_part}{unit_part}"
        pattern = re.compile(rf"\b{re.escape(num_part)}\s*{re.escape(unit_part)}\b", re.IGNORECASE)
    else:
        formatted_size = clean_sz
        pattern = re.compile(rf"\b{re.escape(clean_sz)}\b", re.IGNORECASE)
        
    if pattern.search(item_name):
        return item_name.strip()
        
    return f"{item_name.strip()} {formatted_size}".strip()

# =====================================================================
# 2b. Generic Pack Multiplier Detection
# =====================================================================
@dataclass
class PackMultiplierResult:
    multiplier: D
    multiplier_unit: Optional[str] = None
    raw_match: str = ""
    cleaned_description: str = ""

REJECT_PACK_UNITS: Set[str] = {
    # Weight
    "GM", "GMS", "G", "GRAM", "GRAMS", "KG", "KGS", "KILOGRAM", "KILOGRAMS",
    "MG", "MGS", "OZ", "MT", "TON", "TONS", "QTL", "QUINTAL", "LB", "LBS",
    # Volume
    "ML", "MLT", "LTR", "LTRS", "L", "LITRE", "LITRES", "LITER", "LITERS", "LT", "CC",
    # Dimensions / Length / Area
    "MM", "CM", "MTR", "MTRS", "M", "FT", "INCH", "INCHES", "IN",
    "SQM", "SQFT", "SQMM", "SQMTR", "SQ", "RFT", "YD", "YDS", "YARD",
    # Electrical & Technical specs
    "W", "WATT", "WATTS", "V", "VOLT", "VOLTS", "KV", "KVA", "AH", "MAH", "HP", "RPM",
    "HZ", "KHZ", "MHZ", "GHZ", "A", "AMP", "AMPS", "KWH", "PF", "DB", "K", "C", "F"
}

DIMENSION_OR_TECH_RE = re.compile(
    r"(?i)\b\d+(?:\.\d+)?\s*[*xX]\s*\d+(?:\.\d+)?(?:\s*[*xX]\s*\d+(?:\.\d+)?)?\s*(?:mm|cm|mtr|m|ft|inch|in|sqm|sqft|sqmm|sqmtr|gm|gms|kg|kgs|ml|ltr|l|w|watt|v|volt|ah|mah|rpm|hz|hp|amp|a)\b"
)

BARE_DIM_RE = re.compile(
    r"(?i)\b([2-9]\d*|\d{2,})\s*[*xX]\s*([2-9]\d*|\d{2,})(?!\s*(?:pcs|pkt|packet|pack|units?|pieces?|box|ctn|carton|strip|tin|can|bag|dzn|doz|nos)\b)\b"
)

PACK_ONE_X_RE = re.compile(
    r"(?i)\b1\s*[*xX]\s*([0-9]{1,4})\s*([a-zA-Z]{1,10})?(?=[\s,)\]-]|$|\b)"
)

PACK_OF_RE = re.compile(
    r"(?i)\b(?:pack|pkt|packet|case|box|bag|strip|carton|ctn|tin|can|pouch)\s+of\s+([0-9]{1,4})\s*([a-zA-Z]{1,10})?\b"
)

PACK_PER_CASE_RE = re.compile(
    r"(?i)\b([0-9]{1,4})\s*([a-zA-Z]{1,10})?\s*(?:/|per)\s*(?:case|box|ctn|carton|bag|outer|pack|pkt)\b"
)

PACK_X_PREFIX_RE = re.compile(
    r"(?i)(?:^|[\s,(\[-])(?:[xX*]|[-xX*])\s*[-]?\s*([0-9]{1,4})\s*([a-zA-Z]{1,10})?(?=[\s,)\]-]|$|\b)"
)

def detect_pack_multiplier(description: Optional[str]) -> Optional[PackMultiplierResult]:
    """
    Detects explicit pack/multiplier expressions embedded inside item descriptions.
    e.g. 'Good Knight Gold 65 GM X 72 PKT' -> multiplier = 72, unit = 'PKT'
         'Ball Pen Blue 50 PCS / BOX' -> multiplier = 50, unit = 'PCS'
         'Philips LED Bulb 9W (Pack of 10)' -> multiplier = 10, unit = None
         'Parle-G 250 GM X300' -> multiplier = 300, unit = None
    Strict negative constraints:
      - Weight/Volume ('65 GM', '500 ML', '10 KG') are NEVER multipliers.
      - Dimensions ('200X300 MM', '8X4 FT') are NEVER multipliers.
      - Specs ('40W', '12V', '2.5 SQMM') are NEVER multipliers.
      - Model/Size ('Model 120', 'Size 42') are NEVER multipliers.
      - Realistic range: 2 <= multiplier <= 10000.
    """
    if not description:
        return None

    text = description.strip()

    # 1. Mask out dimensional expressions like 200X300 MM or 200x300
    text_masked = DIMENSION_OR_TECH_RE.sub(" __DIM__ ", text)

    def dim_repl(m: re.Match) -> str:
        start = m.start()
        prefix = text_masked[max(0, start - 12):start].lower()
        if re.search(r'\b(?:size|model|mod|item|cat|code|part)\s*$', prefix):
            return m.group(0)  # Do not mask if preceded by Size/Model
        return " __DIM__ "

    text_masked = BARE_DIM_RE.sub(dim_repl, text_masked)

    candidates = []

    # Check Pattern 1 (1 x N):
    m_one = PACK_ONE_X_RE.search(text_masked)
    if m_one:
        candidates.append((m_one.group(0), m_one.group(1), m_one.group(2)))

    # Check Pattern 2 (Pack of N):
    m_of = PACK_OF_RE.search(text_masked)
    if m_of:
        candidates.append((m_of.group(0), m_of.group(1), m_of.group(2)))

    # Check Pattern 3 (N / Case):
    m_case = PACK_PER_CASE_RE.search(text_masked)
    if m_case:
        candidates.append((m_case.group(0), m_case.group(1), m_case.group(2)))

    # Check Pattern 4 (X Prefix):
    m_x = PACK_X_PREFIX_RE.search(text_masked)
    if m_x:
        candidates.append((m_x.group(0), m_x.group(1), m_x.group(2)))

    for raw_match, num_str, unit_str in candidates:
        try:
            num = int(num_str)
        except (ValueError, TypeError):
            continue

        if num < 2 or num > 10000:
            continue

        clean_unit = None
        if unit_str:
            clean_unit = re.sub(r'[^a-zA-Z]', '', unit_str).upper()

        if clean_unit and clean_unit in REJECT_PACK_UNITS:
            continue

        # Verify not immediately preceded by Model/Size/Code/Batch keywords
        match_start = text.find(num_str)
        if match_start > 0:
            prefix_window = text[max(0, match_start - 12):match_start]
            if re.search(r'(?i)\b(?:model|mod|code|cat|item|part|size|grade|batch)\s*(?:no\.?|#)?$', prefix_window):
                continue

        cleaned = text.replace(raw_match.strip(), "").strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return PackMultiplierResult(
            multiplier=D(str(num)),
            multiplier_unit=clean_unit,
            raw_match=raw_match.strip(),
            cleaned_description=cleaned
        )

    return None

def split_qty_cell(cell: str) -> Tuple[Optional[D], Optional[str]]:
    """
    Splits quantity cell into number and unit.
    '12 PCS' -> (12, 'Pcs') ; '5.000 KG' -> (5, 'Kg') ; '12' -> (12, None)
    Handles commas: '1,200 PCS' -> (1200, 'Pcs')
    """
    if not cell:
        return None, None
    clean_text = cell.strip()
    m = re.match(r"^\s*([\d,]*\.?\d+)\s*([A-Za-z]{1,8}\.?)?\s*$", clean_text)
    if not m:
        # Check if unit is in front, e.g. "PCS 10"
        m_rev = re.match(r"^\s*([A-Za-z]{1,8}\.?)\s*([\d,]*\.?\d+)\s*$", clean_text)
        if m_rev:
            try:
                qty = D(m_rev.group(2).replace(",", ""))
                u_str = re.sub(r'[^A-Za-z]', '', m_rev.group(1)).upper()
                unit = UNIT_CANON.get(u_str, u_str.capitalize() if u_str else None)
                return qty, unit
            except InvalidOperation:
                return None, None
        return None, None
    try:
        qty = D(m.group(1).replace(",", ""))
    except InvalidOperation:
        return None, None
    u_raw = m.group(2)
    unit = None
    if u_raw:
        u_clean = re.sub(r'[^A-Za-z]', '', u_raw).upper()
        unit = UNIT_CANON.get(u_clean, u_clean.capitalize() if u_clean else None)
    return qty, unit

def pick_unit(unit_column_value: Optional[str], qty_cell_unit: Optional[str]) -> Optional[str]:
    """
    Unit comes ONLY from the Unit column or from the qty cell.
    Never from the description.
    """
    for v in (unit_column_value, qty_cell_unit):
        if v:
            clean = re.sub(r"[^A-Za-z]", "", str(v)).upper()
            if clean in UNIT_CANON:
                return UNIT_CANON[clean]
            if clean:
                return clean.capitalize()
    return None

def recover_missing_quantity_or_rate(
    qty: Optional[D],
    rate: Optional[D],
    taxable: Optional[D],
    discount_pct: Optional[D] = None
) -> Tuple[Optional[D], Optional[D]]:
    """
    Recovers missing or defaulted (1.00) quantity using arithmetic relationships:
    taxable = qty * rate * (1 - discount_pct/100)
    If rate > 0 and taxable > 0:
      recovers true quantity if qty is missing or was defaulted.
    If qty > 0 and taxable > 0:
      recovers true rate if rate is missing.
    """
    disc_factor = (D("1") - (discount_pct or D("0")) / D("100")) if discount_pct else D("1")
    if disc_factor <= D("0"):
        disc_factor = D("1")

    # 1. Recover Qty when Rate and Taxable are present
    if rate is not None and rate > D("0") and taxable is not None and taxable > D("0"):
        effective_rate = rate * disc_factor
        if effective_rate > D("0"):
            calc_q = taxable / effective_rate
            # Check if calc_q is clean (e.g. integer or up to 3 decimal places)
            calc_q_rounded = calc_q.quantize(D("0.001"), rounding=ROUND_HALF_UP)
            if close(calc_q_rounded * effective_rate, taxable, abs_tol=D("0.10")):
                is_exact_integer = (calc_q_rounded % D("1")) == D("0")
                # If existing qty is None or <= 0: recover quantity.
                # If existing qty was 1.00: ONLY recover if calc_q is an exact integer multiple > 1 (e.g. 12 boxes, never a fractional guess like 1.185):
                if qty is None or qty <= D("0") or (qty == D("1.00") and is_exact_integer and calc_q_rounded > D("1.00") and not close(rate * disc_factor, taxable, abs_tol=D("0.10"))):
                    qty = calc_q_rounded

    # 2. Recover Rate when Qty and Taxable are present
    if qty is not None and qty > D("0") and taxable is not None and taxable > D("0"):
        if rate is None or rate <= D("0"):
            calc_r = (taxable / (qty * disc_factor)).quantize(D("0.01"), rounding=ROUND_HALF_UP)
            rate = calc_r

    return qty, rate

# =====================================================================
# 3. Column Solver: Let arithmetic decide qty / rate / amount
# =====================================================================
def close(a: Any, b: Any, abs_tol: D = D("1.00"), rel_tol: D = D("0.005")) -> bool:
    a, b = D(str(a)), D(str(b))
    return abs(a - b) <= max(abs_tol, abs(b) * rel_tol)

def solve_columns(
    rows: List[Dict[str, D]],
    numeric_cols: List[str],
    disc_pct_cols: Tuple[str, ...] = (),
    prior: Optional[Dict[Tuple[str, str, str], float]] = None
) -> Optional[Tuple[D, str, str, str]]:
    """
    Determines the correct assignment of (qty_col, rate_col, amount_col)
    by testing all permutations against qty * rate (- discount) ≈ amount.
    Ties broken by prior (from headers), unit adjacency, integer-like qty, left-to-right order.
    MRP columns are systematically rejected because MRP * qty != taxable.
    """
    prior = prior or {}
    results = []
    for q, r, a in itertools.permutations(numeric_cols, 3):
        ok = 0
        n = 0
        for row in rows:
            vq, vr, va = row.get(q), row.get(r), row.get(a)
            if vq is None or vr is None or va is None:
                continue
            n += 1
            gross = vq * vr
            hit = close(gross, va)
            for d in disc_pct_cols:
                if row.get(d) is not None and close(gross * (D("1") - row[d] / D("100")), va):
                    hit = True
            ok += int(hit)
        if n > 0:
            score = D(ok) / D(n) + D("0.01") * D(str(prior.get((q, r, a), 0)))
            results.append((score, q, r, a))

    results.sort(key=lambda t: t[0], reverse=True)
    return results[0] if results else None

# =====================================================================
# 4. GST Rate Resolution (Date-dependent slabs: 2.5 -> 5, 9 -> 18 ...)
# =====================================================================
# All active standard Indian GST rates (0%, 0.1%, 0.25%, 1.5%, 3%, 5%, 6%, 7.5%, 12%, 14%, 18%, 28%, 40%)
ALL_STANDARD_GST_RATES: Set[D] = {
    D("0"), D("0.1"), D("0.25"), D("1.5"), D("3"), D("5"), D("6"),
    D("7.5"), D("12"), D("14"), D("18"), D("28"), D("40")
}

def allowed_rates(invoice_date: Optional[date] = None) -> Set[D]:
    return ALL_STANDARD_GST_RATES

def resolve_gst_rate(
    row: Dict[str, Any],
    allowed: Set[D],
    tol: D = D("0.25")
) -> Tuple[Optional[D], str, bool]:
    """
    Resolves full GST rate for a row from multiple potential representations:
    (IGST rate, CGST + SGST rate, single printed rate, half-rate inference).
    Returns: (rate, how_resolved, needs_flag)
    """
    amount = row.get("amount")
    tax = sum((row.get(k) or D("0")) for k in ("cgst_amt", "sgst_amt", "igst_amt"))
    cands: List[Tuple[D, str]] = []

    # PRD Requirement: Single tax rate column (e.g. TAX % or GST %) must NEVER be doubled!
    has_two_tax_rate_cols = (row.get("cgst_rate") is not None and row.get("sgst_rate") is not None)
    is_explicit_single_rate = bool(row.get("is_single_tax_col")) or (row.get("gst_rate") is not None)

    if row.get("igst_rate") is not None:
        cands.append((D(str(row["igst_rate"])), "igst"))

    if row.get("gst_rate") is not None:
        val = D(str(row["gst_rate"]))
        cands.append((val, "single"))

    if has_two_tax_rate_cols:
        cands.append((D(str(row["cgst_rate"])) + D(str(row["sgst_rate"])), "cgst+sgst"))
    elif not is_explicit_single_rate:
        if row.get("cgst_rate") is not None:
            val = D(str(row["cgst_rate"]))
            cands.append((val, "single_cgst"))
            cands.append((val * D("2"), "cgst_x2"))
        elif row.get("sgst_rate") is not None:
            val = D(str(row["sgst_rate"]))
            cands.append((val, "single_sgst"))
            cands.append((val * D("2"), "sgst_x2"))
    else:
        if row.get("cgst_rate") is not None and row.get("gst_rate") is None:
            cands.append((D(str(row["cgst_rate"])), "single_cgst"))
        elif row.get("sgst_rate") is not None and row.get("gst_rate") is None:
            cands.append((D(str(row["sgst_rate"])), "single_sgst"))

    valid = [(r, w) for r, w in cands if r in allowed]

    hints: List[D] = []
    if amount and tax and amount > D("0"):
        hints.append(tax / amount * D("100"))
        if amount > tax:
            hints.append(tax / (amount - tax) * D("100"))

    def dist(r: D) -> Optional[D]:
        return min((abs(r - h) for h in hints), default=None)

    if valid:
        if hints:
            valid.sort(key=lambda c: dist(c[0]) if dist(c[0]) is not None else D("999"))
        rate, how = valid[0]
        d_val = dist(rate)
        needs_flag = bool(hints) and (d_val is not None and d_val > tol)
        return rate, how, needs_flag

    if hints:
        # Rate unreadable or omitted: derive from tax amounts and snap to allowed rate
        snap = min(allowed, key=lambda a: min(abs(a - h) for h in hints))
        min_d = min(abs(snap - h) for h in hints)
        if min_d <= tol:
            return snap, "from_amounts", True

    return None, "unresolved", True

# =====================================================================
# 5. Tax-Inclusive vs Exclusive Detection by Arithmetic
# =====================================================================
def row_mode(
    amount: D,
    rate: D,
    tax: D,
    abs_tol: D = D("0.06"),
    rel_tol: D = D("0.001")
) -> Optional[str]:
    """
    Evaluates whether a single line's tax agrees with exclusive or inclusive arithmetic.
    """
    if rate <= D("0") or tax <= D("0"):
        return None
    exp_excl = amount * rate / D("100")
    exp_incl = amount * rate / (D("100") + rate)
    e = close(tax, exp_excl, abs_tol, rel_tol)
    i = close(tax, exp_incl, abs_tol, rel_tol)
    if e and not i:
        return "exclusive"
    if i and not e:
        return "inclusive"
    return None

def detect_tax_mode(
    rows: List[Dict[str, Any]],
    grand_total: Optional[D] = None,
    other_charges: D = D("0"),
    round_off: D = D("0")
) -> Tuple[str, str, Dict[str, int]]:
    """
    Decides tax mode (exclusive vs inclusive) using rigorous arithmetic:
    1. Totals test: Σamount + Σtax ≈ grand_total (exclusive) vs Σamount ≈ grand_total (inclusive)
    2. Majority of per-line arithmetic votes
    Returns: (mode, rationale, votes_dict)
    """
    votes = {"exclusive": 0, "inclusive": 0}
    for r in rows:
        amt = r.get("amount")
        rate = r.get("rate")
        tax = r.get("tax")
        if amt is not None and rate is not None and tax is not None:
            v = row_mode(D(str(amt)), D(str(rate)), D(str(tax)))
            if v:
                votes[v] += 1

    result, why = "unknown", "no decisive evidence"

    if grand_total is not None and len(rows) > 0:
        s_amt = sum(D(str(r["amount"])) for r in rows if r.get("amount") is not None)
        s_tax = sum(D(str(r.get("tax") or 0)) for r in rows)

        if not any(r.get("tax") for r in rows):
            s_tax_excl = sum(
                D(str(r["amount"])) * D(str(r.get("rate") or 0)) / D("100")
                for r in rows if r.get("amount") is not None
            )
            e_ok = close(s_amt + s_tax_excl + other_charges + round_off, grand_total)
        else:
            e_ok = close(s_amt + s_tax + other_charges + round_off, grand_total)

        i_ok = close(s_amt + other_charges + round_off, grand_total)

        if e_ok and not i_ok:
            result, why = "exclusive", "amounts + tax = grand total"
        elif i_ok and not e_ok:
            result, why = "inclusive", "amounts alone = grand total"

    if result == "unknown":
        if votes["exclusive"] > votes["inclusive"]:
            result, why = "exclusive", "row arithmetic votes"
        elif votes["inclusive"] > votes["exclusive"]:
            result, why = "inclusive", "row arithmetic votes"

    return result, why, votes

def to_exclusive(amount: D, rate: D, mode: str) -> Tuple[D, D, D, D]:
    """
    Converts amount to canonical tax-exclusive values.
    Returns: (taxable_amount, total_tax, cgst_amount, sgst_amount)
    """
    if mode == "inclusive":
        taxable = (amount * D("100") / (D("100") + rate)).quantize(D("0.01"))
        tax = amount - taxable
    else:
        taxable = amount
        tax = (amount * rate / D("100")).quantize(D("0.01"))

    cgst = (tax / D("2")).quantize(D("0.01"))
    sgst = tax - cgst
    return taxable, tax, cgst, sgst

# =====================================================================
# 6. Addendum 3: GST Rate Source of Truth & Bill Reconciliation
# =====================================================================
def choose_gst_rate(
    bill: Tuple[Optional[D], str, bool],
    master: Optional[D] = None,
    hsn_summary: Optional[D] = None,
    catalog: Optional[D] = None
) -> Dict[str, Any]:
    """
    bill        = (rate, how, flag) returned by resolve_gst_rate() (Addendum 1): what the bill prints
                  (CGST+SGST, IGST, single GST%) or what its tax amounts imply.
    master      = GST rate currently set on the mapped Tally stock item (or None)
    hsn_summary = rate found for this HSN in the bill's own HSN/tax summary table (or None)
    catalog     = rate from earlier purchases of this item (or None)
    Priority: bill line > bill HSN summary > (master / catalog only as a flagged SUGGESTION) > blank.
    """
    rate, how, flag = bill
    if rate is not None:
        out = {"rate": rate, "source": f"bill:{how}", "flags": ["check_rate"] if flag else [], "master": master}
        if master is not None and master != rate:
            out["flags"].append("master_rate_differs")      # voucher keeps the BILL rate; master is not trusted
        return out
    if hsn_summary is not None:
        return {"rate": hsn_summary, "source": "bill:hsn_summary", "flags": ["check_rate"], "master": master}
    for name, val in (("master", master), ("catalog", catalog)):
        if val is not None:
            return {"rate": val, "source": name, "flags": ["suggested_not_on_bill"], "master": master}
    return {"rate": None, "source": "none", "flags": ["rate_missing"], "master": master}   # blank: blocks export. NEVER 18.

def stock_item_action(item_exists_in_tally: bool, master_rate: Optional[D], bill_rate: Optional[D]) -> str:
    if bill_rate is None:
        return "block_rate_missing"
    if not item_exists_in_tally:
        return "create_item_with_bill_rate"
    if master_rate == bill_rate:
        return "use_existing_item"
    return "use_existing_item_override_rate_in_voucher_and_flag"    # change the master only if the user chooses

def split_tax(tax: D) -> Tuple[D, D]:
    cgst = (tax / D("2")).quantize(D("0.01"), rounding=ROUND_HALF_UP)
    return cgst, tax - cgst

def spread_paise(lines: List[Dict[str, Any]], printed_total_tax: D) -> D:
    """Bills round tax per slab or per line. If the printed total tax differs by paise only,
    put the paise on the LAST line so the sum equals the bill. Bigger gaps are not touched."""
    delta = (printed_total_tax - sum(l["tax"] for l in lines)).quantize(D("0.01"))
    if delta != 0 and abs(delta) <= D("0.01") * (len(lines) + 1):
        lines[-1]["tax"] += delta
        return delta
    return D("0.00")

def reconcile(
    lines: List[Dict[str, Any]],
    printed_total: D,
    other_charges: D = D("0"),
    discount: D = D("0"),
    printed_round_off: Optional[D] = None,
    abs_tol: D = D("0.05"),
    round_off_limit: D = D("2.50")
) -> Dict[str, Any]:
    """lines: [{'taxable': D, 'tax': D}] using PRINTED values wherever the bill prints them."""
    base_round = printed_round_off or D("0")
    line_sum = sum(l["taxable"] + l["tax"] for l in lines)

    # 1. If items are gross and discount is subtracted:
    computed_with_disc_sub = line_sum + other_charges - discount + base_round
    diff_sub = (printed_total - computed_with_disc_sub).quantize(D("0.01"))
    if abs(diff_sub) <= abs_tol:
        return {"status": "OK", "diff": diff_sub, "round_off_ledger": base_round, "discount": discount}
    if abs(diff_sub) <= round_off_limit:
        return {"status": "AUTO_ROUND_OFF", "diff": diff_sub, "round_off_ledger": base_round + diff_sub, "discount": discount}

    # 2. If items are net and discount was added to reconcile to printed gross total:
    computed_with_disc_add = line_sum + other_charges + discount + base_round
    diff_add = (printed_total - computed_with_disc_add).quantize(D("0.01"))
    if abs(diff_add) <= abs_tol:
        return {"status": "OK", "diff": diff_add, "round_off_ledger": base_round, "discount": discount}
    if abs(diff_add) <= round_off_limit:
        return {"status": "AUTO_ROUND_OFF", "diff": diff_add, "round_off_ledger": base_round + diff_add, "discount": discount}

    # 3. If discount was not explicitly passed, check if the difference is explained as a discount:
    raw_diff = (printed_total - (line_sum + other_charges + base_round)).quantize(D("0.01"))
    if discount == D("0") and abs(raw_diff) > round_off_limit:
        return {
            "status": "DISCOUNT_EXPLAINED",
            "diff": raw_diff,
            "discount": abs(raw_diff),
            "round_off_ledger": base_round
        }

    return {"status": "BLOCK", "diff": raw_diff, "round_off_ledger": base_round + raw_diff, "discount": discount}

def row_report(printed: Dict[str, D], generated: Dict[str, D], tol: D = D("0.01")) -> Dict[str, Tuple[D, Optional[D]]]:
    """printed/generated: dicts of Decimal fields for ONE row. Returns the fields that differ."""
    return {k: (printed[k], generated.get(k)) for k in printed
            if generated.get(k) is None or abs(printed[k] - generated[k]) > tol}

# =====================================================================
# 7. Addendum 2: Tally Duty Heads & Rate Details Safety
# =====================================================================
ITEM_TAGS: Set[str] = {"ALLINVENTORYENTRIES.LIST", "INVENTORYENTRIES.LIST"}
RATE_TAG, HEAD_TAG, RATE_VALUE_TAG = "RATEDETAILS.LIST", "GSTRATEDUTYHEAD", "GSTRATE"
CANONICAL_HEAD_ORDER: List[str] = ["CGST", "SGST/UTGST", "IGST", "Cess"]

def build_rate_details(
    gst_rate: D,
    intra_state: bool,
    cess_rate: Optional[D] = None,
    emit_all_heads: bool = False
) -> List[Tuple[str, D]]:
    """
    gst_rate: FULL rate (Decimal) from the validated canonical model (e.g. 5, 12, 18, 28).
    intra_state: from seller state vs place of supply, NOT from 'which tax fields are filled'.
    emit_all_heads: if True, emits both intra and inter heads.
    Returns an ordered list of (head, rate). A dict keyed by head => each head appears once.
    A NEW dict is created on every call, so nothing can leak from one item to the next.
    """
    heads: Dict[str, D] = {}
    if intra_state:
        heads["CGST"] = (gst_rate / D("2")).quantize(D("0.01"))
        heads["SGST/UTGST"] = (gst_rate / D("2")).quantize(D("0.01"))
        if emit_all_heads:
            heads["IGST"] = gst_rate
    else:
        heads["IGST"] = gst_rate
        if emit_all_heads:
            heads["CGST"] = (gst_rate / D("2")).quantize(D("0.01"))
            heads["SGST/UTGST"] = (gst_rate / D("2")).quantize(D("0.01"))
    if cess_rate and cess_rate > D("0.00"):
        heads["Cess"] = cess_rate
    return [(h, heads[h]) for h in CANONICAL_HEAD_ORDER if h in heads]

def rate_details_xml(pairs: List[Tuple[str, D]]) -> List[str]:
    lines: List[str] = []
    for head, rate in pairs:
        rate_str = f"{rate:.2f}" if rate == rate.quantize(D("0.01")) else f"{rate}"
        lines.extend([
            f'       <{RATE_TAG}>',
            f'        <{HEAD_TAG}>{escape(head)}</{HEAD_TAG}>',
            '        <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>',
            f'        <{RATE_VALUE_TAG}> {rate_str}</{RATE_VALUE_TAG}>',
            f'       </{RATE_TAG}>'
        ])
    return lines

def find_duplicate_duty_heads(xml_text: str) -> List[Dict[str, Any]]:
    """
    Pre-export guard X02: block the file if any item repeats a duty head.
    """
    clean_xml = xml_text.replace('&#4;', '')
    try:
        root = ET.fromstring(clean_xml.strip())
    except Exception:
        return []

    problems: List[Dict[str, Any]] = []
    for v in root.iter("VOUCHER"):
        vno = (v.findtext("VOUCHERNUMBER") or "?").strip()
        for item in v.iter():
            if item.tag in ITEM_TAGS:
                name = (item.findtext("STOCKITEMNAME") or "?").strip()
                heads = [(rd.findtext(HEAD_TAG) or "").strip() for rd in item.findall(RATE_TAG)]
                for head, n in Counter(heads).items():
                    if head and n > 1:
                        problems.append({"voucher": vno, "item": name, "head": head, "times": n})
    return problems

