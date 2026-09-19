import io
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Tuple, Union, Any, Dict
import openpyxl

from app.transactions.model import CanonicalStatement, TransactionItem
from app.transactions.snapshot import FinalConversionSnapshot, FinalVoucherEntry, validate_conversion_snapshot
from app.core.exceptions import XMLGenerationException
from app.excel.excel_generator import EXCEL_COLUMNS

class ConsistencyValidationException(XMLGenerationException):
    """Raised when consistency invariants are violated."""
    pass

def validate_conversion_consistency(
    statement_or_snapshot: Union[FinalConversionSnapshot, CanonicalStatement],
    bank_ledger_name: str,
    cash_ledger_name: str = "Cash",
    xml_content: Optional[str] = None
) -> Tuple[bool, List[str]]:
    """
    Validates conversion dataset consistency.
    Does NOT require XML generation to exist first.
    If xml_content is provided, performs basic XML parity check.
    """
    if isinstance(statement_or_snapshot, FinalConversionSnapshot):
        snapshot = statement_or_snapshot
    else:
        snapshot = FinalConversionSnapshot.create_from_statement(
            statement_or_snapshot,
            bank_ledger_name=bank_ledger_name,
            cash_ledger_name=cash_ledger_name
        )

    # 1. First validate the single source of truth: FinalConversionSnapshot
    is_valid, errors = validate_conversion_snapshot(snapshot)
    if not is_valid:
        return False, errors

    # 2. Only if XML is optionally passed, verify parity
    if xml_content:
        try:
            root = ET.fromstring(xml_content)
            vouchers = root.findall(".//VOUCHER")
            if len(vouchers) != len(snapshot.transactions):
                errors.append(
                    f"Transaction count mismatch: Snapshot has {len(snapshot.transactions)} transactions, but XML has {len(vouchers)} vouchers."
                )

            for idx, (tx, vch) in enumerate(zip(snapshot.transactions, vouchers), start=1):
                # Voucher type
                xml_vch_type = vch.get("VCHTYPE") or ""
                expected_vch_type = tx.voucher_type or "Payment"
                if xml_vch_type != expected_vch_type:
                    errors.append(f"Row {idx}: Voucher type mismatch: Snapshot='{expected_vch_type}', XML='{xml_vch_type}'")

                # Date
                xml_date_elem = vch.find("DATE")
                if xml_date_elem is not None and xml_date_elem.text:
                    expected_date_str = tx.date.strftime("%Y%m%d") if tx.date else ""
                    if xml_date_elem.text.strip() != expected_date_str:
                        errors.append(f"Row {idx}: Date mismatch: Snapshot='{expected_date_str}', XML='{xml_date_elem.text.strip()}'")

                # Bank ledger entry
                ledger_entries = vch.findall("ALLLEDGERENTRIES.LIST")
                entry_names = [e.find("LEDGERNAME").text.strip() for e in ledger_entries if e.find("LEDGERNAME") is not None and e.find("LEDGERNAME").text]
                if snapshot.bank_ledger_name not in entry_names:
                    errors.append(f"Row {idx}: Configured bank ledger '{snapshot.bank_ledger_name}' not found in XML entries: {entry_names}")

                # Instrument number
                inst_no = tx.instrument_number or tx.cheque_number
                if inst_no:
                    inst_elem = vch.find(".//INSTRUMENTNUMBER")
                    if inst_elem is not None and inst_elem.text:
                        if inst_elem.text.strip() != str(inst_no).strip():
                            errors.append(f"Row {idx}: Instrument number mismatch: Snapshot='{inst_no}', XML='{inst_elem.text.strip()}'")

        except ET.ParseError as e:
            errors.append(f"Failed to parse generated Tally XML: {str(e)}")

    if errors:
        return False, errors
    return True, []


