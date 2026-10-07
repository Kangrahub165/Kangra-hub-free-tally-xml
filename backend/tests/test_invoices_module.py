import os
import io
import pytest
from datetime import date
from decimal import Decimal
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.invoices.model import (
    InvoiceDocument,
    InvoiceItem,
    PartyInfo,
    FinalInvoiceSnapshot,
    LedgerMappingConfig
)
from app.invoices.extractor import InvoiceExtractor
from app.invoices.validator import (
    validate_invoice_document,
    detect_batch_duplicates,
    compute_batch_summary
)
from app.invoices.xml_generator import InvoiceTallyXMLGenerator
from app.invoices.xml_validator import validate_invoice_tally_xml

def create_sample_purchase_pdf() -> bytes:
    """Generates a realistic Purchase Tax Invoice PDF in memory."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(100, 750, "TAX INVOICE")
    c.drawString(100, 730, "WAVE BEVERAGES PVT. LTD.")
    c.drawString(100, 715, "GSTIN: 02AAACW5680K1Z7")
    c.drawString(100, 700, "State: Himachal Pradesh (02)")
    c.drawString(100, 685, "Invoice No: NPDTI2627-000789")
    c.drawString(100, 670, "Date: 03-06-2026")
    c.drawString(100, 655, "Place of Supply: Himachal Pradesh")

    c.drawString(350, 730, "Billed To / Buyer:")
    c.drawString(350, 715, "Kartar Singh & Sons")
    c.drawString(350, 700, "GSTIN: 02AWLPK8092M1Z0")
    c.drawString(350, 685, "State: Himachal Pradesh (02)")

    # Table header
    c.drawString(50, 600, "Item Description")
    c.drawString(250, 600, "HSN")
    c.drawString(320, 600, "Qty")
    c.drawString(380, 600, "Rate")
    c.drawString(450, 600, "Taxable Amount")

    # Item 1
    c.drawString(50, 570, "MM MIX FRUIT 850 ML PET")
    c.drawString(250, 570, "22029920")
    c.drawString(320, 570, "3 case")
    c.drawString(380, 570, "480.00")
    c.drawString(450, 570, "1440.00")

    # Item 2
    c.drawString(50, 540, "COKE 740 ML (1X24)")
    c.drawString(250, 540, "22021010")
    c.drawString(320, 540, "25 case")
    c.drawString(380, 540, "468.06")
    c.drawString(450, 540, "11701.50")

    # Totals
    c.drawString(350, 480, "Taxable Value: 13141.50")
    c.drawString(350, 460, "CGST (2.5%): 328.54")
    c.drawString(350, 440, "SGST (2.5%): 328.54")
    c.drawString(350, 420, "Round Off: 0.42")
    c.drawString(350, 400, "Grand Total: 13799.00")

    c.save()
    return buf.getvalue()

def create_sample_sales_pdf() -> bytes:
    """Generates a realistic Sales Tax Invoice PDF with IGST in memory."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(100, 750, "TAX INVOICE (OUTWARD SUPPLY)")
    c.drawString(100, 730, "Kartar Singh & Sons")
    c.drawString(100, 715, "GSTIN: 02AWLPK8092M1Z0")
    c.drawString(100, 700, "State: Himachal Pradesh (02)")
    c.drawString(100, 685, "Invoice No: GST-14343")
    c.drawString(100, 670, "Date: 01-09-2026")
    c.drawString(100, 655, "Place of Supply: Punjab")

    c.drawString(350, 730, "Billed To / Buyer:")
    c.drawString(350, 715, "PUNJAB TRADERS")
    c.drawString(350, 700, "GSTIN: 03AIBPG9510A2Z3")
    c.drawString(350, 685, "State: Punjab (03)")

    # Table header
    c.drawString(50, 600, "Item Description")
    c.drawString(250, 600, "HSN")
    c.drawString(320, 600, "Qty")
    c.drawString(380, 600, "Rate")
    c.drawString(450, 600, "Taxable Amount")

    # Item 1
    c.drawString(50, 570, "LIMCA 250 ML PET ASSP")
    c.drawString(250, 570, "22021010")
    c.drawString(320, 570, "40 case")
    c.drawString(380, 570, "357.14")
    c.drawString(450, 570, "14285.60")

    # Totals with IGST
    c.drawString(350, 480, "Taxable Value: 14285.60")
    c.drawString(350, 460, "IGST (18%): 2571.41")
    c.drawString(350, 440, "Round Off: -0.01")
    c.drawString(350, 420, "Grand Total: 16857.00")

    c.save()
    return buf.getvalue()

