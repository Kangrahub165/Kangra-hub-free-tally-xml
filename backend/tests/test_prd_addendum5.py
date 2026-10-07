"""
Unit & Integration Tests for PRD Addendum 5:
1. Smart Create Master Form & Stock Group Extraction
2. Isolated Per-Line GST Resolution (No Rate Carryover Bug)
3. Complete Stock Item XML Schema Conformance (Golden Sample)
4. One-File Import (Vouchers + Masters in Single XML)
"""

import pytest
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal
from app.accounting.stock_item_importer import (
    parse_xml_stock_items,
    GlobalStockItemStore,
    global_stock_item_store,
    ImportedStockItem
)
from app.invoices.model import (
    InvoiceDocument,
    InvoiceItem,
    PartyInfo,
    LedgerMappingConfig,
    FinalInvoiceSnapshot
)
from app.invoices.xml_generator import InvoiceTallyXMLGenerator
from app.invoices.extractor import InvoiceExtractor, OCRLine


def test_addendum5_isolated_gst_resolution_no_carryover():
    """
    Problem 2: A bill with 3 items at 18%, 2 items at 5%, and 1 item at 0%
    must keep strictly isolated rates. No rate may spread or carryover to subsequent rows.
    """
    ext = InvoiceExtractor()
    supplier = PartyInfo(name="ABC FMCG Dist", gstin="02AAACW5680K1Z7", state="Himachal Pradesh")
    buyer = PartyInfo(name="Kartar Singh & Sons", gstin="02AWLPK8092M1Z0", state="Himachal Pradesh")

    ocr_lines = [
        OCRLine("TAX INVOICE", [[50, 20], [200, 20], [200, 35], [50, 35]]),
        # Table Header
        OCRLine("Sr Description HSN Qty Unit Rate Taxable GST% Total", [[50, 60], [600, 60], [600, 75], [50, 75]]),
        # 3 items at 18%
        OCRLine("1 Soap A 3401 10 PCS 100.00 1000.00 18% 1180.00", [[50, 90], [600, 90], [600, 105], [50, 105]]),
        OCRLine("2 Soap B 3401 10 PCS 100.00 1000.00 18% 1180.00", [[50, 110], [600, 110], [600, 125], [50, 125]]),
        OCRLine("3 Soap C 3401 10 PCS 100.00 1000.00 18% 1180.00", [[50, 130], [600, 130], [600, 145], [50, 145]]),
        # 2 items at 5%
        OCRLine("4 Oil D 1512 10 PCS 100.00 1000.00 5% 1050.00", [[50, 150], [600, 150], [600, 165], [50, 165]]),
        OCRLine("5 Oil E 1512 10 PCS 100.00 1000.00 5% 1050.00", [[50, 170], [600, 170], [600, 185], [50, 185]]),
        # 1 item at 0%
        OCRLine("6 Wheat F 1001 10 PCS 100.00 1000.00 0% 1000.00", [[50, 190], [600, 190], [600, 205], [50, 205]]),
        # Totals: 3*1000 + 2*1000 + 1*1000 = 6000 taxable. Tax: 3*180 + 2*50 + 0 = 640 (CGST 320, SGST 320)
        OCRLine("Taxable Total: 6000.00", [[50, 230], [400, 230], [400, 245], [50, 245]]),
        OCRLine("CGST: 320.00 SGST: 320.00", [[50, 250], [400, 250], [400, 265], [50, 265]]),
        OCRLine("Grand Total: 6640.00", [[50, 270], [400, 270], [400, 285], [50, 285]]),
    ]
    full_text = "\n".join(l.text for l in ocr_lines)

    items, totals, count, note = ext._extract_items_and_totals(
        ocr_lines=ocr_lines,
        full_text=full_text,
        supplier=supplier,
        buyer=buyer,
        inv_date=date(2026, 4, 1)
    )

    # 1. Verify item rates are strictly isolated
    eighteen_items = [it for it in items if it.cgst_rate == Decimal("9.00") and it.sgst_rate == Decimal("9.00")]
    five_items = [it for it in items if it.cgst_rate == Decimal("2.50") and it.sgst_rate == Decimal("2.50")]
    zero_items = [it for it in items if it.cgst_rate == Decimal("0.00") and it.sgst_rate == Decimal("0.00")]

    assert len(eighteen_items) == 3, f"Expected 3 items at 18%, got {len(eighteen_items)}"
    assert len(five_items) == 2, f"Expected 2 items at 5%, got {len(five_items)}"
    assert len(zero_items) == 1, f"Expected 1 item at 0%, got {len(zero_items)}"

    # 2. Verify slab summary verification box data
    assert "slab_summary" in totals
    slabs = {s["rate_label"]: s for s in totals["slab_summary"]["slabs"]}
    assert "18.0%" in slabs
    assert slabs["18.0%"]["item_count"] == 3
    assert slabs["18.0%"]["taxable_amount"] == 3000.0
    assert slabs["18.0%"]["total_tax"] == 540.0

    assert "5.0%" in slabs
    assert slabs["5.0%"]["item_count"] == 2
    assert slabs["5.0%"]["taxable_amount"] == 2000.0
    assert slabs["5.0%"]["total_tax"] == 100.0

    assert "0.0%" in slabs
    assert slabs["0.0%"]["item_count"] == 1
    assert slabs["0.0%"]["taxable_amount"] == 1000.0
    assert slabs["0.0%"]["total_tax"] == 0.0

    assert totals["slab_summary"]["is_verified"] is True


