import re
import html
import xml.sax.saxutils as saxutils
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel, Field

from app.invoices.state_normalizer import normalize_state
from app.accounting.ledger_importer import sanitize_xml_content

UQC_MAP = {
    "BAG": "BAG-BAGS", "BAGS": "BAG-BAGS", "BOX": "BOX-BOX", "BOXES": "BOX-BOX",
    "BTL": "BTL-BOTTLES", "BOTTLE": "BTL-BOTTLES", "BOTTLES": "BTL-BOTTLES",
    "CAN": "PCS-PIECES", "CANS": "PCS-PIECES", "CASE": "PCS-PIECES", "CASES": "PCS-PIECES",
    "CRATE": "BOX-BOX", "CTN": "CTN-CARTONS", "CARTON": "CTN-CARTONS", "CARTONS": "CTN-CARTONS",
    "DOZ": "DOZ-DOZENS", "DOZEN": "DOZ-DOZENS", "DZN": "DOZ-DOZENS", "GM": "GMS-GRAMMES",
    "GMS": "GMS-GRAMMES", "KG": "KGS-KILOGRAMS", "KGS": "KGS-KILOGRAMS", "LTR": "LTR-LITRES",
    "LTRS": "LTR-LITRES", "ML": "MLT-MILILITRE", "MLT": "MLT-MILILITRE", "MTR": "MTR-METERS",
    "NOS": "NOS-NUMBERS", "PAC": "PAC-PACKS", "PACK": "PAC-PACKS", "PACKS": "PAC-PACKS",
    "PCS": "PCS-PIECES", "PIECES": "PCS-PIECES", "PKT": "PAC-PACKS", "POUCH": "PCS-PIECES",
    "SET": "SET-SETS", "SETS": "SET-SETS", "TIN": "PCS-PIECES", "UNT": "UNT-UNITS",
    "ROLL": "ROL-ROLLS", "ROLLS": "ROL-ROLLS",
}

def escape_xml(val: Optional[str]) -> str:
    """Safely escapes text for Tally XML."""
    if not val:
        return ""
    return saxutils.escape(str(val).strip(), {'"': "&quot;", "'": "&apos;"})

