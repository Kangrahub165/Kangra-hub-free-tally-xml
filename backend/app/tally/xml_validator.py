import xml.etree.ElementTree as ET
from decimal import Decimal
from typing import Tuple, List

def validate_tally_xml(xml_content: str) -> Tuple[bool, List[str]]:
    """
    Performs comprehensive validation of generated Tally XML:
    1. Valid XML syntax
    2. Envelope, Header, ImportData structure
    3. At least one voucher present
    4. Each voucher balanced: sum of ledger amounts == 0
    5. Valid date format (YYYYMMDD)
    """
    errors: List[str] = []

    if not xml_content or not xml_content.strip():
        return False, ["XML content is empty."]

    try:
        root = ET.fromstring(xml_content.strip())
    except ET.ParseError as e:
        return False, [f"XML syntax error: {str(e)}"]

    if root.tag != "ENVELOPE":
        errors.append(f"Root tag must be <ENVELOPE>, found <{root.tag}>.")

    header = root.find("HEADER")
    if header is None or header.find("TALLYREQUEST") is None:
        errors.append("Missing <HEADER><TALLYREQUEST> tag.")

    body = root.find("BODY")
    if body is None:
        errors.append("Missing <BODY> tag.")
        return False, errors

    import_data = body.find("IMPORTDATA")
    if import_data is None:
        errors.append("Missing <IMPORTDATA> tag.")
        return False, errors

    request_data = import_data.find("REQUESTDATA")
    if request_data is None:
        errors.append("Missing <REQUESTDATA> tag.")
        return False, errors

    tally_messages = request_data.findall("TALLYMESSAGE")
    if not tally_messages:
        errors.append("No <TALLYMESSAGE> vouchers found in XML.")

    voucher_count = 0
    for idx, msg in enumerate(tally_messages):
        voucher = msg.find("VOUCHER")
        if voucher is None:
            continue
        voucher_count += 1

        vch_date = voucher.find("DATE")
        if vch_date is None or len(vch_date.text or "") != 8:
            errors.append(f"Voucher #{idx+1} has missing or invalid DATE (must be YYYYMMDD).")

        ledger_entries = voucher.findall("ALLLEDGERENTRIES.LIST")
        if len(ledger_entries) < 2:
            errors.append(f"Voucher #{idx+1} must have at least 2 ledger entries for double entry balancing.")
            continue

        # Check balance
        total_amount = Decimal("0.00")
        for le in ledger_entries:
            amt_tag = le.find("AMOUNT")
            ledger_tag = le.find("LEDGERNAME")
            if ledger_tag is None or not (ledger_tag.text or "").strip():
                errors.append(f"Voucher #{idx+1} has an entry with an empty LEDGERNAME.")
            if amt_tag is None or not amt_tag.text:
                errors.append(f"Voucher #{idx+1} has an entry with a missing AMOUNT.")
            else:
                try:
                    total_amount += Decimal(amt_tag.text)
                except Exception:
                    errors.append(f"Voucher #{idx+1} has an invalid numeric AMOUNT: {amt_tag.text}.")

        if abs(total_amount) > Decimal("0.01"):
            errors.append(f"Voucher #{idx+1} is unbalanced: net sum is {total_amount} (must be 0).")

    if voucher_count == 0:
        errors.append("No valid vouchers could be validated.")

    is_valid = (len(errors) == 0)
    return is_valid, errors
