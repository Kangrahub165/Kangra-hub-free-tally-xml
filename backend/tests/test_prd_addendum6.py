"""
Tests for PRD Addendum 6: Masters Must Land in Tally Exactly As Created
(Stock Items, Units, Ledgers)

Covers Acceptance Criteria 1 through 14:
- AC 1: HSN/SAC Details shows "Specify Details Here" and user HSN
- AC 2: GST Rate Details shows "Specify Details Here", Taxability = Taxable/Nil Rated/Exempt, real rate
- AC 3: Under = user selected Stock Group
- AC 4: Units: small unit = base, big unit = alternate; 1 BIG = N SMALL (<DENOMINATOR> N</DENOMINATOR>, <CONVERSION> 1</CONVERSION>)
- AC 5: Item without alternate unit has no conversion tags
- AC 6: User-saved draft is single source of truth; never overwritten
- AC 7: Missing bill unit creates UNIT master prior to item and voucher
- AC 8: Missing regular party creates LEDGER with State from GSTIN code, PAN, Regular type, LEDGSTREGDETAILS, LEDMAILINGDETAILS
- AC 9: Unregistered party creates LEDGER with Unregistered/Consumer
- AC 10: Invalid GSTIN validation
- AC 11: Mandatory Round-Trip Check: corrupted XML raises MasterRoundTripMismatchError
- AC 12: Tally preview parses generated XML accurately
- AC 13: Unsaved edits block XML generation
- AC 14: Authentic fixture comparison test
"""

import os
import pytest
import xml.etree.ElementTree as ET
from decimal import Decimal
from datetime import date

from app.accounting.tally_master_generator import (
    StockItemDraft,
    LedgerDraft,
    generate_stock_item_master_xml,
    parse_stock_item_master_xml,
    verify_stock_item_round_trip,
    generate_ledger_master_xml,
    parse_ledger_master_xml,
    verify_ledger_round_trip,
    generate_unit_master_xml,
    verify_unit_round_trip,
    generate_stock_group_master_xml,
    extract_pan_from_gstin,
    validate_gstin_format,
    MasterRoundTripMismatchError
)
from app.accounting.ledger_importer import sanitize_xml_content
from app.invoices.model import (
    InvoiceDocument,
    InvoiceItem,
    PartyInfo,
    FinalInvoiceSnapshot,
    LedgerMappingConfig
)
from app.invoices.xml_generator import InvoiceTallyXMLGenerator


# ==============================================================================
# AC 1: HSN/SAC Details shows "Specify Details Here" and user HSN
# ==============================================================================
def test_ac1_hsn_sac_specify_details_here():
    draft = StockItemDraft(
        name="COCA COLA 250ML CAN",
        parent_group="Coldrink",
        base_unit="CAN",
        hsn_code="22021010",
        hsn_description="Carbonated Beverage",
        gst_rate=Decimal("28.00"),
        taxability="Taxable",
        type_of_supply="Goods"
    )
    xml_str = generate_stock_item_master_xml(draft)

    assert "<SRCOFHSNDETAILS>Specify Details Here</SRCOFHSNDETAILS>" in xml_str
    assert "<HSNCODE>22021010</HSNCODE>" in xml_str
    assert "<HSN>Carbonated Beverage</HSN>" in xml_str

    parsed = parse_stock_item_master_xml(xml_str)
    assert parsed["hsn_source"] == "Specify Details Here"
    assert parsed["hsn_code"] == "22021010"
    assert parsed["hsn_description"] == "Carbonated Beverage"