def create_sample_jpg_invoice() -> bytes:
    """Creates a synthetic invoice image in memory for JPG OCR testing."""
    img = Image.new('RGB', (1600, 2200), color=(255, 255, 255))
    d = ImageDraw.Draw(img)

    # Header
    d.text((100, 100), "TAX INVOICE - PURCHASE", fill=(0, 0, 0))
    d.text((100, 150), "Supplier: WAVE BEVERAGES PVT. LTD.", fill=(0, 0, 0))
    d.text((100, 200), "GSTIN: 02AAACW5680K1Z7", fill=(0, 0, 0))
    d.text((100, 250), "State: Himachal Pradesh", fill=(0, 0, 0))
    d.text((100, 300), "Invoice No: NPDTI2627-000789", fill=(0, 0, 0))
    d.text((100, 350), "Date: 03-06-2026", fill=(0, 0, 0))

    # Buyer
    d.text((900, 150), "Bill To: Kartar Singh & Sons", fill=(0, 0, 0))
    d.text((900, 200), "GSTIN: 02AWLPK8092M1Z0", fill=(0, 0, 0))
    d.text((900, 250), "State: Himachal Pradesh", fill=(0, 0, 0))

    # Items Table
    d.text((100, 500), "Item Description        HSN        Qty   Rate     Amount", fill=(0, 0, 0))
    d.text((100, 560), "MM MIX FRUIT 850 ML     22029920   3 case 480.00   1440.00", fill=(0, 0, 0))

    # Totals
    d.text((900, 800), "Taxable Value: 1440.00", fill=(0, 0, 0))
    d.text((900, 850), "CGST (2.5%): 36.00", fill=(0, 0, 0))
    d.text((900, 900), "SGST (2.5%): 36.00", fill=(0, 0, 0))
    d.text((900, 950), "Grand Total: 1512.00", fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=95)
    return buf.getvalue()

def test_purchase_pdf_extraction():
    pdf_bytes = create_sample_purchase_pdf()
    extractor = InvoiceExtractor()
    docs = extractor.extract_from_file(pdf_bytes, "purchase_invoice.pdf")

    assert len(docs) == 1
    doc = docs[0]
    assert doc.invoice_number == "NPDTI2627-000789"
    assert doc.supplier.gstin == "02AAACW5680K1Z7"
    assert doc.buyer.gstin == "02AWLPK8092M1Z0"
    assert doc.invoice_date == date(2026, 6, 3)
    assert len(doc.items) >= 2
    assert doc.taxable_total == Decimal("13141.50")
    assert doc.grand_total == Decimal("13799.00")
    assert doc.cgst_total == Decimal("328.54")
    assert doc.sgst_total == Decimal("328.54")
    assert doc.igst_total == Decimal("0.00")  # CGST+SGST preserved, IGST 0

def test_sales_pdf_extraction_with_igst():
    pdf_bytes = create_sample_sales_pdf()
    extractor = InvoiceExtractor()
    docs = extractor.extract_from_file(pdf_bytes, "sales_invoice.pdf")

    assert len(docs) == 1
    doc = docs[0]
    assert doc.invoice_number == "GST-14343"
    assert doc.invoice_date == date(2026, 9, 1)
    assert doc.buyer.gstin == "03AIBPG9510A2Z3"
    assert doc.igst_total == Decimal("2571.41")
    assert doc.cgst_total == Decimal("0.00")  # IGST preserved, CGST/SGST 0
    assert doc.sgst_total == Decimal("0.00")

def test_jpg_invoice_ocr_extraction():
    jpg_bytes = create_sample_jpg_invoice()
    extractor = InvoiceExtractor()
    docs = extractor.extract_from_file(jpg_bytes, "invoice.jpg")

    assert len(docs) == 1
    doc = docs[0]
    assert "000789" in doc.invoice_number
    assert doc.supplier.gstin == "02AAACW5680K1Z7"
    assert doc.grand_total == Decimal("1512.00")

