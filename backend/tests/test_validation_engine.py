import pytest
from datetime import date
from decimal import Decimal
from app.invoices.model import InvoiceDocument, PartyInfo, InvoiceItem
from app.invoices.validator import validate_invoice_document, run_repair_loop

def test_v01_gstin_checksum_validation():
    # Valid GSTIN: 27AAPFU0939F1ZV
    doc_valid = InvoiceDocument(
        invoice_number="INV-001",
        invoice_date=date(2026, 5, 10),
        supplier=PartyInfo(name="Vendor MH", gstin="27AAPFU0939F1ZV"),
        buyer=PartyInfo(name="Kartar Singh & Sons", gstin="02AWLPK8092M1Z0"),
        items=[InvoiceItem(item_name="Item 1", quantity=Decimal("1"), rate=Decimal("100"), taxable_amount=Decimal("100"), igst_rate=Decimal("18"), igst_amount=Decimal("18"), total_amount=Decimal("118"))],
        taxable_total=Decimal("100"),
        igst_total=Decimal("18"),
        grand_total=Decimal("118")
    )
    validated = validate_invoice_document(doc_valid)
    v01_errors = [v for v in validated.validation_violations if v["rule_id"] == "V01" and v["severity"] == "ERROR"]
    assert len(v01_errors) == 0

    # Invalid GSTIN (bad checksum)
    doc_invalid = InvoiceDocument(
        invoice_number="INV-002",
        invoice_date=date(2026, 5, 10),
        supplier=PartyInfo(name="Vendor MH", gstin="27AAPFU0939F1Z9"),
        buyer=PartyInfo(name="Kartar Singh & Sons", gstin="02AWLPK8092M1Z0"),
        items=[InvoiceItem(item_name="Item 1", quantity=Decimal("1"), rate=Decimal("100"), taxable_amount=Decimal("100"), igst_rate=Decimal("18"), igst_amount=Decimal("18"), total_amount=Decimal("118"))],
        taxable_total=Decimal("100"),
        igst_total=Decimal("18"),
        grand_total=Decimal("118")
    )
    validated_inv = validate_invoice_document(doc_invalid)
    v01_errors = [v for v in validated_inv.validation_violations if v["rule_id"] == "V01" and v["severity"] == "ERROR"]
    assert len(v01_errors) > 0
    assert any("failed format or Mod-36 checksum" in e["message"] for e in v01_errors)

def test_v02_seller_ne_buyer_gstin():
    doc = InvoiceDocument(
        invoice_number="INV-003",
        invoice_date=date(2026, 5, 10),
        supplier=PartyInfo(name="Same Company", gstin="02AWLPK8092M1Z0"),
        buyer=PartyInfo(name="Same Company", gstin="02AWLPK8092M1Z0"),
        items=[InvoiceItem(item_name="Item 1", quantity=Decimal("1"), rate=Decimal("100"), taxable_amount=Decimal("100"))]
    )
    validated = validate_invoice_document(doc)
    v02 = [v for v in validated.validation_violations if v["rule_id"] == "V02"]
    assert len(v02) > 0
    assert "Seller GSTIN cannot be identical to Buyer GSTIN" in v02[0]["message"]

def test_v03_own_company_exclusion_rule():
    # Purchase voucher where supplier has user's own GSTIN (roles inverted!)
    doc_reversed = InvoiceDocument(
        invoice_type="PURCHASE",
        invoice_number="INV-004",
        invoice_date=date(2026, 5, 10),
        supplier=PartyInfo(name="Kartar Singh & Sons", gstin="02AWLPK8092M1Z0"),
        buyer=PartyInfo(name="External Vendor", gstin="27AAPFU0939F1ZV"),
        items=[InvoiceItem(item_name="Item 1", quantity=Decimal("1"), rate=Decimal("100"), taxable_amount=Decimal("100"))]
    )
    validated = validate_invoice_document(doc_reversed)
    v03 = [v for v in validated.validation_violations if v["rule_id"] == "V03" and v["severity"] == "ERROR"]
    assert len(v03) > 0
    assert "Party roles must be swapped" in v03[0]["message"]

def test_v05_invoice_number():
    # Missing invoice number
    doc = InvoiceDocument(
        invoice_number="",
        invoice_date=date(2026, 5, 10),
        supplier=PartyInfo(name="Vendor"),
        buyer=PartyInfo(name="Buyer"),
        items=[InvoiceItem(item_name="Item 1", quantity=Decimal("1"), rate=Decimal("100"), taxable_amount=Decimal("100"))]
    )
    validated = validate_invoice_document(doc)
    assert any("Missing invoice number" in v["message"] for v in validated.validation_violations if v["rule_id"] == "V05")