# ==============================================================================
# AC 2: GST Rate Details shows "Specify Details Here", Taxability, real rate
# ==============================================================================
def test_ac2_gst_rate_specify_details_here_taxable():
    draft = StockItemDraft(
        name="FORTUNE SOYA OIL 1L",
        parent_group="Edible Oil",
        base_unit="BTL",
        hsn_code="1507",
        gst_rate=Decimal("5.00"),
        taxability="Taxable",
        type_of_supply="Goods"
    )
    xml_str = generate_stock_item_master_xml(draft)

    assert "<SRCOFGSTDETAILS>Specify Details Here</SRCOFGSTDETAILS>" in xml_str
    assert "<TAXABILITY>Taxable</TAXABILITY>" in xml_str
    assert "<GSTRATE> 2.50</GSTRATE>" in xml_str  # CGST & SGST
    assert "<GSTRATE> 5.00</GSTRATE>" in xml_str  # IGST

    parsed = parse_stock_item_master_xml(xml_str)
    assert parsed["gst_source"] == "Specify Details Here"
    assert parsed["taxability"] == "Taxable"
    assert parsed["gst_rate"] == Decimal("5.00")
    assert parsed["cgst_rate"] == Decimal("2.50")
    assert parsed["sgst_rate"] == Decimal("2.50")


def test_ac2_gst_rate_specify_details_here_nil_rated_and_exempt():
    # 0% / Nil Rated
    draft_nil = StockItemDraft(
        name="WHEAT UNBRANDED 50KG",
        parent_group="Grains",
        base_unit="BAG",
        hsn_code="1001",
        gst_rate=Decimal("0.00"),
        taxability="Nil Rated",
        type_of_supply="Goods"
    )
    xml_nil = generate_stock_item_master_xml(draft_nil)
    assert "<SRCOFGSTDETAILS>Specify Details Here</SRCOFGSTDETAILS>" in xml_nil
    assert "<TAXABILITY>Nil Rated</TAXABILITY>" in xml_nil

    # Exempt
    draft_ex = StockItemDraft(
        name="FRESH MILK 500ML",
        parent_group="Dairy",
        base_unit="PKT",
        hsn_code="0401",
        gst_rate=Decimal("0.00"),
        taxability="Exempt",
        type_of_supply="Goods"
    )
    xml_ex = generate_stock_item_master_xml(draft_ex)
    assert "<SRCOFGSTDETAILS>Specify Details Here</SRCOFGSTDETAILS>" in xml_ex
    assert "<TAXABILITY>Exempt</TAXABILITY>" in xml_ex


# ==============================================================================
# AC 3: Under = user selected Stock Group from imported Tally groups
# ==============================================================================
def test_ac3_under_group_user_selected():
    draft = StockItemDraft(
        name="PARLE G 250G",
        parent_group="Biscuits & Bakery",
        base_unit="PKT",
        gst_rate=Decimal("18.00")
    )
    xml_str = generate_stock_item_master_xml(draft)

    assert "<PARENT>Biscuits &amp; Bakery</PARENT>" in xml_str
    parsed = parse_stock_item_master_xml(xml_str)
    assert parsed["parent_group"] == "Biscuits & Bakery"


# ==============================================================================
# AC 4: Units: small unit = base, big unit = alternate; 1 BIG = N SMALL
# (<DENOMINATOR> N</DENOMINATOR>, <CONVERSION> 1</CONVERSION>)
# ==============================================================================
def test_ac4_units_pack_conversion_formula():
    """
    Tally Screenshot 1 Fix:
    Base unit = PKT (small), alternate = CASE (big).
    Conversion formula: 1 CASE = 192 PKT
    Must emit <DENOMINATOR> 192</DENOMINATOR> and <CONVERSION> 1</CONVERSION>.
    Must NOT emit upside down (192 CASE = 1 PKT).
    """
    draft = StockItemDraft(
        name="KURKURE MASALA MUNCH 20G",
        parent_group="Snacks",
        base_unit="PKT",
        alternate_unit="CASE",
        conversion=192,
        gst_rate=Decimal("12.00")
    )
    xml_str = generate_stock_item_master_xml(draft)

    assert "<BASEUNITS>PKT</BASEUNITS>" in xml_str
    assert "<ADDITIONALUNITS>CASE</ADDITIONALUNITS>" in xml_str
    assert "<DENOMINATOR> 192</DENOMINATOR>" in xml_str
    assert "<CONVERSION> 1</CONVERSION>" in xml_str

    parsed = parse_stock_item_master_xml(xml_str)
    assert parsed["base_unit"] == "PKT"
    assert parsed["alternate_unit"] == "CASE"
    assert parsed["conversion"] == 192
    assert parsed["conversion_formula"] == "1 CASE = 192 PKT"