def validate_complete_11_field_parity(
    snapshot: FinalConversionSnapshot,
    excel_bytes: bytes,
    xml_content: Optional[str] = None
) -> Tuple[bool, List[str]]:
    """
    RIGOROUS COMPLETE 11-FIELD PARITY VALIDATOR:
    Compares EVERY single exportable field across the entire dataset:
    1. VOUCHER NO.
    2. VOUCHER TYPE
    3. VOUCHER DATE
    4. VOUCHER NARRATION
    5. LEDGER NAME
    6. BANK LEDGER AS TALLY
    7. INST. NUMBER
    8. INST. DATE
    9. DEBIT AMOUNT
    10. CREDIT AMOUNT
    11. BALANCE

    Verifies:
    - Exact transaction set count and ordering (row 1..N)
    - Native date types
    - Numeric amount cells supporting =SUM()
    - Leading-zero preservation in instrument numbers verbatim as text
    - Full alignment between FinalConversionSnapshot, Excel, and XML.
    """
    errors: List[str] = []

    # 1. Open and inspect Excel workbook
    try:
        wb = openpyxl.load_workbook(io.BytesIO(excel_bytes), data_only=True)
    except Exception as e:
        return False, [f"Failed to load Excel workbook: {str(e)}"]

    if "Tally Data" not in wb.sheetnames:
        errors.append("Excel missing worksheet 'Tally Data'")
        return False, errors

    ws = wb["Tally Data"]

    # Verify column headers
    header_values = [ws.cell(row=1, column=c).value for c in range(1, 12)]
    if header_values != EXCEL_COLUMNS:
        errors.append(f"Excel column mismatch. Expected {EXCEL_COLUMNS}, got {header_values}")

    excel_rows = list(ws.iter_rows(min_row=2, max_col=11, values_only=False))
    if len(excel_rows) != len(snapshot.transactions):
        errors.append(
            f"Row count mismatch: Snapshot has {len(snapshot.transactions)} transactions, but Excel has {len(excel_rows)} data rows."
        )

    # 2. Parse XML if provided
    xml_vouchers = []
    if xml_content:
        try:
            root = ET.fromstring(xml_content)
            xml_vouchers = root.findall(".//VOUCHER")
            if len(xml_vouchers) != len(snapshot.transactions):
                errors.append(
                    f"Transaction count mismatch: Snapshot has {len(snapshot.transactions)}, XML has {len(xml_vouchers)} vouchers."
                )
        except ET.ParseError as e:
            errors.append(f"XML parse error: {str(e)}")

    # 3. Transaction-by-Transaction 11-Field Verification
    for idx, tx in enumerate(snapshot.transactions, start=1):
        if idx - 1 >= len(excel_rows):
            break
        row_cells = excel_rows[idx - 1]
        vch = xml_vouchers[idx - 1] if (xml_content and idx - 1 < len(xml_vouchers)) else None

        # Field 1: VOUCHER NO.
        excel_vch_no = row_cells[0].value
        if excel_vch_no != tx.row_index:
            errors.append(f"Row {idx} [VOUCHER NO.]: Excel={excel_vch_no}, Snapshot={tx.row_index}")
        if vch is not None:
            xml_vch_no_elem = vch.find("VOUCHERNUMBER")
            if xml_vch_no_elem is not None and xml_vch_no_elem.text:
                if int(xml_vch_no_elem.text.strip()) != tx.row_index:
                    errors.append(f"Row {idx} [VOUCHER NO.]: XML={xml_vch_no_elem.text}, Snapshot={tx.row_index}")

        # Field 2: VOUCHER TYPE
        excel_vch_type = row_cells[1].value
        if excel_vch_type != tx.voucher_type:
            errors.append(f"Row {idx} [VOUCHER TYPE]: Excel='{excel_vch_type}', Snapshot='{tx.voucher_type}'")
        if vch is not None:
            xml_vch_type = vch.get("VCHTYPE") or ""
            if xml_vch_type != tx.voucher_type:
                errors.append(f"Row {idx} [VOUCHER TYPE]: XML='{xml_vch_type}', Snapshot='{tx.voucher_type}'")

        # Field 3: VOUCHER DATE
        excel_vch_date = row_cells[2].value
        if isinstance(excel_vch_date, datetime):
            excel_vch_date = excel_vch_date.date()
        if excel_vch_date != tx.date:
            errors.append(f"Row {idx} [VOUCHER DATE]: Excel={excel_vch_date}, Snapshot={tx.date}")
        if vch is not None and tx.date:
            xml_date_elem = vch.find("DATE")
            expected_xml_date = tx.date.strftime("%Y%m%d")
            if xml_date_elem is None or xml_date_elem.text.strip() != expected_xml_date:
                actual_xml_date = xml_date_elem.text if xml_date_elem is not None else "None"
                errors.append(f"Row {idx} [VOUCHER DATE]: XML={actual_xml_date}, Snapshot={expected_xml_date}")

        # Field 4: VOUCHER NARRATION
        excel_narration = row_cells[3].value or ""
        expected_narration = tx.narration or ""
        if excel_narration.strip() != expected_narration.strip():
            errors.append(f"Row {idx} [VOUCHER NARRATION]: Excel='{excel_narration}', Snapshot='{expected_narration}'")
        if vch is not None:
            xml_narr_elem = vch.find("NARRATION")
            xml_narr = xml_narr_elem.text or "" if xml_narr_elem is not None else ""
            if xml_narr.strip() != expected_narration.strip():
                errors.append(f"Row {idx} [VOUCHER NARRATION]: XML='{xml_narr}', Snapshot='{expected_narration}'")

        # Field 5: LEDGER NAME (Party Ledger)
        excel_ledger = row_cells[4].value or ""
        if excel_ledger.strip() != tx.ledger_name.strip():
            errors.append(f"Row {idx} [LEDGER NAME]: Excel='{excel_ledger}', Snapshot='{tx.ledger_name}'")
        if vch is not None:
            entries = vch.findall("ALLLEDGERENTRIES.LIST")
            entry_ledgers = [e.find("LEDGERNAME").text.strip() for e in entries if e.find("LEDGERNAME") is not None and e.find("LEDGERNAME").text]
            if tx.ledger_name.strip() not in entry_ledgers:
                errors.append(f"Row {idx} [LEDGER NAME]: Party ledger '{tx.ledger_name}' not found in XML entries: {entry_ledgers}")

        # Field 6: BANK LEDGER AS TALLY
        excel_bank_ledger = row_cells[5].value or ""
        if excel_bank_ledger.strip() != snapshot.bank_ledger_name.strip():
            errors.append(f"Row {idx} [BANK LEDGER AS TALLY]: Excel='{excel_bank_ledger}', Snapshot='{snapshot.bank_ledger_name}'")
        if vch is not None:
            entries = vch.findall("ALLLEDGERENTRIES.LIST")
            entry_ledgers = [e.find("LEDGERNAME").text.strip() for e in entries if e.find("LEDGERNAME") is not None and e.find("LEDGERNAME").text]
            if snapshot.bank_ledger_name.strip() not in entry_ledgers:
                errors.append(f"Row {idx} [BANK LEDGER AS TALLY]: Bank ledger '{snapshot.bank_ledger_name}' not found in XML: {entry_ledgers}")

        # Field 7: INST. NUMBER (Strict leading zero string preservation)
        excel_inst_no = row_cells[6].value
        expected_inst_no = tx.instrument_number or tx.cheque_number
        if expected_inst_no:
            expected_str = str(expected_inst_no).strip()
            if excel_inst_no is None or str(excel_inst_no).strip() != expected_str:
                errors.append(f"Row {idx} [INST. NUMBER]: Excel='{excel_inst_no}', Snapshot='{expected_str}'")
            # Verify leading zeros not lost in Excel cell formatting
            if expected_str.startswith("0") and str(excel_inst_no) != expected_str:
                errors.append(f"Row {idx} [INST. NUMBER]: Leading zero lost in Excel! Excel='{excel_inst_no}', Expected='{expected_str}'")
            if vch is not None:
                xml_inst_elem = vch.find(".//INSTRUMENTNUMBER")
                if xml_inst_elem is None or xml_inst_elem.text.strip() != expected_str:
                    actual_xml_inst = xml_inst_elem.text if xml_inst_elem is not None else "None"
                    errors.append(f"Row {idx} [INST. NUMBER]: XML='{actual_xml_inst}', Snapshot='{expected_str}'")
        else:
            if excel_inst_no not in (None, ""):
                errors.append(f"Row {idx} [INST. NUMBER]: Expected empty, but Excel has '{excel_inst_no}'")

        # Field 8: INST. DATE
        excel_inst_date = row_cells[7].value
        if isinstance(excel_inst_date, datetime):
            excel_inst_date = excel_inst_date.date()
        expected_inst_date = tx.instrument_date
        if expected_inst_date:
            if excel_inst_date != expected_inst_date:
                errors.append(f"Row {idx} [INST. DATE]: Excel={excel_inst_date}, Snapshot={expected_inst_date}")
            if vch is not None:
                xml_inst_d = vch.find(".//INSTRUMENTDATE")
                if xml_inst_d is not None and xml_inst_d.text:
                    if xml_inst_d.text.strip() != expected_inst_date.strftime("%Y%m%d"):
                        errors.append(f"Row {idx} [INST. DATE]: XML={xml_inst_d.text}, Expected={expected_inst_date.strftime('%Y%m%d')}")
        else:
            if excel_inst_date is not None:
                errors.append(f"Row {idx} [INST. DATE]: Expected None, but Excel has {excel_inst_date}")

        # Field 9: DEBIT AMOUNT
        excel_debit = row_cells[8].value
        expected_debit = float(tx.debit) if (tx.debit and tx.debit > Decimal("0.00")) else None
        if expected_debit is not None:
            if excel_debit is None or abs(float(excel_debit) - expected_debit) > 0.001:
                errors.append(f"Row {idx} [DEBIT AMOUNT]: Excel={excel_debit}, Snapshot={expected_debit}")
        else:
            if excel_debit is not None:
                errors.append(f"Row {idx} [DEBIT AMOUNT]: Expected empty cell, but Excel has {excel_debit}")

        # Field 10: CREDIT AMOUNT
        excel_credit = row_cells[9].value
        expected_credit = float(tx.credit) if (tx.credit and tx.credit > Decimal("0.00")) else None
        if expected_credit is not None:
            if excel_credit is None or abs(float(excel_credit) - expected_credit) > 0.001:
                errors.append(f"Row {idx} [CREDIT AMOUNT]: Excel={excel_credit}, Snapshot={expected_credit}")
        else:
            if excel_credit is not None:
                errors.append(f"Row {idx} [CREDIT AMOUNT]: Expected empty cell, but Excel has {excel_credit}")

        # Field 11: BALANCE
        excel_balance = row_cells[10].value
        expected_balance = float(tx.balance) if tx.balance is not None else None
        if expected_balance is not None:
            if excel_balance is None or abs(float(excel_balance) - expected_balance) > 0.001:
                errors.append(f"Row {idx} [BALANCE]: Excel={excel_balance}, Snapshot={expected_balance}")
        else:
            if excel_balance is not None:
                errors.append(f"Row {idx} [BALANCE]: Expected empty cell, but Excel has {excel_balance}")

    if errors:
        return False, errors
    return True, []
