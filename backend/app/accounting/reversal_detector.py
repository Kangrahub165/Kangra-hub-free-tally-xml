import re
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Set, Any
from datetime import date
from app.transactions.model import TransactionItem, CanonicalStatement

# PRD Section 11.2 - Reversal Keywords Catalogue
REVERSAL_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "INSUFFICIENT_FUNDS": {
        "label": "Funds insufficient",
        "keywords": ["FUNDS INSUFFICIENT", "INSUFFICIENT FUNDS", "INSUFF FUND", "EXCEEDS ARRANGEMENT"]
    },
    "CHEQUE_RETURN": {
        "label": "Cheque rejected / returned",
        "keywords": ["REJECTED", "REJECT", "REJ", "CHQ RET", "OW CHQ RET", "INWARD RETURN", "UNPAID", "BOUNCE", "DISHONOUR", "CHQ RETURN"]
    },
    "ACCOUNT_PROBLEM": {
        "label": "Account problem",
        "keywords": ["ACCOUNT NOT FOUND", "A/C NOT FOUND", "NO SUCH ACCOUNT", "INVALID ACCOUNT", "ACCOUNT CLOSED", "A/C FROZEN", "DORMANT", "INCORRECT ACCOUNT"]
    },
    "CHEQUE_PROBLEM": {
        "label": "Cheque signature / date problem",
        "keywords": ["STOP PAYMENT", "PAYMENT STOPPED", "SIGNATURE DIFFERS", "REFER TO DRAWER", "STALE", "POST DATED", "ALTERATION", "IMAGE NOT CLEAR"]
    },
    "ONLINE_FAILURE": {
        "label": "Online transfer failure",
        "keywords": ["NEFT RETURN", "RTGS RETURN", "IMPS FAIL", "UPI REVERSAL", "TXN FAILED", "AUTO REVERSAL", "REVERSAL", "RVSL", "REV"]
    },
    "MANDATE_RETURN": {
        "label": "Mandate / ECS return",
        "keywords": ["ECS RETURN", "NACH RETURN", "MANDATE REJECTED", "AUTO DEBIT RETURN"]
    },
    "CARD_ATM": {
        "label": "Card / ATM reversal",
        "keywords": ["ATM REVERSAL", "POS REVERSAL", "CHARGEBACK", "DISPUTE"]
    }
}

# Compiled regex for whole-word / boundary keyword matching
_KEYWORD_PATTERNS: List[Tuple[re.Pattern, str, str]] = []
for category_key, info in REVERSAL_CATEGORIES.items():
    label = info["label"]
    for kw in info["keywords"]:
        # Escape keyword and use word boundaries where appropriate
        escaped = re.escape(kw)
        pattern = re.compile(rf'(?:\b|_|:|-|\s){escaped}(?:\b|_|:|-|\s|$)', re.IGNORECASE)
        _KEYWORD_PATTERNS.append((pattern, category_key, label))

# Regex to detect reference numbers (cheque numbers, UTRs, RRNs)
_REF_PATTERNS = [
    re.compile(r'(?:INST|CHQ|CHEQUE|INW|OW CHQ|CHQ NO|REJECT)[\s/:]*([0-9]{4,8})\b', re.IGNORECASE),
    re.compile(r'\b([0-9]{6})\b'),  # 6-digit cheque number
    re.compile(r'\b([A-Z]{3,6}[0-9]{10,22})\b', re.IGNORECASE),  # UTR / NEFT
    re.compile(r'\b([0-9]{12})\b')  # 12-digit UPI / IMPS RRN
]

def extract_reference_numbers(text: str) -> List[str]:
    """Extracts candidate reference numbers from narration or reference fields."""
    if not text:
        return []
    refs: List[str] = []
    for pat in _REF_PATTERNS:
        matches = pat.findall(text)
        for m in matches:
            if isinstance(m, str) and m.strip():
                clean_ref = m.strip().upper()
                if clean_ref not in refs:
                    refs.append(clean_ref)
    return refs

def detect_reversal_in_narration(narration: str) -> Optional[Tuple[str, str]]:
    """
    Checks if narration contains any recognized reversal/rejection keyword.
    Returns: (category_key, human_label) or None.
    """
    if not narration:
        return None
    for pattern, cat_key, label in _KEYWORD_PATTERNS:
        if pattern.search(narration):
            return cat_key, label
    return None

