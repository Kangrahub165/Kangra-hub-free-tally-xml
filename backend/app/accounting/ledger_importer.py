import re
import json
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Optional, Tuple, Any
from pydantic import BaseModel, Field

class ImportedGroup(BaseModel):
    name: str
    parent: Optional[str] = None
    guid: Optional[str] = None

class ImportedLedger(BaseModel):
    name: str
    normalized_name: str
    group: Optional[str] = "Primary"
    parent_group: Optional[str] = None
    opening_balance: Optional[Decimal] = None
    party_gstin: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None
    guid: Optional[str] = None
    aliases: List[str] = []
    source_format: str = "MANUAL"

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v)
        }

class LedgerImportResult(BaseModel):
    detected_format: str
    total_imported: int
    total_ledgers: int = 0
    total_groups: int = 0
    groups: List[ImportedGroup] = []
    ledgers: List[ImportedLedger] = []
    duplicates: int = 0
    conflicts: List[str] = []
    needs_review: bool = False
    error: Optional[str] = None

class _SafeHTMLTableParser(HTMLParser):
    """
    Safely parses HTML tables to extract ledger rows without executing scripts.
    """
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_tr = False
        self.in_td = False
        self.in_script = False
        self.current_row: List[str] = []
        self.current_cell: List[str] = []
        self.rows: List[List[str]] = []

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        if tag_lower == "script":
            self.in_script = True
        elif tag_lower == "table":
            self.in_table = True
        elif tag_lower == "tr":
            self.in_tr = True
            self.current_row = []
        elif tag_lower in ("td", "th"):
            self.in_td = True
            self.current_cell = []

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower == "script":
            self.in_script = False
        elif tag_lower == "table":
            self.in_table = False
        elif tag_lower == "tr":
            self.in_tr = False
            if self.current_row:
                self.rows.append(self.current_row)
        elif tag_lower in ("td", "th"):
            self.in_td = False
            cell_text = " ".join("".join(self.current_cell).split())
            self.current_row.append(cell_text)

    def handle_data(self, data):
        if self.in_td and not self.in_script:
            self.current_cell.append(data)

def normalize_ledger_name(name: str) -> str:
    """Normalizes whitespace and converts to uppercase for comparison."""
    return " ".join(name.strip().split()).upper()

def detect_ledger_format(content: str, filename: Optional[str] = None) -> str:
    """
    Inspects content headers, signatures, and file extensions to detect format:
    Returns 'XML', 'JSON', or 'HTML'.
    Raises ValueError if unsupported.
    """
    stripped = content.strip()
    fn_lower = (filename or "").lower()

    if stripped.startswith("{") or stripped.startswith("["):
        return "JSON"

    if stripped.startswith("<?xml") or "<ENVELOPE" in stripped.upper() or "<TALLYMESSAGE" in stripped.upper() or "<LEDGER" in stripped.upper():
        return "XML"

    if "<!DOCTYPE HTML" in stripped.upper() or "<HTML" in stripped.upper() or "<TABLE" in stripped.upper() or "<TR" in stripped.upper():
        return "HTML"

    if fn_lower.endswith(".json"):
        return "JSON"
    if fn_lower.endswith(".xml"):
        return "XML"
    if fn_lower.endswith(".html") or fn_lower.endswith(".htm"):
        return "HTML"

    raise ValueError("Ledger file format could not be recognized. Supported formats: XML, JSON, HTML.")

