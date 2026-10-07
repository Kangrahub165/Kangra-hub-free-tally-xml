import pytest
from decimal import Decimal
from app.invoices.model import InvoiceDocument, InvoiceItem, PartyInfo, FinalInvoiceSnapshot, LedgerMappingConfig
from app.invoices.prd_engine import (
    apply_prd_quantity_rules,
    resolve_prd_discount_pattern,
    reconcile_invoice_document,
    extract_section_5_3_pack_pattern
)
from app.invoices.unit_normalizer import (
    clean_unit_string,
    are_units_equivalent,
    resolve_stock_item_unit
)
from app.accounting.stock_item_importer import ImportedStockItem
from app.invoices.xml_generator import InvoiceTallyXMLGenerator

def test_part_e1_pack_count_description_option_2_pieces():
    """
    Test 1: Pack-count description + bulk quantity, Option 2 (Pieces).
    qty = billed * N, unit = Tally base unit, amount unchanged.
    """
    item = InvoiceItem(
        item_name="Item 35gm.X192PKT.",
        description="Item 35gm.X192PKT.",
        quantity=Decimal("2.00"),
        uom="CB",
        rate=Decimal("1500.00"),
        taxable_amount=Decimal("3000.00"),
        total_amount=Decimal("3000.00")
    )
    processed = apply_prd_quantity_rules(item, default_option="pieces")
    assert processed.math_check_passed is True
    assert processed.is_converted_to_pieces is True
    assert processed.quantity == Decimal("384.00")  # 2 * 192
    assert processed.uom == "Pkt"
    assert processed.rate == Decimal("7.81")  # 3000 / 384 = 7.8125 -> 7.81
    assert processed.taxable_amount == Decimal("3000.00")  # Strict preservation of amount!
    assert processed.alternate_quantity == Decimal("2.00")
    assert processed.alternate_uom == "CB"

def test_part_e2_pack_count_description_option_1_bulk():
    """
    Test 2: Same invoice, Option 1 (Bulk).
    bulk quantity and bulk unit, rate per bulk, amount unchanged.
    """
    item = InvoiceItem(
        item_name="Item 35gm.X192PKT.",
        description="Item 35gm.X192PKT.",
        quantity=Decimal("2.00"),
        uom="CB",
        rate=Decimal("1500.00"),
        taxable_amount=Decimal("3000.00"),
        total_amount=Decimal("3000.00")
    )
    processed = apply_prd_quantity_rules(item, default_option="bulk")
    assert processed.math_check_passed is True
    assert processed.is_converted_to_pieces is False
    assert processed.quantity == Decimal("2.00")
    assert processed.uom == "CB"
    assert processed.rate == Decimal("1500.00")
    assert processed.taxable_amount == Decimal("3000.00")
    assert processed.pack_multiplier == Decimal("192")

def test_part_e3_shipped_vs_billed_separation():
    """
    Test 3: Shipped != Billed.
    Billed used for amount, Shipped used for actual qty.
    Line flagged for review. Never multiplied Shipped * Billed.
    In Option 2, both are multiplied consistently by N.
    """
    item = InvoiceItem(
        item_name="Product X10PCS",
        quantity=Decimal("5.00"),  # Billed
        shipped_qty=Decimal("6.00"),  # Shipped
        uom="BOX",
        rate=Decimal("100.00"),
        taxable_amount=Decimal("500.00"),  # 5 * 100
        total_amount=Decimal("500.00")
    )
    processed = apply_prd_quantity_rules(item, default_option="pieces")
    assert processed.math_check_passed is True
    assert processed.quantity == Decimal("50.00")  # 5 * 10
    assert processed.shipped_qty == Decimal("60.00")  # 6 * 10
    assert processed.taxable_amount == Decimal("500.00")
    assert processed.needs_review is True
    assert "differs from billed quantity" in processed.review_reason

def test_part_e4_description_with_weights_mrp_size_codes():
    """
    Test 4: Description with weight/MRP/size numbers: only number right after X is used.
    e.g. 'Hair Oil 100ml X 72 Pcs Mrp.45/-'
    """
    pattern = extract_section_5_3_pack_pattern("Hair Oil 100ml X 72 Pcs Mrp.45/-")
    assert pattern is not None
    n, unit = pattern
    assert n == 72
    assert unit.upper() == "PCS"

    # Test that 500ML or Mrp.50/- alone are rejected as pack multipliers
    assert extract_section_5_3_pack_pattern("Shampoo 500ML Bottle") is None
    assert extract_section_5_3_pack_pattern("Biscuits Mrp.20/-") is None
    assert extract_section_5_3_pack_pattern("Oil @Rs 150") is None

