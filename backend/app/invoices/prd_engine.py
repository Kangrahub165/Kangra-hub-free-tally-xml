"""
PRD V2 Engine: Invoice OCR -> Tally-Ready XML (Sales & Purchase).
Strictly implements the 6 Golden Rules and Sections 3, 4, 5, 6, 7, 8, 9, 10 of the PRD:

0. Golden Rules:
   1. The line AMOUNT printed on the invoice is the truth. Quantity and rate are only correct if qty * rate (- discount) = amount.
   2. Do not multiply quantities by default. Multiply ONLY per Section 5.3.
   3. Never use a number just because it looks like a quantity (bracket counts, Total Units, Alt Qty, MRP, gm, ml, @Rs).
   4. Do NOT break existing functionality.
   5. Read GST rate from the invoice. Never guess it.
   6. Ignore handwriting, pen marks, ticks, Paid stamps.
"""

import re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Optional, List, Dict, Tuple, Any, Set

from app.invoices.model import InvoiceDocument, InvoiceItem, PartyInfo, to_decimal
from app.invoices.table_engine import (
    UNIT_CANON,
    merge_size_into_item_name,
    pack_size_from_description,
    detect_pack_multiplier
)
from app.invoices.state_normalizer import (
    normalize_document_states,
    normalize_state,
    are_states_intra_state
)

# Bulk units eligible for Section 5.3 conversion
BULK_UNITS: Set[str] = {
    "CB", "CASE", "CASES", "CS", "CTN", "CTNS", "CARTON", "CARTONS", "BOX", "BOXES", "BX"
}

# Final piece units that must NEVER be multiplied (Section 5.4)
PIECE_UNITS: Set[str] = {
    "PCS", "PC", "PIECE", "PIECES", "PKT", "PKTS", "PACKET", "PACKETS",
    "PACK", "PACKS", "NOS", "NO", "UNITS", "UNIT", "DZ", "DOZ", "DOZEN",
    "BOTTLE", "BOTTLES", "BTL", "JAR", "JARS", "CONTAINER", "LADI", "TIN", "CAN"
}

# Non-quantity units (weights, volumes, dimensions, currency) - NEVER multipliers (Section 5.1)
REJECT_MULTIPLIER_UNITS: Set[str] = {
    "GM", "GMS", "G", "GRAM", "GRAMS",
    "ML", "MLT", "MILLILITRE", "MILLILITRES",
    "KG", "KGS", "KILOGRAM", "KILOGRAMS",
    "LTR", "LTRS", "L", "LITRE", "LITRES", "LITER",
    "MTR", "MTRS", "M", "METER", "METERS",
    "SQFT", "SQM", "SQMM", "MM", "CM", "INCH", "FT",
    "RS", "INR", "MRP"
}

STANDARD_GST_SLABS: List[Decimal] = [
    Decimal("0.00"), Decimal("0.10"), Decimal("0.25"), Decimal("1.50"),
    Decimal("3.00"), Decimal("5.00"), Decimal("6.00"), Decimal("7.50"),
    Decimal("12.00"), Decimal("14.00"), Decimal("18.00"), Decimal("28.00"), Decimal("40.00")
]


def is_close(a: Decimal, b: Decimal, abs_tol: Decimal = Decimal("1.00"), rel_tol: Decimal = Decimal("0.005")) -> bool:
    """Checks whether two monetary or quantity amounts match within tolerance."""
    diff = abs(a - b)
    return diff <= abs_tol or diff <= (abs(b) * rel_tol)


# =====================================================================
# SECTION 5: Quantity Logic & Math Check Decision Engine
# =====================================================================

def extract_section_5_3_pack_pattern(description: str) -> Optional[Tuple[int, str]]:
    r"""
    PRD Addendum 2 Section A4 generic pack count extractor:
    Looks for pattern: X (or x) + number + a short letters-only word, optionally followed by dot/comma.
    Regex: [xX]\s*(\d{1,4})\s*([A-Za-z]+)\.?
    Rules:
      - Number must come right after X/x.
      - Never use numbers followed by weight/volume (gm, g, kg, ml, l, ltr), MRP, Rs price, size/model.
      - Range: 1 <= N <= 1000.
    """
    if not description:
        return None

    clean_desc = description.strip()

    # Generic Pattern: [xX*]\s*([0-9]{1,4})\s*([A-Za-z]{1,15})\.?
    matches = list(re.finditer(r'(?i)(?:[xX*]|[-xX*])\s*([0-9]{1,4})\s*([A-Za-z]{1,15})\.?', clean_desc))
    for m in reversed(matches):
        try:
            cnt = int(m.group(1))
            unit_raw = m.group(2).strip()
            unit_upper = unit_raw.upper()
            if unit_upper in REJECT_MULTIPLIER_UNITS:
                continue
            if unit_upper in {"MRP", "RS", "INR", "SIZE", "MOD", "MODEL"}:
                continue
            if 1 <= cnt <= 1000:
                piece_hint = "Pcs" if "PC" in unit_upper else ("Pkt" if "PK" in unit_upper else unit_raw.capitalize())
                return cnt, piece_hint
        except Exception:
            continue

    # Also check brackets e.g. (192pkt), (288PCS), (X192pkt)
    matches_b = list(re.finditer(r'(?i)\(\s*(?:[xX]\s*)?([0-9]{1,4})\s*([A-Za-z]{1,15})\.?\s*\)', clean_desc))
    for m in reversed(matches_b):
        try:
            cnt = int(m.group(1))
            unit_raw = m.group(2).strip()
            unit_upper = unit_raw.upper()
            if unit_upper in REJECT_MULTIPLIER_UNITS:
                continue
            if unit_upper in {"MRP", "RS", "INR", "SIZE", "MOD", "MODEL"}:
                continue
            if 1 <= cnt <= 1000:
                piece_hint = "Pcs" if "PC" in unit_upper else ("Pkt" if "PK" in unit_upper else unit_raw.capitalize())
                return cnt, piece_hint
        except Exception:
            continue

    return None