def sanitize_xml_content(content: str) -> str:
    """
    Sanitizes XML content to ensure safe, compliant XML 1.0 parsing:
    1. Removes DOCTYPE and ENTITY declarations (XXE protection).
    2. Strips illegal XML numeric character references (e.g., &#4; which Tally exports
       for internal dropdown/enumeration values like '&#4; Any').
    3. Strips raw control characters (ASCII 0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F).
    """
    if not content:
        return ""
    # 1. XXE prevention
    sanitized = re.sub(r'<!DOCTYPE[^>]*>', '', content, flags=re.IGNORECASE)
    sanitized = re.sub(r'<!ENTITY[^>]*>', '', sanitized, flags=re.IGNORECASE)
    # 2. Strip illegal XML numeric character references (&#0; - &#8;, &#11;, &#12;, &#14; - &#31;)
    sanitized = re.sub(r'&#(?:0?[0-8]|1[12]|1[4-9]|2[0-9]|3[01]);', '', sanitized)
    sanitized = re.sub(r'&#x(?:0?[0-8a-bA-B]|1[12]|1[4-9a-fA-F]);', '', sanitized, flags=re.IGNORECASE)
    # 3. Strip raw control characters (preserve newline \n, carriage return \r, tab \t)
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', sanitized)
    return sanitized