def test_addendum5_stock_item_importer_groups_and_rates():
    """
    Problem 1 & 3: Test parsing of Tally XML sample to extract Stock Groups,
    HSN codes, and GST rates properly.
    """
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<ENVELOPE>
  <BODY>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <STOCKITEM NAME="PARLE-G 50G" RESERVEDNAME="">
          <PARENT>Biscuits</PARENT>
          <BASEUNITS>PCS</BASEUNITS>
          <ADDITIONALUNITS>BOX</ADDITIONALUNITS>
          <CONVERSION>24</CONVERSION>
          <GSTTYPEOFSUPPLY>Goods</GSTTYPEOFSUPPLY>
          <GSTRATEDETAILS.LIST>
            <GSTRATE> 18</GSTRATE>
          </GSTRATEDETAILS.LIST>
          <HSNDETAILS.LIST>
            <HSNCODE>19053100</HSNCODE>
            <HSN>Biscuits</HSN>
          </HSNDETAILS.LIST>
        </STOCKITEM>
        <STOCKITEM NAME="FORTUNE OIL 1L" RESERVEDNAME="">
          <PARENT>Edible Oils</PARENT>
          <BASEUNITS>LTR</BASEUNITS>
          <GSTTYPEOFSUPPLY>Goods</GSTTYPEOFSUPPLY>
          <GSTRATEDETAILS.LIST>
            <GSTRATE> 5</GSTRATE>
          </GSTRATEDETAILS.LIST>
          <HSNDETAILS.LIST>
            <HSNCODE>15121910</HSNCODE>
          </HSNDETAILS.LIST>
        </STOCKITEM>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>
    """
    items, duplicates, conflicts = parse_xml_stock_items(xml_content)
    assert len(items) == 2

    parle = items[0]
    assert parle.name == "PARLE-G 50G"
    assert parle.parent == "Biscuits"
    assert parle.base_units == "PCS"
    assert parle.additional_units == "BOX"
    assert parle.hsn_code == "19053100"
    assert parle.gst_rate == Decimal("18")

    oil = items[1]
    assert oil.name == "FORTUNE OIL 1L"
    assert oil.parent == "Edible Oils"
    assert oil.gst_rate == Decimal("5")
    assert oil.hsn_code == "15121910"

    # Test GlobalStockItemStore groups
    store = GlobalStockItemStore()
    store.add_items("test_user", items)
    groups = [g["name"] for g in store.get_stock_groups("test_user")]
    assert "Primary" in groups
    assert "Biscuits" in groups
    assert "Edible Oils" in groups


def test_addendum5_golden_sample_stock_item_xml_structure():
    """
    Problem 3: Test that generated Stock Item XML strictly matches the golden sample:
    - <STATENAME>&#4; Any</STATENAME>
    - <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
    - <SRCOFGSTDETAILS>
    - <HSNDETAILS.LIST> with <HSNCODE>
    - <OPENINGBALANCE>0</OPENINGBALANCE>
    """
    xml_str = global_stock_item_store.generate_new_stock_item_xml(
        name="Amul Butter 500g",
        hsn="04051000",
        uom="PCS",
        parent_group="Dairy Products",
        gst_rate=Decimal("12.0"),
        taxability="Taxable",
        type_of_supply="Goods",
        additional_units="CTN",
        conversion=Decimal("20.0")
    )

    assert "<STATENAME>&#4; Any</STATENAME>" in xml_str
    assert "<GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>" in xml_str
    assert "<SRCOFGSTDETAILS>Specify Details Here</SRCOFGSTDETAILS>" in xml_str
    assert "<HSNDETAILS.LIST>" in xml_str
    assert "<HSNCODE>04051000</HSNCODE>" in xml_str
    assert "<PARENT>Dairy Products</PARENT>" in xml_str
    assert "<BASEUNITS>PCS</BASEUNITS>" in xml_str
    assert "<ADDITIONALUNITS>CTN</ADDITIONALUNITS>" in xml_str
    assert "<OPENINGBALANCE>0</OPENINGBALANCE>" in xml_str
    assert "<GSTRATE> 6.00</GSTRATE>" in xml_str
    assert "<GSTRATE> 12.0</GSTRATE>" in xml_str


def test_addendum5_one_file_import_masters_and_vouchers():
    """
    Problem 4: Test that a single XML file contains both missing masters
    (<UNIT>, <STOCKGROUP>, <LEDGER>, <STOCKITEM>) and vouchers (<VOUCHER>).
    """
    inv = InvoiceDocument(
        invoice_number="INV-2026-001",
        invoice_date="2026-10-07",
        voucher_type="Purchase",
        invoice_type="PURCHASE",
        is_purchase=True,
        supplier=PartyInfo(
            name="ABC Suppliers Ltd",
            gstin="02ABCDE1234F1Z5",
            state="Himachal Pradesh",
            requires_ledger_creation=True
        ),
        buyer=PartyInfo(
            name="Kangra Hub Store",
            gstin="02XYZDE1234F1Z9",
            state="Himachal Pradesh"
        ),
        taxable_total=Decimal("1000.00"),
        cgst_total=Decimal("90.00"),
        sgst_total=Decimal("90.00"),
        grand_total=Decimal("1180.00"),
        items=[
            InvoiceItem(
                item_name="Special Organic Honey 500g",
                description="Special Organic Honey 500g",
                quantity=Decimal("10.00"),
                uom="JAR",
                rate=Decimal("100.00"),
                taxable_amount=Decimal("1000.00"),
                cgst_rate=Decimal("9.00"),
                sgst_rate=Decimal("9.00"),
                cgst_amount=Decimal("90.00"),
                sgst_amount=Decimal("90.00"),
                total_amount=Decimal("1180.00"),
                gst_rate=Decimal("18.00"),
                hsn_sac="04090000",
                parent_group="Organic Grocery",
                requires_item_creation=True
            )
        ]
    )

    mapping = LedgerMappingConfig(
        purchase_ledger="Purchase Local",
        sales_ledger="Sales Local",
        cgst_ledger="CGST Input",
        sgst_ledger="SGST Input",
        igst_ledger="IGST Input",
        cess_ledger="Cess Input",
        round_off_ledger="Round Off"
    )

    snapshot = FinalInvoiceSnapshot(
        invoices=[inv],
        ledger_mapping=mapping,
        auto_create_items=True,
        auto_create_parties=True
    )
    generator = InvoiceTallyXMLGenerator()
    xml_output = generator.generate_xml(snapshot)

    # 1. Verify single file contains both masters and vouchers
    assert "<UNIT NAME=\"JAR\"" in xml_output or "<NAME>JAR</NAME>" in xml_output
    assert "<STOCKGROUP NAME=\"Organic Grocery\"" in xml_output
    assert "<STOCKITEM NAME=\"Special Organic Honey 500g\"" in xml_output
    assert 'VCHTYPE="Purchase"' in xml_output
    assert "<VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>" in xml_output

    # 2. Verify complete stock item schema inside the one-file export
    assert "<STATENAME>&#4; Any</STATENAME>" in xml_output
    assert "<GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>" in xml_output
    assert "<SRCOFGSTDETAILS>Specify Details Here</SRCOFGSTDETAILS>" in xml_output
    assert "<HSNDETAILS.LIST>" in xml_output
    assert "<HSNCODE>04090000</HSNCODE>" in xml_output
    assert "<PARENT>Organic Grocery</PARENT>" in xml_output
