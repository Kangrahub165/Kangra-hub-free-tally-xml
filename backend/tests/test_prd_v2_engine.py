import pytest
from decimal import Decimal
from app.invoices.model import InvoiceDocument, InvoiceItem, PartyInfo
from app.invoices.prd_engine import (
    apply_prd_quantity_rules,
    resolve_prd_gst_rates,
    reconcile_invoice_document,
    resolve_sales_vs_purchase,
    extract_section_5_3_pack_pattern,
    run_math_check_decision_engine
)

def test_rule_5_3_pack_size_multiplication_only_when_bulk():
    """Section 5.3: 3 CB @ 1388.00 with X192pkt -> 576 pkt @ 7.23, AMOUNT remains 4164.00."""
    item = InvoiceItem(
        item_name="Item X.X192pkt.",
        description="Item X.X192pkt.",
        quantity=Decimal("3.00"),
        uom="CB",
        rate=Decimal("1388.00"),
        taxable_amount=Decimal("4164.00"),
        total_amount=Decimal("4164.00")
    )
    processed = apply_prd_quantity_rules(item)
    assert processed.math_check_passed is True
    assert processed.is_converted_to_pieces is True
    assert processed.quantity == Decimal("576.00")
    assert processed.uom == "Pkt"
    assert processed.rate == Decimal("7.23")
    # Rule 1 & 5.3: AMOUNT is strictly unchanged!
    assert processed.taxable_amount == Decimal("4164.00")
    assert processed.alternate_quantity == Decimal("3.00")
    assert processed.alternate_uom == "CB"

def test_rule_5_4_never_multiply_when_already_pcs():
    """Section 5.4: 864 PCS with (288PCS) in desc must NOT be multiplied."""
    item = InvoiceItem(
        item_name="Good Day Biscuit (288PCS)",
        description="Good Day Biscuit (288PCS)",
        quantity=Decimal("864.00"),
        uom="PCS",
        rate=Decimal("10.00"),
        taxable_amount=Decimal("8640.00"),
        total_amount=Decimal("8640.00")
    )
    processed = apply_prd_quantity_rules(item)
    assert processed.math_check_passed is True
    assert processed.is_converted_to_pieces is False
    assert processed.quantity == Decimal("864.00")
    assert processed.uom == "PCS"
    assert processed.rate == Decimal("10.00")
    assert processed.taxable_amount == Decimal("8640.00")

def test_rule_5_4_never_multiply_dz_box_container():
    """Section 5.4: Units like DZ, Box, Container stay as printed."""
    item = InvoiceItem(
        item_name="Dairy Milk 36 DZ",
        description="Dairy Milk 36 DZ",
        quantity=Decimal("36.00"),
        uom="DZ",
        rate=Decimal("120.00"),
        taxable_amount=Decimal("4320.00"),
        total_amount=Decimal("4320.00")
    )
    processed = apply_prd_quantity_rules(item)
    assert processed.is_converted_to_pieces is False
    assert processed.quantity == Decimal("36.00")
    assert processed.uom == "DZ"

def test_rule_5_4_never_multiply_weights_or_mrp():
    """Section 5.1 & 5.4: 500ML or @Rs 10 are never multipliers."""
    pat = extract_section_5_3_pack_pattern("Shampoo 500ML Bottle @Rs 10")
    assert pat is None

def test_rule_5_5_math_check_decision_engine_and_reconstruction():
    """Section 5.5: When rate is damaged/missing, reconstruct using amount."""
    item = InvoiceItem(
        item_name="Cement Bag",
        quantity=Decimal("100.00"),
        uom="BAG",
        rate=Decimal("0.00"),  # Missing/damaged
        taxable_amount=Decimal("35000.00"),
        total_amount=Decimal("35000.00")
    )
    processed = apply_prd_quantity_rules(item)
    assert processed.math_check_passed is True
    assert processed.is_reconstructed is True
    assert processed.rate == Decimal("350.00")
    assert processed.taxable_amount == Decimal("35000.00")

def test_rule_5_5_math_check_failure_marks_needs_review():
    """Section 5.5: When qty * rate != amount, mark Needs review and do not guess."""
    item = InvoiceItem(
        item_name="Ambiguous Line",
        quantity=Decimal("10.00"),
        rate=Decimal("50.00"),
        taxable_amount=Decimal("1999.00"),  # Contradicts 10 x 50
        total_amount=Decimal("1999.00")
    )
    processed = apply_prd_quantity_rules(item)
    assert processed.math_check_passed is False
    assert processed.needs_review is True
    assert "Math check failed" in processed.review_reason
    assert processed.taxable_amount == Decimal("1999.00")  # Anchor preserved

def test_section_6_gst_rate_hierarchy_single_vs_component():
    """Section 6: Single column 18% splits into 9% + 9%, never doubled to 36%."""
    item = InvoiceItem(
        item_name="Item 18%",
        taxable_amount=Decimal("1000.00"),
        gst_rate=Decimal("18.00"),
        cgst_rate=Decimal("0.00"),
        sgst_rate=Decimal("0.00")
    )
    res = resolve_prd_gst_rates(item, is_interstate=False, single_column_mode=True)
    assert res.gst_rate == Decimal("18.00")
    assert res.cgst_rate == Decimal("9.00")
    assert res.sgst_rate == Decimal("9.00")
    assert res.cgst_amount == Decimal("90.00")
    assert res.sgst_amount == Decimal("90.00")
    assert res.total_amount == Decimal("1180.00")

def test_section_6_zero_tax_free_line():
    """Section 6: 0% tax-free line stays 0%, never inherits slab."""
    item = InvoiceItem(
        item_name="Unpolished Rice",
        taxable_amount=Decimal("5000.00"),
        gst_rate=Decimal("0.00"),
        cgst_rate=Decimal("0.00"),
        sgst_rate=Decimal("0.00")
    )
    res = resolve_prd_gst_rates(item, is_interstate=False)
    assert res.gst_rate == Decimal("0.00")
    assert res.cgst_rate == Decimal("0.00")
    assert res.sgst_rate == Decimal("0.00")
    assert res.total_amount == Decimal("5000.00")

def test_section_7_reconciliation():
    """Section 7: 6-point reconciliation flags mismatches."""
    doc = InvoiceDocument(
        taxable_total=Decimal("1000.00"),
        cgst_total=Decimal("90.00"),
        sgst_total=Decimal("90.00"),
        grand_total=Decimal("1180.00"),
        items=[
            InvoiceItem(item_name="A", taxable_amount=Decimal("1000.00"), cgst_amount=Decimal("90.00"), sgst_amount=Decimal("90.00"))
        ]
    )
    rec = reconcile_invoice_document(doc)
    assert rec.reconciliation_passed is True
    assert len(rec.reconciliation_flags) == 0

def test_section_3_sales_vs_purchase():
    """Section 3: Buyer is Company GSTIN -> Purchase; Supplier is Company GSTIN -> Sales."""
    my_gstin = "02AWLPK8092M1Z0"
    vendor = PartyInfo(name="Vendor", gstin="02BULPK7285D1ZL")
    me = PartyInfo(name="Kartar Singh", gstin=my_gstin)

    vch_type, p = resolve_sales_vs_purchase(supplier=vendor, buyer=me, company_gstin=my_gstin)
    assert vch_type == "PURCHASE"
    assert p.name == "Vendor"

    vch_type_sales, p_sales = resolve_sales_vs_purchase(supplier=me, buyer=vendor, company_gstin=my_gstin)
    assert vch_type_sales == "SALES"
    assert p_sales.name == "Vendor"