def parse_xml_masters(content: str) -> Tuple[List[ImportedLedger], List[ImportedGroup], int, List[str]]:
    """
    Comprehensive Master XML parser strictly conforming to Master.xml reference:
    - Extracts all <GROUP> elements and builds the group hierarchy.
    - Extracts all <LEDGER> elements with metadata (parent group, opening balance, GSTIN, state, pincode, GUID).
    - Resolves alias names from <LANGUAGENAME.LIST>.
    - Handles duplicates non-destructively and flags conflicts.
    """
    sanitized = sanitize_xml_content(content)

    try:
        root = ET.fromstring(sanitized)
    except ET.ParseError as pe:
        raise ValueError(f"Malformed XML ledger document: {str(pe)}")

    # 1. Extract GROUPS
    found_groups: Dict[str, ImportedGroup] = {}
    for elem in root.iter():
        tag = elem.tag.upper().split('}')[-1]
        if tag == "GROUP":
            name = elem.attrib.get("NAME") or elem.attrib.get("name")
            parent = None
            guid = None
            for child in elem:
                c_tag = child.tag.upper().split('}')[-1]
                if not name and c_tag == "NAME" and child.text:
                    name = child.text.strip()
                elif c_tag == "PARENT" and child.text:
                    parent = child.text.strip()
                elif c_tag == "GUID" and child.text:
                    guid = child.text.strip()
            if name and name.strip():
                clean_name = " ".join(name.strip().split())
                if clean_name not in found_groups:
                    found_groups[clean_name] = ImportedGroup(
                        name=clean_name,
                        parent=parent if parent else None,
                        guid=guid
                    )

    # Group parent map for resolving parent_group hierarchy
    group_parent_map: Dict[str, str] = {
        g.name: g.parent for g in found_groups.values() if g.parent
    }

    # 2. Extract LEDGERS
    found_ledgers: Dict[str, ImportedLedger] = {}
    duplicates = 0
    conflicts: List[str] = []

    for elem in root.iter():
        tag = elem.tag.upper().split('}')[-1]
        if tag == "LEDGER":
            name = elem.attrib.get("NAME") or elem.attrib.get("name")
            group = None
            op_bal_raw = None
            party_gstin = None
            state = None
            country = None
            pincode = None
            guid = None
            aliases: List[str] = []

            for child in elem:
                c_tag = child.tag.upper().split('}')[-1]
                if not name and c_tag == "NAME" and child.text:
                    name = child.text.strip()
                elif c_tag in ("PARENT", "GROUP") and child.text:
                    group = child.text.strip()
                elif c_tag == "OPENINGBALANCE" and child.text:
                    op_bal_raw = child.text.strip()
                elif c_tag == "PARTYGSTIN" and child.text:
                    party_gstin = child.text.strip()
                elif c_tag in ("LEDSTATENAME", "PRIORSTATENAME", "STATE") and child.text:
                    s_val = child.text.strip()
                    if s_val and s_val.upper() not in ("ANY", "NOT APPLICABLE") and not state:
                        state = s_val
                elif c_tag in ("COUNTRYOFRESIDENCE", "OLDCOUNTRYNAME", "COUNTRYNAME") and child.text:
                    c_val = child.text.strip()
                    if c_val and c_val != "+91" and not country:
                        country = c_val
                elif c_tag in ("PINCODE", "OLDPINCODE") and child.text:
                    p_val = child.text.strip()
                    if p_val and not pincode:
                        pincode = p_val
                elif c_tag == "GUID" and child.text:
                    guid = child.text.strip()
                elif c_tag == "LANGUAGENAME.LIST":
                    for sub in child:
                        if sub.tag.upper().split('}')[-1] in ("NAME.LIST", "NAME"):
                            for n in sub:
                                if n.text and n.text.strip():
                                    clean_n = " ".join(n.text.strip().split())
                                    if not name:
                                        name = clean_n
                                    elif clean_n.upper() != (name or "").strip().upper() and clean_n not in aliases:
                                        aliases.append(clean_n)
                elif c_tag == "LEDMAILINGDETAILS.LIST":
                    for m_child in child:
                        m_tag = m_child.tag.upper().split('}')[-1]
                        if m_tag in ("PINCODE", "OLDPINCODE") and m_child.text and not pincode:
                            pincode = m_child.text.strip()
                        elif m_tag in ("STATE", "LEDSTATENAME") and m_child.text and not state:
                            s_val = m_child.text.strip()
                            if s_val and s_val.upper() not in ("ANY", "NOT APPLICABLE"):
                                state = s_val

            if name and name.strip():
                clean_name = " ".join(name.strip().split())
                norm = normalize_ledger_name(clean_name)
                effective_group = group.strip() if group else "Primary"
                parent_group = group_parent_map.get(effective_group) or effective_group

                # Convert opening balance to Decimal safely
                opening_balance_dec: Optional[Decimal] = None
                if op_bal_raw:
                    try:
                        clean_amt = op_bal_raw.replace(",", "").strip()
                        opening_balance_dec = Decimal(clean_amt)
                    except (InvalidOperation, ValueError):
                        opening_balance_dec = None

                if norm in found_ledgers:
                    duplicates += 1
                    existing = found_ledgers[norm]
                    if effective_group != "Primary" and existing.group != "Primary" and existing.group != effective_group:
                        conflicts.append(f"Ledger '{clean_name}' has conflicting groups: '{existing.group}' vs '{effective_group}'")
                    # Non-destructively merge missing fields
                    if not existing.party_gstin and party_gstin:
                        existing.party_gstin = party_gstin
                    if existing.opening_balance is None and opening_balance_dec is not None:
                        existing.opening_balance = opening_balance_dec
                    if not existing.state and state:
                        existing.state = state
                    if not existing.country and country:
                        existing.country = country
                    if not existing.pincode and pincode:
                        existing.pincode = pincode
                    if not existing.guid and guid:
                        existing.guid = guid
                    for a in aliases:
                        if a not in existing.aliases:
                            existing.aliases.append(a)
                else:
                    found_ledgers[norm] = ImportedLedger(
                        name=clean_name,
                        normalized_name=norm,
                        group=effective_group,
                        parent_group=parent_group,
                        opening_balance=opening_balance_dec,
                        party_gstin=party_gstin,
                        state=state,
                        country=country,
                        pincode=pincode,
                        guid=guid,
                        aliases=aliases,
                        source_format="XML"
                    )

    # 3. Fallback: If no <LEDGER> tags, check for flat <LEDGERNAME> or <MASTERNAME> tags
    if not found_ledgers:
        for elem in root.iter():
            tag = elem.tag.upper().split('}')[-1]
            if tag in ("LEDGERNAME", "MASTERNAME"):
                name = elem.text
                if name and name.strip():
                    clean_name = " ".join(name.strip().split())
                    norm = normalize_ledger_name(clean_name)
                    if norm not in found_ledgers:
                        found_ledgers[norm] = ImportedLedger(
                            name=clean_name,
                            normalized_name=norm,
                            group="Primary",
                            parent_group="Primary",
                            source_format="XML"
                        )

    return list(found_ledgers.values()), list(found_groups.values()), duplicates, conflicts