class ReversalDetector:
    """
    PRD Section 11 Engine:
    Detects and pairs reversed & rejected transactions to the Reverse Entries ledger,
    isolates return/bounce bank charges to Bank Charges, and calculates net impact.
    """

    def __init__(
        self,
        reverse_ledger_name: str = "Reverse Entries",
        bank_charges_ledger_name: str = "Bank Charges",
        max_cross_date_days: int = 3
    ):
        self.reverse_ledger_name = reverse_ledger_name
        self.bank_charges_ledger_name = bank_charges_ledger_name
        self.max_cross_date_days = max_cross_date_days

    def process_statement(self, statement: CanonicalStatement) -> Dict[str, Any]:
        """
        Executes Section 11 pairing and charge isolation across statement transactions.
        Modifies transactions in-place and returns reversal summary metrics.
        """
        txs = statement.transactions
        if not txs:
            return {"pairs_count": 0, "unmatched_count": 0, "net_total": Decimal("0.00")}

        # Step 1: Pre-scan transactions for references & reversal hints
        tx_info: List[Dict[str, Any]] = []
        for idx, tx in enumerate(txs):
            full_text = f"{tx.narration or ''} {tx.reference or ''} {tx.cheque_number or ''} {tx.instrument_number or ''}"
            rev_hint = detect_reversal_in_narration(full_text)
            refs = extract_reference_numbers(full_text)
            
            # If tx already has explicit cheque/instrument number, add it
            if tx.cheque_number and tx.cheque_number not in refs:
                refs.append(tx.cheque_number)
            if tx.instrument_number and tx.instrument_number not in refs:
                refs.append(tx.instrument_number)
            if tx.reference and tx.reference not in refs:
                refs.append(tx.reference)

            is_debit = tx.debit > Decimal("0.00")
            amount = tx.debit if is_debit else tx.credit

            tx_info.append({
                "index": idx,
                "tx": tx,
                "is_debit": is_debit,
                "amount": amount,
                "date": tx.date,
                "rev_hint": rev_hint,
                "refs": set(refs),
                "paired": False,
                "is_charge": False
            })

        # Step 2: Identify candidate reversal groups by reference number
        # Groups: { ref: [tx_info_items] }
        ref_groups: Dict[str, List[int]] = {}
        for item in tx_info:
            for r in item["refs"]:
                if len(r) >= 5:  # meaningful reference (cheque/UTR)
                    ref_groups.setdefault(r, []).append(item["index"])

        # Step 3: Identify linked rejection/bounce charges (PRD Section 11.4)
        # Debit on same date sharing reference of a reversal group or with REJ/RET + CHQ,
        # whose amount is smaller/does not match the reversal pair amount.
        for item in tx_info:
            if not item["is_debit"]:
                continue
            tx = item["tx"]
            upper_n = (tx.narration or "").upper()
            
            # Check if this row is a cheque return/rejection charge
            is_chq_rej_charge = (
                ("REJ" in upper_n or "RET" in upper_n or "RTN" in upper_n) and
                ("CHQ" in upper_n or "CHEQUE" in upper_n or "OW" in upper_n or "CHARGE" in upper_n)
            )

            linked_ref = None
            for r in item["refs"]:
                if r in ref_groups and len(ref_groups[r]) > 1:
                    # Check if there is another row in this group that has a reversal hint
                    has_reversal_in_group = any(
                        tx_info[other_idx]["rev_hint"] is not None
                        for other_idx in ref_groups[r]
                        if other_idx != item["index"]
                    )
                    if has_reversal_in_group or is_chq_rej_charge:
                        linked_ref = r
                        break

            if is_chq_rej_charge or (linked_ref and item["rev_hint"]):
                # Verify that this debit amount is NOT identical to a counter credit in the same group
                has_matching_credit = any(
                    (not tx_info[other_idx]["is_debit"]) and
                    abs(tx_info[other_idx]["amount"] - item["amount"]) < Decimal("0.001")
                    for other_idx in (ref_groups.get(linked_ref, []) if linked_ref else [])
                )
                if not has_matching_credit:
                    # This is a bank charge associated with rejection!
                    item["is_charge"] = True
                    item["paired"] = True  # Exclude from reversal pairing
                    tx.ledger_name = self.bank_charges_ledger_name
                    tx.suggested_ledger = self.bank_charges_ledger_name
                    tx.voucher_type = "Payment"
                    tx.is_reverse_entry = False
                    tx.linked_reversal_ref = linked_ref
                    if linked_ref:
                        tx.mapping_status = "Mapped"
                        tx.validation_notes = f"Bank charges linked to reversal {linked_ref}"
                    else:
                        tx.mapping_status = "Requires Review"
                        tx.validation_notes = "Bank charges linked to cheque rejection"

        # Step 4: Pairing rules (PRD Section 11.3)
        # Pair 1 Debit and 1 Credit with same amount where:
        # - at least one row has a reversal keyword OR
        # - both share a reference number
        pair_counter = 1
        paired_indices: Set[int] = set()

        # Phase 4A: Same date pairs
        for i, debit_item in enumerate(tx_info):
            if debit_item["paired"] or not debit_item["is_debit"]:
                continue
            
            best_match_idx = None
            best_match_confidence = 0
            best_match_reason = ""
            shared_ref_found = None

            for j, credit_item in enumerate(tx_info):
                if credit_item["paired"] or credit_item["is_debit"]:
                    continue
                if abs(debit_item["amount"] - credit_item["amount"]) >= Decimal("0.001"):
                    continue

                # Check date
                same_date = (debit_item["date"] == credit_item["date"])
                if not same_date:
                    continue

                # Check reversal criteria
                has_rev = (debit_item["rev_hint"] is not None) or (credit_item["rev_hint"] is not None)
                common_refs = debit_item["refs"].intersection(credit_item["refs"])
                shared_ref = next(iter(common_refs)) if common_refs else None

                if shared_ref and has_rev:
                    # Highest confidence: Same date + reference match + reversal keyword
                    best_match_idx = j
                    best_match_confidence = 100
                    reason_label = (debit_item["rev_hint"] or credit_item["rev_hint"])[1]
                    best_match_reason = f"{reason_label} (Ref: {shared_ref})"
                    shared_ref_found = shared_ref
                    break
                elif shared_ref:
                    # Same date + reference match
                    if best_match_confidence < 90:
                        best_match_idx = j
                        best_match_confidence = 90
                        best_match_reason = f"Shared reference {shared_ref}"
                        shared_ref_found = shared_ref
                elif has_rev:
                    # Same date + reversal keyword
                    if best_match_confidence < 80:
                        best_match_idx = j
                        best_match_confidence = 80
                        reason_label = (debit_item["rev_hint"] or credit_item["rev_hint"])[1]
                        best_match_reason = reason_label

            if best_match_idx is not None:
                credit_item = tx_info[best_match_idx]
                pair_id = f"rev-pair-{pair_counter}"
                pair_counter += 1

                debit_item["paired"] = True
                credit_item["paired"] = True
                paired_indices.add(i)
                paired_indices.add(best_match_idx)

                # Configure debit leg
                d_tx = debit_item["tx"]
                d_tx.ledger_name = self.reverse_ledger_name
                d_tx.suggested_ledger = self.reverse_ledger_name
                d_tx.is_reverse_entry = True
                d_tx.reversal_pair_id = pair_id
                d_tx.paired_row_index = credit_item["tx"].row_index
                d_tx.reversal_reason = best_match_reason
                d_tx.reversal_leg = "REVERSAL" if debit_item["rev_hint"] else "ORIGINAL"
                d_tx.voucher_type = "Payment"
                d_tx.mapping_status = "Mapped" if shared_ref_found else "Requires Review"

                # Configure credit leg
                c_tx = credit_item["tx"]
                c_tx.ledger_name = self.reverse_ledger_name
                c_tx.suggested_ledger = self.reverse_ledger_name
                c_tx.is_reverse_entry = True
                c_tx.reversal_pair_id = pair_id
                c_tx.paired_row_index = debit_item["tx"].row_index
                c_tx.reversal_reason = best_match_reason
                c_tx.reversal_leg = "REVERSAL" if credit_item["rev_hint"] else "ORIGINAL"
                c_tx.voucher_type = "Receipt"
                c_tx.mapping_status = "Mapped" if shared_ref_found else "Requires Review"

        # Phase 4B: Cross-date pairs (within max_cross_date_days, default 3)
        for i, debit_item in enumerate(tx_info):
            if debit_item["paired"] or not debit_item["is_debit"]:
                continue

            for j, credit_item in enumerate(tx_info):
                if credit_item["paired"] or credit_item["is_debit"]:
                    continue
                if abs(debit_item["amount"] - credit_item["amount"]) >= Decimal("0.001"):
                    continue

                day_diff = abs((debit_item["date"] - credit_item["date"]).days)
                if day_diff > self.max_cross_date_days or day_diff == 0:
                    continue

                has_rev = (debit_item["rev_hint"] is not None) or (credit_item["rev_hint"] is not None)
                common_refs = debit_item["refs"].intersection(credit_item["refs"])
                shared_ref = next(iter(common_refs)) if common_refs else None

                if has_rev or shared_ref:
                    pair_id = f"rev-pair-{pair_counter}"
                    pair_counter += 1

                    debit_item["paired"] = True
                    credit_item["paired"] = True
                    paired_indices.add(i)
                    paired_indices.add(j)

                    reason_label = (debit_item["rev_hint"] or credit_item["rev_hint"])[1] if has_rev else "Cross-date reversal"
                    if shared_ref:
                        reason_label += f" (Ref: {shared_ref})"

                    # Cross-date pairs are always Requires Review per Section 11.3
                    d_tx = debit_item["tx"]
                    d_tx.ledger_name = self.reverse_ledger_name
                    d_tx.suggested_ledger = self.reverse_ledger_name
                    d_tx.is_reverse_entry = True
                    d_tx.reversal_pair_id = pair_id
                    d_tx.paired_row_index = credit_item["tx"].row_index
                    d_tx.reversal_reason = reason_label
                    d_tx.reversal_leg = "REVERSAL" if debit_item["rev_hint"] else "ORIGINAL"
                    d_tx.voucher_type = "Payment"
                    d_tx.mapping_status = "Requires Review"

                    c_tx = credit_item["tx"]
                    c_tx.ledger_name = self.reverse_ledger_name
                    c_tx.suggested_ledger = self.reverse_ledger_name
                    c_tx.is_reverse_entry = True
                    c_tx.reversal_pair_id = pair_id
                    c_tx.paired_row_index = debit_item["tx"].row_index
                    c_tx.reversal_reason = reason_label
                    c_tx.reversal_leg = "REVERSAL" if credit_item["rev_hint"] else "ORIGINAL"
                    c_tx.voucher_type = "Receipt"
                    c_tx.mapping_status = "Requires Review"
                    break

        # Step 5: Unpaired reversal entries (PRD Section 11.3)
        # Rows with a reversal keyword but no original in this statement
        unmatched_count = 0
        for item in tx_info:
            if not item["paired"] and item["rev_hint"] is not None:
                tx = item["tx"]
                tx.ledger_name = self.reverse_ledger_name
                tx.suggested_ledger = self.reverse_ledger_name
                tx.is_reverse_entry = True
                tx.reversal_leg = "UNPAIRED"
                tx.reversal_reason = item["rev_hint"][1]
                tx.mapping_status = "Requires Review"
                tx.validation_notes = "original entry not in this statement"
                unmatched_count += 1

        # Summary statistics
        pairs_count = (pair_counter - 1)
        total_reverse_rows = sum(1 for t in txs if t.is_reverse_entry)
        
        statement.reverse_entries_count = total_reverse_rows
        statement.reverse_pairs_count = pairs_count
        statement.reverse_unmatched_count = unmatched_count

        # Verify net total of paired rows (must be 0.00)
        net_total = Decimal("0.00")
        for t in txs:
            if t.is_reverse_entry and t.reversal_pair_id:
                if t.debit > Decimal("0.00"):
                    net_total += t.debit
                elif t.credit > Decimal("0.00"):
                    net_total -= t.credit

        return {
            "pairs_count": pairs_count,
            "unmatched_count": unmatched_count,
            "total_reverse_rows": total_reverse_rows,
            "net_total": net_total
        }
