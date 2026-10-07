import pytest
from decimal import Decimal
from app.invoices.model import InvoiceDocument, InvoiceItem, PartyInfo, FinalInvoiceSnapshot, LedgerMappingConfig
from app.invoices.state_normalizer import (
    normalize_state,
    get_state_from_gstin,
    resolve_party_state,
    are_states_intra_state,
    TALLY_CANONICAL_STATES
)
from app.invoices.prd_engine import (
    detect_prd_tax_mode,
    apply_prd_tax_inclusive_split,
    reconcile_invoice_document
)
from app.invoices.xml_generator import (
    is_intra_state,
    InvoiceTallyXMLGenerator
)

# ==============================================================================
# PART 1: PLACE OF SUPPLY & STATE NORMALIZATION TESTS (PRD Addendum 1 Part 1)
# ==============================================================================

def test_tally_canonical_states_count():
    """Tally canonical states dictionary must contain all 38 valid states and UTs."""
    assert len(TALLY_CANONICAL_STATES) == 38
    assert TALLY_CANONICAL_STATES["02"] == "Himachal Pradesh"
    assert TALLY_CANONICAL_STATES["03"] == "Punjab"
    assert TALLY_CANONICAL_STATES["07"] == "Delhi"
    assert TALLY_CANONICAL_STATES["01"] == "Jammu & Kashmir"
    assert TALLY_CANONICAL_STATES["38"] == "Ladakh"
    assert TALLY_CANONICAL_STATES["26"] == "Dadra & Nagar Haveli and Daman & Diu"

def test_state_normalizer_aliases():
    """State aliases and noisy OCR text must resolve to canonical full names."""
    # Himachal variations
    assert normalize_state("H.P.") == ("Himachal Pradesh", "02")
    assert normalize_state("HP") == ("Himachal Pradesh", "02")
    assert normalize_state("Himachal") == ("Himachal Pradesh", "02")
    assert normalize_state("02") == ("Himachal Pradesh", "02")
    assert normalize_state("H.P, Code : 02") == ("Himachal Pradesh", "02")
    assert normalize_state("State Name : Himachal Pradesh, Code : 02") == ("Himachal Pradesh", "02")
    assert normalize_state("himachal pradesh") == ("Himachal Pradesh", "02")

    # Punjab & Delhi & UP variations
    assert normalize_state("PB") == ("Punjab", "03")
    assert normalize_state("Punjab") == ("Punjab", "03")
    assert normalize_state("03") == ("Punjab", "03")
    assert normalize_state("DL") == ("Delhi", "07")
    assert normalize_state("New Delhi") == ("Delhi", "07")
    assert normalize_state("UP") == ("Uttar Pradesh", "09")
    assert normalize_state("U.P.") == ("Uttar Pradesh", "09")

    # Jammu & Kashmir (with '&', never 'and')
    assert normalize_state("J&K") == ("Jammu & Kashmir", "01")
    assert normalize_state("JK") == ("Jammu & Kashmir", "01")
    assert normalize_state("Jammu and Kashmir") == ("Jammu & Kashmir", "01")

    # Ladakh
    assert normalize_state("Ladakh") == ("Ladakh", "38")
    assert normalize_state("LA") == ("Ladakh", "38")

def test_state_from_gstin():
    """First two digits of GSTIN reliably identify the state."""
    assert get_state_from_gstin("02AWLPK8092M1Z0") == ("Himachal Pradesh", "02")
    assert get_state_from_gstin("03AABCS1429B1Z1") == ("Punjab", "03")
    assert get_state_from_gstin("07AAAAA0000A1Z5") == ("Delhi", "07")
    assert get_state_from_gstin("99INVALIDGSTIN") == (None, None)
    assert get_state_from_gstin(None) == (None, None)

