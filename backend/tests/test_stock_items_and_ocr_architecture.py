import os
import io
import pytest
from decimal import Decimal
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.invoices.model import InvoiceDocument, InvoiceItem, PartyInfo
from app.invoices.extractor import InvoiceExtractor, OCRLine
from app.accounting.stock_item_importer import (
    global_stock_item_store,
    import_stock_items_from_text,
    ImportedStockItem,
    normalize_item_name
)

def test_invoice_number_preserves_leading_zeros_and_rejects_po_phone():
    ext = InvoiceExtractor()
    ocr_lines = [
        OCRLine("TAX INVOICE", [[50, 20], [200, 20], [200, 35], [50, 35]]),
        OCRLine("Invoice No: INV-00125", [[50, 40], [250, 40], [250, 55], [50, 55]]),
        OCRLine("P.O. No: PO-998877", [[50, 60], [250, 60], [250, 75], [50, 75]]),
        OCRLine("Phone: 9816012345", [[50, 80], [250, 80], [250, 95], [50, 95]]),
        OCRLine("E-Way Bill: 121234345656", [[50, 100], [250, 100], [250, 115], [50, 115]]),
    ]
    full_text = "\n".join(l.text for l in ocr_lines)
    inv_num, bill_num = ext._find_invoice_and_bill_numbers(ocr_lines, full_text)
    assert inv_num == "INV-00125", f"Expected 'INV-00125', got '{inv_num}'"
    assert inv_num != "PO-998877"
    assert inv_num != "9816012345"

def test_wrapped_item_description_merging():
    """Verifies that multi-line product descriptions are merged with the previous item and not treated as a new row."""
    ext = InvoiceExtractor()
    supplier = PartyInfo(name="Seller Co", gstin="02AAACW5680K1Z7")
    buyer = PartyInfo(name="Buyer Co", gstin="02AWLPK8092M1Z0")

    ocr_lines = [
        OCRLine("TAX INVOICE", [[50, 20], [200, 20], [200, 35], [50, 35]]),
        OCRLine("Item Description HSN Qty Rate Taxable Amount", [[50, 80], [500, 80], [500, 95], [50, 95]]),
        # Item 1 row
        OCRLine("Ultra Strong Industrial Cement 50kg 252329 100 bags 350.00 35000.00", [[50, 110], [500, 110], [500, 125], [50, 125]]),
        # Wrapped line for Item 1
        OCRLine("Grade 53 OPC conforming to IS 269:2015 standards", [[50, 130], [400, 130], [400, 145], [50, 145]]),
        # Item 2 row
        OCRLine("Binding Wire 18 Gauge 721710 5 kgs 120.00 600.00", [[50, 160], [500, 160], [500, 175], [50, 175]]),
        OCRLine("Total Taxable Value: 35600.00", [[50, 200], [400, 200], [400, 215], [50, 215]]),
        OCRLine("Grand Total: 35600.00", [[50, 220], [400, 220], [400, 235], [50, 235]])
    ]
    full_text = "\n".join(l.text for l in ocr_lines)

    items, totals, detected_count, note = ext._extract_items_and_totals(
        ocr_lines=ocr_lines,
        full_text=full_text,
        supplier=supplier,
        buyer=buyer
    )

    assert len(items) == 2, f"Expected 2 items, got {len(items)}"
    assert "IS 269:2015" in items[0].description, "Wrapped line was not merged into Item 1 description!"
    assert items[0].is_description_wrapped is True
    assert items[1].quantity == Decimal("5.00")
    assert items[1].rate == Decimal("120.00")

def test_stock_items_import_from_sample_xml():
    """Verifies that Tally stock items XML sample can be parsed and indexed."""
    sample_xml_path = "../stock items list sample.xml"
    if not os.path.exists(sample_xml_path):
        sample_xml_path = "stock items list sample.xml"
    if not os.path.exists(sample_xml_path):
        pytest.skip("stock items list sample.xml not found in workspace root")

    with open(sample_xml_path, "rb") as f:
        # Read first 1 MB to test parser speed and accuracy
        raw = f.read(1000000).decode("utf-16", errors="ignore")
        # Ensure it closes properly
        last_item = raw.rfind("</STOCKITEM>")
        if last_item != -1:
            xml_chunk = raw[:last_item + len("</STOCKITEM>")] + "\n</TALLYMESSAGE>\n</REQUESTDATA>\n</IMPORTDATA>\n</BODY>\n</ENVELOPE>"
            res = import_stock_items_from_text(xml_chunk, filename="stock items list sample.xml")
            assert res.total_imported > 0
            assert res.detected_format == "XML"
            # Verify fields on first imported item
            it = res.items[0]
            assert it.name
            assert it.base_units
            assert it.normalized_name

def test_stock_item_store_fuzzy_matching():
    store = global_stock_item_store
    user_id = "test_user_fuzzy_match"
    item1 = ImportedStockItem(
        name="7UP 200ML RGP 24 RS.12",
        normalized_name=normalize_item_name("7UP 200ML RGP 24 RS.12"),
        base_units="case",
        hsn_code="22021010",
        parent="Coldrink 28%"
    )
    store.add_items(user_id, [item1])

    # Test exact match
    match1 = store.match_item(user_id, "7UP 200ML RGP 24 RS.12")
    assert match1.match_type == "EXACT"
    assert match1.confidence == "HIGH"
    assert match1.matched_stock_item.name == "7UP 200ML RGP 24 RS.12"

    # Test fuzzy match with slightly different formatting
    match2 = store.match_item(user_id, "7 Up 200 ml Rgp", hsn="22021010")
    assert match2.confidence in ("HIGH", "MEDIUM")
    assert match2.matched_stock_item.name == "7UP 200ML RGP 24 RS.12"

def test_generate_new_stock_item_xml():
    store = global_stock_item_store
    xml_str = store.generate_new_stock_item_xml(
        name="New Test Product 500ML",
        hsn="22021010",
        uom="case",
        parent_group="Beverages 28%",
        gst_rate=Decimal("28.00")
    )
    assert "<STOCKITEM NAME=\"New Test Product 500ML\" ACTION=\"Create\">" in xml_str
    assert "<PARENT>Beverages 28%</PARENT>" in xml_str
    assert "<BASEUNITS>case</BASEUNITS>" in xml_str
    assert "<HSNCODE>22021010</HSNCODE>" in xml_str
    assert "<GSTRATE>28.00</GSTRATE>" in xml_str