def test_arithmetic_validation():
    doc = InvoiceDocument(
        invoice_number="INV-100",
        invoice_date=date(2026, 6, 1),
        supplier=PartyInfo(name="Wave", gstin="02AAACW5680K1Z7"),
        buyer=PartyInfo(name="Kartar", gstin="02AWLPK8092M1Z0"),
        items=[
            InvoiceItem(
                item_name="Item A",
                quantity=Decimal("2.00"),
                rate=Decimal("500.00"),
                taxable_amount=Decimal("1000.00"),
                cgst_rate=Decimal("9.00"),
                cgst_amount=Decimal("90.00"),
                sgst_rate=Decimal("9.00"),
                sgst_amount=Decimal("90.00"),
                total_amount=Decimal("1180.00")
            )
        ],
        taxable_total=Decimal("1000.00"),
        cgst_total=Decimal("90.00"),
        sgst_total=Decimal("90.00"),
        grand_total=Decimal("1180.00")
    )
    validated = validate_invoice_document(doc)
    assert validated.is_valid is True
    assert len(validated.errors) == 0

def test_arithmetic_mismatch_warning():
    doc = InvoiceDocument(
        invoice_number="INV-101",
        invoice_date=date(2026, 6, 1),
        supplier=PartyInfo(name="Wave", gstin="02AAACW5680K1Z7"),
        buyer=PartyInfo(name="Kartar", gstin="02AWLPK8092M1Z0"),
        items=[
            InvoiceItem(
                item_name="Item A",
                taxable_amount=Decimal("1000.00"),
                total_amount=Decimal("1180.00")
            )
        ],
        taxable_total=Decimal("1000.00"),
        grand_total=Decimal("2000.00")  # Mismatch!
    )
    validated = validate_invoice_document(doc)
    assert any("does not reconcile" in w for w in validated.warnings)

def test_gst_preservation_rule():
    # Intra-state: CGST 9% + SGST 9% must not become IGST
    doc_intra = InvoiceDocument(
        invoice_number="INV-102",
        invoice_date=date(2026, 6, 1),
        supplier=PartyInfo(name="Supplier HP", gstin="02AAACW5680K1Z7"),
        buyer=PartyInfo(name="Buyer HP", gstin="02AWLPK8092M1Z0"),
        taxable_total=Decimal("1000.00"),
        cgst_total=Decimal("90.00"),
        sgst_total=Decimal("90.00"),
        igst_total=Decimal("0.00"),
        grand_total=Decimal("1180.00")
    )
    assert doc_intra.cgst_total == Decimal("90.00")
    assert doc_intra.sgst_total == Decimal("90.00")
    assert doc_intra.igst_total == Decimal("0.00")

    # Inter-state: IGST 18% must not become CGST + SGST
    doc_inter = InvoiceDocument(
        invoice_number="INV-103",
        invoice_date=date(2026, 6, 1),
        supplier=PartyInfo(name="Supplier HP", gstin="02AAACW5680K1Z7"),
        buyer=PartyInfo(name="Buyer Punjab", gstin="03AIBPG9510A2Z3"),
        taxable_total=Decimal("1000.00"),
        cgst_total=Decimal("0.00"),
        sgst_total=Decimal("0.00"),
        igst_total=Decimal("180.00"),
        grand_total=Decimal("1180.00")
    )
    assert doc_inter.igst_total == Decimal("180.00")
    assert doc_inter.cgst_total == Decimal("0.00")
    assert doc_inter.sgst_total == Decimal("0.00")

def test_duplicate_invoice_detection():
    doc1 = InvoiceDocument(
        invoice_number="INV-DUP-1",
        invoice_date=date(2026, 6, 1),
        supplier=PartyInfo(gstin="02AAACW5680K1Z7"),
        grand_total=Decimal("5000.00")
    )
    doc2 = InvoiceDocument(
        invoice_number="INV-DUP-1",
        invoice_date=date(2026, 6, 1),
        supplier=PartyInfo(gstin="02AAACW5680K1Z7"),
        grand_total=Decimal("5000.00")
    )
    invoices = detect_batch_duplicates([doc1, doc2])
    assert invoices[1].duplicate_suspect is True