def test_v07_hsn_format():
    doc = InvoiceDocument(
        invoice_number="INV-005",
        invoice_date=date(2026, 5, 10),
        supplier=PartyInfo(name="Vendor"),
        buyer=PartyInfo(name="Buyer"),
        items=[InvoiceItem(item_name="Item 1", hsn_sac="12345", quantity=Decimal("1"), rate=Decimal("100"), taxable_amount=Decimal("100"))]
    )
    validated = validate_invoice_document(doc)
    assert any("must be 4, 6, or 8 digits" in v["message"] for v in validated.validation_violations if v["rule_id"] == "V07")

def test_v08_date_dependent_gst_rates():
    # Post-reform invoice (date 2026-06-01): rate 12% is NOT in allowed slabs {0, 0.25, 3, 5, 18, 40}
    doc_new = InvoiceDocument(
        invoice_number="INV-006",
        invoice_date=date(2026, 6, 1),
        supplier=PartyInfo(name="Vendor"),
        buyer=PartyInfo(name="Buyer"),
        items=[InvoiceItem(item_name="Item 1", quantity=Decimal("1"), rate=Decimal("100"), taxable_amount=Decimal("100"), igst_rate=Decimal("12.00"))]
    )
    val_new = validate_invoice_document(doc_new)
    assert any("not in allowed slabs for date" in v["message"] for v in val_new.validation_violations if v["rule_id"] == "V08")

    # Pre-reform invoice (date 2024-06-01): rate 12% IS allowed!
    doc_old = InvoiceDocument(
        invoice_number="INV-007",
        invoice_date=date(2024, 6, 1),
        supplier=PartyInfo(name="Vendor"),
        buyer=PartyInfo(name="Buyer"),
        items=[InvoiceItem(item_name="Item 1", quantity=Decimal("1"), rate=Decimal("100"), taxable_amount=Decimal("100"), igst_rate=Decimal("12.00"), igst_amount=Decimal("12.00"), total_amount=Decimal("112.00"))],
        taxable_total=Decimal("100"),
        igst_total=Decimal("12"),
        grand_total=Decimal("112")
    )
    val_old = validate_invoice_document(doc_old)
    v08_old = [v for v in val_old.validation_violations if v["rule_id"] == "V08"]
    assert len(v08_old) == 0

def test_v09_and_v10_arithmetic_checks():
    # Qty 2 * Rate 50 = 100, but taxable set to 80 without discount -> V09 error
    doc = InvoiceDocument(
        invoice_number="INV-008",
        invoice_date=date(2026, 6, 1),
        supplier=PartyInfo(name="Vendor"),
        buyer=PartyInfo(name="Buyer"),
        items=[InvoiceItem(item_name="Item 1", quantity=Decimal("2"), rate=Decimal("50"), taxable_amount=Decimal("80"))]
    )
    val = validate_invoice_document(doc)
    assert any(v["rule_id"] == "V09" for v in val.validation_violations)

def test_v20_reserved_words_rejection():
    # Row named "SUBTOTAL" or "CGST" should be rejected as stock item
    doc = InvoiceDocument(
        invoice_number="INV-009",
        invoice_date=date(2026, 6, 1),
        supplier=PartyInfo(name="Vendor"),
        buyer=PartyInfo(name="Buyer"),
        items=[InvoiceItem(item_name="SUBTOTAL 18%", quantity=Decimal("1"), rate=Decimal("100"), taxable_amount=Decimal("100"))]
    )
    val = validate_invoice_document(doc)
    assert any(v["rule_id"] == "V20" for v in val.validation_violations)

def test_repair_loop_tax_inclusive():
    # Row with inclusive price: 1 item at 118 total (18% GST). Extracted as rate=118, taxable=118, total=118.
    item = InvoiceItem(
        item_name="Inclusive Item",
        quantity=Decimal("1.00"),
        rate=Decimal("118.00"),
        taxable_amount=Decimal("118.00"),
        total_amount=Decimal("118.00"),
        cgst_rate=Decimal("9.00"),
        sgst_rate=Decimal("9.00"),
        tax_mode="inclusive"
    )
    doc = InvoiceDocument(
        invoice_number="INV-INCL-01",
        invoice_date=date(2026, 6, 1),
        tax_mode="inclusive",
        supplier=PartyInfo(name="Vendor HP", gstin="02BULPK7285D1ZL"),
        buyer=PartyInfo(name="Kartar Singh & Sons", gstin="02AWLPK8092M1Z0"),
        items=[item],
        taxable_total=Decimal("100.00"),
        cgst_total=Decimal("9.00"),
        sgst_total=Decimal("9.00"),
        grand_total=Decimal("118.00")
    )
    repaired = run_repair_loop(doc)
    assert repaired is True
    assert doc.items[0].is_tax_inclusive is True
    assert doc.items[0].taxable_amount == Decimal("100.00")
    assert doc.items[0].rate == Decimal("100.00")
    assert doc.items[0].cgst_amount == Decimal("9.00")
    assert doc.items[0].sgst_amount == Decimal("9.00")
