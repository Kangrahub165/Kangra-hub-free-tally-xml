"""
Unit Normalizer for Tally XML and Stock Item Unit Master Parity.
Implements PRD Addendum 2 Part B:
- Units must come from Tally: exact spelling, case, and symbol.
- Unit alias table for case-insensitive, punctuation-tolerant unit translation.
- Mapped items: validates that bill unit exists on the Tally stock item (base or alternate unit).
- New items: generates Unit master first, then Stock Item master with base & alternate units.
"""

import re
from typing import Optional, Tuple, Dict, Set
from app.invoices.model import InvoiceItem
from app.accounting.stock_item_importer import ImportedStockItem

# Canonical alias mapping: normalized token -> standard representation
UNIT_ALIAS_MAP: Dict[str, str] = {
    "PC": "PCS",
    "PCS": "PCS",
    "PIECE": "PCS",
    "PIECES": "PCS",
    "PKT": "PKT",
    "PKTS": "PKT",
    "PACKET": "PKT",
    "PACKETS": "PKT",
    "PACK": "PKT",
    "PACKS": "PKT",
    "BOX": "BOX",
    "BOXES": "BOX",
    "BX": "BOX",
    "CASE": "CASE",
    "CASES": "CASE",
    "CS": "CASE",
    "CB": "CASE",
    "CTN": "CASE",
    "CTNS": "CASE",
    "CARTON": "CASE",
    "CARTONS": "CASE",
    "NOS": "NOS",
    "NO": "NOS",
    "NUMBER": "NOS",
    "NUMBERS": "NOS",
    "UNIT": "NOS",
    "UNITS": "NOS",
    "BOTTLE": "BOTTLE",
    "BOTTLES": "BTL",
    "BTL": "BTL",
    "JAR": "JAR",
    "JARS": "JAR",
    "TIN": "TIN",
    "TINS": "TIN",
    "CAN": "CAN",
    "CANS": "CAN",
    "BAG": "BAG",
    "BAGS": "BAG",
    "DOZ": "DZ",
    "DOZEN": "DZ",
    "DZ": "DZ",
    "LADI": "LADI",
    "STRIP": "STRIP",
    "STRIPS": "STRIP",
    "ROLL": "ROLL",
    "ROLLS": "ROLL",
    "SET": "SET",
    "SETS": "SET"
}

def clean_unit_string(uom: Optional[str]) -> str:
    """Removes dots, slashes, spaces and converts to uppercase for comparison."""
    if not uom:
        return ""
    return re.sub(r'[^A-Za-z0-9]', '', str(uom)).strip().upper()

def get_canonical_unit_alias(uom: Optional[str]) -> str:
    """Translates unit text to canonical alias token."""
    clean = clean_unit_string(uom)
    return UNIT_ALIAS_MAP.get(clean, clean)

def are_units_equivalent(unit_a: Optional[str], unit_b: Optional[str]) -> bool:
    """Checks if two unit strings represent the same unit (case-insensitive, ignoring dots/spaces)."""
    if not unit_a or not unit_b:
        return False
    clean_a = clean_unit_string(unit_a)
    clean_b = clean_unit_string(unit_b)
    if clean_a == clean_b:
        return True
    return UNIT_ALIAS_MAP.get(clean_a, clean_a) == UNIT_ALIAS_MAP.get(clean_b, clean_b)

def resolve_stock_item_unit(
    item: InvoiceItem,
    mapped_stock_item: Optional[ImportedStockItem] = None,
    option: str = "pieces"  # "pieces" (Option 2) or "bulk" (Option 1)
) -> Tuple[str, Optional[str]]:
    """
    PRD Addendum 2 Part B: Determines the exact Tally unit to write into the XML:
    Returns (resolved_unit_name, warning_or_None).
    """
    bill_bulk_uom = item.invoice_uom or item.uom or "NOS"

    # CASE 1: Item is mapped to an existing Tally Stock Item
    if mapped_stock_item:
        tally_base = mapped_stock_item.base_units or "NOS"
        tally_alt = mapped_stock_item.additional_units

        # Option 2 (Pieces): Always use the stock item's base unit in Tally
        if option in ("pieces", "2", "B"):
            return tally_base, None

        # Option 1 (Bulk): Use bill's bulk unit ONLY if it equals base or alternate unit
        if are_units_equivalent(bill_bulk_uom, tally_base):
            return tally_base, None
        if tally_alt and are_units_equivalent(bill_bulk_uom, tally_alt):
            return tally_alt, None

        # Bill's bulk unit is not available on that stock item!
        # Do not send invalid unit to Tally. Return base unit with warning.
        warn = (
            f"Bulk unit '{bill_bulk_uom}' does not exist on Tally stock item '{mapped_stock_item.name}' "
            f"(configured units: {tally_base}{f', {tally_alt}' if tally_alt else ''}). "
            f"Using base unit '{tally_base}'."
        )
        return tally_base, warn

    # CASE 2: Item is NEW (unmapped)
    if option in ("pieces", "2", "B"):
        # Option 2: base unit = piece-unit word found after N in description if it exists
        piece_unit_hint = item.uom_option_b or "Pcs"
        return piece_unit_hint, None
    else:
        # Option 1: base unit = bill's bulk unit
        return bill_bulk_uom, None