def test_party_state_resolution_priority_and_conflict():
    """
    Section 1.3: Priority order:
    1. GSTIN first two digits -> wins if conflict with text, produces warning.
    2. Explicit state code NN.
    3. Place of Supply.
    """
    # 1. GSTIN agrees with text
    name, code, warn = resolve_party_state(
        party=PartyInfo(name="ABC Traders", gstin="02AWLPK8092M1Z0", state="H.P.")
    )
    assert name == "Himachal Pradesh"
    assert code == "02"
    assert warn is None

    # 2. GSTIN conflicts with text: GSTIN wins + warning
    name, code, warn = resolve_party_state(
        party=PartyInfo(name="Punjab Trader", gstin="02AWLPK8092M1Z0", state="Punjab (03)")
    )
    assert name == "Himachal Pradesh"
    assert code == "02"
    assert warn is not None
    assert "State mismatch" in warn

    # 3. No GSTIN, but state text available
    name, code, warn = resolve_party_state(
        party=PartyInfo(name="HP Store", gstin="", state="H.P.")
    )
    assert name == "Himachal Pradesh"
    assert code == "02"
    assert warn is None

    # 4. Missing everything -> fallback for company
    name, code, warn = resolve_party_state(
        party=PartyInfo(name="Kartar Singh", gstin=None, state=None),
        is_company=True,
        default_company_state="Himachal Pradesh",
        default_company_code="02"
    )
    assert name == "Himachal Pradesh"
    assert code == "02"

def test_intra_state_vs_inter_state_code_comparison():
    """Section 1.7: State codes are compared (never raw strings)."""
    # Same code -> Intra-state
    assert are_states_intra_state("02", "02") is True
    # Different code -> Inter-state
    assert are_states_intra_state("02", "03") is False
    assert are_states_intra_state("02", "07") is False

    # In InvoiceDocument context:
    inv_intra = InvoiceDocument(
        supplier=PartyInfo(name="Supplier HP", gstin="02AAAAA0000A1Z1", state="Himachal Pradesh"),
        buyer=PartyInfo(name="Buyer HP", gstin="02BBBBB0000B1Z2", state="H.P."),
        place_of_supply="HP"
    )
    assert is_intra_state(inv_intra) is True

    inv_inter = InvoiceDocument(
        supplier=PartyInfo(name="Supplier HP", gstin="02AAAAA0000A1Z1", state="Himachal Pradesh"),
        buyer=PartyInfo(name="Buyer Punjab", gstin="03CCCCC0000C1Z3", state="PB"),
        place_of_supply="03"
    )
    assert is_intra_state(inv_inter) is False


# ==============================================================================
# PART 2: TAX-INCLUSIVE INVOICE DETECTION & SPLIT (PRD Addendum 1 Part 2)
# ==============================================================================

def test_situation_1_exclusive_invoice_with_rate_incl_of_tax_column():
    """
    Section 2.2 Situation 1: Exclusive invoice with informational 'Rate (Incl. of Tax)' column.
    Math: S + T ≈ G -> stays 'exclusive', no tax split applied.
    """
    ocr_text = """
    TAX INVOICE
    Item        Qty   Rate   Rate (Incl. of Tax)   Amount
    Biscuits    10    100    118                  1000.00
    Sub Total                                     1000.00
    CGST 9%                                         90.00
    SGST 9%                                         90.00
    Total                                         1180.00
    """
    items = [
        InvoiceItem(
            item_name="Biscuits",
            quantity=Decimal("10.00"),
            rate=Decimal("100.00"),
            taxable_amount=Decimal("1000.00"),
            total_amount=Decimal("1180.00"),
            gst_rate=Decimal("18.00"),
            cgst_rate=Decimal("9.00"),
            sgst_rate=Decimal("9.00"),
            cgst_amount=Decimal("90.00"),
            sgst_amount=Decimal("90.00")
        )
    ]
    doc = InvoiceDocument(
        taxable_total=Decimal("1000.00"),
        cgst_total=Decimal("90.00"),
        sgst_total=Decimal("90.00"),
        grand_total=Decimal("1180.00"),
        items=items
    )

    detected_mode = detect_prd_tax_mode(doc, full_text=ocr_text)
    assert detected_mode == "exclusive"

    reconciled = reconcile_invoice_document(doc, full_text=ocr_text)
    assert reconciled.tax_mode == "exclusive"
    # Taxable amount remains untouched
    assert reconciled.items[0].taxable_amount == Decimal("1000.00")
    assert reconciled.items[0].rate == Decimal("100.00")

