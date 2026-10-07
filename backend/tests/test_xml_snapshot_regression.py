import pytest
import xml.etree.ElementTree as ET
from decimal import Decimal
from datetime import date
from app.invoices.model import (
    InvoiceDocument,
    PartyInfo,
    InvoiceItem,
    FinalInvoiceSnapshot,
    LedgerMappingConfig
)
from app.invoices.xml_generator import InvoiceTallyXMLGenerator

def test_purchase_xml_snapshot():
    doc = InvoiceDocument(
        invoice_type="PURCHASE",
        invoice_number="CYCLE/26-27/63",
        invoice_date=date(2026, 5, 9),
        supplier=PartyInfo(
            name="Pong Vally Traders (2026-2027)",
            matched_ledger_name="PONG VALLY TRADERS",
            gstin="02BULPK7285D1ZL",
            state="Himachal Pradesh"
        ),
        buyer=PartyInfo(
            name="Kartar Singh & Sons",
            gstin="02AWLPK8092M1Z0",
            state="Himachal Pradesh"
        ),
        items=[
            InvoiceItem(
                item_name="DHP AGARBATI",
                matched_stock_item="DHP AGARBATI",
                hsn_sac="33074100",
                quantity=Decimal("24.00"),
                uom="BOX",
                rate=Decimal("177.00"),
                gross_amount=Decimal("4248.00"),
                discount=Decimal("202.32"),
                taxable_amount=Decimal("4045.68"),
                cgst_rate=Decimal("2.50"),
                cgst_amount=Decimal("101.14"),
                sgst_rate=Decimal("2.50"),
                sgst_amount=Decimal("101.14"),
                total_amount=Decimal("4247.96")
            )
        ],
        taxable_total=Decimal("4045.68"),
        cgst_total=Decimal("101.14"),
        sgst_total=Decimal("101.14"),
        grand_total=Decimal("4247.96")
    )
    
    snapshot = FinalInvoiceSnapshot(
        invoices=[doc],
        company_name="Kartar Singh & Sons - (from 1-Apr-25)",
        ledger_mapping=LedgerMappingConfig()
    )
    
    generator = InvoiceTallyXMLGenerator()
    xml_str = generator.generate_xml(snapshot)
    
    # Assert top-level envelope
    assert "<ENVELOPE>" in xml_str
    assert "</ENVELOPE>" in xml_str
    assert "<SVCURRENTCOMPANY>Kartar Singh &amp; Sons - (from 1-Apr-25)</SVCURRENTCOMPANY>" in xml_str
    
    # Parse XML with ElementTree to verify valid XML syntax
    root = ET.fromstring(xml_str)
    assert root.tag == "ENVELOPE"
    
    # Verify voucher contents
    vouchers = root.findall(".//VOUCHER")
    assert len(vouchers) == 1
    vch = vouchers[0]
    assert vch.get("VCHTYPE") == "Purchase"
    
    # Verify voucher date and number
    date_el = vch.find("DATE")
    assert date_el is not None and date_el.text == "20260509"
    vch_no = vch.find("VOUCHERNUMBER")
    assert vch_no is not None and vch_no.text == "CYCLE/26-27/63"
    
    # Verify party ledger entry
    party_ledgers = [e.text for e in vch.findall(".//LEDGERNAME")]
    assert "PONG VALLY TRADERS" in party_ledgers
    assert "PURCHASE GST" in party_ledgers
    assert "CGST" in party_ledgers
    assert "SGST" in party_ledgers
    
    # Verify inventory allocations
    inv_names = [e.text for e in vch.findall(".//STOCKITEMNAME")]
    assert "DHP AGARBATI" in inv_names
    
    # Verify billed qty tag contains quantity and unit
    billed_qtys = [e.text for e in vch.findall(".//BILLEDQTY")]
    assert any("24.000 BOX" in b for b in billed_qtys)

def test_sales_xml_snapshot():
    doc = InvoiceDocument(
        invoice_type="SALES",
        invoice_number="SALE-2026-001",
        invoice_date=date(2026, 6, 15),
        supplier=PartyInfo(
            name="Kartar Singh & Sons",
            gstin="02AWLPK8092M1Z0",
            state="Himachal Pradesh"
        ),
        buyer=PartyInfo(
            name="Customer Punjab",
            matched_ledger_name="CUSTOMER PUNJAB",
            gstin="03AAACP0123M1Z5",
            state="Punjab"
        ),
        items=[
            InvoiceItem(
                item_name="KANGRA TEA 500G",
                matched_stock_item="KANGRA TEA 500G",
                hsn_sac="09024020",
                quantity=Decimal("10.00"),
                uom="PKT",
                rate=Decimal("250.00"),
                taxable_amount=Decimal("2500.00"),
                igst_rate=Decimal("5.00"),
                igst_amount=Decimal("125.00"),
                total_amount=Decimal("2625.00")
            )
        ],
        taxable_total=Decimal("2500.00"),
        igst_total=Decimal("125.00"),
        grand_total=Decimal("2625.00")
    )
    
    snapshot = FinalInvoiceSnapshot(
        invoices=[doc],
        company_name="Kartar Singh & Sons - (from 1-Apr-25)",
        ledger_mapping=LedgerMappingConfig()
    )
    
    generator = InvoiceTallyXMLGenerator()
    xml_str = generator.generate_xml(snapshot)
    
    root = ET.fromstring(xml_str)
    vouchers = root.findall(".//VOUCHER")
    assert len(vouchers) == 1
    vch = vouchers[0]
    assert vch.get("VCHTYPE") == "Sales"
    
    party_ledgers = [e.text for e in vch.findall(".//LEDGERNAME")]
    assert "CUSTOMER PUNJAB" in party_ledgers
    assert "SALE GST" in party_ledgers
    assert "IGST" in party_ledgers
