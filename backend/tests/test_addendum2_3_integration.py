import pytest
from decimal import Decimal as D
from datetime import date
import xml.etree.ElementTree as ET

from app.invoices.model import (
    InvoiceDocument,
    FinalInvoiceSnapshot,
    LedgerMappingConfig,
    InvoiceItem,
    PartyInfo
)
from app.invoices.table_engine import (
    choose_gst_rate,
    stock_item_action,
    split_tax,
    spread_paise,
    reconcile,
    row_report,
    build_rate_details,
    rate_details_xml,
    find_duplicate_duty_heads,
    resolve_gst_rate,
    allowed_rates
)
from app.invoices.xml_generator import InvoiceTallyXMLGenerator, is_intra_state
from app.invoices.xml_validator import validate_invoice_tally_xml

# =====================================================================
# 1. Addendum 2 Tests: Duty Head Uniqueness & Guard X02
# =====================================================================

def test_addendum2_reproduce_bug_and_guard_x02():
    """
    Reproduces the exact defect from AT1 & AT6:
    When a shared list of duty heads is reused across items, Guard X02 catches it.
    When build_rate_details is called with fresh dict per item, Guard X02 passes.
    """
    def voucher_envelope(items_xml: str) -> str:
        return (
            '<ENVELOPE><BODY><IMPORTDATA><REQUESTDATA><TALLYMESSAGE><VOUCHER>'
            '<VOUCHERNUMBER>CYCLE/26-27/63</VOUCHERNUMBER>'
            f'{items_xml}'
            '</VOUCHER></TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>'
        )

    # Defect: Reusing a shared list across items
    shared = []
    def buggy_item(name: str, rate: D) -> str:
        for h, r in build_rate_details(rate, True):
            shared.append((h, r))
        return (
            '<ALLINVENTORYENTRIES.LIST>'
            f'<STOCKITEMNAME>{name}</STOCKITEMNAME>'
            f'{"".join(rate_details_xml(shared))}'
            '</ALLINVENTORYENTRIES.LIST>'
        )

    bad_xml = voucher_envelope(buggy_item("Shampoo", D(18)) + buggy_item("Soap", D(5)))
    probs = find_duplicate_duty_heads(bad_xml)
    assert len(probs) > 0
    assert probs[0]["head"] == "CGST"
    assert probs[0]["item"] == "Soap"
    assert probs[0]["voucher"] == "CYCLE/26-27/63"

    # Fix: Fresh dict per item via build_rate_details
    def good_item(name: str, rate: D, intra: bool) -> str:
        pairs = build_rate_details(rate, intra)
        return (
            '<ALLINVENTORYENTRIES.LIST>'
            f'<STOCKITEMNAME>{name}</STOCKITEMNAME>'
            f'{"".join(rate_details_xml(pairs))}'
            '</ALLINVENTORYENTRIES.LIST>'
        )

    clean_xml = voucher_envelope(
        good_item("Shampoo", D(18), True) +
        good_item("Soap", D(5), True) +
        good_item("Oil", D(18), False)
    )
    clean_probs = find_duplicate_duty_heads(clean_xml)
    assert clean_probs == []

def test_addendum2_build_rate_details_intra_and_inter():
    """Verifies that intra-state splits into CGST + SGST, and inter-state into IGST."""
    intra_pairs = build_rate_details(D("5.00"), intra_state=True)
    assert intra_pairs == [("CGST", D("2.50")), ("SGST/UTGST", D("2.50"))]

    inter_pairs = build_rate_details(D("18.00"), intra_state=False)
    assert inter_pairs == [("IGST", D("18.00"))]

    # With cess
    cess_pairs = build_rate_details(D("28.00"), intra_state=True, cess_rate=D("12.00"))
    assert cess_pairs == [("CGST", D("14.00")), ("SGST/UTGST", D("14.00")), ("Cess", D("12.00"))]

# =====================================================================
# 2. Addendum 3 Tests: GST Rate Selection & Reconciliation
# =====================================================================

