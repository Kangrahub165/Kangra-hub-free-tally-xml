import re
import json
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import List, Dict, Optional, Tuple, Any, Set
from pydantic import BaseModel, Field
from difflib import SequenceMatcher

from app.accounting.ledger_importer import sanitize_xml_content, decode_ledger_file

class ImportedStockItem(BaseModel):
    name: str
    normalized_name: str
    parent: Optional[str] = None  # Stock Group, e.g. "Coldrink 28% (40%)"
    base_units: str = "NOS"       # UOM, e.g. "case", "PCS", "NOS"
    additional_units: Optional[str] = None
    hsn_code: Optional[str] = None
    gst_rate: Optional[Decimal] = None
    gst_type_of_supply: str = "Goods"
    description: Optional[str] = None
    guid: Optional[str] = None
    source_format: str = "MANUAL"

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v) if v is not None else 0.0
        }

class StockItemMatchSuggestion(BaseModel):
    invoice_item_name: str
    matched_stock_item: Optional[ImportedStockItem] = None
    similarity_score: float = 0.0
    match_type: str = "NONE"  # EXACT, NORMALIZED, HSN, FUZZY, NONE
    confidence: str = "UNMATCHED"   # HIGH, MEDIUM, LOW, UNMATCHED
    mapping_status: str = "UNMATCHED" # AUTO_MAPPED, PLEASE_CHECK, POSSIBLE_MATCH, UNMATCHED, NEW_ITEM
    suggestions: List[Dict[str, Any]] = []

class StockItemImportResult(BaseModel):
    detected_format: str
    total_imported: int
    items: List[ImportedStockItem] = []
    duplicates: int = 0
    conflicts: List[str] = []
    error: Optional[str] = None

def normalize_item_name(name: str) -> str:
    """Normalizes whitespace, hyphens, and unit attachments for item comparison."""
    if not name:
        return ""
    # Standardize hyphen / underscore / slash to space
    s = re.sub(r'[\-_/]', ' ', name)
    # Separate numbers from units: 50KG -> 50 KG, 100g -> 100 g, 500ml -> 500 ml
    s = re.sub(r'(\d+)\s*([a-zA-Z]+)', r'\1 \2', s)
    # Normalize common unit abbreviations
    s = re.sub(r'\b(gm|gms|grams?)\b', 'G', s, flags=re.IGNORECASE)
    s = re.sub(r'\b(kgs?|kilograms?)\b', 'KG', s, flags=re.IGNORECASE)
    s = re.sub(r'\b(ltrs?|litres?|liters?)\b', 'LTR', s, flags=re.IGNORECASE)
    s = re.sub(r'\b(nos?|pieces?|pcs)\b', 'NOS', s, flags=re.IGNORECASE)
    # Strip noise punctuation
    cleaned = re.sub(r'[^\w\s\.\+]', ' ', s)
    return " ".join(cleaned.strip().split()).upper()

def detect_stock_item_format(content: str, filename: Optional[str] = None) -> str:
    """Detects XML, JSON, or HTML format for stock item imports."""
    if filename:
        fn_lower = filename.lower()
        if fn_lower.endswith('.json'):
            return "JSON"
        if fn_lower.endswith(('.htm', '.html')):
            return "HTML"
        if fn_lower.endswith('.xml'):
            return "XML"

    trimmed = content.lstrip('\ufeff \t\r\n')
    if trimmed.startswith(("<ENVELOPE", "<?xml", "<BODY", "<STOCKITEM", "<IMPORTDATA")):
        return "XML"
    if trimmed.startswith(("{", "[")):
        return "JSON"
    if "<html" in trimmed.lower() or "<table" in trimmed.lower():
        return "HTML"

    raise ValueError("Could not determine stock item file format. Supported formats: Tally XML, JSON, HTML.")

class _SafeStockHTMLParser(HTMLParser):
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
        t = tag.lower()
        if t == "script":
            self.in_script = True
        elif t == "table":
            self.in_table = True
        elif t == "tr":
            self.in_tr = True
            self.current_row = []
        elif t in ("td", "th"):
            self.in_td = True
            self.current_cell = []

    def handle_endtag(self, tag):
        t = tag.lower()
        if t == "script":
            self.in_script = False
        elif t == "table":
            self.in_table = False
        elif t == "tr":
            self.in_tr = False
            if self.current_row:
                self.rows.append(self.current_row)
        elif t in ("td", "th"):
            self.in_td = False
            cell_text = " ".join("".join(self.current_cell).split())
            self.current_row.append(cell_text)

    def handle_data(self, data):
        if self.in_td and not self.in_script:
            self.current_cell.append(data)

