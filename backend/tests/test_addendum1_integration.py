import pytest
from datetime import date
from decimal import Decimal
from app.invoices.model import InvoiceDocument, InvoiceItem, PartyInfo
from app.invoices.extractor import InvoiceExtractor, OCRLine
from app.invoices.table_engine import (
    map_header,
    pack_size_from_description,
    split_qty_cell,
    pick_unit,
    solve_columns,
    allowed_rates,
    resolve_gst_rate,
    detect_tax_mode,
    to_exclusive,
    close as table_close
)
from app.invoices.validator import validate_invoice_document, run_repair_loop

def test_mrp_column_never_assigned_to_qty_or_rate():
    """AD3, AD4, AD10: Invoices with an MRP column must store MRP in item.mrp and not as Qty or Rate."""
    ext = InvoiceExtractor()
    supplier = PartyInfo(name="ABC FMCG Dist", gstin="02AAACW5680K1Z7")
    buyer = PartyInfo(name="Kartar Singh & Sons", gstin="02AWLPK8092M1Z0")

    ocr_lines = [
        OCRLine("TAX INVOICE", [[50, 20], [200, 20], [200, 35], [50, 35]]),
        # Table Header with MRP column
        OCRLine("Sr Description HSN MRP Qty Unit Rate Taxable Total", [[50, 60], [600, 60], [600, 75], [50, 75]]),
        # Item 1: MRP 50.00, Qty 10, Unit PCS, Rate 40.00, Taxable 400.00, Total 472.00 (18% GST)
        OCRLine("1 Dove Soap 100gm 340111 50.00 10 PCS 40.00 400.00 472.00", [[50, 90], [600, 90], [600, 105], [50, 105]]),
        OCRLine("Total Taxable Value: 400.00", [[50, 150], [400, 150], [400, 165], [50, 165]]),
        OCRLine("Grand Total: 472.00", [[50, 170], [400, 170], [400, 185], [50, 185]]),
    ]
    full_text = "\n".join(l.text for l in ocr_lines)

    items, totals, count, note = ext._extract_items_and_totals(
        ocr_lines=ocr_lines,
        full_text=full_text,
        supplier=supplier,
        buyer=buyer,
        inv_date=date(2026, 4, 1)
    )

    assert len(items) == 1, f"Expected 1 item, got {len(items)}"
    it = items[0]
    assert it.quantity == Decimal("10.00"), f"Expected qty 10.00, got {it.quantity}"
    assert it.rate == Decimal("40.00"), f"Expected rate 40.00, got {it.rate}"
    assert it.taxable_amount == Decimal("400.00"), f"Expected taxable 400.00, got {it.taxable_amount}"
    # MRP must be 50.00 and NEVER overwrite qty (10) or rate (40)
    assert it.mrp == Decimal("50.00"), f"Expected MRP 50.00, got {it.mrp}"
    assert it.mrp != it.rate, "MRP must not be conflated with Rate"
    assert it.mrp != it.quantity, "MRP must not be conflated with Quantity"

def test_pack_size_vs_unit_separation():
    """AD4: 'Dove Soap 100gm' or 'Parle-G 200g' has pack size '100 gm', but unit is PCS."""
    ext = InvoiceExtractor()
    supplier = PartyInfo(name="ABC FMCG Dist", gstin="02AAACW5680K1Z7")
    buyer = PartyInfo(name="Kartar Singh & Sons", gstin="02AWLPK8092M1Z0")

    ocr_lines = [
        OCRLine("TAX INVOICE", [[50, 20], [200, 20], [200, 35], [50, 35]]),
        OCRLine("Item Description HSN Qty Unit Rate Taxable Total", [[50, 60], [600, 60], [600, 75], [50, 75]]),
        OCRLine("Sunsilk Shampoo 340ml 330510 12 BTL 150.00 1800.00 2124.00", [[50, 90], [600, 90], [600, 105], [50, 105]]),
        OCRLine("Total Taxable Value: 1800.00", [[50, 150], [400, 150], [400, 165], [50, 165]]),
        OCRLine("Grand Total: 2124.00", [[50, 170], [400, 170], [400, 185], [50, 185]]),
    ]
    full_text = "\n".join(l.text for l in ocr_lines)

    items, totals, count, note = ext._extract_items_and_totals(
        ocr_lines=ocr_lines,
        full_text=full_text,
        supplier=supplier,
        buyer=buyer,
        inv_date=date(2026, 4, 1)
    )

    assert len(items) == 1
    it = items[0]
    assert it.pack_size == "340 ml", f"Expected pack size '340 ml', got '{it.pack_size}'"
    assert it.uom in ("BTL", "BOTTLE"), f"Trade unit must remain BTL/BOTTLE, got {it.uom}"
    assert "340ml" in it.item_name or "340" in it.item_name, "Pack size must remain in item description"

def test_date_dependent_gst_rate_slabs():
    """AD5: Pre-reform (before 22-Sep-2025) allows 12% and 28%. Post-reform allows 18% and 40%."""
    # Pre-reform invoice
    allowed_pre = allowed_rates(date(2025, 6, 1))
    assert Decimal("12.00") in allowed_pre
    assert Decimal("28.00") in allowed_pre
    assert Decimal("40.00") not in allowed_pre

    # Post-reform invoice
    allowed_post = allowed_rates(date(2026, 1, 15))
    assert Decimal("18.00") in allowed_post
    assert Decimal("40.00") in allowed_post
    assert Decimal("12.00") not in allowed_post
    assert Decimal("28.00") not in allowed_post

    # Intra-state half-rates (2.5 + 2.5 -> 5.0)
    rate, how, flag = resolve_gst_rate({"cgst_rate": Decimal("2.50"), "sgst_rate": Decimal("2.50")}, allowed=allowed_post)
    assert rate == Decimal("5.00")
    assert how == "cgst+sgst"
    assert not flag

    # 9.0 + 9.0 -> 18.0
    rate, how, flag = resolve_gst_rate({"cgst_rate": Decimal("9.00"), "sgst_rate": Decimal("9.00")}, allowed=allowed_post)
    assert rate == Decimal("18.00")
    assert how == "cgst+sgst"
    assert not flag

def test_tax_inclusive_detection_and_exclusive_conversion():
    """AD6, AD10: Total amounts equal grand total without separate tax -> inclusive converted to exclusive."""
    # Line 1: 1000 inclusive at 18% GST -> taxable 847.46, tax 152.54, cgst 76.27, sgst 76.27
    taxable, tax, cgst, sgst = to_exclusive(Decimal("1000.00"), Decimal("18.00"), "inclusive")
    assert taxable == Decimal("847.46")
    assert tax == Decimal("152.54")
    assert cgst == Decimal("76.27")
    assert sgst == Decimal("76.27")
    assert taxable + tax == Decimal("1000.00")

    # Detect tax mode from totals
    rows = [
        {"amount": Decimal("1000.00"), "rate": Decimal("18.00"), "tax": Decimal("152.54")},
        {"amount": Decimal("500.00"), "rate": Decimal("18.00"), "tax": Decimal("76.27")},
    ]
    mode, why, votes = detect_tax_mode(rows, grand_total=Decimal("1500.00"))
    assert mode == "inclusive", f"Expected inclusive mode, got {mode} ({why})"