# ==============================================================================
# AC 5: Item without alternate unit has no conversion tags
# ==============================================================================
def test_ac5_item_without_alternate_unit():
    draft = StockItemDraft(
        name="SINGLE UNIT ITEM",
        parent_group="Primary",
        base_unit="NOS",
        alternate_unit=None,
        conversion=None,
        gst_rate=Decimal("18.00")
    )
    xml_str = generate_stock_item_master_xml(draft)

    assert "<ADDITIONALUNITS>" not in xml_str
    assert "<DENOMINATOR>" not in xml_str
    assert "<CONVERSION>" not in xml_str

    parsed = parse_stock_item_master_xml(xml_str)
    assert parsed["alternate_unit"] is None
    assert parsed["conversion"] is None
    assert parsed["conversion_formula"] is None


# ==============================================================================
# AC 6: User-saved draft is single source of truth; never overwritten
# ==============================================================================
def test_ac6_user_saved_draft_is_single_source_of_truth():
    # User saved a draft with modified parent group and specific rate
    user_saved_item = InvoiceItem(
        item_name="RAW OCR PRODUCT NAME WITH NOISE",
        quantity=Decimal("10"),
        unit_price=Decimal("100"),
        uom="NOS",
        gst_rate=Decimal("18.00"),
        # User saved master overrides:
        matched_stock_item="CLEAN PRODUCT MASTER NAME",
        parent_group="Confectionery & Sweets",
        tally_uom="PCS",
        hsn_sac="21069099",
        hsn_description="Sugar Boiled Confectionery",
        alternate_uom="BOX",
        pack_multiplier=Decimal("50"),
        requires_item_creation=True,
        saved_draft_version=1
    )

    doc = InvoiceDocument(
        invoice_number="INV-101",
        invoice_date=date(2025, 4, 15),
        invoice_type="PURCHASE",
        supplier=PartyInfo(name="ABC Vendor", gstin="02AAACW5680K1Z7", state="Himachal Pradesh"),
        buyer=PartyInfo(name="Kartar Singh & Sons", gstin="02AWLPK8092M1Z0", state="Himachal Pradesh"),
        items=[user_saved_item],
        subtotal=Decimal("1000.00"),
        cgst_total=Decimal("90.00"),
        sgst_total=Decimal("90.00"),
        grand_total=Decimal("1180.00")
    )

    snapshot = FinalInvoiceSnapshot(
        invoices=[doc],
        mapping=LedgerMappingConfig(),
        auto_create_items=True,
        auto_create_parties=False
    )

    gen = InvoiceTallyXMLGenerator()
    xml_out = gen.generate_xml(snapshot)

    # Must contain user's clean name and custom group
    assert '<STOCKITEM NAME="CLEAN PRODUCT MASTER NAME"' in xml_out
    assert '<PARENT>Confectionery &amp; Sweets</PARENT>' in xml_out
    assert '<BASEUNITS>PCS</BASEUNITS>' in xml_out
    assert '<ADDITIONALUNITS>BOX</ADDITIONALUNITS>' in xml_out
    assert '<DENOMINATOR> 50</DENOMINATOR>' in xml_out


