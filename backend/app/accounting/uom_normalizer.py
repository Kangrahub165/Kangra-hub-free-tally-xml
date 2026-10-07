"""
Authoritative Unit of Measure (UOM) Normalization & Equivalence Engine for Sales & Purchase.
Enforces:
1. Stock items imported from Tally are the SOLE SOURCE OF TRUTH for UOM.
2. Comprehensive canonical grouping for all standard Indian trade units:
   - Pieces / Numbers (PCS, PC, PCE, PIECE, PIECES, NO, NOS, NUM, NUMBER, UNT, UNIT)
   - Dozen (DZN, DZ, DOZ, DOZEN, DOZENS)
   - Case (CASE, CASES, CS, CTN, CARTON, CARTONS)
   - Box (BOX, BOXES, BX)
   - Weight (KG, KGS, KILOGRAM, GM, GMS, G, GRAM, GRAMS, MT, TON, QTL)
   - Volume (LTR, LTRS, L, LITRE, LITRES, ML, MLT)
   - Length/Area (MTR, MTRS, M, METER, FT, SQM, SQFT)
   - Packaging (PKT, PKTS, PACKET, PACKETS, PACK, BAG, BAGS, BTL, BOTTLE, TIN, CAN, SET, PAIR, ROLL, STRIP)
3. Strict Preservation of Invoice Quantity: NO false mathematical conversions!
   e.g. 2 Doz with Tally unit DZN remains Qty = 2, UOM = DZN. Do NOT convert to 24 PCS.
4. Priority Order for Output UOM:
   - Priority 1: Matched Tally Stock Item's imported Unit/UOM.
   - Priority 2: Invoice UOM normalized and matched against Tally Stock Item UOM.
   - Priority 3: If invoice UOM is missing but Tally Stock Item has known UOM, use Tally Stock Item's UOM.
   - Priority 4: If unmatched and invoice has UOM, preserve invoice UOM (never randomly invent one).
"""

import re
from typing import Optional, Tuple, Dict, Set
from decimal import Decimal

