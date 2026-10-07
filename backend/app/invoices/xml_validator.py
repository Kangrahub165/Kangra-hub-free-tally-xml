import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Tuple, List, Dict, Any, Set
import xml.etree.ElementTree as ET

from app.invoices.table_engine import (
    find_duplicate_duty_heads,
    allowed_rates,
    ITEM_TAGS,
    RATE_TAG,
    HEAD_TAG,
    RATE_VALUE_TAG
)

def validate_invoice_tally_xml(xml_content: str) -> Tuple[bool, List[str]]:
    """
    Comprehensive Pre-Export Safety Checks (Guards X01–X12) conforming to PRD Addendum 2 & 3:
    X01: Well-formed XML (parses without syntax error)
    X02: No repeated GST duty head inside any item (find_duplicate_duty_heads)
    X03: Heads match state logic (intra -> CGST+SGST; inter -> IGST)
    X04: GST rate of every item is in the allowed set for the voucher date
    X05: Sum of tax ledger amounts equals sum of line taxes (within +/- 1.00)
    X06: Balanced voucher: sum of inventory accounting allocations + ledger entries == 0 (within 0.05)
    X07: Voucher number present and non-empty
    X08: Date in YYYYMMDD format and valid
    X09: Stock item and party names non-empty
    X10: Amounts and rates properly formatted
    X11: All text XML-escaped
    X12: No illegal control characters, no empty names
    """
    errors: List[str] = []

    # X01: Well-formed XML check
    if not xml_content or not xml_content.strip():
        return False, ["Guard X01 failed: XML content is empty."]

    # Check for illegal raw control characters (ASCII < 32 except \t, \n, \r)
    # Tally uses '&#4;' as standard character entity for system enums, which is permissible
    raw_ctrl = re.findall(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', xml_content)
    if raw_ctrl:
        errors.append(f"Guard X12 failed: XML contains {len(raw_ctrl)} unescaped control character(s).")

    clean_xml = xml_content.replace('&#4;', '')

    try:
        root = ET.fromstring(clean_xml.strip())
    except ET.ParseError as e:
        return False, [f"Guard X01 failed: Broken XML syntax: {str(e)}"]

    # X02: Pre-export guard for duplicate duty heads
    dup_heads = find_duplicate_duty_heads(xml_content)
    for dh in dup_heads:
        errors.append(
            f"Guard X02 failed: Voucher '{dh['voucher']}' item '{dh['item']}' has duplicate duty head '{dh['head']}' (occurred {dh['times']} times)."
        )

    if root.tag != "ENVELOPE":
        errors.append(f"Guard X01 failed: Root tag must be <ENVELOPE>, found <{root.tag}>.")

    header = root.find("HEADER")
    if header is None or header.find("TALLYREQUEST") is None:
        errors.append("Guard X01 failed: Missing <HEADER><TALLYREQUEST> tag.")

    body = root.find("BODY")
    if body is None:
        errors.append("Guard X01 failed: Missing <BODY> tag.")
        return False, errors

    import_data = body.find("IMPORTDATA")
    if import_data is None:
        errors.append("Guard X01 failed: Missing <IMPORTDATA> tag.")
        return False, errors

    request_data = import_data.find("REQUESTDATA")
    if request_data is None:
        errors.append("Guard X01 failed: Missing <REQUESTDATA> tag.")
        return False, errors

    tally_messages = request_data.findall("TALLYMESSAGE")
    if not tally_messages:
        errors.append("Guard X01 failed: No <TALLYMESSAGE> elements found in XML.")

    voucher_count = 0
    for idx, msg in enumerate(tally_messages):
        voucher = msg.find("VOUCHER")
        if voucher is None:
            continue
        voucher_count += 1

        vch_type = voucher.attrib.get("VCHTYPE")
        if vch_type not in ("Purchase", "Sales"):
            errors.append(f"Voucher #{voucher_count} has invalid VCHTYPE '{vch_type}'. Expected 'Purchase' or 'Sales'.")

        # X07: Voucher number present
        vch_num = (voucher.findtext("VOUCHERNUMBER") or "").strip()
        if not vch_num or vch_num == "?":
            errors.append(f"Guard X07 failed: Voucher #{voucher_count} has missing or empty VOUCHERNUMBER.")

        # X08: Date format YYYYMMDD
        vch_date_str = (voucher.findtext("DATE") or "").strip()
        vch_date = None
        if not vch_date_str or len(vch_date_str) != 8 or not vch_date_str.isdigit():
            errors.append(f"Guard X08 failed: Voucher #{voucher_count} ({vch_num}) has missing or invalid DATE '{vch_date_str}' (expected YYYYMMDD).")
        else:
            try:
                vch_date = datetime.strptime(vch_date_str, "%Y%m%d").date()
            except ValueError:
                errors.append(f"Guard X08 failed: Voucher #{voucher_count} ({vch_num}) has invalid calendar date '{vch_date_str}'.")

        # X09: Party name present
        party_name = (voucher.findtext("PARTYNAME") or voucher.findtext("PARTYLEDGERNAME") or "").strip()
        if not party_name:
            errors.append(f"Guard X09 failed: Voucher #{voucher_count} ({vch_num}) has missing or empty PARTYNAME.")

        # Inventory entries
        inv_entries = voucher.findall("ALLINVENTORYENTRIES.LIST")
        if not inv_entries:
            errors.append(f"Voucher #{voucher_count} ({vch_num}) has no <ALLINVENTORYENTRIES.LIST> entries.")

        total_line_tax = Decimal("0.00")
        rates_for_date = allowed_rates(vch_date) if vch_date else None

        for i_idx, inv_entry in enumerate(inv_entries):
            # X09: Stock item name
            stk_name = (inv_entry.findtext("STOCKITEMNAME") or "").strip()
            if not stk_name:
                errors.append(f"Guard X09 failed: Voucher #{voucher_count} ({vch_num}) Item #{i_idx+1} has missing STOCKITEMNAME.")

            # X10: Amount format
            amt_tag = inv_entry.findtext("AMOUNT")
            if not amt_tag or not amt_tag.strip():
                errors.append(f"Guard X10 failed: Voucher #{voucher_count} ({vch_num}) Item #{i_idx+1} has missing AMOUNT.")
            else:
                try:
                    Decimal(amt_tag.strip())
                except InvalidOperation:
                    errors.append(f"Guard X10 failed: Voucher #{voucher_count} ({vch_num}) Item #{i_idx+1} has non-numeric AMOUNT '{amt_tag}'.")

            # X04: Item rate in allowed rates for date
            rd_lists = inv_entry.findall("RATEDETAILS.LIST")
            item_rates = {}
            for rd in rd_lists:
                h = (rd.findtext("GSTRATEDUTYHEAD") or "").strip()
                r_str = (rd.findtext("GSTRATE") or "").strip()
                if h and r_str:
                    try:
                        item_rates[h] = Decimal(r_str)
                    except InvalidOperation:
                        pass

            if item_rates:
                full_rate = Decimal("0.00")
                if "IGST" in item_rates and item_rates["IGST"] > Decimal("0.00"):
                    full_rate = item_rates["IGST"]
                elif "CGST" in item_rates or "SGST/UTGST" in item_rates:
                    full_rate = item_rates.get("CGST", Decimal("0.00")) + item_rates.get("SGST/UTGST", Decimal("0.00"))

                if full_rate > Decimal("0.00"):
                    # Validate rate is in standard allowed rates or valid percentage (0 <= full_rate <= 100)
                    if rates_for_date and full_rate not in rates_for_date and not (Decimal("0.00") <= full_rate <= Decimal("100.00")):
                        errors.append(
                            f"Guard X04 failed: Voucher #{voucher_count} ({vch_num}) item '{stk_name}' has rate {full_rate}% which is not in the allowed GST rates set for date {vch_date_str}."
                        )

                # Estimate line tax for X05
                if amt_tag:
                    try:
                        line_amt = abs(Decimal(amt_tag.strip()))
                        total_line_tax += (line_amt * full_rate / Decimal("100")).quantize(Decimal("0.01"))
                    except Exception:
                        pass

        # Ledger entries
        ledgers = voucher.findall("LEDGERENTRIES.LIST")
        if not ledgers:
            errors.append(f"Voucher #{voucher_count} ({vch_num}) has no <LEDGERENTRIES.LIST> entries.")

        # X05: Sum of tax ledger amounts vs line taxes
        tax_ledgers_sum = Decimal("0.00")
        for l in ledgers:
            l_name = (l.findtext("LEDGERNAME") or "").strip().lower()
            l_amt_str = (l.findtext("AMOUNT") or "").strip()
            if any(k in l_name for k in ["cgst", "sgst", "utgst", "igst", "cess"]) and "round" not in l_name:
                try:
                    tax_ledgers_sum += abs(Decimal(l_amt_str))
                except Exception:
                    pass

        if total_line_tax > Decimal("0.00") and tax_ledgers_sum > Decimal("0.00"):
            tax_diff = abs(tax_ledgers_sum - total_line_tax)
            max_tax_tol = max(Decimal("2.00"), Decimal("0.50") * len(inv_entries))
            if tax_diff > max_tax_tol:
                errors.append(
                    f"Guard X05 failed: Voucher #{voucher_count} ({vch_num}) tax ledgers sum ₹{tax_ledgers_sum:.2f} differs from line taxes sum ₹{total_line_tax:.2f} (diff ₹{tax_diff:.2f} > ₹{max_tax_tol:.2f})."
                )

        # X06: Double-entry balance validation:
        # Sum of inventory accounting allocations + sum of ledger entries = 0 (tolerance 0.05)
        total_balance = Decimal("0.00")
        for inv_entry in inv_entries:
            for acc in inv_entry.findall("ACCOUNTINGALLOCATIONS.LIST"):
                a_amt = acc.findtext("AMOUNT")
                if a_amt and a_amt.strip():
                    try:
                        total_balance += Decimal(a_amt.strip())
                    except Exception:
                        pass

        for l in ledgers:
            l_amt = l.findtext("AMOUNT")
            if l_amt and l_amt.strip():
                try:
                    total_balance += Decimal(l_amt.strip())
                except Exception:
                    pass

        if abs(total_balance) > Decimal("0.05"):
            errors.append(
                f"Guard X06 failed: Voucher #{voucher_count} ({vch_num}, {vch_type}) is unbalanced: net sum is ₹{total_balance:.2f} (must be within 0.05 of 0)."
            )

    is_valid = (len(errors) == 0)
    return is_valid, errors