# ==============================================================================
# AC 7: Missing bill unit creates UNIT master prior to item and voucher
# ==============================================================================
def test_ac7_missing_unit_creates_unit_master_prior_to_item():
    item = InvoiceItem(
        item_name="CUSTOM UOM PRODUCT",
        quantity=Decimal("5"),
        unit_price=Decimal("200"),
        uom="TIN",
        requires_item_creation=True
    )

    doc = InvoiceDocument(
        invoice_number="INV-202",
        invoice_date=date(2025, 4, 16),
        invoice_type="PURCHASE",
        supplier=PartyInfo(name="Vendor X", gstin="02AAACW5680K1Z7"),
        buyer=PartyInfo(name="Buyer Y", gstin="02AWLPK8092M1Z0"),
        items=[item],
        subtotal=Decimal("1000.00"),
        grand_total=Decimal("1000.00")
    )

    snapshot = FinalInvoiceSnapshot(
        invoices=[doc],
        mapping=LedgerMappingConfig(),
        auto_create_items=True,
        auto_create_parties=False
    )

    gen = InvoiceTallyXMLGenerator()
    xml_out = gen.generate_xml(snapshot)

    unit_idx = xml_out.find('<UNIT NAME="TIN"')
    item_idx = xml_out.find('<STOCKITEM NAME="CUSTOM UOM PRODUCT"')
    voucher_idx = xml_out.find('<VOUCHER ')

    assert unit_idx != -1, "UNIT master for TIN must be created"
    assert item_idx != -1, "STOCKITEM master must be created"
    assert voucher_idx != -1, "VOUCHER must be created"

    # Order must be UNIT -> STOCKITEM -> VOUCHER
    assert unit_idx < item_idx < voucher_idx


# ==============================================================================
# AC 8: Missing regular party creates LEDGER with state from GSTIN code, PAN, etc.
# ==============================================================================
def test_ac8_missing_regular_party_creates_ledger():
    draft = LedgerDraft(
        name="HIMACHAL ENTERPRISES",
        parent_group="Sundry Creditors",
        address_lines=["The Mall Road", "Shimla"],
        gstin="02AAACH1234F1Z8",  # 02 = Himachal Pradesh
        pincode="171001",
        registration_type="Regular"
    )
    xml_str = generate_ledger_master_xml(draft)

    assert "<PARENT>Sundry Creditors</PARENT>" in xml_str
    assert "<LEDSTATENAME>Himachal Pradesh</LEDSTATENAME>" in xml_str
    assert "<INCOMETAXNUMBER>AAACH1234F</INCOMETAXNUMBER>" in xml_str
    assert "<PARTYGSTIN>02AAACH1234F1Z8</PARTYGSTIN>" in xml_str
    assert "<GSTREGISTRATIONTYPE>Regular</GSTREGISTRATIONTYPE>" in xml_str
    assert "<LEDGSTREGDETAILS.LIST>" in xml_str
    assert "<LEDMAILINGDETAILS.LIST>" in xml_str

    parsed = parse_ledger_master_xml(xml_str)
    assert parsed["name"] == "HIMACHAL ENTERPRISES"
    assert parsed["parent_group"] == "Sundry Creditors"
    assert parsed["state"] == "Himachal Pradesh"
    assert parsed["pan"] == "AAACH1234F"
    assert parsed["gstin"] == "02AAACH1234F1Z8"
    assert parsed["registration_type"] == "Regular"
    assert parsed["pincode"] == "171001"


# ==============================================================================
# AC 9: Unregistered party creates LEDGER with Unregistered/Consumer
# ==============================================================================
def test_ac9_unregistered_party_creates_ledger():
    draft = LedgerDraft(
        name="LOCAL CASH CONSUMER",
        parent_group="Sundry Debtors",
        address_lines=["Kangra Market"],
        state="Himachal Pradesh",
        gstin=None,
        pan=None,
        registration_type="Unregistered/Consumer"
    )
    xml_str = generate_ledger_master_xml(draft)

    assert "<PARENT>Sundry Debtors</PARENT>" in xml_str
    assert "<GSTREGISTRATIONTYPE>Unregistered/Consumer</GSTREGISTRATIONTYPE>" in xml_str
    assert "<PARTYGSTIN>" not in xml_str
    assert "<INCOMETAXNUMBER>" not in xml_str

    parsed = parse_ledger_master_xml(xml_str)
    assert parsed["name"] == "LOCAL CASH CONSUMER"
    assert parsed["registration_type"] == "Unregistered/Consumer"
    assert parsed["gstin"] is None
    assert parsed["pan"] is None


