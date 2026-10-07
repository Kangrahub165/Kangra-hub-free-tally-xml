"""
State Normalizer for Indian GST & Tally XML.
Implements PRD Addendum 1 Part 1:
- Normalizes all Place of Supply / State variations to canonical full Tally state names.
- Uses GSTIN 2-digit prefix as primary truth, followed by explicit state codes and alias matching.
- Compares normalized state codes (not raw text) for intra-state (CGST+SGST) vs inter-state (IGST).
"""

import re
from typing import Optional, Tuple, Dict, Any, List
from app.invoices.model import PartyInfo, InvoiceDocument

# Exact Canonical Tally State Names from PRD Addendum 1 Section 1.5
TALLY_STATE_TABLE: Dict[str, str] = {
    "01": "Jammu & Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "25": "Dadra & Nagar Haveli and Daman & Diu",  # Old code 25 merged into 26
    "26": "Dadra & Nagar Haveli and Daman & Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman & Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
    "97": "Other Territory"
}

# Clean normalized token -> 2-digit GST state code
STATE_ALIASES: Dict[str, str] = {
    # 01 Jammu & Kashmir
    "01": "01", "JK": "01", "J&K": "01", "J AND K": "01", "J K": "01",
    "JAMMU": "01", "KASHMIR": "01", "JAMMU & KASHMIR": "01", "JAMMU AND KASHMIR": "01",

    # 02 Himachal Pradesh
    "02": "02", "HP": "02", "H P": "02", "HIMACHAL": "02", "HIMACHAL PRADESH": "02",
    "H PRADESH": "02", "HPRADESH": "02", "HIMACHALPRADESH": "02",

    # 03 Punjab
    "03": "03", "PB": "03", "P B": "03", "PUNJAB": "03", "PUN": "03",

    # 04 Chandigarh
    "04": "04", "CH": "04", "CHD": "04", "CHANDIGARH": "04",

    # 05 Uttarakhand
    "05": "05", "UK": "05", "UA": "05", "U K": "05", "UTTARAKHAND": "05",
    "UTTARANCHAL": "05", "UTTRAKHAND": "05",

    # 06 Haryana
    "06": "06", "HR": "06", "H R": "06", "HARYANA": "06", "HAR": "06",

    # 07 Delhi
    "07": "07", "DL": "07", "D L": "07", "DELHI": "07", "NEW DELHI": "07",
    "NEWDELHI": "07", "NCT OF DELHI": "07", "ND": "07",

    # 08 Rajasthan
    "08": "08", "RJ": "08", "R J": "08", "RAJASTHAN": "08", "RAJ": "08",

    # 09 Uttar Pradesh
    "09": "09", "UP": "09", "U P": "09", "UTTAR PRADESH": "09", "UTTARPRADESH": "09",
    "U PRADESH": "09",

    # 10 Bihar
    "10": "10", "BR": "10", "BHR": "10", "BIHAR": "10",

    # 11 Sikkim
    "11": "11", "SK": "11", "SIKKIM": "11",

    # 12 Arunachal Pradesh
    "12": "12", "AR": "12", "ARUNACHAL": "12", "ARUNACHAL PRADESH": "12",

    # 13 Nagaland
    "13": "13", "NL": "13", "NAGALAND": "13",

    # 14 Manipur
    "14": "14", "MN": "14", "MANIPUR": "14",

    # 15 Mizoram
    "15": "15", "MZ": "15", "MIZORAM": "15",

    # 16 Tripura
    "16": "16", "TR": "16", "TRIPURA": "16",

    # 17 Meghalaya
    "17": "17", "ML": "17", "MEGHALAYA": "17",

    # 18 Assam
    "18": "18", "AS": "18", "ASSAM": "18",

    # 19 West Bengal
    "19": "19", "WB": "19", "W B": "19", "WEST BENGAL": "19", "WESTBENGAL": "19",

    # 20 Jharkhand
    "20": "20", "JH": "20", "JHARKHAND": "20",

    # 21 Odisha
    "21": "21", "OR": "21", "OD": "21", "ODISHA": "21", "ORISSA": "21",

    # 22 Chhattisgarh
    "22": "22", "CG": "22", "CT": "22", "CHHATTISGARH": "22", "CHATTISGARH": "22",

    # 23 Madhya Pradesh
    "23": "23", "MP": "23", "M P": "23", "MADHYA PRADESH": "23", "MADHYAPRADESH": "23",
    "M PRADESH": "23",

    # 24 Gujarat
    "24": "24", "GJ": "24", "GUJARAT": "24", "GUJ": "24",

    # 25 & 26 Dadra & Nagar Haveli and Daman & Diu
    "25": "26", "26": "26", "DN": "26", "DD": "26", "DAMAN": "26", "DIU": "26",
    "DADRA": "26", "NAGAR HAVELI": "26", "DAMAN & DIU": "26", "DAMAN AND DIU": "26",
    "DADRA & NAGAR HAVELI": "26", "DADRA AND NAGAR HAVELI": "26",
    "DADRA & NAGAR HAVELI AND DAMAN & DIU": "26", "DADRA AND NAGAR HAVELI AND DAMAN AND DIU": "26",

    # 27 Maharashtra
    "27": "27", "MH": "27", "MAHARASHTRA": "27", "MAH": "27",

    # 29 Karnataka
    "29": "29", "KA": "29", "KARNATAKA": "29", "KAR": "29",

    # 30 Goa
    "30": "30", "GA": "30", "GOA": "30",

    # 31 Lakshadweep
    "31": "31", "LD": "31", "LAKSHADWEEP": "31",

    # 32 Kerala
    "32": "32", "KL": "32", "KERALA": "32", "KER": "32",

    # 33 Tamil Nadu
    "33": "33", "TN": "33", "T N": "33", "TAMIL NADU": "33", "TAMILNADU": "33",

    # 34 Puducherry
    "34": "34", "PY": "34", "PUDUCHERRY": "34", "PONDICHERRY": "34",

    # 35 Andaman & Nicobar Islands
    "35": "35", "AN": "35", "ANDAMAN": "35", "NICOBAR": "35",
    "ANDAMAN & NICOBAR ISLANDS": "35", "ANDAMAN AND NICOBAR ISLANDS": "35",

    # 36 Telangana
    "36": "36", "TS": "36", "TG": "36", "TELANGANA": "36",

    # 37 Andhra Pradesh
    "37": "37", "AP": "37", "A P": "37", "ANDHRA PRADESH": "37", "ANDHRAPRADESH": "37",
    "A PRADESH": "37",

    # 38 Ladakh
    "38": "38", "LA": "38", "LADAKH": "38",

    # 97 Other Territory
    "97": "97", "OT": "97", "OTHER TERRITORY": "97"
}