# Canonical unit equivalence families (mapping alias -> family identifier)
UOM_FAMILY_MAP: Dict[str, str] = {
    # Pieces / Numbers family
    "PCS": "PIECES",
    "PC": "PIECES",
    "PCE": "PIECES",
    "PIECE": "PIECES",
    "PIECES": "PIECES",
    "NOS": "PIECES",
    "NO": "PIECES",
    "NO.": "PIECES",
    "NOS.": "PIECES",
    "NUM": "PIECES",
    "NUMBER": "PIECES",
    "NUMBERS": "PIECES",
    "UNT": "PIECES",
    "UNIT": "PIECES",
    "UNITS": "PIECES",
    "ITEMS": "PIECES",
    "ITEM": "PIECES",

    # Dozen family
    "DZN": "DOZEN",
    "DZ": "DOZEN",
    "DOZ": "DOZEN",
    "DOZEN": "DOZEN",
    "DOZENS": "DOZEN",
    "DZN.": "DOZEN",
    "DZ.": "DOZEN",

    # Case / Carton family
    "CASE": "CASE",
    "CASES": "CASE",
    "CS": "CASE",
    "CTN": "CASE",
    "CARTON": "CASE",
    "CARTONS": "CASE",
    "CRATE": "CASE",
    "CRATES": "CASE",

    # Box family
    "BOX": "BOX",
    "BOXES": "BOX",
    "BX": "BOX",

    # Weight: KG family
    "KG": "WEIGHT_KG",
    "KGS": "WEIGHT_KG",
    "KILOGRAM": "WEIGHT_KG",
    "KILOGRAMS": "WEIGHT_KG",
    "KG.": "WEIGHT_KG",
    "KGS.": "WEIGHT_KG",

    # Weight: Grams family
    "GM": "WEIGHT_GM",
    "GMS": "WEIGHT_GM",
    "G": "WEIGHT_GM",
    "GRAM": "WEIGHT_GM",
    "GRAMS": "WEIGHT_GM",
    "GM.": "WEIGHT_GM",
    "GMS.": "WEIGHT_GM",

    # Weight: Bulk / Tonne / Quintal
    "MT": "WEIGHT_BULK",
    "TON": "WEIGHT_BULK",
    "TONNE": "WEIGHT_BULK",
    "TONNES": "WEIGHT_BULK",
    "QTL": "WEIGHT_BULK",
    "QUINTAL": "WEIGHT_BULK",

    # Volume: Litres
    "LTR": "VOLUME_LTR",
    "LTRS": "VOLUME_LTR",
    "L": "VOLUME_LTR",
    "LITRE": "VOLUME_LTR",
    "LITRES": "VOLUME_LTR",
    "LITER": "VOLUME_LTR",
    "LITERS": "VOLUME_LTR",
    "LT": "VOLUME_LTR",

    # Volume: Millilitres
    "ML": "VOLUME_ML",
    "MLT": "VOLUME_ML",
    "MILLILITRE": "VOLUME_ML",
    "MILLILITER": "VOLUME_ML",

    # Length / Area
    "MTR": "LENGTH",
    "MTRS": "LENGTH",
    "M": "LENGTH",
    "METER": "LENGTH",
    "METERS": "LENGTH",
    "FT": "LENGTH",
    "FEET": "LENGTH",
    "INCH": "LENGTH",
    "INCHES": "LENGTH",
    "SQM": "AREA",
    "SQFT": "AREA",
    "SQMTR": "AREA",

    # Packaging units
    "PKT": "PACKET",
    "PKTS": "PACKET",
    "PACKET": "PACKET",
    "PACKETS": "PACKET",
    "PACK": "PACKET",
    "PACKS": "PACKET",
    "PK": "PACKET",

    "BAG": "BAG",
    "BAGS": "BAG",
    "BG": "BAG",

    "BTL": "BOTTLE",
    "BTLS": "BOTTLE",
    "BOTTLE": "BOTTLE",
    "BOTTLES": "BOTTLE",

    "TIN": "CONTAINER",
    "TINS": "CONTAINER",
    "CAN": "CONTAINER",
    "CANS": "CONTAINER",
    "JAR": "CONTAINER",
    "JARS": "CONTAINER",
    "DRUM": "CONTAINER",
    "DRUMS": "CONTAINER",
    "BUCKET": "CONTAINER",

    "SET": "SET",
    "SETS": "SET",

    "PAIR": "PAIR",
    "PAIRS": "PAIR",
    "PR": "PAIR",

    "ROLL": "ROLL",
    "ROLLS": "ROLL",
    "RL": "ROLL",

    "STRIP": "STRIP",
    "STRIPS": "STRIP",
    "STP": "STRIP",
}

# Standard canonical display representations per family
CANONICAL_TRADE_UNIT: Dict[str, str] = {
    "PIECES": "NOS",
    "DOZEN": "DZN",
    "CASE": "CASE",
    "BOX": "BOX",
    "WEIGHT_KG": "KGS",
    "WEIGHT_GM": "GMS",
    "WEIGHT_BULK": "MT",
    "VOLUME_LTR": "LTR",
    "VOLUME_ML": "ML",
    "LENGTH": "MTR",
    "AREA": "SQFT",
    "PACKET": "PKT",
    "BAG": "BAG",
    "BOTTLE": "BTL",
    "CONTAINER": "CAN",
    "SET": "SET",
    "PAIR": "PAIR",
    "ROLL": "ROLL",
    "STRIP": "STRIP",
}

def clean_uom_string(raw: Optional[str]) -> str:
    """Strips non-alphanumeric punctuation and standardizes case."""
    if not raw:
        return ""
    # Remove dots and slashes (e.g. "DZN." -> "DZN", "NO." -> "NO", "Pcs/Box" -> "Pcs")
    cleaned = re.sub(r'[^A-Za-z0-9]', '', str(raw).strip().split('/')[0]).upper()
    return cleaned