def parse_xml_ledgers(content: str) -> List[ImportedLedger]:
    """
    Parses Tally XML ledger exports with XML entity and character sanitization.
    Returns list of ImportedLedgers (backwards-compatible).
    """
    ledgers, _, _, _ = parse_xml_masters(content)
    return ledgers

def parse_json_ledgers(content: str) -> List[ImportedLedger]:
    """
    Parses JSON ledger exports.
    Supports:
      - Array of strings: ["ABC TRADERS", "XYZ CORP"]
      - Array of objects: [{"name": "ABC TRADERS", "group": "Sundry Debtors"}]
      - Object with ledgers key: {"ledgers": [...]} or {"masters": [...]}
    """
    try:
        data = json.loads(content)
    except Exception as e:
        raise ValueError(f"Malformed JSON ledger file: {str(e)}")

    raw_list: List[Any] = []
    if isinstance(data, list):
        raw_list = data
    elif isinstance(data, dict):
        for key in ("ledgers", "masters", "items", "data", "records"):
            if key in data and isinstance(data[key], list):
                raw_list = data[key]
                break
        if not raw_list:
            # Maybe the keys themselves are ledger names: {"ABC TRADERS": "Sundry Debtors"}
            for k, v in data.items():
                if isinstance(v, str):
                    raw_list.append({"name": k, "group": v})
                elif isinstance(v, dict):
                    raw_list.append({"name": k, "group": v.get("group", "Primary")})

    found_ledgers: Dict[str, ImportedLedger] = {}
    for item in raw_list:
        name = None
        group = "Primary"

        if isinstance(item, str) and item.strip():
            name = item.strip()
        elif isinstance(item, dict):
            for k in ("name", "ledger_name", "title", "ledger", "Name", "LEDGERNAME"):
                if k in item and item[k]:
                    name = str(item[k]).strip()
                    break
            for gk in ("group", "parent", "group_name", "Parent", "GROUP"):
                if gk in item and item[gk]:
                    group = str(item[gk]).strip()
                    break

        if name:
            clean_name = " ".join(name.split())
            norm = normalize_ledger_name(clean_name)
            if norm not in found_ledgers:
                found_ledgers[norm] = ImportedLedger(
                    name=clean_name,
                    normalized_name=norm,
                    group=group or "Primary",
                    source_format="JSON"
                )

    return list(found_ledgers.values())

def parse_html_ledgers(content: str) -> List[ImportedLedger]:
    """
    Parses exported HTML ledger tables safely using HTMLParser.
    """
    parser = _SafeHTMLTableParser()
    try:
        parser.feed(content)
    except Exception as e:
        raise ValueError(f"Failed to parse HTML ledger content: {str(e)}")

    if not parser.rows:
        raise ValueError("Ledger HTML format could not be recognized. No table rows found.")

    found_ledgers: Dict[str, ImportedLedger] = {}
    ignored_headers = {
        "SL NO", "S.NO", "SR NO", "NAME", "LEDGER NAME", "PARTICULARS",
        "GROUP", "PARENT", "CLOSING BALANCE", "OPENING BALANCE", "DR/CR", "TOTAL"
    }

    for row in parser.rows:
        if not row:
            continue

        # Skip header-like rows
        row_joined = " ".join(c.upper() for c in row)
        if any(h in row_joined for h in ("LEDGER NAME", "PARTICULARS")):
            continue

        # Find non-empty cells
        cells = [c.strip() for c in row if c and c.strip()]
        if not cells:
            continue

        name = None
        group = "Primary"

        # Check if first cell is a serial number
        if cells[0].isdigit() and len(cells) > 1:
            name = cells[1]
            if len(cells) > 2:
                group = cells[2]
        else:
            name = cells[0]
            if len(cells) > 1 and not cells[1].replace(',', '').replace('.', '').isdigit():
                group = cells[1]

        if name and name.upper() not in ignored_headers and len(name) > 1:
            clean_name = " ".join(name.split())
            norm = normalize_ledger_name(clean_name)
            if norm not in found_ledgers:
                found_ledgers[norm] = ImportedLedger(
                    name=clean_name,
                    normalized_name=norm,
                    group=group or "Primary",
                    source_format="HTML"
                )

    if not found_ledgers:
        raise ValueError("Ledger HTML format could not be recognized.")

    return list(found_ledgers.values())

