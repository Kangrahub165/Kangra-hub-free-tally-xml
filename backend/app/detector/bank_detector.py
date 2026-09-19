import re
from typing import Optional, Dict, Any, List, Tuple
from pydantic import BaseModel
from app.detector.signatures import BANK_SIGNATURES
from app.pdf.extractor import ExtractedDocument

class DetectedBankResult(BaseModel):
    bank_name: str
    parser_key: str
    format_name: str = "Standard"
    confidence: float
    confidence_tier: str = "HIGH"  # HIGH | MEDIUM | LOW | AMBIGUOUS
    is_ambiguous: bool = False
    account_number_masked: Optional[str] = None
    detected_ifsc: Optional[str] = None
    runner_up_bank: Optional[str] = None
    runner_up_confidence: Optional[float] = None
    detection_reasons: List[str] = []
    candidates: List[Dict[str, Any]] = []

def detect_bank_from_document(doc: ExtractedDocument) -> DetectedBankResult:
    """
    Analyzes document text with strict Header Zone isolation.
    Evaluates official bank names, issuing branch IFSC codes, domains,
    statement-specific header markers, and exact account number lengths.
    
    Prevents false positives by:
    1. Isolating header metadata from transaction body narrations.
    2. Using word-bounded regexes and negative lookbehinds.
    3. Checking exact account number digit boundaries.
    4. Categorizing confidence into HIGH, MEDIUM, LOW, and AMBIGUOUS.
    5. NEVER defaulting to PNB or any arbitrary bank.
    """
    first_page_text = doc.first_page_text
    lines = [l.strip() for l in first_page_text.split('\n') if l.strip()]
    
    # Identify Header Zone vs Body Zone by finding the start of transaction table
    table_headers = [
        "DATE", "PARTICULARS", "DESCRIPTION", "WITHDRAWAL", "DEPOSIT", 
        "BALANCE", "CHQ", "REF NO", "POST DATE", "VAL DATE", "TXN DATE"
    ]
    table_start_idx = len(lines)
    for idx, l in enumerate(lines):
        upper_l = l.upper()
        # Avoid treating account metadata lines as table headers (e.g. "Account Description : OD Banks Deposits PER")
        if any(meta in upper_l for meta in ["ACCOUNT DESCRIPTION", "ACCOUNT TYPE", "PRODUCT :", "SCHEME :", "BRANCH :"]):
            continue
        matches = sum(1 for h in table_headers if h in upper_l)
        if matches >= 3 or (matches >= 2 and any(d in upper_l for d in ["DATE", "TXN DATE", "VAL DATE", "POST DATE"]) and any(a in upper_l for a in ["WITHDRAWAL", "DEPOSIT", "DEBIT", "CREDIT", "BALANCE"])):
            table_start_idx = idx
            break
        if re.match(r'^(?:(?:[A-Za-z]*\d+[A-Za-z0-9_\-]*|\d+)\s+)?(\d{1,2}[/\-\.](?:\d{1,2}|[A-Za-z]{3})[/\-\.]\d{2,4})\b', l):
            table_start_idx = idx
            break

    # Header lines are strictly those before transaction entries begin
    header_lines = lines[:table_start_idx]
    header_text = "\n".join(header_lines)
    if not header_text and lines:
        header_text = "\n".join(lines[:25])

    candidates = []
    for sig in BANK_SIGNATURES:
        score = 0.0
        reasons: List[str] = []
        
        # 1. Header Bank Name (Primary authority)
        for name_pat in sig.get("header_names", []):
            if re.search(name_pat, header_text, re.IGNORECASE):
                score += 70.0
                reasons.append(f"Header name: '{name_pat}'")
                break

        # 2. Issuing Branch IFSC (Strongest technical signature in Header)
        ifsc_prefix = sig.get("ifsc_prefix")
        detected_ifsc = None
        if ifsc_prefix:
            # Check labeled IFSC e.g. "IFS Code: SBIN0003248" or "IFSC : PUNB0..."
            labeled_m = re.search(r'(?:IFS\s*Code|IFSC|RTGS/NEFT\s*IFSC)[\s:\-]+([A-Z0-9]+)', header_text, re.IGNORECASE)
            if labeled_m and labeled_m.group(1).upper().startswith(ifsc_prefix):
                score += 65.0
                detected_ifsc = labeled_m.group(1).upper()
                reasons.append(f"Labeled issuing branch IFSC: {detected_ifsc}")
            else:
                m_ifsc = re.search(rf'\b({ifsc_prefix}[0-9A-Z]{{6}})\b', header_text, re.IGNORECASE)
                if m_ifsc:
                    score += 50.0
                    detected_ifsc = m_ifsc.group(1).upper()
                    reasons.append(f"Header branch IFSC: {detected_ifsc}")

        # 3. Official Internet Banking Portal Domain
        for d in sig.get("domains", []):
            if d.lower() in header_text.lower():
                score += 35.0
                reasons.append(f"Official banking domain: {d}")
                break

        # 4. Bank-Specific Header Markers (e.g. CIF No., Drawing Power, Scheme Code)
        for marker in sig.get("header_markers", []):
            if re.search(marker, header_text, re.IGNORECASE):
                score += 25.0
                reasons.append(f"Header marker: '{marker}'")

        # 5. Account Number Format (Exact Length Verified)
        acc_num = None
        for acc_pat in sig.get("account_patterns", []):
            m = re.search(acc_pat, header_text, re.IGNORECASE)
            if not m:
                m = re.search(acc_pat, first_page_text, re.IGNORECASE)
            if m:
                raw_acc = m.group(1).strip()
                acc_num = raw_acc
                score += 25.0
                reasons.append(f"Account format ({len(raw_acc)} digits): ...{raw_acc[-4:]}")
                break

        # 6. Column Patterns in Table Header
        for col_pat in sig.get("column_patterns", []):
            if re.search(col_pat, first_page_text, re.IGNORECASE):
                score += 30.0
                reasons.append("Table column header structure match")
                break

        if score > 0:
            candidates.append({
                "bank_name": sig["bank_name"],
                "parser_key": sig["parser_key"],
                "score": score,
                "reasons": reasons,
                "account_number": acc_num,
                "detected_ifsc": detected_ifsc
            })

    candidates.sort(key=lambda x: x["score"], reverse=True)

    if not candidates or candidates[0]["score"] < 40.0:
        return DetectedBankResult(
            bank_name="Unable to confidently identify",
            parser_key="manual_selection_required",
            format_name="Standard",
            confidence=0.0,
            confidence_tier="LOW",
            is_ambiguous=True,
            account_number_masked=None,
            detection_reasons=["No distinctive bank signatures found in document header."]
        )

    top = candidates[0]
    runner_up = candidates[1] if len(candidates) > 1 else None
    margin = top["score"] - (runner_up["score"] if runner_up else 0.0)

    # Mask account number
    masked_acc = None
    if top.get("account_number"):
        raw_acc = top["account_number"]
        masked_acc = f"XXXX{raw_acc[-4:]}" if len(raw_acc) >= 4 else raw_acc

    # Confidence calculation & ambiguity detection
    if top["score"] >= 80.0 and margin >= 25.0:
        # High confidence: margin is dominant, high raw score
        conf = min(99.0, max(85.0, 75.0 + margin / 3.0))
        tier = "HIGH"
        is_ambiguous = False
        bank_name = top["bank_name"]
        parser_key = top["parser_key"]
    elif top["score"] >= 50.0 and margin >= 15.0:
        # Medium confidence: clear winner, but lower overall score
        conf = min(84.0, max(60.0, top["score"]))
        tier = "MEDIUM"
        is_ambiguous = False
        bank_name = top["bank_name"]
        parser_key = top["parser_key"]
    elif margin < 15.0:
        # Ambiguous: Top 2 candidates have conflicting scores
        conf = 45.0
        tier = "AMBIGUOUS"
        is_ambiguous = True
        bank_name = "Unable to confidently identify"
        parser_key = "manual_selection_required"
    else:
        conf = 30.0
        tier = "LOW"
        is_ambiguous = True
        bank_name = "Unable to confidently identify"
        parser_key = "manual_selection_required"

    return DetectedBankResult(
        bank_name=bank_name,
        parser_key=parser_key,
        format_name="Standard",
        confidence=round(conf, 1),
        confidence_tier=tier,
        is_ambiguous=is_ambiguous,
        account_number_masked=masked_acc,
        detected_ifsc=top.get("detected_ifsc"),
        runner_up_bank=runner_up["bank_name"] if runner_up else None,
        runner_up_confidence=round(runner_up["score"], 1) if runner_up else None,
        detection_reasons=top["reasons"],
        candidates=[{"bank_name": c["bank_name"], "score": round(c["score"], 1)} for c in candidates if c["score"] > 0][:5]
    )