def test_purchase_xml_generation_and_validation():
    doc = InvoiceDocument(
        invoice_type="PURCHASE",
        invoice_number="NPDTI2627-000789",
        invoice_date=date(2026, 6, 3),
        supplier=PartyInfo(name="WAVE BEVERAGES PVT. LTD.", gstin="02AAACW5680K1Z7", state="Himachal Pradesh", requires_ledger_creation=True),
        buyer=PartyInfo(name="Kartar Singh & Sons", gstin="02AWLPK8092M1Z0", state="Himachal Pradesh"),
        items=[
            InvoiceItem(
                item_name="MM MIX FRUIT 850 ML PET",
                hsn_sac="22029920",
                quantity=Decimal("3.000"),
                uom="case",
                rate=Decimal("480.00"),
                taxable_amount=Decimal("1440.00"),
                cgst_rate=Decimal("2.50"),
                cgst_amount=Decimal("36.00"),
                sgst_rate=Decimal("2.50"),
                sgst_amount=Decimal("36.00"),
                total_amount=Decimal("1512.00"),
                requires_item_creation=True
            )
        ],
        taxable_total=Decimal("1440.00"),
        cgst_total=Decimal("36.00"),
        sgst_total=Decimal("36.00"),
        grand_total=Decimal("1512.00")
    )

    snapshot = FinalInvoiceSnapshot(
        invoices=[doc],
        ledger_mapping=LedgerMappingConfig(
            purchase_ledger="PURCHASE GST",
            cgst_ledger="CGST",
            sgst_ledger="SGST"
        ),
        auto_create_items=True,
        auto_create_parties=True
    )

    generator = InvoiceTallyXMLGenerator()
    xml_str = generator.generate_xml(snapshot)

    # 1. Structure assertions
    assert "<ENVELOPE>" in xml_str
    assert '<VOUCHER' in xml_str
    assert 'VCHTYPE="Purchase"' in xml_str
    assert '<STOCKITEM NAME="MM MIX FRUIT 850 ML PET"' in xml_str
    assert '<LEDGER NAME="WAVE BEVERAGES PVT. LTD."' in xml_str
    assert '<STOCKITEMNAME>MM MIX FRUIT 850 ML PET</STOCKITEMNAME>' in xml_str
    assert '<AMOUNT>-1440.00</AMOUNT>' in xml_str  # Purchase inventory negative
    assert '<AMOUNT>1512.00</AMOUNT>' in xml_str   # Supplier positive credit
    assert '<AMOUNT>-36.00</AMOUNT>' in xml_str    # CGST/SGST negative debit

    # 2. XML Validation
    is_valid, errors = validate_invoice_tally_xml(xml_str)
    assert is_valid is True, f"XML validation failed with errors: {errors}"

def test_sales_xml_generation_and_validation():
    doc = InvoiceDocument(
        invoice_type="SALES",
        invoice_number="GST-14343",
        invoice_date=date(2026, 9, 1),
        supplier=PartyInfo(name="Kartar Singh & Sons", gstin="02AWLPK8092M1Z0", state="Himachal Pradesh"),
        buyer=PartyInfo(name="KRISHAN KARYANA STORE HARIPUR", state="Himachal Pradesh", requires_ledger_creation=True),
        items=[
            InvoiceItem(
                item_name="LIMCA 250 ML PET ASSP",
                hsn_sac="22021010",
                quantity=Decimal("40.000"),
                uom="case",
                rate=Decimal("357.14"),
                taxable_amount=Decimal("14285.60"),
                cgst_rate=Decimal("20.00"),
                cgst_amount=Decimal("2857.12"),
                sgst_rate=Decimal("20.00"),
                sgst_amount=Decimal("2857.12"),
                total_amount=Decimal("20000.00"),
                requires_item_creation=True
            )
        ],
        taxable_total=Decimal("14285.60"),
        cgst_total=Decimal("2857.12"),
        sgst_total=Decimal("2857.12"),
        other_charges=Decimal("0.00"),
        round_off=Decimal("0.16"),
        grand_total=Decimal("20000.00")
    )

    snapshot = FinalInvoiceSnapshot(
        invoices=[doc],
        ledger_mapping=LedgerMappingConfig(
            sales_ledger="SALE GST",
            cgst_ledger="CGST",
            sgst_ledger="SGST"
        ),
        auto_create_items=True,
        auto_create_parties=True
    )

    generator = InvoiceTallyXMLGenerator()
    xml_str = generator.generate_xml(snapshot)

    assert "<ENVELOPE>" in xml_str
    assert '<VOUCHER' in xml_str
    assert 'VCHTYPE="Sales"' in xml_str
    assert '<AMOUNT>14285.60</AMOUNT>' in xml_str  # Sales inventory positive
    assert '<AMOUNT>-20000.00</AMOUNT>' in xml_str # Customer negative debit
    assert '<AMOUNT>2857.12</AMOUNT>' in xml_str   # CGST/SGST positive credit

    is_valid, errors = validate_invoice_tally_xml(xml_str)
    assert is_valid is True, f"XML validation failed with errors: {errors}"