# ==============================================================================
# AC 10: GSTIN validation & PAN extraction
# ==============================================================================
def test_ac10_gstin_validation_and_pan():
    valid_gstin = "02AAACW5680K1Z7"
    assert validate_gstin_format(valid_gstin) is True
    assert extract_pan_from_gstin(valid_gstin) == "AAACW5680K"

    invalid_gstins = [
        "1234",
        "02AAACW5680K1Z",    # 14 chars
        "02AAACW5680K1Z78",  # 16 chars
        "ZZAAACW5680K1Z7",   # Invalid state digits
        "",
        None
    ]
    for inv in invalid_gstins:
        assert validate_gstin_format(inv) is False


# ==============================================================================
# AC 11: Mandatory Round-Trip Check: Corrupted XML raises MasterRoundTripMismatchError
# ==============================================================================
def test_ac11_round_trip_check_blocks_corrupted_xml():
    draft = StockItemDraft(
        name="ORIGINAL PRODUCT",
        parent_group="Coldrink",
        base_unit="BTL",
        gst_rate=Decimal("18.00"),
        alternate_unit="CASE",
        conversion=24
    )
    xml_valid = generate_stock_item_master_xml(draft)
    assert verify_stock_item_round_trip(draft, xml_valid) is True

    # 1. Corrupt stock group
    xml_corrupt_group = xml_valid.replace("<PARENT>Coldrink</PARENT>", "<PARENT>Primary</PARENT>")
    with pytest.raises(MasterRoundTripMismatchError, match="Stock group mismatch"):
        verify_stock_item_round_trip(draft, xml_corrupt_group)

    # 2. Corrupt GST rate (spread bug)
    xml_corrupt_rate = xml_valid.replace("<GSTRATE> 18.00</GSTRATE>", "<GSTRATE> 5.00</GSTRATE>")
    with pytest.raises(MasterRoundTripMismatchError, match="GST rate mismatch"):
        verify_stock_item_round_trip(draft, xml_corrupt_rate)

    # 3. Corrupt Ledger
    led_draft = LedgerDraft(
        name="VENDOR ONE",
        parent_group="Sundry Creditors",
        gstin="02AAACH1234F1Z8",
        registration_type="Regular"
    )
    xml_led = generate_ledger_master_xml(led_draft)
    assert verify_ledger_round_trip(led_draft, xml_led) is True

    xml_led_corrupt = xml_led.replace("<GSTREGISTRATIONTYPE>Regular</GSTREGISTRATIONTYPE>", "<GSTREGISTRATIONTYPE>Unregistered/Consumer</GSTREGISTRATIONTYPE>")
    with pytest.raises(MasterRoundTripMismatchError, match="Registration type mismatch"):
        verify_ledger_round_trip(led_draft, xml_led_corrupt)


# ==============================================================================
# AC 12: Tally preview parses generated XML accurately
# ==============================================================================
def test_ac12_tally_preview_parses_accurately():
    draft = StockItemDraft(
        name="MANGO JUICE 1L",
        parent_group="Beverages",
        base_unit="PKT",
        alternate_unit="CASE",
        conversion=12,
        hsn_code="2202",
        hsn_description="Fruit Juice",
        gst_rate=Decimal("12.00"),
        taxability="Taxable",
        type_of_supply="Goods"
    )
    xml_str = generate_stock_item_master_xml(draft)
    preview = parse_stock_item_master_xml(xml_str)

    assert preview["name"] == "MANGO JUICE 1L"
    assert preview["parent_group"] == "Beverages"
    assert preview["base_unit"] == "PKT"
    assert preview["alternate_unit"] == "CASE"
    assert preview["conversion_formula"] == "1 CASE = 12 PKT"
    assert preview["hsn_source"] == "Specify Details Here"
    assert preview["hsn_code"] == "2202"
    assert preview["hsn_description"] == "Fruit Juice"
    assert preview["gst_source"] == "Specify Details Here"
    assert preview["taxability"] == "Taxable"
    assert preview["gst_rate"] == Decimal("12.00")
    assert preview["cgst_rate"] == Decimal("6.00")
    assert preview["sgst_rate"] == Decimal("6.00")


