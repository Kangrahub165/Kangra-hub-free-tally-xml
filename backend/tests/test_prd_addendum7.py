import pytest
from decimal import Decimal
from app.accounting.stock_item_importer import (
    GlobalStockItemStore,
    ImportedStockItem,
    parse_xml_stock_items,
    import_stock_items_from_text
)
from app.accounting.tally_master_generator import (
    StockItemDraft,
    generate_stock_item_master_xml,
    parse_stock_item_master_xml,
    LedgerDraft,
    generate_ledger_master_xml,
    parse_ledger_master_xml
)

def test_prd_addendum7_no_items_returns_empty_units_and_groups():
    """
    PRD Addendum 7 §2.2 & §3.2:
    With no imported items, units and groups return empty lists so the UI can display
    'No units found. Import your Tally stock items first' and
    'No groups imported yet. Import your Tally stock items.'
    No fake or hardcoded units (no default PCS, NOS, BOX, etc.) are offered.
    """
    store = GlobalStockItemStore()
    user_id = "test_user_empty_masters"

    units = store.get_stock_units(user_id)
    assert units == [], "Expected empty units list when no stock items are imported"

    groups = store.get_stock_groups(user_id)
    assert groups == [], "Expected empty groups list when no stock items are imported"

def test_prd_addendum7_units_only_from_tally():
    """
    PRD Addendum 7 §2.1 & §2.2:
    Units and Alternate units dropdowns show ONLY the units that exist in the user's Tally.
    Gathers both base_units and additional_units.
    No hardcoded units are injected.
    """
    store = GlobalStockItemStore()
    user_id = "test_user_tally_units"

    items = [
        ImportedStockItem(
            name="Product Alpha",
            normalized_name="PRODUCT ALPHA",
            parent="Snacks",
            base_units="PKT",
            additional_units="CASE"
        ),
        ImportedStockItem(
            name="Product Beta",
            normalized_name="PRODUCT BETA",
            parent="Snacks",
            base_units="PKT",
            additional_units=None
        ),
        ImportedStockItem(
            name="Product Gamma",
            normalized_name="PRODUCT GAMMA",
            parent="Beverages",
            base_units="BTL",
            additional_units="CRATE"
        )
    ]
    store.add_items(user_id, items)

    units = store.get_stock_units(user_id)
    unit_names = [u["name"] for u in units]

    # Verify that only the user's Tally units are present: PKT (2), CASE (1), BTL (1), CRATE (1)
    assert set(unit_names) == {"PKT", "CASE", "BTL", "CRATE"}
    # Assert standard unimported units are NOT injected
    assert "NOS" not in unit_names
    assert "KG" not in unit_names
    assert "LTR" not in unit_names
    assert "GM" not in unit_names

    # Item counts
    pkt_unit = next(u for u in units if u["name"] == "PKT")
    assert pkt_unit["item_count"] == 2
    case_unit = next(u for u in units if u["name"] == "CASE")
    assert case_unit["item_count"] == 1
    assert "imported_at" in pkt_unit

def test_prd_addendum7_stock_groups_real_tally_groups_pinned_primary():
    """
    PRD Addendum 7 §3.2:
    The list = all groups from the imported Tally stock items (distinct parents)
    plus Primary (Tally's root, always valid).
    Primary is pinned at the top. The rest are sorted A to Z with item counts.
    """
    store = GlobalStockItemStore()
    user_id = "test_user_tally_groups"

    items = [
        ImportedStockItem(name="A", normalized_name="A", parent="Spices", base_units="PKT"),
        ImportedStockItem(name="B", normalized_name="B", parent="Spices", base_units="PKT"),
        ImportedStockItem(name="C", normalized_name="C", parent="Bakery", base_units="PKT"),
        ImportedStockItem(name="D", normalized_name="D", parent="Confectionery", base_units="PKT"),
        ImportedStockItem(name="E", normalized_name="E", parent=None, base_units="PKT"), # Defaults to Primary
    ]
    store.add_items(user_id, items)

    groups = store.get_stock_groups(user_id)
    assert len(groups) == 4

    # Primary pinned at top
    assert groups[0]["name"] == "Primary"
    assert groups[0]["item_count"] == 1

    # Rest sorted A to Z
    other_groups = [g["name"] for g in groups[1:]]
    assert other_groups == ["Bakery", "Confectionery", "Spices"]

    spices = next(g for g in groups if g["name"] == "Spices")
    assert spices["item_count"] == 2
    assert "imported_at" in spices

def test_prd_addendum7_pack_conversion_formula():
    """
    PRD Addendum 7 §1.3 & §2.3:
    Screen reads '1 CASE = 192 PKT'.
    Tally XML: <DENOMINATOR> 192</DENOMINATOR>, <CONVERSION> 1</CONVERSION>.
    Round trip check confirms proper values.
    """
    draft = StockItemDraft(
        name="CY AGB RHYTHM SANDAL RS 150",
        parent_group="Agarbatti",
        base_unit="PKT",
        alternate_unit="CASE",
        conversion=192,
        hsn_code="33074100",
        hsn_description="Incense Sticks",
        gst_rate=Decimal("5.00"),
        taxability="Taxable",
        type_of_supply="Goods"
    )

    xml_snippet = generate_stock_item_master_xml(draft)
    assert "<BASEUNITS>PKT</BASEUNITS>" in xml_snippet
    assert "<ADDITIONALUNITS>CASE</ADDITIONALUNITS>" in xml_snippet
    assert "<DENOMINATOR> 192</DENOMINATOR>" in xml_snippet
    assert "<CONVERSION> 1</CONVERSION>" in xml_snippet

    preview = parse_stock_item_master_xml(xml_snippet)
    assert preview["conversion_formula"] == "1 CASE = 192 PKT"
    assert preview["base_unit"] == "PKT"
    assert preview["alternate_unit"] == "CASE"
    assert preview["hsn_code"] == "33074100"
    assert preview["gst_rate"] == Decimal("5.00")