def test_critical_xml_parity():
    """
    CRITICAL XML PARITY TEST (PRD Section 40):
    Extracted/reviewed data must exactly match the final XML.
    Values verified:
    Invoice Number, Date, Party, Item Name, HSN, Quantity, Rate,
    Taxable Amount, CGST, SGST, IGST, Grand Total.
    """
    item = InvoiceItem(
        item_name="PARITY TEST BEVERAGE 500ML",
        hsn_sac="22029920",
        quantity=Decimal("15.000"),
        uom="case",
        rate=Decimal("300.00"),
        taxable_amount=Decimal("4500.00"),
        cgst_rate=Decimal("9.00"),
        cgst_amount=Decimal("405.00"),
        sgst_rate=Decimal("9.00"),
        sgst_amount=Decimal("405.00"),
        total_amount=Decimal("5310.00")
    )

    doc = InvoiceDocument(
        invoice_type="PURCHASE",
        invoice_number="INV-PARITY-999",
        invoice_date=date(2026, 6, 15),
        supplier=PartyInfo(name="PARITY SUPPLIER ENTERPRISE", gstin="02AAACW5680K1Z7", state="Himachal Pradesh"),
        buyer=PartyInfo(name="Kartar Singh & Sons", gstin="02AWLPK8092M1Z0", state="Himachal Pradesh"),
        items=[item],
        taxable_total=Decimal("4500.00"),
        cgst_total=Decimal("405.00"),
        sgst_total=Decimal("405.00"),
        grand_total=Decimal("5310.00")
    )

    snapshot = FinalInvoiceSnapshot(invoices=[doc])
    generator = InvoiceTallyXMLGenerator()
    xml_str = generator.generate_xml(snapshot)

    # Verify exact parity
    assert f"<VOUCHERNUMBER>{doc.invoice_number}</VOUCHERNUMBER>" in xml_str
    assert f"<DATE>{doc.invoice_date.strftime('%Y%m%d')}</DATE>" in xml_str
    assert f"<PARTYNAME>{doc.supplier.name}</PARTYNAME>" in xml_str
    assert f"<STOCKITEMNAME>{item.item_name}</STOCKITEMNAME>" in xml_str
    assert f"<GSTHSNNAME>{item.hsn_sac}</GSTHSNNAME>" in xml_str
    assert f"{item.quantity:.3f}" in xml_str
    assert f"{item.rate:.2f}" in xml_str
    assert f"-{item.taxable_amount:.2f}" in xml_str
    assert f"-{item.cgst_amount:.2f}" in xml_str
    assert f"-{item.sgst_amount:.2f}" in xml_str
    assert f"{doc.grand_total:.2f}" in xml_str

def test_api_endpoints_workflow():
    from fastapi.testclient import TestClient
    from main import app
    from app.core.security import get_current_user, CurrentUser

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="test_workflow_user",
        email="workflow@test.com",
        role="USER",
        is_unlimited=True
    )

    try:
        client = TestClient(app)

        # 1. Upload
        pdf_bytes = create_sample_purchase_pdf()
        files = {"files": ("test_purchase.pdf", pdf_bytes, "application/pdf")}
        resp = client.post("/api/invoices/upload", files=files, data={"default_invoice_type": "PURCHASE"})
        assert resp.status_code == 200
        data = resp.json()
        assert "invoices" in data
        assert len(data["invoices"]) == 1
        inv = data["invoices"][0]
        assert inv["invoice_number"] == "NPDTI2627-000789"
        assert inv["invoice_type"] == "PURCHASE"

        # 2. Validate
        snapshot_payload = {
            "invoices": data["invoices"],
            "ledger_mapping": data["ledger_mapping"],
            "auto_create_items": True,
            "auto_create_parties": True
        }
        val_resp = client.post("/api/invoices/validate", json=snapshot_payload)
        assert val_resp.status_code == 200
        val_data = val_resp.json()
        assert val_data["summary"]["total_documents"] == 1

        # 3. Generate XML
        gen_resp = client.post("/api/invoices/generate-xml", json=snapshot_payload)
        assert gen_resp.status_code == 200
        gen_data = gen_resp.json()
        assert gen_data["is_valid"] is True
        assert "<ENVELOPE>" in gen_data["xml_content"]
        assert "Purchase_INV_NPDTI2627-000789.xml" in gen_data["filename"]

        # 4. Download XML
        down_resp = client.post("/api/invoices/download-xml", json=snapshot_payload)
        assert down_resp.status_code == 200
        assert down_resp.headers["content-type"] == "application/xml"
        assert "<ENVELOPE>" in down_resp.text
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# -------------------------------------------------------------
# PRD SECTION 66 SPECIFIC REGRESSION TESTS (Tests 1 to 15)
# -------------------------------------------------------------

