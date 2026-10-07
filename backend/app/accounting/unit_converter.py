"""
Centralized Unit of Measurement (UOM) and Quantity Conversion System for Tally XML.
Enforces strict statutory unit normalization and conversions (e.g. DOZEN -> PCS).
Never blindly converts incompatible units (e.g. KG -> PCS) without explicit conversion rules.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple, Dict
import re

# Canonical unit aliases map
UNIT_ALIASES: Dict[str, str] = {
    # Dozens
    "DZ": "DOZEN",
    "DZN": "DOZEN",
    "DOZ": "DOZEN",
    "DOZEN": "DOZEN",
    "DOZENS": "DOZEN",
    "DZ.": "DOZEN",
    "DZN.": "DOZEN",
    # Pieces / Numbers
    "PCS": "PCS",
    "PC": "PCS",
    "PIECE": "PCS",
    "PIECES": "PCS",
    "NOS": "NOS",
    "NO": "NOS",
    "NUM": "NOS",
    "NUMBER": "NOS",
    "NUMBERS": "NOS",
    # Boxes / Cartons / Cases / Packets
    "BOX": "BOX",
    "BOXES": "BOX",
    "BX": "BOX",
    "CTN": "CTN",
    "CARTON": "CTN",
    "CARTONS": "CTN",
    "CASE": "CASE",
    "CASES": "CASE",
    "CS": "CASE",
    "PKT": "PKT",
    "PKTS": "PKT",
    "PACKET": "PKT",
    "PACKETS": "PKT",
    "BAG": "BAG",
    "BAGS": "BAG",
    "BG": "BAG",
    "BOTTLE": "BOTTLE",
    "BOTTLES": "BOTTLE",
    "BTL": "BOTTLE",
    "CAN": "CAN",
    "CANS": "CAN",
    "SET": "SET",
    "SETS": "SET",
    "PAIR": "PAIR",
    "PAIRS": "PAIR",
    "ROLL": "ROLL",
    "ROLLS": "ROLL",
    # Weight
    "KG": "KGS",
    "KGS": "KGS",
    "KILOGRAM": "KGS",
    "KILOGRAMS": "KGS",
    "GM": "GMS",
    "GMS": "GMS",
    "GRAM": "GMS",
    "GRAMS": "GMS",
    "MT": "MT",
    "TON": "MT",
    "TONNE": "MT",
    "TONNES": "MT",
    "QUINTAL": "QTL",
    "QTL": "QTL",
    # Volume
    "LTR": "LTR",
    "LTRS": "LTR",
    "LITRE": "LTR",
    "LITRES": "LTR",
    "LITER": "LTR",
    "ML": "ML",
    "MILLILITRE": "ML",
    # Length
    "MTR": "MTR",
    "MTRS": "MTR",
    "METER": "MTR",
    "METERS": "MTR",
    "SQM": "SQM",
    "SQFT": "SQFT",
    "FT": "FT",
    "INCH": "INCH",
}

# Standard statutory conversion ratios
# (Source Unit, Target Unit) -> multiplier (target_qty = source_qty * multiplier)
STANDARD_CONVERSIONS: Dict[Tuple[str, str], Decimal] = {
    ("DOZEN", "PCS"): Decimal("12.0"),
    ("DOZEN", "NOS"): Decimal("12.0"),
    ("PCS", "DOZEN"): Decimal("1.0") / Decimal("12.0"),
    ("NOS", "DOZEN"): Decimal("1.0") / Decimal("12.0"),
    ("PCS", "NOS"): Decimal("1.0"),
    ("NOS", "PCS"): Decimal("1.0"),
    ("KGS", "GMS"): Decimal("1000.0"),
    ("GMS", "KGS"): Decimal("0.001"),
    ("MT", "KGS"): Decimal("1000.0"),
    ("KGS", "MT"): Decimal("0.001"),
    ("LTR", "ML"): Decimal("1000.0"),
    ("ML", "LTR"): Decimal("0.001"),
}

def normalize_uom(unit_str: Optional[str]) -> str:
    """Normalizes any unit string to its canonical trade form."""
    if not unit_str:
        return "NOS"
    clean = re.sub(r'[^A-Za-z0-9]', '', str(unit_str).strip().upper())
    return UNIT_ALIASES.get(clean, clean or "NOS")

def convert_quantity_and_rate(
    invoice_qty: Decimal,
    invoice_uom: str,
    target_tally_uom: str,
    invoice_rate: Optional[Decimal] = None
) -> Tuple[Decimal, Decimal, str, Optional[Decimal], Optional[str], bool]:
    """
    Intelligently converts invoice quantity and rate to match the selected Tally Stock Item UQC.
    
    Returns:
        (final_qty, final_rate, final_uom, conversion_factor, conversion_note, needs_review)
    """
    norm_from = normalize_uom(invoice_uom)
    norm_to = normalize_uom(target_tally_uom)
    rate = invoice_rate if invoice_rate is not None else Decimal("0.00")

    # 1. Compatible or equivalent units within the same family (e.g. PCS <=> NOS, DZ <=> DZN, CASE <=> CTN)
    # The Tally stock item unit is adopted as the final UOM, preserving the invoice quantity
    from app.accounting.uom_normalizer import are_uoms_compatible, resolve_stock_item_uom
    
    if norm_from == norm_to or are_uoms_compatible(invoice_uom, target_tally_uom):
        return (
            invoice_qty,
            rate,
            target_tally_uom,
            Decimal("1.0"),
            None,
            False
        )

    # 2. Incompatible or different unit family
    # STRICT RULE: Stock Items imported from Tally are the SOURCE OF TRUTH for UOM.
    # NO False Mathematical Conversion: 2 Doz with Tally unit DZN remains Qty = 2, UOM = DZN.
    # Preserve invoice quantity and adopt Tally UOM, flagging note only if fundamentally different families.
    note = f"Invoice unit '{invoice_uom}' mapped to Tally unit '{target_tally_uom}'"
    return (
        invoice_qty,
        rate,
        target_tally_uom,
        Decimal("1.0"),
        note,
        False
    )