def test_part_e5_quantity_already_in_pieces():
    """
    Test 5: Quantity already in pieces. No multiplication.
    """
    item = InvoiceItem(
        item_name="Toothpaste 100g X 12 PCS",
        quantity=Decimal("120.00"),
        uom="PCS",  # Billed unit is already pieces!
        rate=Decimal("50.00"),
        taxable_amount=Decimal("6000.00"),
        total_amount=Decimal("6000.00")
    )
    processed = apply_prd_quantity_rules(item, default_option="pieces")
    assert processed.is_converted_to_pieces is False
    assert processed.quantity == Decimal("120.00")
    assert processed.uom == "PCS"
    assert processed.rate == Decimal("50.00")
    assert processed.taxable_amount == Decimal("6000.00")

def test_part_e6_discount_pattern_p1_already_net():
    """
    Test 6.1: P1: Already Net.
    Amount = 1800, Grand = 2124 (18% tax = 324), discount = 200.
    X ~= S, G ~= X + T.
    Taxable remains 1800. Discount is NOT subtracted again.
    """
    doc = InvoiceDocument(
        taxable_total=Decimal("1800.00"),
        cgst_total=Decimal("162.00"),
        sgst_total=Decimal("162.00"),
        grand_total=Decimal("2124.00"),
        discount_total=Decimal("200.00"),
        items=[
            InvoiceItem(
                item_name="Item A",
                quantity=Decimal("10.00"),
                rate=Decimal("200.00"),
                discount_amount=Decimal("200.00"),
                taxable_amount=Decimal("1800.00"),
                cgst_rate=Decimal("9.00"),
                sgst_rate=Decimal("9.00")
            )
        ]
    )
    res = resolve_prd_discount_pattern(doc)
    assert res.discount_pattern == "P1_ALREADY_NET"
    reconciled = reconcile_invoice_document(doc)
    assert reconciled.reconciliation_passed is True
    assert reconciled.items[0].taxable_amount == Decimal("1800.00")

def test_part_e6_discount_pattern_p2_gross_amount():
    """
    Test 6.2: P2: Gross Amount.
    Line Amount = 2000, Line Disc = 200, Taxable Net = 1800, Grand = 2124.
    X ~= S - D, G ~= X + T.
    Net = Amount - Discount. GST on net.
    """
    doc = InvoiceDocument(
        taxable_total=Decimal("1800.00"),
        cgst_total=Decimal("162.00"),
        sgst_total=Decimal("162.00"),
        grand_total=Decimal("2124.00"),
        discount_total=Decimal("200.00"),
        items=[
            InvoiceItem(
                item_name="Item B",
                quantity=Decimal("10.00"),
                rate=Decimal("200.00"),
                discount_amount=Decimal("200.00"),
                taxable_amount=Decimal("2000.00"),  # Gross line amount
                cgst_rate=Decimal("9.00"),
                sgst_rate=Decimal("9.00")
            )
        ]
    )
    res = resolve_prd_discount_pattern(doc)
    assert res.discount_pattern == "P2_GROSS_SUBTRACT_LINE_DISCOUNT"
    reconciled = reconcile_invoice_document(doc)
    assert reconciled.reconciliation_passed is True
    assert reconciled.items[0].taxable_amount == Decimal("1800.00")