def import_ledgers_from_text(content: str, filename: Optional[str] = None) -> LedgerImportResult:
    """
    Main entrypoint: detects format and imports ledgers and groups.
    """
    fmt = detect_ledger_format(content, filename)
    groups: List[ImportedGroup] = []
    duplicates = 0
    conflicts: List[str] = []

    if fmt == "XML":
        ledgers, groups, duplicates, conflicts = parse_xml_masters(content)
    elif fmt == "JSON":
        ledgers = parse_json_ledgers(content)
    elif fmt == "HTML":
        ledgers = parse_html_ledgers(content)
    else:
        raise ValueError(f"Unsupported format: {fmt}")

    return LedgerImportResult(
        detected_format=fmt,
        total_imported=len(ledgers),
        total_ledgers=len(ledgers),
        total_groups=len(groups),
        groups=groups,
        ledgers=ledgers,
        duplicates=duplicates,
        conflicts=conflicts,
        needs_review=(len(conflicts) > 0)
    )

class UserLedgerStore:
    """
    Thread-safe in-memory store for user-imported ledgers and groups.
    Supports user isolation, rapid search, adding, deletion, and rich metadata.
    """
    def __init__(self):
        # { user_id: { normalized_name: ImportedLedger } }
        self._user_stores: Dict[str, Dict[str, ImportedLedger]] = {}
        # { user_id: { group_name: ImportedGroup } }
        self._user_groups: Dict[str, Dict[str, ImportedGroup]] = {}

    def get_user_ledgers(self, user_id: str) -> List[ImportedLedger]:
        return list(self._user_stores.get(user_id, {}).values())

    def get_bank_ledgers(self, user_id: str) -> List[ImportedLedger]:
        """Returns only bank account ledgers from the user's chart of accounts."""
        all_ledgers = self.get_user_ledgers(user_id)
        bank_ledgers = []
        for l in all_ledgers:
            grp = (l.group or "").strip().upper()
            parent = (l.parent_group or "").strip().upper()
            name = l.name.upper()

            # Exclude known expense / income / party ledgers
            if any(e in name for e in ("BANK CHARGES", "BANK CHARGE", "BANK CHGS", "BANK INTEREST", "INTEREST ON")):
                continue
            if "DEBTOR" in grp or "CREDITOR" in grp or "EXPENSE" in grp or "INCOME" in grp:
                continue

            # Standard Tally bank groups
            if any(bg in grp for bg in ("BANK ACCOUNTS", "BANK OCC", "BANK OD", "BANK A/C")) or \
               any(bg in parent for bg in ("BANK ACCOUNTS", "BANK OCC", "BANK OD", "BANK A/C")):
                bank_ledgers.append(l)
            elif "BANK" in grp and "EXPENSE" not in grp and "INCOME" not in grp:
                bank_ledgers.append(l)

        return bank_ledgers

    def get_cash_ledgers(self, user_id: str) -> List[ImportedLedger]:
        """Returns cash-in-hand ledgers from the user's chart of accounts."""
        all_ledgers = self.get_user_ledgers(user_id)
        cash_ledgers = []
        for l in all_ledgers:
            grp = (l.group or "").strip().upper()
            parent = (l.parent_group or "").strip().upper()
            name = l.name.upper()
            if "CASH" in grp or "CASH" in parent or name in ("CASH", "PETTY CASH", "CASH IN HAND", "CASH-IN-HAND"):
                cash_ledgers.append(l)
        return cash_ledgers

    def get_user_groups(self, user_id: str) -> List[ImportedGroup]:
        return list(self._user_groups.get(user_id, {}).values())

    def add_groups(self, user_id: str, groups: List[ImportedGroup]) -> int:
        if user_id not in self._user_groups:
            self._user_groups[user_id] = {}
        for g in groups:
            self._user_groups[user_id][g.name] = g
        return len(self._user_groups[user_id])

    def add_ledgers(self, user_id: str, ledgers: List[ImportedLedger]) -> int:
        if user_id not in self._user_stores:
            self._user_stores[user_id] = {}
        for l in ledgers:
            if l.normalized_name in self._user_stores[user_id]:
                # Non-destructively merge missing attributes
                existing = self._user_stores[user_id][l.normalized_name]
                if not existing.party_gstin and l.party_gstin:
                    existing.party_gstin = l.party_gstin
                if existing.opening_balance is None and l.opening_balance is not None:
                    existing.opening_balance = l.opening_balance
                if not existing.state and l.state:
                    existing.state = l.state
                if not existing.country and l.country:
                    existing.country = l.country
                if not existing.pincode and l.pincode:
                    existing.pincode = l.pincode
                if not existing.guid and l.guid:
                    existing.guid = l.guid
                for a in l.aliases:
                    if a not in existing.aliases:
                        existing.aliases.append(a)
            else:
                self._user_stores[user_id][l.normalized_name] = l
        return len(self._user_stores[user_id])

    def add_single_ledger(self, user_id: str, name: str, group: Optional[str] = "Primary") -> ImportedLedger:
        clean_name = " ".join(name.strip().split())
        norm = normalize_ledger_name(clean_name)
        ledger = ImportedLedger(
            name=clean_name,
            normalized_name=norm,
            group=group or "Primary",
            parent_group=group or "Primary",
            source_format="MANUAL"
        )
        if user_id not in self._user_stores:
            self._user_stores[user_id] = {}
        self._user_stores[user_id][norm] = ledger
        return ledger

    def delete_ledger(self, user_id: str, name: str) -> bool:
        norm = normalize_ledger_name(name)
        if user_id in self._user_stores and norm in self._user_stores[user_id]:
            del self._user_stores[user_id][norm]
            return True
        return False

    def search_ledgers(self, user_id: str, query: str, limit: Optional[int] = None) -> List[ImportedLedger]:
        store = self._user_stores.get(user_id, {})
        if not query or not query.strip():
            items = list(store.values())
            return items[:limit] if limit else items

        q = normalize_ledger_name(query)
        q_raw = query.strip().upper()
        results: List[Tuple[int, ImportedLedger]] = []

        for norm, l in store.items():
            # Exact name or GSTIN match
            if norm == q or (l.party_gstin and l.party_gstin.upper() == q_raw):
                results.append((0, l))
            elif any(normalize_ledger_name(a) == q for a in l.aliases):
                results.append((1, l))
            elif norm.startswith(q):
                results.append((2, l))
            elif q in norm or (l.party_gstin and q_raw in l.party_gstin.upper()):
                results.append((3, l))
            elif l.group and q in normalize_ledger_name(l.group):
                results.append((4, l))
            else:
                # Token match
                q_tokens = q.split()
                if any(t in norm for t in q_tokens):
                    results.append((5, l))

        results.sort(key=lambda x: x[0])
        matched = [r[1] for r in results]
        return matched[:limit] if limit else matched

    def clear(self, user_id: str):
        if user_id in self._user_stores:
            self._user_stores[user_id].clear()
        if user_id in self._user_groups:
            self._user_groups[user_id].clear()

# Global singleton store
global_ledger_store = UserLedgerStore()