def test_situation_2_truly_inclusive_invoice_split():
    """
    Section 2.2 Situation 2: Truly inclusive invoice.
    Lines sum directly to grand total: S ≈ G (e.g. Item Amount = 1180.00, Grand Total = 1180.00, GST = 180.00).
    Split:
      Taxable = 1180.00 / 1.18 = 1000.00
      GST = 180.00 (CGST 90.00, SGST 90.00)
      Base Rate = 1000.00 / 10 = 100.00
      Total Amount = 1180.00 (unchanged printed line amount)
    """
    ocr_text = """
    RETAIL INVOICE
    (Prices are inclusive of all taxes)
    Item        Qty   Rate     Amount
    Biscuits    10    118.00   1180.00
    Total                      1180.00
    GST Included: ₹180.00 (CGST 9% ₹90, SGST 9% ₹90)
    """
    items = [
        InvoiceItem(
            item_name="Biscuits",
            quantity=Decimal("10.00"),
            rate=Decimal("118.00"),
            taxable_amount=Decimal("1180.00"), # Raw OCR put line amount here
            total_amount=Decimal("1180.00"),
            gst_rate=Decimal("18.00"),
            cgst_rate=Decimal("9.00"),
            sgst_rate=Decimal("9.00")
        )
    ]
    doc = InvoiceDocument(
        taxable_total=Decimal("1180.00"),
        cgst_total=Decimal("90.00"),
        sgst_total=Decimal("90.00"),
        grand_total=Decimal("1180.00"),
        items=items
    )

    detected_mode = detect_prd_tax_mode(doc, full_text=ocr_text)
    assert detected_mode == "inclusive"

    # Split lines
    split_items = apply_prd_tax_inclusive_split(items, is_interstate=False)
    split_item = split_items[0]

    assert split_item.taxable_amount == Decimal("1000.00")
    assert split_item.rate == Decimal("100.00")
    assert split_item.cgst_amount == Decimal("90.00")
    assert split_item.sgst_amount == Decimal("90.00")
    # Section 2.7: Line amount remains equal to printed invoice line amount
    assert split_item.total_amount == Decimal("1180.00")
    assert split_item.is_tax_inclusive is True

    # Full reconciliation passes
    reconciled = reconcile_invoice_document(doc, full_text=ocr_text)
    assert reconciled.tax_mode == "inclusive"
    assert reconciled.taxable_total == Decimal("1000.00")
    assert reconciled.grand_total == Decimal("1180.00")
    assert reconciled.reconciliation_passed is True

def test_situation_2_mixed_slabs_and_zero_tax_free_line():
    """
    Section 2.5: Mixed slabs on inclusive invoice:
    - Line 1: 0% tax-free (Rice 500.00) -> stays un-split (Taxable = 500.00, GST = 0)
    - Line 2: 5% (Oil 105.00) -> Taxable = 100.00, GST = 5.00
    - Line 3: 18% (Soap 118.00) -> Taxable = 100.00, GST = 18.00
    Grand Total = 500 + 105 + 118 = 723.00
    """
    ocr_text = "Inclusive of all taxes\nTotal Amount: 723.00"
    items = [
        InvoiceItem(
            item_name="Rice 10kg",
            quantity=Decimal("1.00"),
            rate=Decimal("500.00"),
            taxable_amount=Decimal("500.00"),
            total_amount=Decimal("500.00"),
            gst_rate=Decimal("0.00"),
            cgst_rate=Decimal("0.00"),
            sgst_rate=Decimal("0.00")
        ),
        InvoiceItem(
            item_name="Cooking Oil 1L",
            quantity=Decimal("1.00"),
            rate=Decimal("105.00"),
            taxable_amount=Decimal("105.00"),
            total_amount=Decimal("105.00"),
            gst_rate=Decimal("5.00"),
            cgst_rate=Decimal("2.50"),
            sgst_rate=Decimal("2.50")
        ),
        InvoiceItem(
            item_name="Soap Bar",
            quantity=Decimal("1.00"),
            rate=Decimal("118.00"),
            taxable_amount=Decimal("118.00"),
            total_amount=Decimal("118.00"),
            gst_rate=Decimal("18.00"),
            cgst_rate=Decimal("9.00"),
            sgst_rate=Decimal("9.00")
        )
    ]
    doc = InvoiceDocument(
        taxable_total=Decimal("723.00"),
        cgst_total=Decimal("11.50"),
        sgst_total=Decimal("11.50"),
        grand_total=Decimal("723.00"),
        items=items
    )

    reconciled = reconcile_invoice_document(doc, full_text=ocr_text)
    assert reconciled.tax_mode == "inclusive"
    assert reconciled.reconciliation_passed is True

    # Check 0% line
    it0 = reconciled.items[0]
    assert it0.taxable_amount == Decimal("500.00")
    assert it0.cgst_amount == Decimal("0.00")
    assert it0.sgst_amount == Decimal("0.00")
    assert it0.total_amount == Decimal("500.00")

    # Check 5% line
    it5 = reconciled.items[1]
    assert it5.taxable_amount == Decimal("100.00")
    assert it5.cgst_amount == Decimal("2.50")
    assert it5.sgst_amount == Decimal("2.50")
    assert it5.total_amount == Decimal("105.00")

    # Check 18% line
    it18 = reconciled.items[2]
    assert it18.taxable_amount == Decimal("100.00")
    assert it18.cgst_amount == Decimal("9.00")
    assert it18.sgst_amount == Decimal("9.00")
    assert it18.total_amount == Decimal("118.00")

    # Total Taxable = 500 + 100 + 100 = 700.00
    assert reconciled.taxable_total == Decimal("700.00")