# ==============================================================================
# AC 13: Unsaved edits block XML generation
# ==============================================================================
def test_ac13_unsaved_edits_block_xml_generation():
    doc = InvoiceDocument(
        invoice_number="INV-999",
        invoice_date=date(2025, 4, 15),
        invoice_type="PURCHASE",
        supplier=PartyInfo(name="ABC Vendor", gstin="02AAACW5680K1Z7"),
        buyer=PartyInfo(name="Buyer", gstin="02AWLPK8092M1Z0"),
        items=[InvoiceItem(item_name="Item 1", quantity=Decimal("1"), unit_price=Decimal("100"), uom="NOS")],
        subtotal=Decimal("100.00"),
        grand_total=Decimal("100.00")
    )

    # Snapshot marked with unsaved edits
    snapshot = FinalInvoiceSnapshot(
        invoices=[doc],
        mapping=LedgerMappingConfig(),
        has_unsaved_master_edits=True
    )

    gen = InvoiceTallyXMLGenerator()
    with pytest.raises(ValueError, match="unsaved changes"):
        gen.generate_xml(snapshot)


# ==============================================================================
# AC 14: Fixture comparison test matches authentic templates
# ==============================================================================
def test_ac14_fixture_comparison_matches_authentic_templates():
    fixture_dir = os.path.join(os.path.dirname(__file__), "..", "fixtures", "tally-templates")

    # 1. 5% Stock Item with Alternate Units (CASE -> PKT, 1 CASE = 192 PKT)
    fixture_5pct = os.path.join(fixture_dir, "stock_item_5pct.xml")
    assert os.path.exists(fixture_5pct), f"Missing fixture {fixture_5pct}"
    with open(fixture_5pct, "r", encoding="utf-8") as f:
        tmpl_content = f.read()

    # Parse template with our parser to verify structure
    tmpl_parsed = parse_stock_item_master_xml(tmpl_content)
    assert tmpl_parsed["conversion_formula"] == "1 CASE = 192 PKT"
    assert tmpl_parsed["gst_rate"] == Decimal("5.00")
    assert tmpl_parsed["gst_source"] == "Specify Details Here"
    assert tmpl_parsed["hsn_source"] == "Specify Details Here"

    # Generate draft matching template and round trip
    draft_match = StockItemDraft(
        name=tmpl_parsed["name"],
        parent_group=tmpl_parsed["parent_group"],
        base_unit=tmpl_parsed["base_unit"],
        alternate_unit=tmpl_parsed["alternate_unit"],
        conversion=tmpl_parsed["conversion"],
        hsn_code=tmpl_parsed["hsn_code"],
        gst_rate=tmpl_parsed["gst_rate"],
        taxability=tmpl_parsed["taxability"],
        type_of_supply=tmpl_parsed["type_of_supply"]
    )
    gen_xml = generate_stock_item_master_xml(draft_match)
    assert verify_stock_item_round_trip(draft_match, gen_xml) is True

    # 2. Regular Creditor Ledger Template
    fixture_creditor = os.path.join(fixture_dir, "ledger_regular_creditor.xml")
    assert os.path.exists(fixture_creditor), f"Missing fixture {fixture_creditor}"
    with open(fixture_creditor, "r", encoding="utf-8") as f:
        cred_content = f.read()

    cred_parsed = parse_ledger_master_xml(cred_content)
    assert cred_parsed["parent_group"] == "Sundry Creditors"
    assert cred_parsed["registration_type"] == "Regular"
    assert cred_parsed["gstin"] is not None
    assert cred_parsed["pan"] is not None