def test_regression_test_1_and_9_seller_buyer_roles_never_swapped():
    """Test 1 & 9: Seller GSTIN and Buyer GSTIN must never be swapped; correct supplier/customer selected."""
    pdf_bytes = create_sample_purchase_pdf()
    ext = InvoiceExtractor()
    docs = ext.extract_from_file(pdf_bytes, "purchase.pdf", type_hint="PURCHASE")
    assert len(docs) == 1
    doc = docs[0]

    # In Purchase: Supplier is Wave Beverages (02AAACW5680K1Z7), Buyer is Kartar Singh & Sons (02AWLPK8092M1Z0)
    assert doc.supplier.gstin == "02AAACW5680K1Z7"
    assert doc.buyer.gstin == "02AWLPK8092M1Z0"
    assert "WAVE BEVERAGES" in doc.supplier.name
    assert "Kartar Singh" in doc.buyer.name


def test_regression_test_2_invoice_number_extraction():
    """Test 2: Invoice number must be correctly extracted without confusion."""
    pdf_bytes = create_sample_sales_pdf()
    ext = InvoiceExtractor()
    docs = ext.extract_from_file(pdf_bytes, "sales.pdf", type_hint="SALES")
    assert len(docs) == 1
    doc = docs[0]
    assert doc.invoice_number == "GST-14343"


def test_regression_test_3_4_5_6_items_hsn_qty_rate_preservation():
    """Test 3, 4, 5, 6: Items must not be mixed together; HSN, Qty, Rate must remain attached to correct item."""
    pdf_bytes = create_sample_purchase_pdf()
    ext = InvoiceExtractor()
    docs = ext.extract_from_file(pdf_bytes, "purchase.pdf")
    doc = docs[0]

    assert len(doc.items) == 2
    item1 = doc.items[0]
    item2 = doc.items[1]

    # Item 1 checks: numbers in product name preserved, HSN/Qty/Rate correct
    assert "MIX FRUIT" in item1.item_name
    assert "850 ML" in item1.item_name  # Numbers in product name must be preserved!
    assert item1.hsn_sac == "22029920"
    assert item1.quantity == Decimal("3.00")
    assert item1.rate == Decimal("480.00")
    assert item1.taxable_amount == Decimal("1440.00")

    # Item 2 checks
    assert "COKE" in item2.item_name
    assert "740 ML" in item2.item_name
    assert item2.hsn_sac == "22021010"
    assert item2.quantity == Decimal("25.00")
    assert item2.rate == Decimal("468.06")
    assert item2.taxable_amount == Decimal("11701.50")


def test_regression_test_7_and_8_gst_preservation_cgst_sgst_vs_igst():
    """Test 7 & 8: CGST/SGST must not become IGST, and IGST must not become CGST/SGST."""
    # 1. Purchase invoice has CGST + SGST (intra-state Himachal Pradesh)
    p_bytes = create_sample_purchase_pdf()
    ext = InvoiceExtractor()
    p_docs = ext.extract_from_file(p_bytes, "purchase.pdf")
    p_doc = p_docs[0]
    assert p_doc.cgst_total > Decimal("0.00")
    assert p_doc.sgst_total > Decimal("0.00")
    assert p_doc.igst_total == Decimal("0.00")

    # 2. Sales invoice has IGST (inter-state HP to Punjab)
    s_bytes = create_sample_sales_pdf()
    s_docs = ext.extract_from_file(s_bytes, "sales.pdf")
    s_doc = s_docs[0]
    assert s_doc.igst_total > Decimal("0.00")
    assert s_doc.cgst_total == Decimal("0.00")
    assert s_doc.sgst_total == Decimal("0.00")