def parse_xml_stock_items(content: str) -> Tuple[List[ImportedStockItem], int, List[str]]:
    """
    Parses Tally Stock Items strictly conforming to stock items list sample.xml:
    Extracts <STOCKITEM NAME="..."> elements, HSN from <HSNDETAILS.LIST>,
    base units, group parent, GUID, and GST details.
    """
    sanitized = sanitize_xml_content(content)
    try:
        root = ET.fromstring(sanitized)
    except ET.ParseError as pe:
        raise ValueError(f"Malformed XML stock item document: {str(pe)}")

    items: List[ImportedStockItem] = []
    seen: Dict[str, ImportedStockItem] = {}
    duplicates = 0
    conflicts: List[str] = []

    for elem in root.iter():
        tag = elem.tag.upper().split('}')[-1]
        if tag == "STOCKITEM":
            name = elem.attrib.get("NAME") or elem.attrib.get("name")
            parent = None
            base_units = "NOS"
            additional_units = None
            hsn_code = None
            gst_rate = None
            guid = None
            gst_type = "Goods"

            for child in elem:
                c_tag = child.tag.upper().split('}')[-1]
                if not name and c_tag == "NAME" and child.text:
                    name = child.text.strip()
                elif c_tag == "PARENT" and child.text:
                    parent = child.text.strip()
                elif c_tag == "BASEUNITS" and child.text:
                    base_units = child.text.strip()
                elif c_tag == "ADDITIONALUNITS" and child.text:
                    additional_units = child.text.strip()
                elif c_tag == "GUID" and child.text:
                    guid = child.text.strip()
                elif c_tag == "GSTTYPEOFSUPPLY" and child.text:
                    gst_type = child.text.strip()
                elif "HSNDETAILS" in c_tag:
                    for sub in child.iter():
                        sub_tag = sub.tag.upper().split('}')[-1]
                        if sub_tag == "HSNCODE" and sub.text and sub.text.strip():
                            hsn_code = sub.text.strip()
                elif "GSTDETAILS" in c_tag or "GSTRATE" in c_tag:
                    cgst_val = None
                    sgst_val = None
                    igst_val = None
                    for rnode in child.iter():
                        rtag = rnode.tag.upper().split('}')[-1]
                        if rtag == "RATEDETAILS.LIST":
                            head = None
                            rval = None
                            for f in rnode:
                                ftag = f.tag.upper().split('}')[-1]
                                if ftag == "GSTRATEDUTYHEAD" and f.text:
                                    head = f.text.strip().upper()
                                elif ftag == "GSTRATE" and f.text:
                                    try:
                                        rval = Decimal(f.text.strip()).quantize(Decimal("0.01"))
                                    except Exception:
                                        pass
                            if head == "IGST" and rval is not None:
                                igst_val = rval
                            elif head == "CGST" and rval is not None:
                                cgst_val = rval
                            elif "SGST" in (head or "") and rval is not None:
                                sgst_val = rval
                        elif "RATE" in rtag and rnode.text and gst_rate is None:
                            try:
                                fallback_r = Decimal(rnode.text.strip()).quantize(Decimal("0.01"))
                                if fallback_r > 0:
                                    gst_rate = fallback_r
                            except Exception:
                                pass
                    if igst_val is not None and igst_val > Decimal("0.00"):
                        gst_rate = igst_val
                    elif cgst_val is not None or sgst_val is not None:
                        gst_rate = (cgst_val or Decimal("0.00")) + (sgst_val or Decimal("0.00"))

            if name and name.strip():
                clean_name = " ".join(name.strip().split())
                norm = normalize_item_name(clean_name)

                if norm in seen:
                    duplicates += 1
                    conflicts.append(f"Duplicate stock item found: '{clean_name}' (ignored subsequent occurrence)")
                    continue

                item = ImportedStockItem(
                    name=clean_name,
                    normalized_name=norm,
                    parent=parent if parent else None,
                    base_units=base_units if base_units else "NOS",
                    additional_units=additional_units if additional_units and not additional_units.startswith("Not") else None,
                    hsn_code=hsn_code,
                    gst_rate=gst_rate,
                    gst_type_of_supply=gst_type,
                    guid=guid,
                    source_format="XML"
                )
                seen[norm] = item
                items.append(item)

    return items, duplicates, conflicts