def run_math_check_decision_engine(
    billed_qty: Decimal,
    rate: Decimal,
    printed_amount: Decimal,
    discount_pct: Decimal = Decimal("0.00"),
    discount_amt: Decimal = Decimal("0.00"),
    case_qty: Optional[Decimal] = None,
    rate_incl_tax: Optional[Decimal] = None,
    gst_rate: Optional[Decimal] = None
) -> Tuple[bool, Decimal, Decimal, str]:
    """
    Section 5.5 Math check algorithm (decision engine).
    The printed line AMOUNT is the immutable anchor.
    Candidates to try, in order, stopping at first match within Rs 1 (or 0.5%):
      1. billed_qty * rate
      2. case_qty * rate (when separate CASE/QUANTITY column exists)
      3. billed_qty * rate where rate is excl. tax
    Reconstructs third value if one is missing/unreadable.
    Returns: (math_passed, resolved_qty, resolved_rate, match_source)
    """
    amt = printed_amount if printed_amount > Decimal("0.00") else Decimal("0.00")
    if amt <= Decimal("0.00"):
        return False, billed_qty, rate, "no_amount"

    def compute_expected(q: Decimal, r: Decimal) -> Decimal:
        base = q * r
        if discount_pct > Decimal("0.00"):
            base = base * (Decimal("1.00") - discount_pct / Decimal("100.00"))
        if discount_amt > Decimal("0.00"):
            base = max(Decimal("0.00"), base - discount_amt)
        return base.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Candidate 1: billed_qty * rate
    if billed_qty > Decimal("0.00") and rate > Decimal("0.00"):
        exp1 = compute_expected(billed_qty, rate)
        if is_close(exp1, amt, abs_tol=Decimal("1.00"), rel_tol=Decimal("0.005")):
            return True, billed_qty, rate, "billed_qty_x_rate"

    # Candidate 2: case_qty * rate (when case_qty is present and differs from billed_qty)
    if case_qty and case_qty > Decimal("0.00") and rate > Decimal("0.00") and case_qty != billed_qty:
        exp2 = compute_expected(case_qty, rate)
        if is_close(exp2, amt, abs_tol=Decimal("1.00"), rel_tol=Decimal("0.005")):
            return True, case_qty, rate, "case_qty_x_rate"

    # Candidate 3: billed_qty * rate (excl. tax) when rate was taken from incl_tax column
    if billed_qty > Decimal("0.00") and rate_incl_tax and rate_incl_tax > Decimal("0.00") and gst_rate and gst_rate > Decimal("0.00"):
        rate_excl = (rate_incl_tax / (Decimal("1.00") + gst_rate / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        exp3 = compute_expected(billed_qty, rate_excl)
        if is_close(exp3, amt, abs_tol=Decimal("1.00"), rel_tol=Decimal("0.005")):
            return True, billed_qty, rate_excl, "rate_excl_tax"

    # Reconstruction (Section 5.5): If amount is present and either qty or rate is readable
    d_factor = (Decimal("1.00") - discount_pct / Decimal("100.00")) if discount_pct > Decimal("0.00") else Decimal("1.00")
    if rate <= Decimal("0.00") and billed_qty > Decimal("0.00"):
        reconstructed_rate = ((amt + discount_amt) / (billed_qty * d_factor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return True, billed_qty, reconstructed_rate, "reconstructed_rate"

    if billed_qty <= Decimal("0.00") and rate > Decimal("0.00"):
        reconstructed_qty = ((amt + discount_amt) / (rate * d_factor)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        return True, reconstructed_qty, rate, "reconstructed_qty"

    return False, billed_qty, rate, "failed"


def apply_prd_quantity_rules(
    item: InvoiceItem,
    preferred_option: Optional[str] = None,
    default_option: Optional[str] = None,
    pack_option: Optional[str] = None
) -> InvoiceItem:
    """
    PRD Addendum 2 Part A: 2-option quantity design (Bulk vs Multiplied pieces).
    - Amount is identical in both options. Never changes.
    - Shipped vs Billed: Never multiply Shipped x Billed.
      Billed qty used for Amount and BILLEDQTY.
      Shipped qty used for ACTUALQTY.
      If Shipped != Billed, flag line for review.
    - Multiplied quantity (Option 2): Billed qty * N, rate per piece = net amount / total pieces.
    - Bulk quantity (Option 1): Billed qty, rate per bulk unit.
    - Default: Option 2 for lines where a pack count is found, Option 1 for all other lines.
    """
    eff_option = preferred_option or default_option or pack_option
    # 1. Determine base amount as anchor
    line_amt = item.taxable_amount if item.taxable_amount > Decimal("0.00") else item.gross_amount
    if line_amt <= Decimal("0.00") and item.total_amount > Decimal("0.00"):
        tot_tax = item.cgst_amount + item.sgst_amount + item.igst_amount
        line_amt = max(Decimal("0.00"), item.total_amount - tot_tax)

    item.taxable_amount = line_amt

    # Check Shipped vs Billed (A3)
    if item.shipped_qty is not None and item.quantity is not None:
        if item.shipped_qty != item.quantity:
            diff_msg = f"Shipped quantity ({item.shipped_qty}) differs from billed quantity ({item.quantity})."
            item.validation_errors.append(diff_msg)
            item.needs_review = True
            item.review_reason = diff_msg

    billed_uom_upper = (item.uom or "").strip().upper()
    desc = item.description or item.item_name or ""

    # Check for Section 5.3 conversion eligibility:
    is_bulk_unit = billed_uom_upper in BULK_UNITS
    is_already_pieces = billed_uom_upper in PIECE_UNITS
    pack_match = extract_section_5_3_pack_pattern(desc)

    # Rule 5.4 / A5 check: If unit is already pieces (e.g. 864 PCS), NEVER multiply, even if (288PCS) in desc!
    can_convert = False
    pack_count = None
    piece_unit = None
    if is_bulk_unit and not is_already_pieces and pack_match:
        pack_count, piece_unit = pack_match
        can_convert = True

    item.can_convert_to_pieces = can_convert
    item.pack_size_multiplier = pack_count
    if pack_count:
        item.pack_multiplier = Decimal(str(pack_count))

    # Run Math Check Decision Engine on the printed bulk values first
    passed, res_qty, res_rate, match_source = run_math_check_decision_engine(
        billed_qty=item.quantity,
        rate=item.rate,
        printed_amount=line_amt,
        discount_pct=item.discount_pct,
        discount_amt=item.discount_amount or item.discount,
        gst_rate=item.gst_rate
    )

    item.math_check_passed = passed
    item.rate_source = match_source

    if match_source in ("reconstructed_rate", "reconstructed_qty"):
        item.is_reconstructed = True
        item.validation_errors.append("Reconstructed: One value recovered using line amount math.")

    if not passed:
        item.needs_review = True
        item.review_reason = f"Math check failed: {item.quantity} x {item.rate} != {line_amt}"
        item.validation_errors.append(f"Needs review: Printed line amount ({line_amt}) does not match Qty x Rate.")

    # If pack count found and eligible: populate Option 1 (Bulk) and Option 2 (Pieces)
    if can_convert and pack_count and pack_count > 1:
        item.quantity_option_a = res_qty
        item.uom_option_a = item.uom
        item.rate_option_a = res_rate

        total_pieces = (res_qty * Decimal(str(pack_count))).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        rate_per_piece = (res_rate / Decimal(str(pack_count))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        item.quantity_option_b = total_pieces
        item.uom_option_b = piece_unit or "Pkt"
        item.rate_option_b = rate_per_piece
        item.has_dual_qty = True

        # Choose option: eff_option or default to Option 2 if pack count found
        choose_pieces = (eff_option not in ("1", "bulk", "A"))
        if choose_pieces and passed:
            item.quantity = total_pieces
            item.uom = piece_unit or "Pkt"
            item.rate = rate_per_piece
            item.alternate_quantity = res_qty
            item.alternate_uom = item.uom_option_a
            item.is_converted_to_pieces = True
            item.selected_qty_option = "B"
            if item.shipped_qty is not None:
                item.shipped_qty = (item.shipped_qty * Decimal(str(pack_count))).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        else:
            item.quantity = res_qty
            item.rate = res_rate
            item.is_converted_to_pieces = False
            item.selected_qty_option = "A"
    else:
        # Single quantity column: update resolved quantity and rate without activating dual options
        item.quantity = res_qty
        item.rate = res_rate
        item.is_converted_to_pieces = False
        if not pack_match and is_bulk_unit:
            item.validation_errors.append("No pack count")

    # AMOUNT printed on invoice stays strictly unchanged!
    item.taxable_amount = line_amt
    item.gross_amount = line_amt
    return item


# =====================================================================
# SECTION 6: GST Rate Extraction & Priority Hierarchy
# =====================================================================

def resolve_prd_gst_rates(
    item: InvoiceItem,
    is_interstate: bool = False,
    single_column_mode: bool = False
) -> InvoiceItem:
    """
    Section 6 GST Rate Hierarchy:
    1. Line-level 'GST Rate' or 'TAX %' column (Total rate - DO NOT double).
    2. CGST(%) + SGST(%) columns (Combine or double half-rates).
    3. CGST/SGST rate + amount per line.
    4. Derive rate from CGST+SGST amount / taxable * 100 -> nearest standard slab.
    5. Bottom tax summary table.
    Enforces 0% tax-free lines.
    Enforces IGST for interstate.
    """
    taxable = item.taxable_amount

    # Trap: 0% tax-free line (must stay 0, do not apply main slab)
    if (item.cgst_rate == Decimal("0.00") and item.sgst_rate == Decimal("0.00") and item.igst_rate == Decimal("0.00")
            and item.gst_rate == Decimal("0.00")):
        item.gst_rate = Decimal("0.00")
        item.cgst_rate = Decimal("0.00")
        item.sgst_rate = Decimal("0.00")
        item.igst_rate = Decimal("0.00")
        item.cgst_amount = Decimal("0.00")
        item.sgst_amount = Decimal("0.00")
        item.igst_amount = Decimal("0.00")
        item.gst_rate_source = "zero_tax_free"
        item.total_amount = taxable
        return item

    # Priority 1: Single GST Rate / Tax % Column
    if single_column_mode or (item.gst_rate is not None and item.gst_rate > Decimal("0.00") and item.cgst_rate == Decimal("0.00") and item.sgst_rate == Decimal("0.00")):
        tot_r = item.gst_rate
        item.gst_rate_source = "single_tax_pct_column"
        if is_interstate:
            item.igst_rate = tot_r
            item.cgst_rate = Decimal("0.00")
            item.sgst_rate = Decimal("0.00")
        else:
            item.cgst_rate = (tot_r / Decimal("2.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            item.sgst_rate = tot_r - item.cgst_rate
            item.igst_rate = Decimal("0.00")

    # Priority 2: Component columns (CGST% + SGST%)
    elif item.cgst_rate > Decimal("0.00") or item.sgst_rate > Decimal("0.00"):
        if is_interstate:
            item.igst_rate = item.cgst_rate + item.sgst_rate
            item.cgst_rate = Decimal("0.00")
            item.sgst_rate = Decimal("0.00")
        else:
            if item.cgst_rate > Decimal("0.00") and item.sgst_rate == Decimal("0.00"):
                item.sgst_rate = item.cgst_rate
            elif item.sgst_rate > Decimal("0.00") and item.cgst_rate == Decimal("0.00"):
                item.cgst_rate = item.sgst_rate
        item.gst_rate = item.igst_rate if is_interstate else (item.cgst_rate + item.sgst_rate)
        item.gst_rate_source = "component_rate_columns"

    # Priority 4: Derive rate from tax amounts when only amounts are printed
    elif taxable > Decimal("0.00") and (item.cgst_amount > Decimal("0.00") or item.igst_amount > Decimal("0.00")):
        tot_tax = item.igst_amount if is_interstate else (item.cgst_amount + item.sgst_amount)
        raw_rate = (tot_tax / taxable * Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # Snap to nearest standard GST slab (0, 3, 5, 12, 18, 28)
        best_slab = min(STANDARD_GST_SLABS, key=lambda s: abs(s - raw_rate))
        item.gst_rate = best_slab
        item.gst_rate_source = "derived_from_amount"
        if is_interstate:
            item.igst_rate = best_slab
            item.cgst_rate = Decimal("0.00")
            item.sgst_rate = Decimal("0.00")
        else:
            item.cgst_rate = (best_slab / Decimal("2.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            item.sgst_rate = best_slab - item.cgst_rate
            item.igst_rate = Decimal("0.00")

    # Recompute component amounts matching taxable value
    if taxable > Decimal("0.00"):
        if is_interstate:
            if item.igst_rate > Decimal("0.00") and item.igst_amount <= Decimal("0.00"):
                item.igst_amount = (taxable * item.igst_rate / Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            if item.cgst_rate > Decimal("0.00") and item.cgst_amount <= Decimal("0.00"):
                item.cgst_amount = (taxable * item.cgst_rate / Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if item.sgst_rate > Decimal("0.00") and item.sgst_amount <= Decimal("0.00"):
                item.sgst_amount = (taxable * item.sgst_rate / Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    item.total_amount = taxable + item.cgst_amount + item.sgst_amount + item.igst_amount + item.cess_amount
    return item


# =====================================================================
# ADDENDUM 1 PART 2: Tax-Inclusive Invoices Detection & Split
# =====================================================================

TAX_INCLUSIVE_KEYWORDS: List[str] = [
    "incl. of tax", "incl of tax", "inclusive of tax", "inclusive of taxes",
    "inclusive of gst", "tax included", "mrp inclusive", "rates are inclusive",
    "prices inclusive of all taxes", "all taxes inclusive", "rates incl", "tax inclusive"
]

class TaxModeResult(str):
    """Result object for detect_prd_tax_mode that behaves as both a string and a (mode, why, metrics) tuple."""
    def __new__(cls, mode: str, why: str = "", metrics: Optional[Dict[str, Any]] = None):
        instance = super().__new__(cls, mode)
        instance.mode = mode
        instance.why = why
        instance.metrics = metrics or {}
        return instance

    def __iter__(self):
        return iter((self.mode, self.why, self.metrics))

def detect_prd_tax_mode(
    items_or_doc: Any = None,
    grand_total: Optional[Decimal] = None,
    discounts: Decimal = Decimal("0.00"),
    other_charges: Decimal = Decimal("0.00"),
    round_off: Decimal = Decimal("0.00"),
    full_text: Optional[str] = None,
    printed_taxable_total: Optional[Decimal] = None,
    printed_tax_total: Optional[Decimal] = None,
    items: Optional[List[InvoiceItem]] = None
) -> TaxModeResult:
    """
    PRD Addendum 1 Part 2.3: Decides tax mode (exclusive vs inclusive) using rigorous signals:
    S = sum of line amounts
    T = total GST printed (CGST + SGST or IGST)
    G = Grand total / Net amount
    Exclusive test: S - D + T + C + RO ≈ G
    Inclusive test: S - D + C + RO ≈ G (T is already inside S)
    Returns: TaxModeResult (str & tuple compatible: mode, why, metrics)
    """
    if items is not None:
        items_or_doc = items

    if hasattr(items_or_doc, "items"):
        doc = items_or_doc
        items_list = doc.items
        grand_total = grand_total if grand_total is not None else doc.grand_total
        discounts = discounts if discounts != Decimal("0.00") else (doc.discount_total or Decimal("0.00"))
        other_charges = other_charges if other_charges != Decimal("0.00") else (doc.other_charges or Decimal("0.00"))
        round_off = round_off if round_off != Decimal("0.00") else (doc.round_off or Decimal("0.00"))
        printed_taxable_total = printed_taxable_total if printed_taxable_total is not None else doc.taxable_total
        printed_tax_total = printed_tax_total if printed_tax_total is not None else (doc.cgst_total + doc.sgst_total + doc.igst_total)
    else:
        items_list = items_or_doc or []
        grand_total = grand_total or Decimal("0.00")

    has_incl_text = False
    if full_text:
        lower_txt = full_text.lower()
        has_incl_text = any(k in lower_txt for k in TAX_INCLUSIVE_KEYWORDS)

    s_amt = sum((it.taxable_amount if it.taxable_amount > Decimal("0.00") else it.total_amount for it in items_list), Decimal("0.00"))
    t_tax = printed_tax_total if printed_tax_total is not None and printed_tax_total > Decimal("0.00") else sum(
        (it.cgst_amount + it.sgst_amount + it.igst_amount for it in items_list), Decimal("0.00")
    )
    g_total = grand_total if grand_total > Decimal("0.00") else (s_amt + t_tax)

    excl_expected = s_amt - discounts + t_tax + other_charges + round_off
    incl_expected = s_amt - discounts + other_charges + round_off

    excl_diff = abs(excl_expected - g_total)
    incl_diff = abs(incl_expected - g_total)

    metrics = {
        "s_amt": float(s_amt),
        "t_tax": float(t_tax),
        "g_total": float(g_total),
        "excl_diff": float(excl_diff),
        "incl_diff": float(incl_diff),
        "has_incl_text": has_incl_text
    }

    # Situation 1 (Section 2.2): Exclusive invoice with informational rate incl column
    # S + T ≈ G -> exclusive!
    if excl_diff <= Decimal("1.50") and (incl_diff > Decimal("1.50") or t_tax <= Decimal("0.00")):
        return TaxModeResult("exclusive", "Line amounts + GST = Grand Total (Exclusive invoice)", metrics)

    # Situation 2 (Section 2.2): Truly inclusive invoice
    # S ≈ G and T > 0 -> inclusive!
    if incl_diff <= Decimal("1.50") and t_tax > Decimal("0.00") and excl_diff > Decimal("1.50"):
        return TaxModeResult("inclusive", "Line amounts alone ≈ Grand Total; GST is included inside amounts (Inclusive invoice)", metrics)

    if has_incl_text and incl_diff <= Decimal("2.00") and t_tax > Decimal("0.00"):
        return TaxModeResult("inclusive", "Invoice states tax-inclusive pricing and line amounts match grand total", metrics)

    # Bottom summary comparison test per line
    if printed_taxable_total and printed_taxable_total > Decimal("0.00"):
        calc_split_taxable = Decimal("0.00")
        for it in items_list:
            r = (it.gst_rate or Decimal("0.00"))
            if r <= Decimal("0.00"):
                r = (it.cgst_rate or Decimal("0.00")) + (it.sgst_rate or Decimal("0.00")) + (it.igst_rate or Decimal("0.00"))
            if r > Decimal("0.00"):
                calc_split_taxable += (it.taxable_amount / (Decimal("1.00") + r / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                calc_split_taxable += it.taxable_amount
        if abs(calc_split_taxable - printed_taxable_total) <= Decimal("1.50"):
            return TaxModeResult("inclusive", "Line amounts divided by (1+GST) match printed taxable summary (Inclusive invoice)", metrics)

    if excl_diff < incl_diff:
        return TaxModeResult("exclusive", "Exclusive formula has closer arithmetic match", metrics)
    elif incl_diff < excl_diff and t_tax > Decimal("0.00"):
        return TaxModeResult("inclusive", "Inclusive formula has closer arithmetic match", metrics)

    return TaxModeResult("unknown", "Tax mode unclear from arithmetic; please verify on review screen", metrics)


def apply_prd_tax_inclusive_split(
    item_or_items: Any,
    is_interstate: bool = False
) -> Any:
    """
    PRD Addendum 1 Section 2.4: Calculates tax-inclusive breakdown per line:
    taxable_value = line_amount / (1 + gst_rate / 100)
    gst_amount = line_amount - taxable_value
    CGST = SGST = gst_amount / 2 (same state)
    IGST = gst_amount (different state)
    base_rate = taxable_value / qty (or rate / (1 + gst_rate / 100))
    0% tax-free lines: taxable = amount, tax = 0. Do not divide.
    """
    if isinstance(item_or_items, list):
        return [apply_prd_tax_inclusive_split(it, is_interstate=is_interstate) for it in item_or_items]

    item: InvoiceItem = item_or_items
    disc = item.discount if (item.discount is not None and item.discount > Decimal("0.00")) else (item.discount_amount or Decimal("0.00"))
    if item.total_amount > Decimal("0.00") and (disc > Decimal("0.00") or item.taxable_amount <= Decimal("0.00")):
        line_amount = item.total_amount
    elif item.taxable_amount > Decimal("0.00"):
        line_amount = item.taxable_amount - disc
    else:
        line_amount = item.total_amount

    if line_amount <= Decimal("0.00"):
        return item

    gst_r = item.gst_rate if item.gst_rate is not None and item.gst_rate > Decimal("0.00") else (
        item.igst_rate if item.igst_rate > Decimal("0.00") else (item.cgst_rate + item.sgst_rate)
    )

    if gst_r <= Decimal("0.00"):
        item.taxable_amount = line_amount
        item.gross_amount = line_amount
        item.total_amount = line_amount
        item.cgst_amount = Decimal("0.00")
        item.sgst_amount = Decimal("0.00")
        item.igst_amount = Decimal("0.00")
        item.is_tax_inclusive = True
        item.tax_mode = "inclusive"
        return item

    factor = Decimal("1.00") + (gst_r / Decimal("100.00"))
    taxable_val = (line_amount / factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    gst_amt = line_amount - taxable_val

    if is_interstate:
        cgst = Decimal("0.00")
        sgst = Decimal("0.00")
        igst = gst_amt
    else:
        cgst = (gst_amt / Decimal("2.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sgst = gst_amt - cgst
        igst = Decimal("0.00")

    if item.quantity > Decimal("0.00"):
        base_rate = (taxable_val / item.quantity).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    elif item.rate > Decimal("0.00"):
        base_rate = (item.rate / factor).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    else:
        base_rate = taxable_val

    item.taxable_amount = taxable_val
    item.gross_amount = taxable_val
    item.rate = base_rate
    item.cgst_amount = cgst
    item.sgst_amount = sgst
    item.igst_amount = igst
    item.total_amount = line_amount
    item.is_tax_inclusive = True
    item.tax_mode = "inclusive"
    return item


# =====================================================================
# SECTION 7: 6-Point Reconciliation Engine, Discounts & State Normalizer
# =====================================================================

def resolve_prd_discount_pattern(
    doc: InvoiceDocument,
    full_text: Optional[str] = None
) -> InvoiceDocument:
    """
    PRD Addendum 2 Part C: Discount Handling & Decision Procedure.
    Answers:
      1. Is the discount already inside the Amount, or must it still be subtracted?
      2. Is the discount applied before GST (on taxable value), or after GST (on the grand total)?
    Evaluates Patterns P1 - P7 using the bill's own totals as judge:
      P1: Amount is already net of discount (qty * rate - disc = Amount).
      P2: Amount is gross; separate discount column subtracted (Net = Amount - discount).
      P3: One discount line at bottom before tax (spread proportionally across lines).
      P4: Discount after GST (post-tax discount posted to separate ledger, taxable & GST unchanged).
      P5: Rate already net (no discount).
      P6: Two discounts applied sequentially.
      P7: Free goods / scheme quantity (quantity with zero amount).
    """
    s_amt = sum((it.taxable_amount if it.taxable_amount > Decimal("0.00") else it.total_amount for it in doc.items), Decimal("0.00"))
    d_line = sum(((it.discount or it.discount_amount or Decimal("0.00")) for it in doc.items), Decimal("0.00"))
    d_bottom = doc.discount_total or Decimal("0.00")
    x_taxable = doc.taxable_total
    t_tax = doc.cgst_total + doc.sgst_total + doc.igst_total
    g_total = doc.grand_total

    # P7 Check: Identify free goods lines
    has_free = False
    for it in doc.items:
        if it.quantity > Decimal("0.00") and (it.taxable_amount <= Decimal("0.00") or it.rate <= Decimal("0.00")):
            it.is_free_item = True
            it.discount_pattern = "P7_FREE_GOODS"
            has_free = True

    if has_free and d_line <= Decimal("0.00") and d_bottom <= Decimal("0.00"):
        doc.discount_pattern = "P7_FREE_GOODS"
        doc.discount_pattern_note = "Invoice contains free/scheme items with zero taxable amount."
        return doc

    # Pattern P5: No discounts present
    if d_line <= Decimal("0.00") and d_bottom <= Decimal("0.00"):
        doc.discount_pattern = "P5_NO_DISCOUNT"
        doc.discount_pattern_note = "No discounts detected; rates and amounts are net."
        return doc

    # Pattern P4 Check: Discount after GST (on total)
    # Taxable summary equals line amounts (X ≈ S), GST is on full amount, and G ≈ X + T - D_bottom
    if d_bottom > Decimal("0.00") and x_taxable > Decimal("0.00"):
        if is_close(x_taxable, s_amt, abs_tol=Decimal("1.50")) and is_close(g_total, x_taxable + t_tax - d_bottom, abs_tol=Decimal("2.00")):
            doc.discount_pattern = "P4_POST_TAX_DISCOUNT"
            doc.discount_pattern_note = f"Post-tax discount ₹{d_bottom} applied after GST; posted to Discount ledger."
            doc.post_tax_discount = d_bottom
            for it in doc.items:
                it.discount_pattern = "P4_POST_TAX_DISCOUNT"
            return doc

    # Pattern P1 Check: Amount is already net of line discount
    # Lines satisfy: qty * rate - disc ≈ Amount, X ≈ S, and G ≈ X + T
    if d_line > Decimal("0.00"):
        line_p1_matches = 0
        for it in doc.items:
            disc = it.discount or it.discount_amount or Decimal("0.00")
            if disc > Decimal("0.00") and it.quantity > Decimal("0.00") and it.rate > Decimal("0.00"):
                gross = (it.quantity * it.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if is_close(gross - disc, it.taxable_amount, abs_tol=Decimal("1.00")):
                    line_p1_matches += 1

        if line_p1_matches > 0 or (x_taxable > Decimal("0.00") and is_close(x_taxable, s_amt, abs_tol=Decimal("1.50"))):
            doc.discount_pattern = "P1_ALREADY_NET"
            doc.discount_pattern_note = "Line amounts are already net of discount. Discount not subtracted again."
            for it in doc.items:
                it.discount_pattern = "P1_ALREADY_NET"
            return doc

    # Pattern P2 Check: Amount is gross, separate discount column subtracted
    # Taxable summary X ≈ S - D_line and G ≈ X + T
    if d_line > Decimal("0.00"):
        if x_taxable > Decimal("0.00") and is_close(x_taxable, s_amt - d_line, abs_tol=Decimal("1.50")):
            doc.discount_pattern = "P2_GROSS_SUBTRACT_LINE_DISCOUNT"
            doc.discount_pattern_note = "Line discounts subtracted from gross line amounts before GST."
            for it in doc.items:
                disc = it.discount or it.discount_amount or Decimal("0.00")
                if disc > Decimal("0.00"):
                    it.gross_amount = it.taxable_amount
                    it.taxable_amount = max(Decimal("0.00"), it.taxable_amount - disc)
                    # Recompute taxes on net taxable
                    gst_r = (it.gst_rate or Decimal("0.00"))
                    if gst_r <= Decimal("0.00"):
                        gst_r = (it.cgst_rate or Decimal("0.00")) + (it.sgst_rate or Decimal("0.00")) + (it.igst_rate or Decimal("0.00"))
                    if gst_r > Decimal("0.00"):
                        if (it.igst_rate or Decimal("0.00")) > Decimal("0.00"):
                            it.igst_amount = (it.taxable_amount * gst_r / Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        else:
                            cgst = (it.taxable_amount * (gst_r / Decimal("2.00")) / Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                            it.cgst_amount = cgst
                            it.sgst_amount = cgst
                    it.total_amount = it.taxable_amount + it.cgst_amount + it.sgst_amount + it.igst_amount
                it.discount_pattern = "P2_GROSS_SUBTRACT_LINE_DISCOUNT"

            doc.taxable_total = sum(it.taxable_amount for it in doc.items)
            doc.cgst_total = sum(it.cgst_amount for it in doc.items)
            doc.sgst_total = sum(it.sgst_amount for it in doc.items)
            doc.igst_total = sum(it.igst_amount for it in doc.items)
            return doc

    # Pattern P3 Check: One discount line at bottom before tax (spread proportionally)
    # Taxable summary X ≈ S - D_bottom and G ≈ X + T
    if d_bottom > Decimal("0.00"):
        if x_taxable > Decimal("0.00") and is_close(x_taxable, s_amt - d_bottom, abs_tol=Decimal("1.50")):
            doc.discount_pattern = "P3_BOTTOM_DISCOUNT_BEFORE_TAX"
            doc.discount_pattern_note = f"Bottom discount ₹{d_bottom} spread proportionally across lines before GST."
            # Spread d_bottom proportionally by line amount
            for it in doc.items:
                ratio = (it.taxable_amount / s_amt) if s_amt > Decimal("0.00") else (Decimal("1.00") / Decimal(str(len(doc.items))))
                alloc_disc = (d_bottom * ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                it.taxable_amount = max(Decimal("0.00"), it.taxable_amount - alloc_disc)
                gst_r = (it.gst_rate or Decimal("0.00"))
                if gst_r <= Decimal("0.00"):
                    gst_r = (it.cgst_rate or Decimal("0.00")) + (it.sgst_rate or Decimal("0.00")) + (it.igst_rate or Decimal("0.00"))
                if gst_r > Decimal("0.00"):
                    if (it.igst_rate or Decimal("0.00")) > Decimal("0.00"):
                        it.igst_amount = (it.taxable_amount * gst_r / Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    else:
                        cgst = (it.taxable_amount * (gst_r / Decimal("2.00")) / Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        it.cgst_amount = cgst
                        it.sgst_amount = cgst
                it.total_amount = it.taxable_amount + it.cgst_amount + it.sgst_amount + it.igst_amount
                it.discount_pattern = "P3_BOTTOM_DISCOUNT_BEFORE_TAX"

            doc.taxable_total = sum(it.taxable_amount for it in doc.items)
            doc.cgst_total = sum(it.cgst_amount for it in doc.items)
            doc.sgst_total = sum(it.sgst_amount for it in doc.items)
            doc.igst_total = sum(it.igst_amount for it in doc.items)
            return doc

    # Pattern P6 Check: Two discounts applied sequentially
    if d_line > Decimal("0.00") and d_bottom > Decimal("0.00"):
        s_after_line = s_amt - d_line
        if x_taxable > Decimal("0.00") and is_close(x_taxable, s_after_line - d_bottom, abs_tol=Decimal("2.00")):
            doc.discount_pattern = "P6_TWO_DISCOUNTS_SEQUENTIAL"
            doc.discount_pattern_note = "Sequential trade and bottom discounts applied."
            for it in doc.items:
                disc = it.discount or it.discount_amount or Decimal("0.00")
                it.taxable_amount = max(Decimal("0.00"), it.taxable_amount - disc)
            s_rem = sum(it.taxable_amount for it in doc.items)
            for it in doc.items:
                ratio = (it.taxable_amount / s_rem) if s_rem > Decimal("0.00") else Decimal("0.00")
                alloc = (d_bottom * ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                it.taxable_amount = max(Decimal("0.00"), it.taxable_amount - alloc)
                gst_r = (it.gst_rate or Decimal("0.00"))
                if gst_r <= Decimal("0.00"):
                    gst_r = (it.cgst_rate or Decimal("0.00")) + (it.sgst_rate or Decimal("0.00")) + (it.igst_rate or Decimal("0.00"))
                if gst_r > Decimal("0.00"):
                    if (it.igst_rate or Decimal("0.00")) > Decimal("0.00"):
                        it.igst_amount = (it.taxable_amount * gst_r / Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    else:
                        cgst = (it.taxable_amount * (gst_r / Decimal("2.00")) / Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        it.cgst_amount = cgst
                        it.sgst_amount = cgst
                it.total_amount = it.taxable_amount + it.cgst_amount + it.sgst_amount + it.igst_amount
                it.discount_pattern = "P6_TWO_DISCOUNTS_SEQUENTIAL"

            doc.taxable_total = sum(it.taxable_amount for it in doc.items)
            doc.cgst_total = sum(it.cgst_amount for it in doc.items)
            doc.sgst_total = sum(it.sgst_amount for it in doc.items)
            doc.igst_total = sum(it.igst_amount for it in doc.items)
            return doc

    # Fallback when tax summary is not printed: compare computed grand total hypotheses
    if is_close(g_total, s_amt + t_tax, abs_tol=Decimal("2.00")):
        doc.discount_pattern = "P1_ALREADY_NET"
        doc.discount_pattern_note = "Line amounts match Grand Total - Tax. Discarding double discount."
        return doc
    elif d_line > Decimal("0.00") and is_close(g_total, (s_amt - d_line) + t_tax, abs_tol=Decimal("2.00")):
        doc.discount_pattern = "P2_GROSS_SUBTRACT_LINE_DISCOUNT"
        doc.discount_pattern_note = "Line discount subtracted to match Grand Total."
        return doc
    elif d_bottom > Decimal("0.00") and is_close(g_total, (s_amt - d_bottom) + t_tax, abs_tol=Decimal("2.00")):
        doc.discount_pattern = "P3_BOTTOM_DISCOUNT_BEFORE_TAX"
        doc.discount_pattern_note = "Bottom discount subtracted before tax to match Grand Total."
        return doc
    elif d_bottom > Decimal("0.00") and is_close(g_total, s_amt + t_tax - d_bottom, abs_tol=Decimal("2.00")):
        doc.discount_pattern = "P4_POST_TAX_DISCOUNT"
        doc.discount_pattern_note = "Post-tax discount deducted after GST."
        doc.post_tax_discount = d_bottom
        return doc

    doc.discount_pattern = "DISCOUNT_UNCLEAR"
    doc.discount_pattern_note = "Discount application unclear from arithmetic; please verify on review screen."
    doc.warnings.append("Discount unclear: please verify whether discount is before or after tax.")
    return doc


def reconcile_invoice_document(
    doc: InvoiceDocument,
    full_text: Optional[str] = None
) -> InvoiceDocument:
    """
    Section 7 Unified Reconciliation Checks & Addendum 1 & Addendum 2:
    1. Normalizes all states (doc.supplier.state, doc.buyer.state, doc.place_of_supply) to canonical Tally names.
    2. Resolves discount pattern (P1 - P7) to determine pre-tax vs post-tax discounts.
    3. Detects and applies tax mode (exclusive vs inclusive) using rigorous signals.
    4. Reconciles subtotal, grand total, round-off, tax slabs, and line item counts.
    """
    # 1. State normalization (Addendum 1 Part 1)
    normalize_document_states(doc)
    is_interstate = not are_states_intra_state(doc.supplier.state_code, doc.buyer.state_code)

    # 2. Tax mode handling (Addendum 1 Part 2)
    if doc.tax_mode == "inclusive" or any(it.is_tax_inclusive for it in doc.items) or doc.is_tax_inclusive:
        doc.tax_mode = "inclusive"
        doc.is_tax_inclusive = True
        if not any(it.is_tax_inclusive for it in doc.items):
            for it in doc.items:
                apply_prd_tax_inclusive_split(it, is_interstate=is_interstate)
        doc.taxable_total = sum(it.taxable_amount for it in doc.items)
        doc.cgst_total = sum(it.cgst_amount for it in doc.items)
        doc.sgst_total = sum(it.sgst_amount for it in doc.items)
        doc.igst_total = sum(it.igst_amount for it in doc.items)
    elif doc.tax_mode == "exclusive" or doc.tax_mode is None or doc.tax_mode == "unknown":
        t_printed = (doc.cgst_total + doc.sgst_total + doc.igst_total) if (doc.cgst_total + doc.sgst_total + doc.igst_total) > Decimal("0.00") else None
        mode, why, _ = detect_prd_tax_mode(
            items=doc.items,
            grand_total=doc.grand_total,
            discounts=doc.discount_total,
            other_charges=doc.other_charges,
            round_off=doc.round_off,
            full_text=full_text or doc.raw_text_preview,
            printed_taxable_total=doc.taxable_total if doc.taxable_total > Decimal("0.00") else None,
            printed_tax_total=t_printed
        )
        doc.tax_mode = mode
        doc.tax_mode_evidence = why
        if mode == "inclusive":
            doc.is_tax_inclusive = True
            for it in doc.items:
                apply_prd_tax_inclusive_split(it, is_interstate=is_interstate)
            doc.taxable_total = sum(it.taxable_amount for it in doc.items)
            doc.cgst_total = sum(it.cgst_amount for it in doc.items)
            doc.sgst_total = sum(it.sgst_amount for it in doc.items)
            doc.igst_total = sum(it.igst_amount for it in doc.items)

    # 3. Discount pattern resolution (Addendum 2 Part C)
    resolve_prd_discount_pattern(doc, full_text=full_text)

    flags: List[str] = []

    # 4. Reconciliation Checks
    calc_taxable = sum((it.taxable_amount for it in doc.items), Decimal("0.00"))
    calc_cgst = sum((it.cgst_amount for it in doc.items), Decimal("0.00"))
    calc_sgst = sum((it.sgst_amount for it in doc.items), Decimal("0.00"))
    calc_igst = sum((it.igst_amount for it in doc.items), Decimal("0.00"))
    calc_cess = sum((it.cess_amount for it in doc.items), Decimal("0.00"))

    if doc.cgst_total <= Decimal("0.00"):
        doc.cgst_total = calc_cgst
    if doc.sgst_total <= Decimal("0.00"):
        doc.sgst_total = calc_sgst
    if doc.igst_total <= Decimal("0.00"):
        doc.igst_total = calc_igst
    if doc.cess_total <= Decimal("0.00"):
        doc.cess_total = calc_cess

    if doc.tax_mode == "inclusive":
        calc_incl_sum = sum((it.total_amount for it in doc.items), Decimal("0.00"))
        expected_incl = doc.grand_total - doc.other_charges - doc.round_off + doc.discount_total
        if doc.grand_total > Decimal("0.00") and not is_close(calc_incl_sum, expected_incl, abs_tol=Decimal("1.50")):
            flags.append(f"Inclusive line sum mismatch: Sum of lines ({calc_incl_sum}) != Net amount ({expected_incl})")
        doc.taxable_total = calc_taxable
    else:
        if doc.taxable_total > Decimal("0.00"):
            if not is_close(calc_taxable, doc.taxable_total, abs_tol=Decimal("1.50")):
                flags.append(f"Sub-total mismatch: Sum of lines ({calc_taxable}) != Sub-total ({doc.taxable_total})")
        else:
            doc.taxable_total = calc_taxable

    # Check whether discount was already subtracted or is post-tax
    disc_deduct = doc.post_tax_discount if doc.discount_pattern == "P4_POST_TAX_DISCOUNT" else Decimal("0.00")
    if doc.discount_pattern not in ("P1_ALREADY_NET", "P2_GROSS_SUBTRACT_LINE_DISCOUNT", "P3_BOTTOM_DISCOUNT_BEFORE_TAX", "P5_NO_DISCOUNT", "P6_TWO_DISCOUNTS_SEQUENTIAL") and disc_deduct == Decimal("0.00"):
        disc_deduct = doc.discount_total

    computed_grand = (
        doc.taxable_total - disc_deduct
        + doc.cgst_total + doc.sgst_total + doc.igst_total + doc.cess_total
        + doc.other_charges + doc.round_off
    )

    if doc.grand_total > Decimal("0.00"):
        if not is_close(computed_grand, doc.grand_total, abs_tol=Decimal("1.50")):
            flags.append(f"Grand total mismatch: Computed ({computed_grand}) != Printed ({doc.grand_total})")
    else:
        doc.grand_total = computed_grand.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    ro_diff = abs(doc.grand_total - (computed_grand - doc.round_off))
    if ro_diff >= Decimal("1.00") and doc.round_off != Decimal("0.00"):
        flags.append(f"Round-off discrepancy: Round-off value ({doc.round_off}) exceeds +/- 1.00")

    if doc.tax_mode == "unknown":
        flags.append("Tax mode unclear: Please verify whether amounts include GST.")

    unresolved_lines = [it for it in doc.items if it.needs_review]
    if unresolved_lines:
        flags.append(f"{len(unresolved_lines)} line(s) failed math check and need review.")

    doc.reconciliation_flags = flags
    doc.reconciliation_passed = len(flags) == 0
    if not doc.reconciliation_passed:
        doc.needs_review = True

    return doc


# =====================================================================
# SECTION 3: Sales vs Purchase via Company GSTIN
# =====================================================================

def resolve_sales_vs_purchase(
    supplier: PartyInfo,
    buyer: PartyInfo,
    company_gstin: Optional[str] = None
) -> Tuple[str, PartyInfo]:
    """
    Section 3: Sales vs Purchase
    If Company GSTIN == Buyer GSTIN -> PURCHASE (party = Supplier).
    If Company GSTIN == Supplier GSTIN -> SALES (party = Buyer).
    Returns (voucher_type, party_to_map).
    """
    clean_co = (company_gstin or "02AWLPK8092M1Z0").strip().upper()
    sup_g = (supplier.gstin or "").strip().upper()
    buy_g = (buyer.gstin or "").strip().upper()

    if clean_co and buy_g and buy_g == clean_co:
        return "PURCHASE", supplier

    if clean_co and sup_g and sup_g == clean_co:
        return "SALES", buyer

    # Default based on presence
    return "PURCHASE", supplier