def test_addendum3_choose_gst_rate_reported_case():
    """
    Test reported bug in AB1/AB9:
    Bill says CGST 2.5% + SGST 2.5%.
    Master in Tally has 18%.
    choose_gst_rate must pick 5%, source 'bill:cgst+sgst', flag 'master_rate_differs'.
    Never 18%.
    """
    A = allowed_rates(date(2026, 5, 9))
    bill = resolve_gst_rate({
        "cgst_rate": D("2.5"), "sgst_rate": D("2.5"),
        "amount": D(1000), "cgst_amt": D(25), "sgst_amt": D(25)
    }, A)

    pick = choose_gst_rate(bill, master=D(18))
    assert pick["rate"] == D(5)
    assert pick["source"] == "bill:cgst+sgst"
    assert "master_rate_differs" in pick["flags"]

    # Stock item action
    act = stock_item_action(True, D(18), D(5))
    assert act == "use_existing_item_override_rate_in_voucher_and_flag"

    act_new = stock_item_action(False, None, D(5))
    assert act_new == "create_item_with_bill_rate"

def test_addendum3_never_defaults_to_18_when_missing():
    """When rate is completely missing on the bill, it must NEVER default to 18%."""
    none_bill = (None, "unresolved", True)
    res = choose_gst_rate(none_bill)
    assert res["rate"] is None
    assert res["source"] == "none"
    assert "rate_missing" in res["flags"]

    # If master has 12%, it can only be a suggestion
    res_master = choose_gst_rate(none_bill, master=D(12))
    assert res_master["rate"] == D(12)
    assert res_master["source"] == "master"
    assert "suggested_not_on_bill" in res_master["flags"]

def test_addendum3_reconcile_and_spread_paise():
    """
    Tests bill-total reconciliation (AB6, AB9):
    - Matching totals pass (OK).
    - 18% forced on 5% line causes diff of ₹130 and BLOCKS export.
    - Small paise rounding auto-applies round off.
    - spread_paise adjusts tax rounding drift to last line.
    """
    # 1. 5% line + 18% line, printed total 3410.00
    good = [{"taxable": D(1000), "tax": D(50)}, {"taxable": D(2000), "tax": D(360)}]
    assert reconcile(good, D("3410.00"))["status"] == "OK"

    # 2. 18% forced on 5% line: taxable 1000 * 18% = 180, total 3540 vs bill 3410
    wrong = [{"taxable": D(1000), "tax": D(180)}, {"taxable": D(2000), "tax": D(360)}]
    res = reconcile(wrong, D("3410.00"))
    assert res["status"] == "BLOCK"
    assert res["diff"] == D("-130.00")

    # 3. Bill rounds grand total to whole rupee: diff of 39 paise
    paise_lines = [{"taxable": D("1000.37"), "tax": D("50.02")}, {"taxable": D(2000), "tax": D(360)}]
    rec_paise = reconcile(paise_lines, D("3410.00"))
    assert rec_paise["status"] == "AUTO_ROUND_OFF"
    assert rec_paise["round_off_ledger"] == D("-0.39")

    # 4. spread_paise
    tax_lines = [{"tax": D("50.01")}, {"tax": D("49.98")}]  # sum = 99.99
    printed_tax = D("100.00")  # 1 paisa drift
    delta = spread_paise(tax_lines, printed_tax)
    assert delta == D("0.01")
    assert tax_lines[-1]["tax"] == D("49.99")
    assert sum(l["tax"] for l in tax_lines) == D("100.00")

# =====================================================================
# 3. End-to-End Voucher XML Generation & Safety Validation
# =====================================================================