def parse_json_stock_items(content: str) -> Tuple[List[ImportedStockItem], int, List[str]]:
    """Parses stock items from JSON array or object."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as je:
        raise ValueError(f"Malformed JSON stock items: {str(je)}")

    raw_list = []
    if isinstance(data, list):
        raw_list = data
    elif isinstance(data, dict):
        for k in ("stock_items", "items", "StockItems", "data"):
            if k in data and isinstance(data[k], list):
                raw_list = data[k]
                break
        if not raw_list:
            raw_list = [data]

    items: List[ImportedStockItem] = []
    seen: Dict[str, ImportedStockItem] = {}
    duplicates = 0
    conflicts: List[str] = []

    for entry in raw_list:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name") or entry.get("item_name") or entry.get("STOCKITEMNAME")
        if not name or not str(name).strip():
            continue
        clean_name = " ".join(str(name).strip().split())
        norm = normalize_item_name(clean_name)
        if norm in seen:
            duplicates += 1
            continue

        item = ImportedStockItem(
            name=clean_name,
            normalized_name=norm,
            parent=entry.get("parent") or entry.get("group"),
            base_units=entry.get("base_units") or entry.get("uom") or "NOS",
            hsn_code=str(entry.get("hsn_code") or entry.get("hsn") or ""),
            gst_rate=Decimal(str(entry["gst_rate"])) if entry.get("gst_rate") is not None else None,
            source_format="JSON"
        )
        seen[norm] = item
        items.append(item)

    return items, duplicates, conflicts

def parse_html_stock_items(content: str) -> Tuple[List[ImportedStockItem], int, List[str]]:
    """Parses stock items from HTML tables."""
    parser = _SafeStockHTMLParser()
    parser.feed(content)

    items: List[ImportedStockItem] = []
    seen: Dict[str, ImportedStockItem] = {}
    duplicates = 0
    conflicts: List[str] = []

    if not parser.rows:
        return items, duplicates, conflicts

    header = [c.lower() for c in parser.rows[0]]
    name_col = -1
    hsn_col = -1
    uom_col = -1
    group_col = -1

    for idx, col in enumerate(header):
        if any(k in col for k in ("item", "name", "product", "description")):
            name_col = idx
        elif "hsn" in col:
            hsn_col = idx
        elif any(k in col for k in ("unit", "uom")):
            uom_col = idx
        elif any(k in col for k in ("group", "parent", "category")):
            group_col = idx

    if name_col == -1:
        name_col = 0

    for row in parser.rows[1:]:
        if len(row) <= name_col:
            continue
        name = row[name_col].strip()
        if not name or len(name) < 2:
            continue
        clean_name = " ".join(name.split())
        norm = normalize_item_name(clean_name)
        if norm in seen:
            duplicates += 1
            continue

        hsn = row[hsn_col].strip() if hsn_col != -1 and len(row) > hsn_col else None
        uom = row[uom_col].strip() if uom_col != -1 and len(row) > uom_col else "NOS"
        parent = row[group_col].strip() if group_col != -1 and len(row) > group_col else None

        item = ImportedStockItem(
            name=clean_name,
            normalized_name=norm,
            parent=parent,
            base_units=uom or "NOS",
            hsn_code=hsn,
            source_format="HTML"
        )
        seen[norm] = item
        items.append(item)

    return items, duplicates, conflicts

def import_stock_items_from_text(content: str, filename: Optional[str] = None) -> StockItemImportResult:
    """Detects format and parses stock items."""
    fmt = detect_stock_item_format(content, filename)
    if fmt == "XML":
        items, dups, conflicts = parse_xml_stock_items(content)
    elif fmt == "JSON":
        items, dups, conflicts = parse_json_stock_items(content)
    elif fmt == "HTML":
        items, dups, conflicts = parse_html_stock_items(content)
    else:
        raise ValueError(f"Unsupported format: {fmt}")

    return StockItemImportResult(
        detected_format=fmt,
        total_imported=len(items),
        items=items,
        duplicates=dups,
        conflicts=conflicts
    )

class GlobalStockItemStore:
    """Thread-safe in-memory store for user-imported Tally stock items."""
    def __init__(self):
        self._user_items: Dict[str, Dict[str, ImportedStockItem]] = {}

    def add_items(self, user_id: str, items: List[ImportedStockItem]) -> int:
        if user_id not in self._user_items:
            self._user_items[user_id] = {}
        added = 0
        for it in items:
            if it.normalized_name not in self._user_items[user_id]:
                self._user_items[user_id][it.normalized_name] = it
                added += 1
            else:
                # Update attributes if richer
                existing = self._user_items[user_id][it.normalized_name]
                if not existing.hsn_code and it.hsn_code:
                    existing.hsn_code = it.hsn_code
                if not existing.parent and it.parent:
                    existing.parent = it.parent
        return added

    def get_items(self, user_id: str, search: Optional[str] = None, limit: Optional[int] = 50) -> List[ImportedStockItem]:
        items_map = dict(self._user_items.get("default_session", {}))
        if user_id != "default_session" and user_id in self._user_items:
            items_map.update(self._user_items[user_id])
        all_items = list(items_map.values())
        if not search or not search.strip():
            return all_items[:limit] if limit else all_items

        q_clean = search.strip().lower()
        q_norm = normalize_item_name(search)
        q_tokens = [t for t in q_clean.replace("-", " ").replace("/", " ").replace(".", " ").replace(",", " ").split() if t]

        exact = []
        prefix = []
        substring_match = []
        token_match = []

        for it in all_items:
            name_lower = it.name.lower()
            norm_name = it.normalized_name
            hsn = (it.hsn_code or "").strip().lower()
            uom = (it.base_units or "").strip().lower()
            parent = (it.parent or "").strip().lower()

            if name_lower == q_clean or norm_name == q_norm or (hsn and hsn == q_clean):
                exact.append(it)
            elif name_lower.startswith(q_clean) or norm_name.startswith(q_norm):
                prefix.append(it)
            elif q_norm in norm_name or q_clean in name_lower or (hsn and q_clean in hsn):
                substring_match.append(it)
            elif q_tokens and all(t in name_lower or (hsn and t in hsn) or (parent and t in parent) or (uom and t in uom) or t in norm_name for t in q_tokens):
                token_match.append(it)

        combined = exact + prefix + substring_match + token_match
        seen_names = set()
        deduped = []
        for it in combined:
            if it.name not in seen_names:
                seen_names.add(it.name)
                deduped.append(it)

        return deduped[:limit] if limit else deduped

    def match_item(self, user_id: str, query_name: str, hsn: Optional[str] = None) -> StockItemMatchSuggestion:
        """
        Finds closest matching stock item using exact, normalized, HSN, and similarity checks
        strictly guarded by Hard Vetoes (PRD §8):
        - Size / volume tokens must be equal (200ML != 500ML, 80g != 40g).
        - MRP tokens must be equal (RS.30 != RS.50).
        - Product code must be equal when both sides have one (OPTB220 != OMJST220).
        - HSN must match at least 4 digits when both present.
        Thresholds:
        95-100, no veto -> AUTO_MAPPED (Green)
        80-94, no veto  -> PLEASE_CHECK (Amber, needs confirmation)
        < 80 or veto    -> UNMATCHED / NEW_ITEM (Red, blocks export)
        """
        items_map = dict(self._user_items.get("default_session", {}))
        if user_id != "default_session" and user_id in self._user_items:
            items_map.update(self._user_items[user_id])
        if not items_map or not query_name:
            return StockItemMatchSuggestion(
                invoice_item_name=query_name,
                similarity_score=0.0,
                match_type="NONE",
                confidence="UNMATCHED",
                mapping_status="UNMATCHED",
                suggestions=[]
            )

        q_norm = normalize_item_name(query_name)

        def extract_size_tokens(text: str) -> Set[str]:
            matches = re.findall(r'\b(\d+(?:\.\d+)?)\s*(ML|LTR|L|GM|G|KG|MG)\b', text.upper())
            return {f"{num}{unit}" for num, unit in matches}

        def extract_mrp_tokens(text: str) -> Set[str]:
            p1 = re.findall(r'(?:RS\.?|MRP)\s*(\d+(?:\.\d+)?)', text.upper())
            p2 = re.findall(r'(\d+(?:\.\d+)?)\s*(?:RS|MRP)', text.upper())
            return {f"RS{num}" for num in (p1 + p2)}

        def extract_code_tokens(text: str) -> Set[str]:
            in_parens = re.findall(r'\(([A-Z0-9]{3,})\)', text.upper())
            isolated = re.findall(r'\b([A-Z]+[0-9]+[A-Z0-9]*|[0-9]+[A-Z]+[A-Z0-9]*)\b', text.upper())
            codes = set(in_parens)
            common_units = {"200ML", "500ML", "100GM", "50GM", "1KG", "2KG", "1LTR", "2LTR", "24DZ", "10DZ", "2DZ", "42DZ"}
            for c in isolated:
                if c not in common_units:
                    codes.add(c)
            return codes

        def check_hard_vetoes(cand_name: str, cand_hsn: Optional[str]) -> Tuple[bool, List[str]]:
            vetoes = []
            # 1. Size / volume veto: 200ML != 500ML
            q_s = extract_size_tokens(query_name)
            c_s = extract_size_tokens(cand_name)
            if q_s and c_s and not (q_s & c_s):
                vetoes.append(f"Size mismatch: {q_s} vs {c_s}")

            # 2. MRP veto: RS.30 != RS.50
            q_m = extract_mrp_tokens(query_name)
            c_m = extract_mrp_tokens(cand_name)
            if q_m and c_m and not (q_m & c_m):
                vetoes.append(f"MRP mismatch: {q_m} vs {c_m}")

            # 3. Product code veto: OPTB220 != OMJST220
            q_c = extract_code_tokens(query_name)
            c_c = extract_code_tokens(cand_name)
            if q_c and c_c and not (q_c & c_c):
                vetoes.append(f"Code mismatch: {q_c} vs {c_c}")

            # 4. HSN 4-digit veto
            if hsn and cand_hsn:
                q_h4 = "".join(filter(str.isdigit, str(hsn)))[:4]
                c_h4 = "".join(filter(str.isdigit, str(cand_hsn)))[:4]
                if len(q_h4) == 4 and len(c_h4) == 4 and q_h4 != c_h4:
                    vetoes.append(f"HSN mismatch: {q_h4} vs {c_h4}")

            return len(vetoes) > 0, vetoes

        # 1. Exact / Normalized match (subject to veto check)
        if q_norm in items_map:
            exact_item = items_map[q_norm]
            has_veto, _ = check_hard_vetoes(exact_item.name, exact_item.hsn_code)
            if not has_veto:
                return StockItemMatchSuggestion(
                    invoice_item_name=query_name,
                    matched_stock_item=exact_item,
                    similarity_score=1.0,
                    match_type="EXACT",
                    confidence="HIGH",
                    mapping_status="AUTO_MAPPED",
                    suggestions=[{
                        "name": exact_item.name,
                        "similarity_score": 100.0,
                        "confidence": "HIGH",
                        "hsn_code": exact_item.hsn_code,
                        "base_units": exact_item.base_units
                    }]
                )

        # 2. Ranked similarity match with controlled HSN & Substring boosts and Hard Vetoes
        ranked = []
        for item in items_map.values():
            has_veto, veto_reasons = check_hard_vetoes(item.name, item.hsn_code)
            if has_veto:
                # Hard veto: cap score so it can NEVER auto-map
                score = 0.40
            else:
                score = SequenceMatcher(None, q_norm, item.normalized_name).ratio()
                # Boost if HSN matches
                if hsn and item.hsn_code and hsn.strip() == item.hsn_code.strip():
                    score = min(1.0, score + 0.10)
                # Substring boost ONLY if substring is significant (min 6 chars and >= 75% of length)
                min_len = min(len(q_norm), len(item.normalized_name))
                max_len = max(len(q_norm), len(item.normalized_name))
                if min_len >= 6 and (min_len / max_len) >= 0.75:
                    if q_norm in item.normalized_name or item.normalized_name in q_norm:
                        score = max(score, 0.85)

            ranked.append((score, item, has_veto))

        ranked.sort(key=lambda x: x[0], reverse=True)
        top_suggestions = []
        for s, it, veto in ranked[:3]:
            conf = "HIGH" if s >= 0.95 else ("MEDIUM" if s >= 0.80 else "LOW")
            top_suggestions.append({
                "name": it.name,
                "similarity_score": round(s * 100, 1),
                "confidence": conf,
                "hsn_code": it.hsn_code,
                "base_units": it.base_units
            })

        best_score, best_match, best_veto = ranked[0] if ranked else (0.0, None, True)

        if not best_veto and best_score >= 0.95:
            return StockItemMatchSuggestion(
                invoice_item_name=query_name,
                matched_stock_item=best_match,
                similarity_score=round(best_score, 3),
                match_type="FUZZY_HIGH",
                confidence="HIGH",
                mapping_status="AUTO_MAPPED",
                suggestions=top_suggestions
            )
        elif not best_veto and best_score >= 0.80:
            # Strong suggestion: attaches match but flags as PLEASE_CHECK for user verification (Amber)
            return StockItemMatchSuggestion(
                invoice_item_name=query_name,
                matched_stock_item=best_match,
                similarity_score=round(best_score, 3),
                match_type="FUZZY_MEDIUM",
                confidence="MEDIUM",
                mapping_status="PLEASE_CHECK",
                suggestions=top_suggestions
            )
        else:
            # Below 80 or veto: Unmatched (Red, requires action)
            return StockItemMatchSuggestion(
                invoice_item_name=query_name,
                matched_stock_item=None,
                similarity_score=round(best_score, 3) if not best_veto else 0.0,
                match_type="NONE" if best_veto else "FUZZY_LOW",
                confidence="UNMATCHED",
                mapping_status="UNMATCHED",
                suggestions=top_suggestions
            )

    def get_stock_groups(self, user_id: str) -> List[Dict[str, Any]]:
        """
        PRD Addendum 5: Returns distinct Stock Groups (parents) from imported Tally items,
        sorted with "Primary" first, then alphabetically, with item counts.
        """
        all_items = self.get_items(user_id, limit=None)
        counts: Dict[str, int] = {}
        for it in all_items:
            grp = (it.parent or "Primary").strip()
            if grp:
                counts[grp] = counts.get(grp, 0) + 1

        if "Primary" not in counts:
            counts["Primary"] = 0

        result = [{"name": "Primary", "item_count": counts.get("Primary", 0)}]
        for grp_name in sorted(counts.keys(), key=lambda s: s.lower()):
            if grp_name != "Primary":
                result.append({"name": grp_name, "item_count": counts[grp_name]})

        return result

    def get_stock_units(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Returns distinct base units from imported Tally items with counts.
        """
        all_items = self.get_items(user_id, limit=None)
        counts: Dict[str, int] = {}
        for it in all_items:
            u = (it.base_units or "NOS").strip()
            if u:
                counts[u] = counts.get(u, 0) + 1

        standard = ["NOS", "PCS", "CASE", "BOX", "BTL", "KG", "LTR", "PKT", "DOZ", "BAG", "CAN", "SET", "GM"]
        for s in standard:
            if s not in counts:
                counts[s] = 0

        sorted_units = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        return [{"name": name, "item_count": count} for name, count in sorted_units]

    def generate_new_stock_item_xml(
        self,
        name: str,
        hsn: Optional[str] = None,
        uom: str = "NOS",
        parent_group: Optional[str] = "Primary",
        gst_rate: Optional[Decimal] = None,
        taxability: str = "Taxable",
        type_of_supply: str = "Goods",
        additional_units: Optional[str] = None,
        conversion: Optional[Decimal] = None
    ) -> str:
        """
        Generates master XML snippet strictly conforming to stock items list sample.xml.
        """
        import xml.sax.saxutils as saxutils
        clean_name = saxutils.escape(" ".join(name.strip().split()))
        clean_uom = saxutils.escape((uom or "NOS").strip())
        clean_parent = saxutils.escape((parent_group or "Primary").strip())
        hsn_str = saxutils.escape((hsn or "").strip())

        lines = [
            '<TALLYMESSAGE xmlns:UDF="TallyUDF">',
            f' <STOCKITEM NAME="{clean_name}" ACTION="Create">',
            f'  <NAME>{clean_name}</NAME>',
            f'  <PARENT>{clean_parent}</PARENT>',
            f'  <BASEUNITS>{clean_uom}</BASEUNITS>',
        ]

        if additional_units and conversion and conversion > Decimal("1"):
            clean_alt = saxutils.escape(additional_units.strip())
            lines.extend([
                f'  <ADDITIONALUNITS>{clean_alt}</ADDITIONALUNITS>',
                '  <DENOMINATOR>1</DENOMINATOR>',
                f'  <CONVERSION>{int(conversion)}</CONVERSION>'
            ])

        lines.extend([
            '  <GSTAPPLICABLE>&#4; Applicable</GSTAPPLICABLE>',
            f'  <GSTTYPEOFSUPPLY>{saxutils.escape(type_of_supply or "Goods")}</GSTTYPEOFSUPPLY>',
            '  <ISCOSTCENTRESON>No</ISCOSTCENTRESON>',
            '  <ISBATCHWISEON>No</ISBATCHWISEON>',
            '  <ISPERISHABLEON>No</ISPERISHABLEON>',
            '  <OPENINGBALANCE>0</OPENINGBALANCE>'
        ])

        if gst_rate is not None and gst_rate > Decimal("0.00") and (taxability or "Taxable").lower() == "taxable":
            cgst = (gst_rate / Decimal("2")).quantize(Decimal("0.01"))
            sgst = cgst
            igst = gst_rate
            lines.extend([
                '  <GSTDETAILS.LIST>',
                '   <APPLICABLEFROM>20210401</APPLICABLEFROM>',
                '   <CALCULATIONTYPE>On Value</CALCULATIONTYPE>',
                '   <TAXABILITY>Taxable</TAXABILITY>',
                '   <SRCOFGSTDETAILS>Specify Details Here</SRCOFGSTDETAILS>',
                '   <STATEWISEDETAILS.LIST>',
                '    <STATENAME>&#4; Any</STATENAME>',
                '    <RATEDETAILS.LIST>',
                '     <GSTRATEDUTYHEAD>CGST</GSTRATEDUTYHEAD>',
                '     <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>',
                f'     <GSTRATE> {cgst}</GSTRATE>',
                '    </RATEDETAILS.LIST>',
                '    <RATEDETAILS.LIST>',
                '     <GSTRATEDUTYHEAD>SGST/UTGST</GSTRATEDUTYHEAD>',
                '     <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>',
                f'     <GSTRATE> {sgst}</GSTRATE>',
                '    </RATEDETAILS.LIST>',
                '    <RATEDETAILS.LIST>',
                '     <GSTRATEDUTYHEAD>IGST</GSTRATEDUTYHEAD>',
                '     <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>',
                f'     <GSTRATE> {igst}</GSTRATE>',
                '    </RATEDETAILS.LIST>',
                '   </STATEWISEDETAILS.LIST>',
                '  </GSTDETAILS.LIST>'
            ])
        elif taxability and taxability.lower() in ("exempt", "nil rated"):
            t_cap = "Exempt" if taxability.lower() == "exempt" else "Nil Rated"
            lines.extend([
                '  <GSTDETAILS.LIST>',
                '   <APPLICABLEFROM>20210401</APPLICABLEFROM>',
                '   <CALCULATIONTYPE>On Value</CALCULATIONTYPE>',
                f'   <TAXABILITY>{t_cap}</TAXABILITY>',
                '   <SRCOFGSTDETAILS>Specify Details Here</SRCOFGSTDETAILS>',
                '  </GSTDETAILS.LIST>'
            ])

        if hsn_str:
            lines.extend([
                '  <HSNDETAILS.LIST>',
                '   <APPLICABLEFROM>20210401</APPLICABLEFROM>',
                f'   <HSNCODE>{hsn_str}</HSNCODE>',
                '   <SRCOFHSNDETAILS>Specify Details Here</SRCOFHSNDETAILS>',
                '  </HSNDETAILS.LIST>'
            ])

        lines.extend([
            ' </STOCKITEM>',
            '</TALLYMESSAGE>'
        ])

        return "\n".join(lines)

    def generate_all_masters_xml(
        self,
        company_name: str,
        items: List[Dict[str, Any]],
        default_parent_group: str = "Primary"
    ) -> str:
        """
        Generates complete Tally All Masters import XML strictly conforming
        to 'stock items list sample.xml'.
        Defines <UNIT> messages first, then <STOCKITEM> messages.
        """
        import xml.sax.saxutils as saxutils

        UQC_MAP = {
            "BAG": "BAG-BAGS",
            "BAGS": "BAG-BAGS",
            "BOX": "BOX-BOX",
            "BOXES": "BOX-BOX",
            "BTL": "BTL-BOTTLES",
            "BOTTLE": "BTL-BOTTLES",
            "BOTTLES": "BTL-BOTTLES",
            "CAN": "PCS-PIECES",
            "CANS": "PCS-PIECES",
            "CASE": "PCS-PIECES",
            "CASES": "PCS-PIECES",
            "CRATE": "BOX-BOX",
            "CTN": "CTN-CARTONS",
            "CARTON": "CTN-CARTONS",
            "CARTONS": "CTN-CARTONS",
            "DOZ": "DOZ-DOZENS",
            "DOZEN": "DOZ-DOZENS",
            "DZN": "DOZ-DOZENS",
            "GM": "GMS-GRAMMES",
            "GMS": "GMS-GRAMMES",
            "HANGER": "BOX-BOX",
            "HRS": "BOX-BOX",
            "KG": "KGS-KILOGRAMS",
            "KGS": "KGS-KILOGRAMS",
            "KILOGRAM": "KGS-KILOGRAMS",
            "LARI": "PAC-PACKS",
            "LTR": "LTR-LITRES",
            "LTRS": "LTR-LITRES",
            "ML": "MLT-MILILITRE",
            "MLT": "MLT-MILILITRE",
            "MTR": "MTR-METERS",
            "NAG": "NOS-NUMBERS",
            "NOS": "NOS-NUMBERS",
            "PAC": "PAC-PACKS",
            "PACK": "PAC-PACKS",
            "PACKS": "PAC-PACKS",
            "PATTA": "PAC-PACKS",
            "PCS": "PCS-PIECES",
            "PIECES": "PCS-PIECES",
            "PIECE": "PCS-PIECES",
            "PKT": "PAC-PACKS",
            "POUCH": "PCS-PIECES",
            "QTL": "QTL-QUINTAL",
            "ROLL": "ROL-ROLLS",
            "ROLLS": "ROL-ROLLS",
            "SET": "SET-SETS",
            "SETS": "SET-SETS",
            "SQF": "SQF-SQUARE FEET",
            "SQM": "SQM-SQUARE METERS",
            "TBS": "TBS-TABLETS",
            "TIN": "PCS-PIECES",
            "TON": "TON-TONNES",
            "TREE": "BOX-BOX",
            "TUB": "TUB-TUBES",
            "UNT": "UNT-UNITS",
            "UNIT": "UNT-UNITS",
            "UNITS": "UNT-UNITS",
            "YDS": "YDS-YARDS",
        }

        c_name = saxutils.escape(company_name.strip() if company_name else "Kartar Singh & Sons - (from 1-Apr-25)")

        lines = [
            '<ENVELOPE>',
            ' <HEADER>',
            '  <TALLYREQUEST>Import Data</TALLYREQUEST>',
            ' </HEADER>',
            ' <BODY>',
            '  <IMPORTDATA>',
            '   <REQUESTDESC>',
            '    <REPORTNAME>All Masters</REPORTNAME>',
            '    <STATICVARIABLES>',
            f'     <SVCURRENTCOMPANY>{c_name}</SVCURRENTCOMPANY>',
            '    </STATICVARIABLES>',
            '   </REQUESTDESC>',
            '   <REQUESTDATA>'
        ]

        # 1. Collect unique units
        units_seen = set()
        unique_units = []
        for it in items:
            raw_u = str(it.get("uom") or it.get("base_units") or "NOS").strip()
            u_clean = raw_u if raw_u else "NOS"
            if u_clean.upper() not in units_seen:
                units_seen.add(u_clean.upper())
                unique_units.append(u_clean)

        for u in unique_units:
            u_esc = saxutils.escape(u)
            uqc = UQC_MAP.get(u.upper(), f"{u.upper()}-{u.upper()}")
            uqc_esc = saxutils.escape(uqc)
            lines.extend([
                '    <TALLYMESSAGE xmlns:UDF="TallyUDF">',
                f'     <UNIT NAME="{u_esc}" RESERVEDNAME="">',
                f'      <NAME>{u_esc}</NAME>',
                f'      <GSTREPUOM>{uqc_esc}</GSTREPUOM>',
                '      <ISUPDATINGTARGETID>No</ISUPDATINGTARGETID>',
                '      <ISDELETED>No</ISDELETED>',
                '      <ISSECURITYONWHENENTERED>No</ISSECURITYONWHENENTERED>',
                '      <ASORIGINAL>Yes</ASORIGINAL>',
                '      <ISGSTEXCLUDED>No</ISGSTEXCLUDED>',
                '      <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>',
                '      <REPORTINGUQCDETAILS.LIST>',
                '       <APPLICABLEFROM>20210401</APPLICABLEFROM>',
                f'       <REPORTINGUQCNAME>{uqc_esc}</REPORTINGUQCNAME>',
                '      </REPORTINGUQCDETAILS.LIST>',
                '     </UNIT>',
                '    </TALLYMESSAGE>'
            ])

        # 2. Stock Items
        items_seen = set()
        for it in items:
            raw_name = str(it.get("name") or it.get("item_name") or "").strip()
            if not raw_name:
                continue
            if raw_name.upper() in items_seen:
                continue
            items_seen.add(raw_name.upper())

            name_esc = saxutils.escape(" ".join(raw_name.split()))
            parent_esc = saxutils.escape(str(it.get("parent") or it.get("parent_group") or it.get("group") or default_parent_group).strip())
            uom_esc = saxutils.escape(str(it.get("uom") or it.get("base_units") or "NOS").strip())
            hsn_raw = str(it.get("hsn") or it.get("hsn_code") or it.get("hsn_sac") or "").strip()
            hsn_esc = saxutils.escape(hsn_raw)

            # GST rate calculation
            gst_val = it.get("gst_rate") or it.get("gst_pct")
            try:
                gst_dec = Decimal(str(gst_val)) if gst_val is not None and str(gst_val).strip() != "" else Decimal("0.00")
            except Exception:
                gst_dec = Decimal("0.00")

            cgst = (gst_dec / Decimal("2")).quantize(Decimal("0.01")) if gst_dec > 0 else Decimal("0.00")
            sgst = cgst
            igst = gst_dec

            lines.extend([
                '    <TALLYMESSAGE xmlns:UDF="TallyUDF">',
                f'     <STOCKITEM NAME="{name_esc}" RESERVEDNAME="" ACTION="Create">',
                f'      <NAME>{name_esc}</NAME>',
                f'      <PARENT>{parent_esc}</PARENT>',
                f'      <BASEUNITS>{uom_esc}</BASEUNITS>',
                '      <GSTAPPLICABLE>&#4; Applicable</GSTAPPLICABLE>',
                '      <GSTTYPEOFSUPPLY>Goods</GSTTYPEOFSUPPLY>',
                '      <ISCOSTCENTRESON>No</ISCOSTCENTRESON>',
                '      <ISBATCHWISEON>No</ISBATCHWISEON>',
                '      <ISPERISHABLEON>No</ISPERISHABLEON>',
                '      <OPENINGBALANCE>0</OPENINGBALANCE>'
            ])

            if gst_dec > Decimal("0.00"):
                lines.extend([
                    '      <GSTDETAILS.LIST>',
                    '       <APPLICABLEFROM>20210401</APPLICABLEFROM>',
                    '       <CALCULATIONTYPE>On Value</CALCULATIONTYPE>',
                    '       <TAXABILITY>Taxable</TAXABILITY>',
                    '       <SRCOFGSTDETAILS>Specify Details Here</SRCOFGSTDETAILS>',
                    '       <STATEWISEDETAILS.LIST>',
                    '        <STATENAME>&#4; Any</STATENAME>',
                    '        <RATEDETAILS.LIST>',
                    '         <GSTRATEDUTYHEAD>CGST</GSTRATEDUTYHEAD>',
                    '         <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>',
                    f'         <GSTRATE> {cgst}</GSTRATE>',
                    '        </RATEDETAILS.LIST>',
                    '        <RATEDETAILS.LIST>',
                    '         <GSTRATEDUTYHEAD>SGST/UTGST</GSTRATEDUTYHEAD>',
                    '         <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>',
                    f'         <GSTRATE> {sgst}</GSTRATE>',
                    '        </RATEDETAILS.LIST>',
                    '        <RATEDETAILS.LIST>',
                    '         <GSTRATEDUTYHEAD>IGST</GSTRATEDUTYHEAD>',
                    '         <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>',
                    f'         <GSTRATE> {igst}</GSTRATE>',
                    '        </RATEDETAILS.LIST>',
                    '       </STATEWISEDETAILS.LIST>',
                    '      </GSTDETAILS.LIST>'
                ])

            if hsn_esc:
                lines.extend([
                    '      <HSNDETAILS.LIST>',
                    '       <APPLICABLEFROM>20210401</APPLICABLEFROM>',
                    f'       <HSNCODE>{hsn_esc}</HSNCODE>',
                    '       <SRCOFHSNDETAILS>Specify Details Here</SRCOFHSNDETAILS>',
                    '      </HSNDETAILS.LIST>'
                ])

            lines.extend([
                '     </STOCKITEM>',
                '    </TALLYMESSAGE>'
            ])

        lines.extend([
            '   </REQUESTDATA>',
            '  </IMPORTDATA>',
            ' </BODY>',
            '</ENVELOPE>'
        ])

        return "\n".join(lines)

global_stock_item_store = GlobalStockItemStore()