def test_situation_2_inclusive_invoice_with_discount():
    """
    Section 2.5: Line amount after discount is split into taxable and GST:
    Base Amount = 1180.00, Discount = 118.00 -> Net Line Amount = 1062.00
    Taxable = 1062.00 / 1.18 = 900.00
    GST = 162.00 (CGST 81.00, SGST 81.00)
    """
    ocr_text = "All prices inclusive of taxes"
    items = [
        InvoiceItem(
            item_name="Item with Discount",
            quantity=Decimal("10.00"),
            rate=Decimal("118.00"),
            discount=Decimal("118.00"),
            taxable_amount=Decimal("1180.00"),
            total_amount=Decimal("1062.00"),
            gst_rate=Decimal("18.00"),
            cgst_rate=Decimal("9.00"),
            sgst_rate=Decimal("9.00")
        )
    ]
    doc = InvoiceDocument(
        taxable_total=Decimal("1062.00"),
        cgst_total=Decimal("81.00"),
        sgst_total=Decimal("81.00"),
        grand_total=Decimal("1062.00"),
        items=items
    )

    reconciled = reconcile_invoice_document(doc, full_text=ocr_text)
    assert reconciled.tax_mode == "inclusive"
    split_it = reconciled.items[0]
    assert split_it.taxable_amount == Decimal("900.00")
    assert split_it.cgst_amount == Decimal("81.00")
    assert split_it.sgst_amount == Decimal("81.00")
    assert split_it.total_amount == Decimal("1062.00")
    assert reconciled.reconciliation_passed is True


# ==============================================================================
# PART 3: XML EXPORT NORMALIZATION (PRD Addendum 1 Section 1.2 & 2.6)
# ==============================================================================