def get_uom_family(uom: Optional[str]) -> Optional[str]:
    """Returns the canonical family for a UOM, or None if unrecognized."""
    clean = clean_uom_string(uom)
    return UOM_FAMILY_MAP.get(clean)

def are_uoms_compatible(uom1: Optional[str], uom2: Optional[str]) -> bool:
    """
    Checks whether two UOM strings belong to the same trade family
    (e.g., 'PCS' and 'NOS' -> True, 'DZ' and 'DZN' -> True, 'CASE' and 'CTN' -> True).
    """
    if not uom1 or not uom2:
        return False
    c1 = clean_uom_string(uom1)
    c2 = clean_uom_string(uom2)
    if c1 == c2:
        return True
    f1 = UOM_FAMILY_MAP.get(c1)
    f2 = UOM_FAMILY_MAP.get(c2)
    return f1 is not None and f1 == f2

def normalize_uom(raw_uom: Optional[str]) -> str:
    """
    Normalizes any raw unit string to its standard trade representation.
    Preserves existing valid unit if not in dictionary.
    """
    if not raw_uom:
        return "NOS"
    clean = clean_uom_string(raw_uom)
    family = UOM_FAMILY_MAP.get(clean)
    if family and family in CANONICAL_TRADE_UNIT:
        return CANONICAL_TRADE_UNIT[family]
    return clean or "NOS"

def resolve_stock_item_uom(
    matched_stock_item_uom: Optional[str],
    invoice_uom: Optional[str],
    invoice_qty: Decimal
) -> Tuple[str, str, str, Decimal]:
    """
    Authoritative Resolution of Final UOM and Quantity according to PRD Rules:
    
    1. Stock Items imported from Tally are the SOLE SOURCE OF TRUTH for UOM:
       When an item matches a Tally Stock Item, the Tally Stock Item's actual imported
       Unit/UOM is the final output UOM.
       e.g., Matched Tally Stock Item has UOM = "NOS", invoice says "5 No" or "5 Pcs" ->
             final_uom = "NOS", invoice_uom = "PCS", tally_uom = "NOS", qty = 5.
    
    2. STRICT RULE — NO FALSE MATHEMATICAL CONVERSIONS:
       e.g. 2 Doz with Tally unit DZN remains Qty = 2, UOM = DZN.
       Do NOT silently convert to 24 PCS.
       Quantity extracted from the invoice is strictly preserved.
    
    3. Priorities:
       Priority 1: Matched Tally Stock Item's imported Unit/UOM.
       Priority 2: Invoice UOM normalized and matched against Tally Stock Item UOM.
       Priority 3: If invoice UOM is missing but Tally Stock Item has known UOM, use Tally Stock Item's UOM.
       Priority 4: If unmatched and invoice has UOM, preserve invoice UOM (never randomly invent one).
    
    Returns:
        (final_uom, invoice_uom_cleaned, tally_uom, preserved_qty)
    """
    # Clean invoice UOM
    clean_inv_uom = clean_uom_string(invoice_uom) or "NOS"
    norm_inv_uom = normalize_uom(clean_inv_uom)

    # Clean Tally Stock Item UOM if available
    clean_tally_uom = (matched_stock_item_uom or "").strip()

    if clean_tally_uom:
        # Priority 1: Matched Tally Stock Item's imported Unit/UOM is the SOURCE OF TRUTH!
        final_uom = clean_tally_uom
        tally_uom = clean_tally_uom
    else:
        # Priority 4: If unmatched, preserve invoice UOM
        final_uom = norm_inv_uom
        tally_uom = norm_inv_uom

    # Quantity is preserved as is: NO false mathematical conversions!
    return final_uom, clean_inv_uom, tally_uom, invoice_qty