def test_full_invoice_xml_generation_with_addendum2_and_3():
    """
    Tests end-to-end XML generation for a Purchase voucher with mixed rates:
    - Item 1: 5% (CGST 2.5% + SGST 2.5%)
    - Item 2: 18% (CGST 9% + SGST 9%)
    - Validates no duplicate duty heads (Guard X02)
    - Validates complete pre-export safety checks (Guards X01-X12)
    """
    item1 = InvoiceItem(
        item_name="Dettol Soap 75g",
        hsn_sac="34011110",
        quantity=D("10.000"),
        uom="NOS",
        rate=D("40.00"),
        taxable_amount=D("400.00"),
        cgst_rate=D("2.50"),
        sgst_rate=D("2.50"),
        cgst_amount=D("10.00"),
        sgst_amount=D("10.00"),
        total_amount=D("420.00")
    )
    item2 = InvoiceItem(
        item_name="Colgate Toothpaste 150g",
        hsn_sac="33061020",
        quantity=D("5.000"),
        uom="NOS",
        rate=D("100.00"),
        taxable_amount=D("500.00"),
        cgst_rate=D("9.00"),
        sgst_rate=D("9.00"),
        cgst_amount=D("45.00"),
        sgst_amount=D("45.00"),
        total_amount=D("590.00")
    )

    doc = InvoiceDocument(
        invoice_number="INV/2026/042",
        invoice_date=date(2026, 4, 15),
        invoice_type="PURCHASE",
        supplier=PartyInfo(
            name="Kartar Traders",
            gstin="02ABCDE1234F1Z5",
            state="Himachal Pradesh"
        ),
        buyer=PartyInfo(
            name="Kartar Singh & Sons",
            gstin="02XYZAB5678C1Z2",
            state="Himachal Pradesh"
        ),
        items=[item1, item2],
        cgst_total=D("55.00"),
        sgst_total=D("55.00"),
        grand_total=D("1010.00"),
        round_off=D("0.00")
    )

    snapshot = FinalInvoiceSnapshot(
        invoices=[doc],
        company_name="Kartar Singh & Sons",
        ledger_mapping=LedgerMappingConfig(
            purchase_ledger="Purchase Account",
            cgst_ledger="Input CGST",
            sgst_ledger="Input SGST",
            round_off_ledger="Round Off"
        )
    )

    generator = InvoiceTallyXMLGenerator()
    xml_str = generator.generate_xml(snapshot)

    # 1. Guard X02 must find 0 duplicate duty heads
    dup_heads = find_duplicate_duty_heads(xml_str)
    assert dup_heads == []

    # 2. Complete validation (Guards X01 - X12)
    is_valid, errors = validate_invoice_tally_xml(xml_str)
    assert is_valid, f"Validation errors: {errors}"
    assert len(errors) == 0

    # 3. Item 1 has 2.50% CGST / SGST (never 18%)
    assert "<GSTRATE> 2.50</GSTRATE>" in xml_str
    # Item 2 has 9.00% CGST / SGST
    assert "<GSTRATE> 9.00</GSTRATE>" in xml_str

def test_reconciliation_difference_exceeding_rupee_blocks_export():
    """
    If the invoice items total differs from the bill total by more than ₹1.00,
    generate_xml must raise a ValueError and block export with clear details.
    """
    item = InvoiceItem(
        item_name="Cycle Tyre",
        quantity=D("1.000"),
        uom="NOS",
        rate=D("1000.00"),
        taxable_amount=D("1000.00"),
        cgst_rate=D("9.00"),
        sgst_rate=D("9.00"),
        cgst_amount=D("90.00"),
        sgst_amount=D("90.00"),
        total_amount=D("1180.00")
    )
    doc = InvoiceDocument(
        invoice_number="INV/ERR/01",
        invoice_date=date(2026, 4, 15),
        invoice_type="PURCHASE",
        supplier=PartyInfo(name="Vendor A", state="Himachal Pradesh"),
        buyer=PartyInfo(name="Kangra Hub", state="Himachal Pradesh"),
        items=[item],
        cgst_total=D("90.00"),
        sgst_total=D("90.00"),
        grand_total=D("1250.00")  # ₹70 difference!
    )
    snapshot = FinalInvoiceSnapshot(invoices=[doc])

    generator = InvoiceTallyXMLGenerator()
    with pytest.raises(ValueError) as excinfo:
        generator.generate_xml(snapshot)

    assert "Bill reconciliation blocked" in str(excinfo.value)
    assert "exceeds ₹1.00 tolerance" in str(excinfo.value)