def test_part_e6_discount_pattern_p3_bottom_discount_spread():
    """
    Test 6.3: P3: Bottom Discount Before Tax.
    Lines = 2000 (taxable_amount = 2000), Bottom Disc = 200, Taxable Total = 1800, Grand = 2124.
    Spread proportionally across lines before tax.
    """
    doc = InvoiceDocument(
        taxable_total=Decimal("1800.00"),
        cgst_total=Decimal("162.00"),
        sgst_total=Decimal("162.00"),
        grand_total=Decimal("2124.00"),
        discount_total=Decimal("200.00"),
        items=[
            InvoiceItem(
                item_name="Item C1",
                quantity=Decimal("10.00"),
                rate=Decimal("100.00"),
                taxable_amount=Decimal("1000.00"),
                cgst_rate=Decimal("9.00"),
                sgst_rate=Decimal("9.00")
            ),
            InvoiceItem(
                item_name="Item C2",
                quantity=Decimal("10.00"),
                rate=Decimal("100.00"),
                taxable_amount=Decimal("1000.00"),
                cgst_rate=Decimal("9.00"),
                sgst_rate=Decimal("9.00")
            )
        ]
    )
    res = resolve_prd_discount_pattern(doc)
    assert res.discount_pattern == "P3_BOTTOM_DISCOUNT_BEFORE_TAX"
    reconciled = reconcile_invoice_document(doc)
    assert reconciled.reconciliation_passed is True
    assert reconciled.items[0].taxable_amount == Decimal("900.00")
    assert reconciled.items[1].taxable_amount == Decimal("900.00")

def test_part_e6_discount_pattern_p4_post_tax_discount():
    """
    Test 6.4: P4: Discount After GST.
    Line = 2000, 18% GST = 360, Bottom Post-tax Disc = 200, Grand = 2160.
    Line amounts and GST are undiscounted.
    Post-tax discount posted to Discount ledger entry after tax.
    """
    doc = InvoiceDocument(
        taxable_total=Decimal("2000.00"),
        cgst_total=Decimal("180.00"),
        sgst_total=Decimal("180.00"),
        grand_total=Decimal("2160.00"),  # 2000 + 360 - 200 = 2160
        discount_total=Decimal("200.00"),
        items=[
            InvoiceItem(
                item_name="Item D",
                quantity=Decimal("10.00"),
                rate=Decimal("200.00"),
                taxable_amount=Decimal("2000.00"),
                cgst_rate=Decimal("9.00"),
                sgst_rate=Decimal("9.00")
            )
        ]
    )
    res = resolve_prd_discount_pattern(doc)
    assert res.discount_pattern == "P4_POST_TAX_DISCOUNT"
    assert res.post_tax_discount == Decimal("200.00")
    reconciled = reconcile_invoice_document(doc)
    assert reconciled.reconciliation_passed is True
    # Line items remain gross
    assert reconciled.items[0].taxable_amount == Decimal("2000.00")
    assert reconciled.post_tax_discount == Decimal("200.00")

def test_part_e6_discount_pattern_p5_rate_already_net():
    """
    Test 6.5: P5: Rate Already Net.
    Printed Rate is 180, Qty is 10, Amount = 1800, Grand = 2124.
    """
    doc = InvoiceDocument(
        taxable_total=Decimal("1800.00"),
        cgst_total=Decimal("162.00"),
        sgst_total=Decimal("162.00"),
        grand_total=Decimal("2124.00"),
        items=[
            InvoiceItem(
                item_name="Item E",
                quantity=Decimal("10.00"),
                rate=Decimal("180.00"),
                taxable_amount=Decimal("1800.00"),
                cgst_rate=Decimal("9.00"),
                sgst_rate=Decimal("9.00")
            )
        ]
    )
    res = resolve_prd_discount_pattern(doc)
    assert res.discount_pattern in ("P5_NO_DISCOUNT", "P5_RATE_ALREADY_NET")

def test_part_e6_discount_pattern_p6_sequential_discounts():
    """
    Test 6.6: P6: Two discounts applied sequentially (e.g. 10% trade + 5% cash).
    Gross = 2000. Less 10% = 1800. Less 5% = 1710. Taxable = 1710.
    """
    doc = InvoiceDocument(
        taxable_total=Decimal("1710.00"),
        cgst_total=Decimal("153.90"),
        sgst_total=Decimal("153.90"),
        grand_total=Decimal("2017.80"),
        items=[
            InvoiceItem(
                item_name="Item F",
                quantity=Decimal("10.00"),
                rate=Decimal("200.00"),
                discount_amount=Decimal("290.00"),  # 2000 - 1710 = 290
                taxable_amount=Decimal("1710.00"),
                cgst_rate=Decimal("9.00"),
                sgst_rate=Decimal("9.00")
            )
        ]
    )
    res = resolve_prd_discount_pattern(doc)
    assert res.discount_pattern in ("P1_ALREADY_NET", "P6_TWO_DISCOUNTS_SEQUENTIAL")
    reconciled = reconcile_invoice_document(doc)
    assert reconciled.reconciliation_passed is True