def test_regression_test_10_11_12_13_mapping_and_small_differences():
    """Test 10, 11, 12, 13: Matching priority, small spelling differences mapped, low-confidence shown."""
    from app.accounting.stock_item_importer import global_stock_item_store, ImportedStockItem
    from app.accounting.ledger_importer import global_ledger_store, ImportedLedger

    # Add existing Tally stock item
    global_stock_item_store.add_items("test_session", [
        ImportedStockItem(
            name="SAMSUNG LED TV 43 INCH",
            normalized_name="SAMSUNG LED TV 43 INCH",
            base_units="NOS",
            hsn_code="8528"
        ),
        ImportedStockItem(
            name="TATA SALT 1 KG",
            normalized_name="TATA SALT 1 KG",
            base_units="PKT",
            hsn_code="2501"
        )
    ])

    # Add existing Tally ledger
    global_ledger_store.add_ledgers(
        user_id="test_session",
        ledgers=[
            ImportedLedger(
                name="ABC Traders Pvt. Ltd.",
                normalized_name="ABC TRADERS PVT. LTD.",
                group="Sundry Creditors",
                party_gstin="02AAACW5680K1Z7",
                state="Himachal Pradesh"
            )
        ]
    )

    # 1. Test Stock Item match with small case/symbol difference
    match_salt = global_stock_item_store.match_item("test_session", "Tata Salt 1Kg", "2501")
    assert match_salt.confidence in ("HIGH", "MEDIUM")
    assert match_salt.matched_stock_item is not None
    assert match_salt.matched_stock_item.name == "TATA SALT 1 KG"

    # 2. Test Ledger match by GSTIN
    match_ledger = global_ledger_store.match_ledger(
        user_id="test_session",
        query_name="ABC TRADERS",
        gstin="02AAACW5680K1Z7"
    )
    assert match_ledger["confidence"] == "HIGH"
    assert match_ledger["matched_ledger_name"] == "ABC Traders Pvt. Ltd."

    # 3. Test completely unknown item triggers NEW_ITEM / UNMATCHED without silent wrong map
    match_unknown = global_stock_item_store.match_item("test_session", "Completely Unknown Gadget X900")
    assert match_unknown.matched_stock_item is None
    assert match_unknown.confidence in ("LOW", "UNMATCHED")


def test_regression_test_15_multipage_pdf_remains_one_invoice():
    """Test 15: Multi-page invoice must remain one invoice document."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    # Page 1
    c.drawString(100, 750, "TAX INVOICE")
    c.drawString(100, 730, "SUPPLIER CO")
    c.drawString(100, 715, "GSTIN: 02AAAAA0000A1Z5")
    c.drawString(100, 700, "Invoice No: MULTI-001")
    c.drawString(100, 685, "Date: 15-08-2026")
    c.drawString(50, 600, "Item Description")
    c.drawString(250, 600, "HSN")
    c.drawString(320, 600, "Qty")
    c.drawString(380, 600, "Rate")
    c.drawString(450, 600, "Taxable Amount")
    c.drawString(50, 570, "ITEM PAGE ONE")
    c.drawString(250, 570, "11112222")
    c.drawString(320, 570, "10 pcs")
    c.drawString(380, 570, "100.00")
    c.drawString(450, 570, "1000.00")
    c.showPage()
    # Page 2 (Remaining items + totals)
    c.drawString(50, 700, "ITEM PAGE TWO")
    c.drawString(250, 700, "33334444")
    c.drawString(320, 700, "5 pcs")
    c.drawString(380, 700, "200.00")
    c.drawString(450, 700, "1000.00")
    c.drawString(350, 600, "Taxable Value: 2000.00")
    c.drawString(350, 580, "CGST (9%): 180.00")
    c.drawString(350, 560, "SGST (9%): 180.00")
    c.drawString(350, 540, "Grand Total: 2360.00")
    c.save()

    ext = InvoiceExtractor()
    docs = ext.extract_from_file(buf.getvalue(), "multipage_inv.pdf")
    assert len(docs) == 1, "Multi-page invoice must remain ONE invoice, not split!"
    assert docs[0].invoice_number == "MULTI-001"