def extract_pan_from_gstin(gstin: Optional[str]) -> Optional[str]:
    """Extracts characters 3 to 12 from 15-character Indian GSTIN."""
    if not gstin:
        return None
    clean = re.sub(r'[^A-Za-z0-9]', '', gstin.strip()).upper()
    if len(clean) == 15 and re.match(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$', clean):
        return clean[2:12]
    return None

def validate_gstin_format(gstin: Optional[str]) -> bool:
    """Validates 15-character GSTIN structure."""
    if not gstin:
        return False
    clean = re.sub(r'[^A-Za-z0-9]', '', gstin.strip()).upper()
    return bool(re.match(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$', clean))

class MasterRoundTripMismatchError(ValueError):
    """Raised when generated XML does not match user saved master draft."""
    pass

class StockItemDraft(BaseModel):
    name: str
    parent_group: str = "Primary"
    base_unit: str = "NOS"
    alternate_unit: Optional[str] = None
    conversion: Optional[int] = None  # 1 BIG = N SMALL (N >= 1)
    hsn_code: Optional[str] = None
    hsn_description: Optional[str] = None
    gst_rate: Decimal = Decimal("0.00")
    taxability: str = "Taxable"  # Taxable, Exempt, Nil Rated
    type_of_supply: str = "Goods"  # Goods, Services
    reporting_uqc: Optional[str] = None
    version: int = 1
    saved_at: Optional[str] = None

class LedgerDraft(BaseModel):
    name: str
    alias: Optional[str] = None
    parent_group: str = "Sundry Creditors"  # Sundry Creditors or Sundry Debtors
    address_lines: List[str] = []
    state: str = "Himachal Pradesh"
    country: str = "India"
    pincode: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    registration_type: str = "Regular"  # Regular, Unregistered/Consumer, Composition
    version: int = 1
    saved_at: Optional[str] = None

# ==============================================================================
# 1. UNIT MASTER GENERATOR & PARSER
# ==============================================================================

def generate_unit_master_xml(symbol: str, uqc: Optional[str] = None) -> str:
    """Generates Tally UNIT master snippet."""
    sym_clean = (symbol or "NOS").strip().upper()
    sym_esc = escape_xml(sym_clean)
    final_uqc = uqc or UQC_MAP.get(sym_clean, f"{sym_clean}-{sym_clean}")
    uqc_esc = escape_xml(final_uqc)

    lines = [
        '    <TALLYMESSAGE xmlns:UDF="TallyUDF">',
        f'     <UNIT NAME="{sym_esc}" RESERVEDNAME="" ACTION="Create">',
        f'      <NAME>{sym_esc}</NAME>',
        f'      <GSTREPUOM>{uqc_esc}</GSTREPUOM>',
        '      <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>',
        '      <REPORTINGUQCDETAILS.LIST>',
        '       <APPLICABLEFROM>20210401</APPLICABLEFROM>',
        f'       <REPORTINGUQCNAME>{uqc_esc}</REPORTINGUQCNAME>',
        '      </REPORTINGUQCDETAILS.LIST>',
        '     </UNIT>',
        '    </TALLYMESSAGE>'
    ]
    return "\n".join(lines)

def parse_unit_master_xml(xml_content: str) -> Dict[str, Any]:
    """Parses a generated UNIT master back into fields."""
    root = ET.fromstring(f"<ROOT>{sanitize_xml_content(xml_content)}</ROOT>")
    unit_el = root.find(".//UNIT")
    if unit_el is None:
        raise ValueError("No <UNIT> found in XML")
    name = (unit_el.findtext("NAME") or unit_el.attrib.get("NAME") or "").strip()
    uqc = (unit_el.findtext("GSTREPUOM") or "").strip()
    return {"name": name, "uqc": uqc}

def verify_unit_round_trip(symbol: str, xml_content: str) -> bool:
    parsed = parse_unit_master_xml(xml_content)
    if parsed["name"].upper() != symbol.strip().upper():
        raise MasterRoundTripMismatchError(f"Unit symbol mismatch: draft '{symbol}' vs XML '{parsed['name']}'")
    return True

# ==============================================================================
# 2. STOCK GROUP MASTER GENERATOR
# ==============================================================================

def generate_stock_group_master_xml(group_name: str, parent: str = "Primary") -> str:
    """Generates Tally STOCKGROUP master snippet."""
    g_esc = escape_xml(group_name)
    p_esc = escape_xml(parent)
    lines = [
        '    <TALLYMESSAGE xmlns:UDF="TallyUDF">',
        f'     <STOCKGROUP NAME="{g_esc}" RESERVEDNAME="" ACTION="Create">',
        f'      <NAME>{g_esc}</NAME>',
        f'      <PARENT>{p_esc}</PARENT>',
        '      <ISADDABLE>Yes</ISADDABLE>',
        '     </STOCKGROUP>',
        '    </TALLYMESSAGE>'
    ]
    return "\n".join(lines)

# ==============================================================================
# 3. STOCK ITEM MASTER GENERATOR & PARSER (PRD Addendum 6 Sections 3, 4, 5)
# ==============================================================================

def generate_stock_item_master_xml(draft: StockItemDraft) -> str:
    """
    Generates authentic Tally Stock Item XML strictly adhering to PRD Addendum 6:
    - Base unit = SMALL unit
    - Alternate unit = BIG unit
    - Formula in Tally: 1 BIG = N SMALL -> <DENOMINATOR> N</DENOMINATOR>, <CONVERSION> 1</CONVERSION>
    - HSN: Specify Details Here (with HSNCODE and optional HSN description)
    - GST: Specify Details Here (Taxable / Nil Rated / Exempt with CGST/SGST/IGST rates)
    - Under: Parent group
    """
    name_esc = escape_xml(draft.name)
    parent_esc = escape_xml(draft.parent_group or "Primary")
    base_uom_esc = escape_xml(draft.base_unit.upper())
    supply_esc = escape_xml(draft.type_of_supply or "Goods")
    taxability_val = draft.taxability.strip() if draft.taxability else "Taxable"
    hsn_esc = escape_xml(draft.hsn_code or "")
    hsn_desc_esc = escape_xml(draft.hsn_description or "")

    lines = [
        '    <TALLYMESSAGE xmlns:UDF="TallyUDF">',
        f'     <STOCKITEM NAME="{name_esc}" RESERVEDNAME="" ACTION="Create">',
        f'      <NAME>{name_esc}</NAME>',
        f'      <PARENT>{parent_esc}</PARENT>',
        f'      <BASEUNITS>{base_uom_esc}</BASEUNITS>',
    ]

    # Alternate unit & pack conversion (PRD Addendum 6 Section 5)
    # 1 BIG = N SMALL -> <DENOMINATOR> N</DENOMINATOR>, <CONVERSION> 1</CONVERSION>
    if draft.alternate_unit and draft.conversion and draft.conversion >= 1:
        alt_uom_esc = escape_xml(draft.alternate_unit.upper())
        if alt_uom_esc != base_uom_esc:
            n_conv = int(draft.conversion)
            lines.append(f'      <ADDITIONALUNITS>{alt_uom_esc}</ADDITIONALUNITS>')
            lines.append(f'      <DENOMINATOR> {n_conv}</DENOMINATOR>')
            lines.append('      <CONVERSION> 1</CONVERSION>')

    lines.extend([
        '      <GSTAPPLICABLE>&#4; Applicable</GSTAPPLICABLE>',
        f'      <GSTTYPEOFSUPPLY>{supply_esc}</GSTTYPEOFSUPPLY>',
        '      <ISCOSTCENTRESON>No</ISCOSTCENTRESON>',
        '      <ISBATCHWISEON>No</ISBATCHWISEON>',
        '      <ISPERISHABLEON>No</ISPERISHABLEON>',
        '      <OPENINGBALANCE>0</OPENINGBALANCE>'
    ])

    # GST Rate & Related Details: ALWAYS Specify Details Here
    tot_rate = Decimal(str(draft.gst_rate or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    cgst_rate = (tot_rate / Decimal("2.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sgst_rate = (tot_rate - cgst_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    t_cap = "Taxable"
    if taxability_val.lower() == "exempt":
        t_cap = "Exempt"
    elif taxability_val.lower() == "nil rated" or (tot_rate == Decimal("0.00") and taxability_val.lower() != "taxable"):
        t_cap = "Nil Rated"

    lines.extend([
        '      <GSTDETAILS.LIST>',
        '       <APPLICABLEFROM>20210401</APPLICABLEFROM>',
        '       <CALCULATIONTYPE>On Value</CALCULATIONTYPE>',
        f'       <TAXABILITY>{t_cap}</TAXABILITY>',
        '       <SRCOFGSTDETAILS>Specify Details Here</SRCOFGSTDETAILS>',
        '       <STATEWISEDETAILS.LIST>',
        '        <STATENAME>&#4; Any</STATENAME>',
        '        <RATEDETAILS.LIST>',
        '         <GSTRATEDUTYHEAD>CGST</GSTRATEDUTYHEAD>',
        '         <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>',
        f'         <GSTRATE> {cgst_rate:.2f}</GSTRATE>',
        '        </RATEDETAILS.LIST>',
        '        <RATEDETAILS.LIST>',
        '         <GSTRATEDUTYHEAD>SGST/UTGST</GSTRATEDUTYHEAD>',
        '         <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>',
        f'         <GSTRATE> {sgst_rate:.2f}</GSTRATE>',
        '        </RATEDETAILS.LIST>',
        '        <RATEDETAILS.LIST>',
        '         <GSTRATEDUTYHEAD>IGST</GSTRATEDUTYHEAD>',
        '         <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>',
        f'         <GSTRATE> {tot_rate:.2f}</GSTRATE>',
        '        </RATEDETAILS.LIST>',
        '       </STATEWISEDETAILS.LIST>',
        '      </GSTDETAILS.LIST>'
    ])

    # HSN/SAC Details: ALWAYS Specify Details Here
    lines.extend([
        '      <HSNDETAILS.LIST>',
        '       <APPLICABLEFROM>20210401</APPLICABLEFROM>',
        f'       <HSNCODE>{hsn_esc}</HSNCODE>',
    ])
    if hsn_desc_esc:
        lines.append(f'       <HSN>{hsn_desc_esc}</HSN>')
    lines.extend([
        '       <SRCOFHSNDETAILS>Specify Details Here</SRCOFHSNDETAILS>',
        '      </HSNDETAILS.LIST>'
    ])

    lines.extend([
        '     </STOCKITEM>',
        '    </TALLYMESSAGE>'
    ])
    return "\n".join(lines)

def parse_stock_item_master_xml(xml_content: str) -> Dict[str, Any]:
    """
    Parses a generated Stock Item XML snippet back into structured fields.
    Used for round-trip validation and 'How it will look in Tally' preview.
    """
    root = ET.fromstring(f"<ROOT>{sanitize_xml_content(xml_content)}</ROOT>")
    item_el = root.find(".//STOCKITEM")
    if item_el is None:
        raise ValueError("No <STOCKITEM> found in XML snippet.")

    name = (item_el.findtext("NAME") or item_el.attrib.get("NAME") or "").strip()
    parent = (item_el.findtext("PARENT") or "Primary").strip()
    base_unit = (item_el.findtext("BASEUNITS") or "").strip()
    alt_unit = item_el.findtext("ADDITIONALUNITS")
    alt_unit = alt_unit.strip() if alt_unit else None

    # Conversion parsing: in Tally export, <DENOMINATOR> holds N, <CONVERSION> holds 1
    # formula: 1 ALT = N BASE
    conv_val = None
    denom_txt = item_el.findtext("DENOMINATOR")
    conv_txt = item_el.findtext("CONVERSION")
    if denom_txt and conv_txt:
        try:
            d_int = int(denom_txt.strip())
            c_int = int(conv_txt.strip())
            # If CONVERSION is 1 and DENOMINATOR is N: N is pack count
            if c_int == 1 and d_int >= 1:
                conv_val = d_int
            elif d_int == 1 and c_int >= 1:
                # Upside down case!
                conv_val = c_int
        except Exception:
            pass

    supply_type = (item_el.findtext("GSTTYPEOFSUPPLY") or "Goods").strip()

    # HSN details
    hsn_node = item_el.find(".//HSNDETAILS.LIST")
    hsn_code = (hsn_node.findtext("HSNCODE") if hsn_node is not None else "") or ""
    hsn_desc = (hsn_node.findtext("HSN") if hsn_node is not None else "") or ""
    hsn_src = (hsn_node.findtext("SRCOFHSNDETAILS") if hsn_node is not None else "") or ""

    # GST details
    gst_node = item_el.find(".//GSTDETAILS.LIST")
    taxability = (gst_node.findtext("TAXABILITY") if gst_node is not None else "Taxable") or "Taxable"
    gst_src = (gst_node.findtext("SRCOFGSTDETAILS") if gst_node is not None else "") or ""

    igst_rate = Decimal("0.00")
    cgst_rate = Decimal("0.00")
    sgst_rate = Decimal("0.00")
    if gst_node is not None:
        for rnode in gst_node.findall(".//RATEDETAILS.LIST"):
            head = (rnode.findtext("GSTRATEDUTYHEAD") or "").strip().upper()
            rate_s = (rnode.findtext("GSTRATE") or "").strip()
            try:
                r_dec = Decimal(rate_s).quantize(Decimal("0.01"))
                if head == "IGST":
                    igst_rate = r_dec
                elif head == "CGST":
                    cgst_rate = r_dec
                elif "SGST" in head:
                    sgst_rate = r_dec
            except Exception:
                pass

    tot_gst = igst_rate if igst_rate > Decimal("0.00") else (cgst_rate + sgst_rate)

    return {
        "name": name,
        "parent_group": parent,
        "base_unit": base_unit,
        "alternate_unit": alt_unit,
        "conversion": conv_val,
        "conversion_formula": f"1 {alt_unit} = {conv_val} {base_unit}" if alt_unit and conv_val else None,
        "hsn_code": hsn_code.strip() if hsn_code else None,
        "hsn_description": hsn_desc.strip() if hsn_desc else None,
        "hsn_source": hsn_src.strip(),
        "taxability": taxability.strip(),
        "gst_source": gst_src.strip(),
        "gst_rate": tot_gst,
        "cgst_rate": cgst_rate,
        "sgst_rate": sgst_rate,
        "type_of_supply": supply_type
    }

def verify_stock_item_round_trip(draft: StockItemDraft, xml_content: str) -> bool:
    """
    Mandatory Round-Trip Check (PRD Addendum 6 Section 3.3):
    Compares parsed XML against the user saved draft.
    Raises MasterRoundTripMismatchError if any field differs.
    """
    parsed = parse_stock_item_master_xml(xml_content)

    # 1. Name
    if parsed["name"].lower() != draft.name.strip().lower():
        raise MasterRoundTripMismatchError(f"Item name mismatch: draft '{draft.name}' vs XML '{parsed['name']}'")

    # 2. Parent Group
    expected_parent = (draft.parent_group or "Primary").strip().lower()
    if parsed["parent_group"].lower() != expected_parent:
        raise MasterRoundTripMismatchError(f"Stock group mismatch: draft '{draft.parent_group}' vs XML '{parsed['parent_group']}'")

    # 3. Base Unit
    if parsed["base_unit"].upper() != draft.base_unit.strip().upper():
        raise MasterRoundTripMismatchError(f"Base unit mismatch: draft '{draft.base_unit}' vs XML '{parsed['base_unit']}'")

    # 4. Alternate Unit & Conversion
    if draft.alternate_unit and draft.conversion and draft.conversion >= 1:
        if not parsed["alternate_unit"] or parsed["alternate_unit"].upper() != draft.alternate_unit.strip().upper():
            raise MasterRoundTripMismatchError(f"Alternate unit mismatch: draft '{draft.alternate_unit}' vs XML '{parsed['alternate_unit']}'")
        if parsed["conversion"] != int(draft.conversion):
            raise MasterRoundTripMismatchError(f"Conversion multiplier mismatch: draft '{draft.conversion}' vs XML '{parsed['conversion']}'")
    else:
        if parsed["alternate_unit"]:
            raise MasterRoundTripMismatchError(f"Unexpected alternate unit in XML: '{parsed['alternate_unit']}'")

    # 5. HSN Code
    if draft.hsn_code and draft.hsn_code.strip():
        if parsed["hsn_code"] != draft.hsn_code.strip():
            raise MasterRoundTripMismatchError(f"HSN code mismatch: draft '{draft.hsn_code}' vs XML '{parsed['hsn_code']}'")
        if parsed["hsn_source"] != "Specify Details Here":
            raise MasterRoundTripMismatchError(f"HSN details source is '{parsed['hsn_source']}', expected 'Specify Details Here'")

    # 6. Taxability & GST Rate
    expected_tax = draft.taxability.strip().lower()
    if expected_tax == "taxable":
        if parsed["taxability"].lower() != "taxable":
            raise MasterRoundTripMismatchError(f"Taxability mismatch: draft '{draft.taxability}' vs XML '{parsed['taxability']}'")
        expected_rate = Decimal(str(draft.gst_rate or 0)).quantize(Decimal("0.01"))
        if abs(parsed["gst_rate"] - expected_rate) > Decimal("0.05"):
            raise MasterRoundTripMismatchError(f"GST rate mismatch: draft {expected_rate}% vs XML {parsed['gst_rate']}%")
    elif expected_tax in ("exempt", "nil rated"):
        if parsed["taxability"].lower() not in ("exempt", "nil rated"):
            raise MasterRoundTripMismatchError(f"Taxability mismatch: draft '{draft.taxability}' vs XML '{parsed['taxability']}'")

    if parsed["gst_source"] != "Specify Details Here":
        raise MasterRoundTripMismatchError(f"GST details source is '{parsed['gst_source']}', expected 'Specify Details Here'")

    # 7. Type of Supply
    expected_supply = (draft.type_of_supply or "Goods").strip().lower()
    if parsed["type_of_supply"].lower() != expected_supply:
        raise MasterRoundTripMismatchError(f"Type of supply mismatch: draft '{draft.type_of_supply}' vs XML '{parsed['type_of_supply']}'")

    return True

# ==============================================================================
# 4. LEDGER MASTER GENERATOR & PARSER (PRD Addendum 6 Section 6)
# ==============================================================================

def generate_ledger_master_xml(draft: LedgerDraft) -> str:
    """
    Generates authentic Tally Ledger XML strictly adhering to PRD Addendum 6 Section 6:
    - Mirror Tally's Ledger Creation screen
    - State: from 2-digit GSTIN state code -> full Tally state name
    - PAN: chars 3 to 12 of GSTIN
    - Registration type: Regular, Unregistered/Consumer, or Composition
    - Address list, Pincode, Country=India
    - Complete LEDGSTREGDETAILS and LEDMAILINGDETAILS matching real Tally export
    """
    name_esc = escape_xml(draft.name)
    parent_esc = escape_xml(draft.parent_group or "Sundry Creditors")
    country_esc = escape_xml(draft.country or "India")

    # State Normalization (trust GSTIN state code if available)
    state_name = draft.state or "Himachal Pradesh"
    if draft.gstin and len(draft.gstin.strip()) >= 2:
        gstin_code = draft.gstin.strip()[:2]
        s_norm, _ = normalize_state(gstin_code)
        if s_norm:
            state_name = s_norm
    else:
        s_norm, _ = normalize_state(state_name)
        if s_norm:
            state_name = s_norm

    state_esc = escape_xml(state_name)
    pin_esc = escape_xml(draft.pincode or "")
    gstin_clean = draft.gstin.strip().upper() if draft.gstin else ""
    gstin_esc = escape_xml(gstin_clean)

    # PAN extraction
    pan_val = draft.pan or extract_pan_from_gstin(gstin_clean) or ""
    pan_esc = escape_xml(pan_val)

    # Registration type
    reg_type = draft.registration_type
    if not reg_type or reg_type == "Unknown":
        reg_type = "Regular" if gstin_clean else "Unregistered/Consumer"
    reg_type_esc = escape_xml(reg_type)

    lines = [
        '    <TALLYMESSAGE xmlns:UDF="TallyUDF">',
        f'     <LEDGER NAME="{name_esc}" RESERVEDNAME="" ACTION="Create">',
        f'      <NAME>{name_esc}</NAME>',
        f'      <PARENT>{parent_esc}</PARENT>',
        f'      <COUNTRYOFRESIDENCE>{country_esc}</COUNTRYOFRESIDENCE>',
        '      <LEDGERCOUNTRYISDCODE>+91</LEDGERCOUNTRYISDCODE>',
        f'      <LEDSTATENAME>{state_esc}</LEDSTATENAME>',
    ]

    if pan_esc:
        lines.append(f'      <INCOMETAXNUMBER>{pan_esc}</INCOMETAXNUMBER>')

    if gstin_esc:
        lines.append(f'      <PARTYGSTIN>{gstin_esc}</PARTYGSTIN>')

    lines.append(f'      <GSTREGISTRATIONTYPE>{reg_type_esc}</GSTREGISTRATIONTYPE>')

    # Addresses
    if draft.address_lines:
        lines.append('      <ADDRESS.LIST TYPE="String">')
        for addr in draft.address_lines:
            a_clean = addr.strip()
            if a_clean:
                lines.append(f'       <ADDRESS>{escape_xml(a_clean)}</ADDRESS>')
        lines.append('      </ADDRESS.LIST>')

    if pin_esc:
        lines.append(f'      <PINCODE>{pin_esc}</PINCODE>')

    # Complete LEDGSTREGDETAILS.LIST (matching real Tally export)
    lines.extend([
        '      <LEDGSTREGDETAILS.LIST>',
        '       <APPLICABLEFROM>20210401</APPLICABLEFROM>',
        f'       <GSTREGISTRATIONTYPE>{reg_type_esc}</GSTREGISTRATIONTYPE>',
        f'       <STATE>{state_esc}</STATE>',
        f'       <PLACEOFSUPPLY>{state_esc}</PLACEOFSUPPLY>',
    ])
    if gstin_esc:
        lines.append(f'       <GSTIN>{gstin_esc}</GSTIN>')
    lines.extend([
        '       <ISOTHTERRITORYASSESSEE>No</ISOTHTERRITORYASSESSEE>',
        '      </LEDGSTREGDETAILS.LIST>'
    ])

    # Complete LEDMAILINGDETAILS.LIST (matching real Tally export)
    lines.extend([
        '      <LEDMAILINGDETAILS.LIST>',
        '       <APPLICABLEFROM>20210401</APPLICABLEFROM>',
        f'       <MAILINGNAME>{name_esc}</MAILINGNAME>',
        f'       <STATE>{state_esc}</STATE>',
        f'       <COUNTRY>{country_esc}</COUNTRY>',
    ])
    if pin_esc:
        lines.append(f'       <PINCODE>{pin_esc}</PINCODE>')
    if draft.address_lines:
        lines.append('       <ADDRESS.LIST TYPE="String">')
        for addr in draft.address_lines:
            a_clean = addr.strip()
            if a_clean:
                lines.append(f'        <ADDRESS>{escape_xml(a_clean)}</ADDRESS>')
        lines.append('       </ADDRESS.LIST>')
    lines.extend([
        '      </LEDMAILINGDETAILS.LIST>',
        '     </LEDGER>',
        '    </TALLYMESSAGE>'
    ])

    return "\n".join(lines)

def parse_ledger_master_xml(xml_content: str) -> Dict[str, Any]:
    """Parses a generated Ledger XML snippet back into structured fields."""
    root = ET.fromstring(f"<ROOT>{sanitize_xml_content(xml_content)}</ROOT>")
    led_el = root.find(".//LEDGER")
    if led_el is None:
        raise ValueError("No <LEDGER> found in XML snippet.")

    name = (led_el.findtext("NAME") or led_el.attrib.get("NAME") or "").strip()
    parent = (led_el.findtext("PARENT") or "").strip()
    state = (led_el.findtext("LEDSTATENAME") or "").strip()
    country = (led_el.findtext("COUNTRYOFRESIDENCE") or "India").strip()
    pan = (led_el.findtext("INCOMETAXNUMBER") or "").strip()
    gstin = (led_el.findtext("PARTYGSTIN") or "").strip()
    reg_type = (led_el.findtext("GSTREGISTRATIONTYPE") or "").strip()
    pincode = (led_el.findtext("PINCODE") or "").strip()

    address_lines = []
    addr_node = led_el.find(".//ADDRESS.LIST")
    if addr_node is not None:
        for a in addr_node.findall("ADDRESS"):
            txt = (a.text or "").strip()
            if txt:
                address_lines.append(txt)

    return {
        "name": name,
        "parent_group": parent,
        "state": state,
        "country": country,
        "pan": pan if pan else None,
        "gstin": gstin if gstin else None,
        "registration_type": reg_type,
        "pincode": pincode if pincode else None,
        "address_lines": address_lines
    }

def verify_ledger_round_trip(draft: LedgerDraft, xml_content: str) -> bool:
    """Mandatory Round-Trip Check for Ledgers (PRD Addendum 6 Section 3.3)."""
    parsed = parse_ledger_master_xml(xml_content)

    if parsed["name"].lower() != draft.name.strip().lower():
        raise MasterRoundTripMismatchError(f"Ledger name mismatch: draft '{draft.name}' vs XML '{parsed['name']}'")

    if parsed["parent_group"].lower() != draft.parent_group.strip().lower():
        raise MasterRoundTripMismatchError(f"Ledger group mismatch: draft '{draft.parent_group}' vs XML '{parsed['parent_group']}'")

    if parsed["state"].lower() != draft.state.strip().lower():
        # Check if draft had state normalized
        s_norm, _ = normalize_state(draft.state)
        if parsed["state"].lower() != (s_norm or "").lower():
            raise MasterRoundTripMismatchError(f"Ledger state mismatch: draft '{draft.state}' vs XML '{parsed['state']}'")

    if draft.gstin and draft.gstin.strip():
        if parsed["gstin"] != draft.gstin.strip().upper():
            raise MasterRoundTripMismatchError(f"GSTIN mismatch: draft '{draft.gstin}' vs XML '{parsed['gstin']}'")

    if draft.pan and draft.pan.strip():
        if parsed["pan"] != draft.pan.strip().upper():
            raise MasterRoundTripMismatchError(f"PAN mismatch: draft '{draft.pan}' vs XML '{parsed['pan']}'")

    expected_reg = draft.registration_type
    if not expected_reg:
        expected_reg = "Regular" if draft.gstin else "Unregistered/Consumer"
    if parsed["registration_type"].lower() != expected_reg.lower():
        raise MasterRoundTripMismatchError(f"Registration type mismatch: draft '{expected_reg}' vs XML '{parsed['registration_type']}'")

    return True