def test_xml_contains_canonical_full_state_name_and_never_short_form():
    """
    Section 1.2: PLACEOFSUPPLY, STATENAME, CONSIGNEESTATENAME and Master Ledgers
    must strictly output canonical full state names (e.g. 'Himachal Pradesh'),
    NEVER raw short-forms like 'H.P.' or '02'.
    """
    inv_purchase = InvoiceDocument(
        invoice_number="INV-HP-001",
        invoice_type="PURCHASE",
        supplier=PartyInfo(name="ABC Traders", gstin="02AWLPK8092M1Z0", state="H.P.", requires_ledger_creation=True),
        buyer=PartyInfo(name="Kartar Singh", gstin="02AWLPK8092M1Z0", state="Himachal"),
        place_of_supply="HP",
        taxable_total=Decimal("1000.00"),
        cgst_total=Decimal("90.00"),
        sgst_total=Decimal("90.00"),
        grand_total=Decimal("1180.00"),
        items=[
            InvoiceItem(
                item_name="Item A",
                quantity=Decimal("10.00"),
                rate=Decimal("100.00"),
                taxable_amount=Decimal("1000.00"),
                cgst_rate=Decimal("9.00"),
                sgst_rate=Decimal("9.00"),
                cgst_amount=Decimal("90.00"),
                sgst_amount=Decimal("90.00"),
                total_amount=Decimal("1180.00")
            )
        ]
    )

    inv_sales = InvoiceDocument(
        invoice_number="INV-HP-002",
        invoice_type="SALES",
        supplier=PartyInfo(name="Kartar Singh", gstin="02AWLPK8092M1Z0", state="Himachal Pradesh"),
        buyer=PartyInfo(name="Local Buyer", gstin=None, state="H.P.", requires_ledger_creation=True),
        place_of_supply="HP",
        taxable_total=Decimal("1000.00"),
        cgst_total=Decimal("90.00"),
        sgst_total=Decimal("90.00"),
        grand_total=Decimal("1180.00"),
        items=[
            InvoiceItem(
                item_name="Item B",
                quantity=Decimal("10.00"),
                rate=Decimal("100.00"),
                taxable_amount=Decimal("1000.00"),
                cgst_rate=Decimal("9.00"),
                sgst_rate=Decimal("9.00"),
                cgst_amount=Decimal("90.00"),
                sgst_amount=Decimal("90.00"),
                total_amount=Decimal("1180.00")
            )
        ]
    )

    snapshot = FinalInvoiceSnapshot(
        invoices=[inv_purchase, inv_sales],
        ledger_mapping=LedgerMappingConfig(),
        auto_create_parties=True
    )

    xml_gen = InvoiceTallyXMLGenerator()
    xml_output = xml_gen.generate_xml(snapshot)

    # 1. Full canonical state name present
    assert "<PLACEOFSUPPLY>Himachal Pradesh</PLACEOFSUPPLY>" in xml_output
    assert "<STATENAME>Himachal Pradesh</STATENAME>" in xml_output
    assert "<CONSIGNEESTATENAME>Himachal Pradesh</CONSIGNEESTATENAME>" in xml_output

    # 2. Never short forms inside state tags
    assert "<PLACEOFSUPPLY>H.P.</PLACEOFSUPPLY>" not in xml_output
    assert "<PLACEOFSUPPLY>HP</PLACEOFSUPPLY>" not in xml_output
    assert "<STATENAME>H.P.</STATENAME>" not in xml_output
    assert "<STATENAME>HP</STATENAME>" not in xml_output
    assert "<CONSIGNEESTATENAME>H.P.</CONSIGNEESTATENAME>" not in xml_output
    assert "<CONSIGNEESTATENAME>HP</CONSIGNEESTATENAME>" not in xml_output

    # 3. Party Master also has canonical state
    assert "<LEDSTATENAME>Himachal Pradesh</LEDSTATENAME>" in xml_output

def test_xml_tax_inclusive_invoice_outputs_exclusive_rate_and_amount():
    """
    Section 2.6: Tally XML for tax-inclusive invoices must contain exclusive
    taxable rate and taxable amount in RATE and AMOUNT tags, with separate tax ledgers.
    """
    inv = InvoiceDocument(
        invoice_number="INV-INCL-001",
        invoice_type="SALES",
        supplier=PartyInfo(name="Kartar Singh", gstin="02AWLPK8092M1Z0", state="Himachal Pradesh"),
        buyer=PartyInfo(name="Walk-in Customer", gstin=None, state="Himachal Pradesh"),
        place_of_supply="Himachal Pradesh",
        tax_mode="inclusive",
        taxable_total=Decimal("1000.00"),
        cgst_total=Decimal("90.00"),
        sgst_total=Decimal("90.00"),
        grand_total=Decimal("1180.00"),
        items=[
            InvoiceItem(
                item_name="Biscuits 100g",
                quantity=Decimal("10.00"),
                rate=Decimal("100.00"),          # Exclusive rate
                taxable_amount=Decimal("1000.00"), # Exclusive taxable amount
                cgst_rate=Decimal("9.00"),
                sgst_rate=Decimal("9.00"),
                cgst_amount=Decimal("90.00"),
                sgst_amount=Decimal("90.00"),
                total_amount=Decimal("1180.00"),
                is_tax_inclusive=True
            )
        ]
    )

    snapshot = FinalInvoiceSnapshot(
        invoices=[inv],
        ledger_mapping=LedgerMappingConfig(),
        auto_create_parties=False
    )

    xml_gen = InvoiceTallyXMLGenerator()
    xml_output = xml_gen.generate_xml(snapshot)

    # Line item in inventory entries must be taxable amount (1000.00), not 1180.00
    assert "<RATE>100.00/NOS</RATE>" in xml_output
    assert "<AMOUNT>1000.00</AMOUNT>" in xml_output

    # Separate tax ledger entries must exist for CGST and SGST
    assert "<LEDGERNAME>CGST</LEDGERNAME>" in xml_output
    assert "<AMOUNT>-90.00</AMOUNT>" in xml_output or "<AMOUNT>90.00</AMOUNT>" in xml_output
    assert "<LEDGERNAME>SGST</LEDGERNAME>" in xml_output
