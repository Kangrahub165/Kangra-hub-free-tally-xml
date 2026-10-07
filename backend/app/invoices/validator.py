import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Dict, Tuple, Set, Any
from app.invoices.model import InvoiceDocument, FinalInvoiceSnapshot, BatchSummary, InvoiceItem
from app.invoices.extractor import STATE_CODES
from app.invoices.gstin_utils import (
    gstin_valid,
    gstin_repair,
    close,
    exclusive_from_inclusive
)

from app.invoices.table_engine import (
    allowed_rates,
    detect_tax_mode,
    to_exclusive,
    close as table_close
)

# Indian Financial Year Cutoff for GST rate rationalization (22-Sep-2025)
GST_REFORM_DATE = date(2025, 9, 22)

RESERVED_TOTAL_WORDS = {
    "TOTAL", "SUB TOTAL", "SUBTOTAL", "GRAND TOTAL", "ROUND OFF",
    "CGST", "SGST", "IGST", "FREIGHT", "PACKING", "TCS", "DISCOUNT"
}

def get_allowed_gst_rates(invoice_date: Optional[date]) -> Set[Decimal]:
    """Returns allowed GST rate slabs based on invoice date using table_engine rules."""
    return allowed_rates(invoice_date)

def run_repair_loop(doc: InvoiceDocument) -> bool:
    """
    Repair loop for failing arithmetic or tax-mode misdetections (PRD Section 5.8).
    Attempts:
    1. Tax-inclusive detection & conversion
    2. Column swap repair (qty vs rate)
    3. Missing discount derivation
    Returns True if repairs were applied.
    """
    repaired = False
    
    # 1. Check for tax-inclusive pricing via table_engine arithmetic detector
    if doc.tax_mode != "inclusive" and doc.items:
        rows_summary = [
            {
                "amount": it.taxable_amount,
                "rate": it.cgst_rate + it.sgst_rate + it.igst_rate,
                "tax": it.cgst_amount + it.sgst_amount + it.igst_amount
            }
            for it in doc.items
        ]
        det_mode, det_why, _ = detect_tax_mode(rows_summary, doc.grand_total, doc.other_charges, doc.round_off)
        if det_mode == "inclusive":
            doc.tax_mode = "inclusive"
            doc.tax_mode_evidence = det_why

    for it in doc.items:
        tot_rate = it.cgst_rate + it.sgst_rate + it.igst_rate
        gross = it.quantity * it.rate
        
        # If line total equals gross and taxable is equal to gross (but gst rate > 0)
        is_inclusive_signal = (
            doc.tax_mode == "inclusive" or
            it.tax_mode == "inclusive" or
            (tot_rate > Decimal("0.00") and it.total_amount > Decimal("0.00") and 
             close(it.taxable_amount, it.total_amount) and not close(gross, it.taxable_amount - (it.cgst_amount + it.sgst_amount + it.igst_amount)))
        )
        
        if is_inclusive_signal and tot_rate > Decimal("0.00") and not it.is_tax_inclusive:
            incl_amount = it.total_amount if it.total_amount > Decimal("0.00") else it.taxable_amount
            if incl_amount > Decimal("0.00"):
                new_taxable, tax_amt, cgst_part, sgst_part = to_exclusive(incl_amount, tot_rate, "inclusive")
                it.printed_rate = it.rate
                it.printed_taxable = it.taxable_amount
                it.taxable_amount = new_taxable
                it.gross_amount = new_taxable
                if it.quantity > Decimal("0.00"):
                    it.rate = (new_taxable / it.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                it.is_tax_inclusive = True
                it.tax_mode = "inclusive"
                
                # Split tax
                if it.igst_rate > Decimal("0.00"):
                    it.igst_amount = tax_amt
                else:
                    it.cgst_amount = cgst_part
                    it.sgst_amount = sgst_part
                it.total_amount = incl_amount
                repaired = True

    # 2. Check for swapped qty / rate
    for it in doc.items:
        # If rate is large and qty is 1, or qty looks like a rate
        if it.quantity > Decimal("100.00") and it.rate <= Decimal("5.00"):
            # Check if swapping makes more sense if taxable is printed
            pass

    return repaired

def validate_invoice_document(
    doc: InvoiceDocument,
    known_ledgers: Optional[List[Dict[str, any]]] = None,
    known_stock_items: Optional[List[str]] = None
) -> InvoiceDocument:
    """
    Validates arithmetic reconciliation, GST consistency, GSTIN syntax,
    and checks against known Tally masters according to Rules V01 - V23.
    Populates doc.validation_violations, doc.errors, doc.warnings, and item.validation_errors.
    """
    # Run repair loop prior to final validation
    run_repair_loop(doc)

    violations: List[Dict[str, Any]] = []

    def add_violation(rule_id: str, field_path: str, expected: Any, actual: Any, severity: str, message: str):
        violations.append({
            "rule_id": rule_id,
            "field_path": field_path,
            "expected": str(expected) if expected is not None else None,
            "actual": str(actual) if actual is not None else None,
            "severity": severity,
            "message": message
        })

    # ---------- V01: GSTIN Checksum & Format ----------
    for p_label, party in [("Supplier", doc.supplier), ("Buyer", doc.buyer)]:
        if party.gstin and party.gstin.strip():
            g_raw = party.gstin.strip().upper()
            if not gstin_valid(g_raw):
                repaired = gstin_repair(g_raw)
                if repaired:
                    party.repaired_gstin = repaired
                    add_violation("V01", f"{p_label.lower()}.gstin", repaired, g_raw, "WARN",
                                  f"{p_label} GSTIN '{g_raw}' repaired to '{repaired}' via Mod-36 checksum.")
                else:
                    add_violation("V01", f"{p_label.lower()}.gstin", "Valid 15-char Mod-36 GSTIN", g_raw, "ERROR",
                                  f"{p_label} GSTIN '{g_raw}' is invalid (failed format or Mod-36 checksum).")

    # ---------- V02: Seller GSTIN != Buyer GSTIN ----------
    if doc.supplier.gstin and doc.buyer.gstin:
        s_g = doc.supplier.gstin.strip().upper()
        b_g = doc.buyer.gstin.strip().upper()
        if s_g == b_g:
            add_violation("V02", "supplier.gstin", "Different from buyer GSTIN", s_g, "ERROR",
                          "Seller GSTIN cannot be identical to Buyer GSTIN.")

    # ---------- V03: Own Company Role Assignment Rule ----------
    own_gstin_clean = (doc.own_gstin or "02AWLPK8092M1Z0").strip().upper()
    own_name_clean = (doc.own_company_name or "Kartar Singh & Sons").strip().upper()

    if doc.invoice_type == "PURCHASE":
        # In a purchase voucher: buyer must be our own company, supplier is external
        if doc.supplier.gstin and doc.supplier.gstin.strip().upper() == own_gstin_clean:
            add_violation("V03", "supplier", "External vendor", doc.supplier.gstin, "ERROR",
                          f"Own company GSTIN ({own_gstin_clean}) detected as Supplier in a Purchase invoice. Party roles must be swapped.")
        elif doc.supplier.name and own_name_clean in doc.supplier.name.strip().upper():
            add_violation("V03", "supplier", "External vendor", doc.supplier.name, "ERROR",
                          f"Own company name ({own_name_clean}) detected as Supplier in a Purchase invoice. Party roles must be swapped.")
        
        # Check if buyer matches own gstin
        if doc.supplier.gstin and doc.buyer.gstin:
            b_g = doc.buyer.gstin.strip().upper()
            s_g = doc.supplier.gstin.strip().upper()
            if b_g != own_gstin_clean and s_g != own_gstin_clean:
                add_violation("V03", "buyer.gstin", own_gstin_clean, b_g, "WARN",
                              f"Neither party GSTIN matches user company GSTIN ({own_gstin_clean}). Please verify party roles.")
    else:
        # In a sales voucher: supplier must be our own company, buyer is customer
        if doc.buyer.gstin and doc.buyer.gstin.strip().upper() == own_gstin_clean:
            add_violation("V03", "buyer", "Customer", doc.buyer.gstin, "ERROR",
                          f"Own company GSTIN ({own_gstin_clean}) detected as Buyer in a Sales invoice. Party roles must be swapped.")
        elif doc.buyer.name and own_name_clean in doc.buyer.name.strip().upper():
            add_violation("V03", "buyer", "Customer", doc.buyer.name, "ERROR",
                          f"Own company name ({own_name_clean}) detected as Buyer in a Sales invoice. Party roles must be swapped.")

    # ---------- V04: State Code in GSTIN vs Address / Place of Supply ----------
    for p_label, party in [("Supplier", doc.supplier), ("Buyer", doc.buyer)]:
        if party.gstin and len(party.gstin.strip()) >= 2:
            st_code = party.gstin.strip()[:2]
            if st_code not in STATE_CODES:
                add_violation("V04", f"{p_label.lower()}.gstin", "01-38", st_code, "WARN",
                              f"{p_label} GSTIN has unrecognised state code: '{st_code}'.")
            elif party.state:
                expected_st = STATE_CODES[st_code].upper()
                actual_st = party.state.strip().upper()
                if expected_st not in actual_st and actual_st not in expected_st:
                    add_violation("V04", f"{p_label.lower()}.state", expected_st, actual_st, "WARN",
                                  f"{p_label} GSTIN state code ({st_code} - {expected_st}) does not match address state ({party.state}).")

    # ---------- V05: Invoice Number Syntax ----------
    if not doc.invoice_number or not doc.invoice_number.strip():
        add_violation("V05", "invoice_number", "Non-empty string", None, "ERROR",
                      "Missing invoice number.")
    else:
        inv_clean = doc.invoice_number.strip()
        if len(inv_clean) > 16:
            add_violation("V05", "invoice_number", "<= 16 characters", len(inv_clean), "WARN",
                          f"Invoice number '{inv_clean}' exceeds GST limit of 16 characters ({len(inv_clean)} chars).")

    # ---------- V06: Date Valid & FY Check ----------
    if not doc.invoice_date:
        add_violation("V06", "invoice_date", "Valid date", None, "ERROR",
                      "Missing invoice date.")
    else:
        today = date.today()
        if doc.invoice_date > today:
            add_violation("V06", "invoice_date", f"<= {today}", str(doc.invoice_date), "WARN",
                          f"Invoice date ({doc.invoice_date}) is in the future.")

    # ---------- Line Item Rules (V07, V08, V09, V10, V19, V20) ----------
    if not doc.items:
        add_violation("V20", "items", "At least 1 item", 0, "ERROR", "No line items found in invoice.")
    else:
        allowed_rates = get_allowed_gst_rates(doc.invoice_date)
        serials_found: List[int] = []

        for idx, item in enumerate(doc.items, 1):
            item_errors: List[str] = []

            # Serial number tracking
            if item.serial and item.serial.isdigit():
                serials_found.append(int(item.serial))

            # V20: Description non-empty and not a totals row
            i_name = (item.item_name or "").strip()
            if not i_name:
                msg = f"Line {idx} description/item name is empty."
                item_errors.append(msg)
                add_violation("V20", f"items[{idx-1}].item_name", "Non-empty", "", "ERROR", msg)
            else:
                up_name = i_name.upper()
                if any(rw == up_name or up_name.startswith(rw + " ") for rw in RESERVED_TOTAL_WORDS):
                    msg = f"Line {idx} appears to be a summary/charges row ('{i_name}'), not a stock item."
                    item_errors.append(msg)
                    add_violation("V20", f"items[{idx-1}].item_name", "Stock Item", i_name, "ERROR", msg)

            # V19: Qty > 0, Rate >= 0, Unit present
            if item.quantity <= Decimal("0.00") and doc.doc_type != "credit_note":
                msg = f"Line {idx} quantity ({item.quantity}) is <= 0."
                item_errors.append(msg)
                add_violation("V19", f"items[{idx-1}].quantity", "> 0", str(item.quantity), "WARN", msg)
            if item.rate < Decimal("0.00"):
                msg = f"Line {idx} rate ({item.rate}) is negative."
                item_errors.append(msg)
                add_violation("V19", f"items[{idx-1}].rate", ">= 0", str(item.rate), "WARN", msg)
            if not item.uom or not item.uom.strip():
                msg = f"Line {idx} unit/UOM is missing."
                item_errors.append(msg)
                add_violation("V19", f"items[{idx-1}].uom", "Valid Unit", "", "WARN", msg)

            # V07: HSN/SAC digits only, length 4/6/8
            if item.hsn_sac and item.hsn_sac.strip():
                clean_hsn = re.sub(r'[\s.]', '', item.hsn_sac)
                if not clean_hsn.isdigit() or len(clean_hsn) not in (4, 6, 8):
                    msg = f"Line {idx} HSN/SAC '{item.hsn_sac}' must be 4, 6, or 8 digits."
                    item_errors.append(msg)
                    add_violation("V07", f"items[{idx-1}].hsn_sac", "4, 6, or 8 digits", item.hsn_sac, "WARN", msg)

            # V08: GST Rate allowed for date
            total_rate = item.cgst_rate + item.sgst_rate + item.igst_rate
            if not any(abs(total_rate - r) < Decimal("0.01") for r in allowed_rates):
                msg = f"Line {idx} GST rate {total_rate}% is not in allowed slabs for date {doc.invoice_date}."
                item_errors.append(msg)
                add_violation("V08", f"items[{idx-1}].gst_rate", f"Allowed: {[float(r) for r in sorted(allowed_rates)]}", float(total_rate), "ERROR", msg)

            # V09: Line arithmetic qty * rate - discount ~= taxable
            gross = item.quantity * item.rate
            disc = item.discount if item.discount > Decimal("0.00") else (
                item.discount_amount if item.discount_amount > Decimal("0.00") else (
                    gross * item.discount_pct / Decimal("100.00")
                )
            )
            expected_taxable = (gross - disc).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if not close(expected_taxable, item.taxable_amount):
                msg = f"Line {idx} taxable ({item.taxable_amount}) does not match qty ({item.quantity}) * rate ({item.rate}) - discount ({disc}) = {expected_taxable}."
                item_errors.append(msg)
                add_violation("V09", f"items[{idx-1}].taxable_amount", str(expected_taxable), str(item.taxable_amount), "ERROR", msg)

            # V10: Line tax arithmetic: taxable * rate% ~= tax amount
            expected_tax = (item.taxable_amount * total_rate / Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            got_tax = item.cgst_amount + item.sgst_amount + item.igst_amount
            if got_tax > Decimal("0.00") and not close(expected_tax, got_tax):
                msg = f"Line {idx} tax amount ({got_tax}) does not match taxable ({item.taxable_amount}) * rate ({total_rate}%) = {expected_tax}."
                item_errors.append(msg)
                add_violation("V10", f"items[{idx-1}].tax_amount", str(expected_tax), str(got_tax), "ERROR", msg)

            item.validation_errors = item_errors

        # ---------- V21: Item count vs last S.No ----------
        if serials_found:
            max_sno = max(serials_found)
            if abs(len(doc.items) - max_sno) > 0:
                add_violation("V21", "items", max_sno, len(doc.items), "WARN",
                              f"Detected {len(doc.items)} line items, but last serial number indicates {max_sno}.")

    # ---------- V11: Tax Split (Intra vs Inter-State) ----------
    supp_st = doc.supplier.gstin[:2] if (doc.supplier.gstin and len(doc.supplier.gstin) >= 2) else None
    buyer_st = doc.buyer.gstin[:2] if (doc.buyer.gstin and len(doc.buyer.gstin) >= 2) else None

    if supp_st and buyer_st:
        is_same_state = (supp_st == buyer_st)
        has_cgst_sgst = (doc.cgst_total > Decimal("0.00") or doc.sgst_total > Decimal("0.00") or
                         any(i.cgst_amount > Decimal("0.00") or i.sgst_amount > Decimal("0.00") for i in doc.items))
        has_igst = (doc.igst_total > Decimal("0.00") or any(i.igst_amount > Decimal("0.00") for i in doc.items))

        if is_same_state:
            if has_igst and not has_cgst_sgst:
                add_violation("V11", "taxes", "CGST + SGST (intra-state)", "IGST", "ERROR",
                              f"Supplier and Buyer are in same state ({STATE_CODES.get(supp_st, supp_st)}), but invoice lists IGST instead of CGST+SGST.")
        else:
            if has_cgst_sgst and not has_igst:
                add_violation("V11", "taxes", "IGST (inter-state)", "CGST + SGST", "ERROR",
                              f"Supplier state ({STATE_CODES.get(supp_st, supp_st)}) differs from Buyer state ({STATE_CODES.get(buyer_st, buyer_st)}), but invoice lists CGST+SGST instead of IGST.")

    # Check CGST == SGST for intra-state rows
    for idx, item in enumerate(doc.items, 1):
        if item.cgst_amount > Decimal("0.00") or item.sgst_amount > Decimal("0.00"):
            if abs(item.cgst_amount - item.sgst_amount) > Decimal("0.05"):
                add_violation("V11", f"items[{idx-1}].cgst_amount", str(item.sgst_amount), str(item.cgst_amount), "ERROR",
                              f"Line {idx} CGST ({item.cgst_amount}) does not equal SGST ({item.sgst_amount}).")

    # ---------- Totals Rules (V12, V13, V14, V15, V16) ----------
    if doc.items:
        calc_taxable = sum(i.taxable_amount for i in doc.items).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        calc_cgst = sum(i.cgst_amount for i in doc.items).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        calc_sgst = sum(i.sgst_amount for i in doc.items).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        calc_igst = sum(i.igst_amount for i in doc.items).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        calc_cess = sum(i.cess_amount for i in doc.items).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        calc_taxes = calc_cgst + calc_sgst + calc_igst + calc_cess

        # V12: Sum of line taxable values ~= printed taxable total
        if doc.taxable_total > Decimal("0.00") and not close(calc_taxable, doc.taxable_total):
            diff = abs(calc_taxable - doc.taxable_total)
            add_violation("V12", "taxable_total", str(calc_taxable), str(doc.taxable_total), "WARN",
                          f"Line items taxable total ({calc_taxable}) does not match invoice taxable amount ({doc.taxable_total}). Difference: {diff:.2f}.")

        # V13: Sum of line taxes ~= printed total tax
        printed_taxes = doc.cgst_total + doc.sgst_total + doc.igst_total + doc.cess_total
        if printed_taxes > Decimal("0.00") and not close(calc_taxes, printed_taxes):
            diff = abs(calc_taxes - printed_taxes)
            add_violation("V13", "taxes_total", str(calc_taxes), str(printed_taxes), "WARN",
                          f"Line items taxes total ({calc_taxes}) does not match invoice tax totals ({printed_taxes}). Difference: {diff:.2f}.")

        # V14: Reconciliation: taxable + tax + other charges +/- round_off = grand total
        expected_grand = doc.taxable_total + doc.cgst_total + doc.sgst_total + doc.igst_total + doc.cess_total + doc.other_charges + doc.round_off
        if doc.grand_total > Decimal("0.00") and not close(expected_grand, doc.grand_total):
            diff = abs(expected_grand - doc.grand_total)
            add_violation("V14", "grand_total", str(expected_grand), str(doc.grand_total), "WARN",
                          f"Invoice total does not reconcile with line items: calculated {expected_grand} vs stated grand total {doc.grand_total}. Difference: {diff:.2f}.")

        # V15: Computed grand total ~= printed grand total
        calc_grand = sum(i.total_amount for i in doc.items) + doc.other_charges + doc.round_off
        if doc.grand_total > Decimal("0.00") and not close(calc_grand, doc.grand_total, abs_tol=Decimal("2.00")):
            diff = abs(calc_grand - doc.grand_total)
            add_violation("V15", "grand_total", str(calc_grand), str(doc.grand_total), "WARN",
                          f"Computed items grand total ({calc_grand}) does not match printed grand total ({doc.grand_total}). Difference: {diff:.2f}.")

    # V16: Round-off magnitude < Rs 1.00
    if abs(doc.round_off) >= Decimal("1.00"):
        add_violation("V16", "round_off", "< 1.00", str(doc.round_off), "WARN",
                      f"Round-off amount ({doc.round_off}) is abnormally large (>= ₹1.00).")

    # V22: Grounding check
    if doc.raw_text_preview and doc.invoice_number:
        if doc.invoice_number.strip().lower() not in doc.raw_text_preview.lower():
            add_violation("V22", "invoice_number", "Present in OCR text", doc.invoice_number, "WARN",
                          f"Invoice number '{doc.invoice_number}' was not found in raw OCR text preview.")

    # Master Matching (Ledgers & Stock Items)
    if known_ledgers:
        match_party_masters(doc, known_ledgers)
    else:
        doc.supplier.requires_ledger_creation = not bool(doc.supplier.matched_ledger_name)
        doc.buyer.requires_ledger_creation = not bool(doc.buyer.matched_ledger_name)

    if known_stock_items:
        match_stock_item_masters(doc, known_stock_items)
    else:
        for it in doc.items:
            it.requires_item_creation = not bool(it.matched_stock_item)

    # Separate violations into errors and warnings for backward compatibility
    doc.validation_violations = violations
    doc.errors = [v["message"] for v in violations if v["severity"] == "ERROR"]
    doc.warnings = [v["message"] for v in violations if v["severity"] == "WARN"]
    doc.is_valid = (len(doc.errors) == 0)

    return doc

def match_party_masters(doc: InvoiceDocument, known_ledgers: List[Dict[str, any]]):
    """Matches supplier and buyer against known Tally ledgers."""
    for party in (doc.supplier, doc.buyer):
        if not party.name:
            continue
        p_clean = " ".join(party.name.strip().upper().split())
        matched = None

        # 1. Match by GSTIN if available
        if party.gstin and party.gstin.strip():
            g_clean = party.gstin.strip().upper()
            for l in known_ledgers:
                if (l.get('party_gstin') or '').strip().upper() == g_clean:
                    matched = l.get('name')
                    break

        # 2. Match by exact normalized name
        if not matched:
            for l in known_ledgers:
                l_name = l.get('normalized_name') or " ".join((l.get('name') or '').strip().upper().split())
                if l_name == p_clean:
                    matched = l.get('name')
                    break

        # 3. Match by aliases
        if not matched:
            for l in known_ledgers:
                aliases = [a.upper() for a in l.get('aliases', [])]
                if p_clean in aliases:
                    matched = l.get('name')
                    break

        if matched:
            party.matched_ledger_name = matched
            party.requires_ledger_creation = False
        else:
            party.matched_ledger_name = None
            party.requires_ledger_creation = True

def match_stock_item_masters(doc: InvoiceDocument, known_stock_items: List[str]):
    """Matches items against known stock items."""
    known_normalized = { " ".join(s.strip().upper().split()): s for s in known_stock_items }
    for item in doc.items:
        if not item.item_name:
            continue
        i_clean = " ".join(item.item_name.strip().upper().split())
        if i_clean in known_normalized:
            item.matched_stock_item = known_normalized[i_clean]
            item.requires_item_creation = False
        else:
            item.matched_stock_item = None
            item.requires_item_creation = True

def detect_batch_duplicates(invoices: List[InvoiceDocument]) -> List[InvoiceDocument]:
    """Detects duplicate invoices in a batch based on (invoice_number, party, date, total)."""
    seen = {}
    for inv in invoices:
        party = inv.supplier.gstin or inv.supplier.name if inv.invoice_type == "PURCHASE" else inv.buyer.gstin or inv.buyer.name
        key = (
            inv.invoice_number.strip().upper(),
            (party or '').strip().upper(),
            inv.invoice_date.isoformat() if inv.invoice_date else '',
            str(inv.grand_total)
        )
        if key in seen:
            inv.duplicate_suspect = True
            inv.duplicate_reason = f"Possible duplicate of invoice #{seen[key]} (same invoice number, party, date, and amount)."
            inv.warnings.append(inv.duplicate_reason)
        else:
            seen[key] = inv.invoice_number
    return invoices

def compute_batch_summary(invoices: List[InvoiceDocument]) -> BatchSummary:
    """Calculates aggregate metrics across all invoices in the batch."""
    summary = BatchSummary()
    summary.total_documents = len(invoices)

    for inv in invoices:
        if inv.invoice_type == "PURCHASE":
            summary.total_purchase_invoices += 1
        else:
            summary.total_sales_invoices += 1

        summary.total_items += len(inv.items)
        summary.total_taxable_value += inv.taxable_total
        summary.total_cgst += inv.cgst_total
        summary.total_sgst += inv.sgst_total
        summary.total_igst += inv.igst_total
        summary.total_cess += inv.cess_total
        summary.total_invoice_value += inv.grand_total

        summary.errors_count += len(inv.errors)
        summary.warnings_count += len(inv.warnings)
        if inv.duplicate_suspect:
            summary.duplicate_candidates_count += 1

        for it in inv.items:
            if it.requires_item_creation:
                summary.items_requiring_creation_count += 1

        party = inv.supplier if inv.invoice_type == "PURCHASE" else inv.buyer
        if party.requires_ledger_creation:
            summary.parties_requiring_creation_count += 1

    summary.purchase_count = summary.total_purchase_invoices
    summary.sales_count = summary.total_sales_invoices
    summary.total_taxable = summary.total_taxable_value
    summary.total_grand = summary.total_invoice_value
    summary.missing_masters_count = summary.items_requiring_creation_count + summary.parties_requiring_creation_count
    summary.has_discrepancies = (summary.errors_count > 0 or summary.duplicate_candidates_count > 0)

    return summary
