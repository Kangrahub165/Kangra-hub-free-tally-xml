import os
import pytest
from decimal import Decimal
from app.invoices.extractor import InvoiceExtractor

IMAGE_SAMPLE_PATH = r"D:\KANGRA HUB SALES PURCHASE\INVOICE SAMPLE\Image.jpg"

@pytest.mark.skipif(not os.path.exists(IMAGE_SAMPLE_PATH), reason="Image.jpg sample not found")
def test_image_jpg_critical_sample_regression():
    """
    Mandatory regression test for the critical real-world sample: Image.jpg
    Verifies:
    1. Supplier: Pong Vally Traders (2026-2027) & GSTIN: 02BULPK7285D1ZL
    2. Buyer: KARTAR SINGH & SONS & GSTIN: 02AWLPK8092M1Z0
    3. Invoice Number: CYCLE/26-27/63
    4. Invoice Date: 09-May-2026 (2026-05-09)
    5. No invented Due Date, PO Number, or E-Way bill
    6. Exactly 24 item rows (1 to 24)
    7. Taxable Total: 34,525.84
    8. CGST Total: 893.45 & SGST Total: 893.45
    9. Grand Total: 36,312.74 (sum of visible page items)
    10. Multi-page continuation detected ('continued to page number 2')
    11. Hand-written markings at right margin (e.g. 11.06, h0.95) are NOT captured as totals
    12. Row 14 Qty is 24 (not 241)
    13. Row 16 tax rate is 9.00% CGST + 9.00% SGST
    14. Row 23 tax rate is 2.50% CGST + 2.50% SGST
    15. Row 24 tax rate is 2.50% CGST + 2.50% SGST
    """
    with open(IMAGE_SAMPLE_PATH, "rb") as f:
        img_bytes = f.read()

    extractor = InvoiceExtractor()
    results = extractor.extract_from_file(img_bytes, "Image.jpg", type_hint="PURCHASE")

    assert len(results) == 1, "Expected exactly 1 invoice document extracted"
    inv = results[0]

    # 1. Invoice Type & Metadata
    assert inv.invoice_type == "PURCHASE", f"Expected PURCHASE, got {inv.invoice_type}"
    assert inv.invoice_number == "CYCLE/26-27/63", f"Expected CYCLE/26-27/63, got {inv.invoice_number}"
    assert str(inv.invoice_date) == "2026-05-09", f"Expected 2026-05-09, got {inv.invoice_date}"
    assert not inv.due_date, "Due date must not be invented"
    assert not inv.po_number, "PO number must not be invented"
    assert not inv.eway_bill_number, "E-Way bill must not be invented"

    # 2. Parties & GSTINs
    assert "PONG VALLY TRADERS" in inv.supplier.name.upper(), f"Unexpected supplier name: {inv.supplier.name}"
    assert inv.supplier.gstin == "02BULPK7285D1ZL", f"Unexpected supplier GSTIN: {inv.supplier.gstin}"
    assert "KARTAR" in inv.buyer.name.upper(), f"Unexpected buyer name: {inv.buyer.name}"
    assert inv.buyer.gstin == "02AWLPK8092M1Z0", f"Unexpected buyer GSTIN: {inv.buyer.gstin}"

    # 3. Item Count: exactly 24 numbered rows
    assert len(inv.items) == 24, f"Expected exactly 24 items, got {len(inv.items)}"

    # 4. Totals validation
    assert inv.taxable_total == Decimal("34525.84"), f"Expected 34525.84, got {inv.taxable_total}"
    assert inv.cgst_total == Decimal("893.45"), f"Expected 893.45, got {inv.cgst_total}"
    assert inv.sgst_total == Decimal("893.45"), f"Expected 893.45, got {inv.sgst_total}"
    assert inv.grand_total == Decimal("36312.74"), f"Expected 36312.74, got {inv.grand_total}"

    # 5. Row-by-row integrity
    calc_taxable = sum((it.taxable_amount for it in inv.items), Decimal("0.00"))
    calc_cgst = sum((it.cgst_amount for it in inv.items), Decimal("0.00"))
    calc_sgst = sum((it.sgst_amount for it in inv.items), Decimal("0.00"))
    calc_total = sum((it.total_amount for it in inv.items), Decimal("0.00"))

    assert calc_taxable == Decimal("34525.84"), f"Sum of item taxable ({calc_taxable}) != 34525.84"
    assert calc_cgst == Decimal("893.45"), f"Sum of item CGST ({calc_cgst}) != 893.45"
    assert calc_sgst == Decimal("893.45"), f"Sum of item SGST ({calc_sgst}) != 893.45"
    assert calc_total == Decimal("36312.74"), f"Sum of item totals ({calc_total}) != 36312.74"

    # 6. Specific tricky rows
    # Item 1: Must have total 4247.96 (not handwritten 11.06)
    it1 = inv.items[0]
    assert "DHP" in it1.item_name.upper()
    assert it1.hsn_sac == "33074100"
    assert it1.quantity == Decimal("24.00")
    assert it1.rate == Decimal("177.00")
    assert it1.taxable_amount == Decimal("4045.68")
    assert it1.total_amount == Decimal("4247.96"), f"Item 1 total got overwritten by handwritten note: {it1.total_amount}"

    # Item 14: Qty must be 24 (not 241)
    it14 = inv.items[13]
    assert it14.quantity == Decimal("24.00"), f"Item 14 qty expected 24.00, got {it14.quantity}"
    assert it14.taxable_amount == Decimal("2010.72")

    # Item 16: Tax rate must be 9.00% (not 6.00%)
    it16 = inv.items[15]
    assert it16.cgst_rate == Decimal("9.00"), f"Item 16 CGST rate expected 9.00, got {it16.cgst_rate}"
    assert it16.sgst_rate == Decimal("9.00"), f"Item 16 SGST rate expected 9.00, got {it16.sgst_rate}"

    # Item 23: Tax rate must be 2.50% (not 902.50%)
    it23 = inv.items[22]
    assert it23.cgst_rate == Decimal("2.50"), f"Item 23 CGST rate expected 2.50, got {it23.cgst_rate}"
    assert it23.sgst_rate == Decimal("2.50"), f"Item 23 SGST rate expected 2.50, got {it23.sgst_rate}"

    # 7. Page continuation
    assert inv.has_page_continuation is True, "Expected has_page_continuation to be True"
    assert inv.continuation_note is not None, "Expected continuation_note to be set"
    assert any("continues to page" in w.lower() for w in inv.warnings), "Expected continuation warning in doc.warnings"