def test_part_e6_discount_pattern_p7_free_goods():
    """
    Test 6.7: P7: Free Goods / Scheme (quantity with zero amount).
    """
    doc = InvoiceDocument(
        taxable_total=Decimal("1000.00"),
        cgst_total=Decimal("90.00"),
        sgst_total=Decimal("90.00"),
        grand_total=Decimal("1180.00"),
        items=[
            InvoiceItem(
                item_name="Paid Item",
                quantity=Decimal("10.00"),
                rate=Decimal("100.00"),
                taxable_amount=Decimal("1000.00")
            ),
            InvoiceItem(
                item_name="Free Scheme Item",
                quantity=Decimal("2.00"),
                rate=Decimal("0.00"),
                taxable_amount=Decimal("0.00")
            )
        ]
    )
    res = resolve_prd_discount_pattern(doc)
    assert res.discount_pattern == "P7_FREE_GOODS"
    assert doc.items[1].is_free_item is True

def test_part_e7_new_item_masters_and_voucher_order():
    """
    Test 7: New item generates Unit master + Stock Item master XML before voucher.
    If both units known, stock item has base unit = piece, alternate unit = bulk, conversion = N.
    """
    item = InvoiceItem(
        item_name="Parle Biscuit X192PKT",
        quantity=Decimal("384.00"),  # 2 CB converted to 384 Pkt
        uom="PKT",
        alternate_uom="CB",
        pack_multiplier=Decimal("192"),
        is_converted_to_pieces=True,
        requires_item_creation=True,
        rate=Decimal("5.00"),
        taxable_amount=Decimal("1920.00"),
        cgst_rate=Decimal("9.00"),
        sgst_rate=Decimal("9.00"),
        cgst_amount=Decimal("172.80"),
        sgst_amount=Decimal("172.80")
    )
    inv = InvoiceDocument(
        invoice_type="PURCHASE",
        invoice_number="INV-2026-001",
        taxable_total=Decimal("1920.00"),
        cgst_total=Decimal("172.80"),
        sgst_total=Decimal("172.80"),
        grand_total=Decimal("2265.60"),
        supplier=PartyInfo(name="ABC FMCG Distributors", gstin="02AAACW5680K1Z7"),
        buyer=PartyInfo(name="Kartar Singh & Sons", gstin="02AWLPK8092M1Z0"),
        discount_pattern="P1_ALREADY_NET",
        items=[item]
    )
    snapshot = FinalInvoiceSnapshot(
        invoices=[inv],
        company_name="Kartar Singh & Sons",
        auto_create_items=True,
        auto_create_parties=False,
        ledger_mapping=LedgerMappingConfig()
    )

    gen = InvoiceTallyXMLGenerator()
    xml = gen.generate_xml(snapshot)

    # 1. Check Unit masters are created for BOTH PKT and CB
    assert '<UNIT NAME="PKT" ACTION="Create">' in xml
    assert '<UNIT NAME="CB" ACTION="Create">' in xml

    # 2. Check Stock item master is created with base = PKT, alternate = CB, conversion = 192
    assert '<STOCKITEM NAME="Parle Biscuit X192PKT" ACTION="Create">' in xml
    assert '<BASEUNITS>PKT</BASEUNITS>' in xml
    assert '<ADDITIONALUNITS>CB</ADDITIONALUNITS>' in xml
    assert '<CONVERSION>192</CONVERSION>' in xml

    # 3. Check Order: UNIT before STOCKITEM, STOCKITEM before VOUCHER
    idx_unit = xml.find('<UNIT NAME="PKT"')
    idx_stock = xml.find('<STOCKITEM NAME="Parle Biscuit X192PKT"')
    idx_vch = xml.find('<VOUCHER ')
    assert idx_unit < idx_stock < idx_vch, "Import order must be UNIT -> STOCKITEM -> VOUCHER"

    # 4. Check Double Discounting Prevention:
    # Since P1_ALREADY_NET, NO Discount ledger entry should be present in voucher!
    assert '<LEDGERNAME>Discount</LEDGERNAME>' not in xml