def clean_state_text(raw: Optional[str]) -> str:
    """Cleans raw state text: strips punctuation, extra spaces, and common boilerplate words."""
    if not raw:
        return ""
    text = str(raw).strip().upper()
    # Replace dots, commas, hyphens, colons, slashes with spaces
    text = re.sub(r'[\.,\-:/\(\)\[\]]', ' ', text)
    # Remove words: STATE, CODE, NAME, NO
    text = re.sub(r'\b(STATE|CODE|NAME|NO)\b', ' ', text)
    # Collapse whitespace
    return " ".join(text.split())


def normalize_state(raw: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Normalizes any state string/code into (canonical_tally_name, state_code).
    Handles:
    - 'H.P.' -> ('Himachal Pradesh', '02')
    - 'Himachal Pradesh, Code : 02' -> ('Himachal Pradesh', '02')
    - '02' -> ('Himachal Pradesh', '02')
    - 'UP' -> ('Uttar Pradesh', '09')
    - 'Jammu and Kashmir' -> ('Jammu & Kashmir', '01')
    Returns (None, None) if unresolvable.
    """
    if not raw:
        return None, None

    raw_str = str(raw).strip()
    if not raw_str:
        return None, None

    # 1. Direct check if input is a 2-digit code
    m_code = re.search(r'\b(0[1-9]|[1-2][0-9]|3[0-8]|97)\b', raw_str)
    if m_code:
        code = m_code.group(1)
        name = TALLY_STATE_TABLE.get(code)
        if name:
            # If the raw string contains only the code or "Code: NN" or state text that matches code
            cleaned = clean_state_text(raw_str)
            if cleaned == code or not cleaned:
                return name, code

    cleaned = clean_state_text(raw_str)
    if not cleaned:
        if m_code:
            code = m_code.group(1)
            return TALLY_STATE_TABLE.get(code), code
        return None, None

    # 2. Check exact alias match
    if cleaned in STATE_ALIASES:
        code = STATE_ALIASES[cleaned]
        return TALLY_STATE_TABLE.get(code), code

    # 3. Check alias after removing all whitespace (e.g. "H P" -> "HP")
    no_space = cleaned.replace(" ", "")
    if no_space in STATE_ALIASES:
        code = STATE_ALIASES[no_space]
        return TALLY_STATE_TABLE.get(code), code

    # 4. Check if code extracted via regex matches table
    if m_code:
        code = m_code.group(1)
        name = TALLY_STATE_TABLE.get(code)
        if name:
            return name, code

    # 5. Check if any alias is contained as a distinct word/phrase
    # Sort aliases by length descending so longer matches (e.g. "HIMACHAL PRADESH") match first
    for alias in sorted(STATE_ALIASES.keys(), key=len, reverse=True):
        if len(alias) >= 3 and alias in cleaned:
            code = STATE_ALIASES[alias]
            return TALLY_STATE_TABLE.get(code), code

    return None, None


def derive_state_from_gstin(gstin: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Derives canonical state name and code from GSTIN's first two digits."""
    if not gstin:
        return None, None
    clean = re.sub(r'[^0-9A-Za-z]', '', str(gstin)).strip().upper()
    if len(clean) >= 2 and clean[:2].isdigit():
        code = clean[:2]
        if code in TALLY_STATE_TABLE:
            return TALLY_STATE_TABLE[code], code
    return None, None

get_state_from_gstin = derive_state_from_gstin
TALLY_CANONICAL_STATES = TALLY_STATE_TABLE


def resolve_party_state(
    party: PartyInfo,
    is_company: bool = False,
    default_company_state: str = "Himachal Pradesh",
    default_company_code: str = "02"
) -> Tuple[str, str, Optional[str]]:
    """
    Section 1.3 Priority Order Resolution for Party State:
    1. GSTIN first two digits (most reliable).
    2. Explicit text on invoice ('State Name : ..., Code : NN').
    3. If sources disagree (e.g. GSTIN 02 vs text Punjab), GSTIN wins + warning.
    4. If nothing found: for company use default ('Himachal Pradesh'), for party flag 'State missing'.
    Returns: (canonical_name, state_code, warning_or_None)
    """
    warning = None

    # 1. From GSTIN
    gstin_name, gstin_code = derive_state_from_gstin(party.gstin)

    # 2. From raw text
    text_name, text_code = normalize_state(party.state or party.source_text)

    # Reconcile priority & conflict check
    if gstin_code:
        final_code = gstin_code
        final_name = gstin_name
        if text_code and text_code != gstin_code:
            warning = (
                f"State mismatch for party '{party.name or party.gstin}': "
                f"GSTIN prefix indicates {gstin_name} ({gstin_code}), but invoice text states {text_name} ({text_code}). "
                f"GSTIN state ({gstin_name}) was used per GST law."
            )
    elif text_code:
        final_code = text_code
        final_name = text_name
    elif is_company:
        final_code = default_company_code
        final_name = default_company_state
    else:
        final_code = ""
        final_name = ""
        warning = f"State missing for party '{party.name or 'Unknown'}'. Please review."

    return final_name or "", final_code or "", warning


def are_states_intra_state(supp_code: Optional[str], buy_code: Optional[str]) -> bool:
    """
    Section 1.7: Compares normalized 2-digit state codes.
    Never compares raw strings.
    Returns True for intra-state (CGST + SGST), False for inter-state (IGST).
    """
    if not supp_code or not buy_code:
        return True  # Default to intra-state if code missing
    return str(supp_code).strip() == str(buy_code).strip()


def normalize_document_states(
    doc: InvoiceDocument,
    company_gstin: Optional[str] = "02AWLPK8092M1Z0",
    default_company_state: str = "Himachal Pradesh",
    default_company_code: str = "02"
) -> InvoiceDocument:
    """
    Applies state normalizer across the entire InvoiceDocument (Section 1.6):
    - doc.supplier.state and doc.supplier.state_code
    - doc.buyer.state and doc.buyer.state_code
    - doc.place_of_supply
    Ensures no short forms like 'H.P.' ever survive into Tally XML or Review UI.
    """
    # 1. Determine which party is Our Company
    clean_co = (company_gstin or "02AWLPK8092M1Z0").strip().upper()
    is_supp_company = bool(doc.supplier.gstin and doc.supplier.gstin.strip().upper() == clean_co)
    is_buy_company = bool(doc.buyer.gstin and doc.buyer.gstin.strip().upper() == clean_co)

    # 2. Resolve Supplier State
    s_name, s_code, s_warn = resolve_party_state(
        doc.supplier,
        is_company=is_supp_company or doc.invoice_type == "SALES",
        default_company_state=default_company_state,
        default_company_code=default_company_code
    )
    doc.supplier.state = s_name
    doc.supplier.state_code = s_code
    if s_warn:
        doc.warnings.append(s_warn)

    # 3. Resolve Buyer State
    b_name, b_code, b_warn = resolve_party_state(
        doc.buyer,
        is_company=is_buy_company or doc.invoice_type == "PURCHASE",
        default_company_state=default_company_state,
        default_company_code=default_company_code
    )
    doc.buyer.state = b_name
    doc.buyer.state_code = b_code
    if b_warn:
        doc.warnings.append(b_warn)

    # 4. Resolve Place of Supply (Section 1.3 & 1.6)
    # If explicit place of supply exists on doc, normalize it
    pos_name, pos_code = normalize_state(doc.place_of_supply)
    if pos_name:
        doc.place_of_supply = pos_name
    else:
        # Destination of supply is Buyer state in Sales/Purchase
        doc.place_of_supply = b_name or s_name or default_company_state

    return doc
