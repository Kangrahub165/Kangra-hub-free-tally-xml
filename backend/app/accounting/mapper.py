import re
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from app.transactions.model import TransactionItem
from app.accounting.entity_extractor import NarrationEntityExtractor
from app.accounting.ledger_importer import ImportedLedger, normalize_ledger_name

class LedgerMatchCandidate:
    def __init__(self, ledger_name: str, confidence: float, reason: str):
        self.ledger_name = ledger_name
        self.confidence = confidence
        self.reason = reason

class LedgerMapper:
    """
    Intelligent ledger mapping engine conforming strictly to the PRD:
    - Extracts parties, cheque numbers, and references.
    - Matches against imported Tally ledgers and saved mappings.
    - Defaults to 'Suspense' for unmatched or low-confidence transactions.
    - Preserves user-configured bank and cash ledger names.
    """

    def __init__(
        self,
        user_saved_mappings: Optional[Dict[str, str]] = None,
        imported_ledgers: Optional[List[ImportedLedger]] = None,
        bank_ledger_name: str = "Bank Account",
        cash_ledger_name: str = "Cash",
        suspense_ledger_name: str = "Suspense"
    ):
        # Saved memory mappings: { pattern_or_party: tally_ledger_name }
        self.saved_mappings = {k.upper().strip(): v for k, v in (user_saved_mappings or {}).items()}
        self.bank_ledger_name = bank_ledger_name
        self.cash_ledger_name = cash_ledger_name
        self.suspense_ledger_name = suspense_ledger_name

        # Index imported ledgers by normalized name, aliases, and GSTIN
        self.imported_ledgers = imported_ledgers or []
        self._norm_ledger_index: Dict[str, str] = {}
        self._gstin_ledger_index: Dict[str, str] = {}
        self._alias_ledger_index: Dict[str, str] = {}
        for l in self.imported_ledgers:
            norm = normalize_ledger_name(l.name)
            self._norm_ledger_index[norm] = l.name
            if getattr(l, "party_gstin", None):
                self._gstin_ledger_index[l.party_gstin.upper().strip()] = l.name
            for alias in getattr(l, "aliases", []):
                norm_alias = normalize_ledger_name(alias)
                self._alias_ledger_index[norm_alias] = l.name

    def extract_party_from_narration(self, narration: str, is_debit: bool = True) -> str:
        """Helper for backward compatibility."""
        party, _ = NarrationEntityExtractor.extract_party_from_narration(narration, is_debit)
        return party or ""

    def find_best_ledger_match(self, party: Optional[str], narration: str, is_debit: bool) -> Tuple[str, float, str, List[Tuple[str, float]]]:
        """
        Finds the best matching ledger from memory and imported ledgers.
        Returns: (selected_ledger, confidence_score, mapping_status, candidates)
        """
        # 1. Check Cash
        is_cash, cash_type = NarrationEntityExtractor.identify_cash_transaction(narration, is_debit)
        if is_cash or (party and party.upper() == "CASH"):
            return self.cash_ledger_name, 99.0, "Auto", [(self.cash_ledger_name, 99.0)]

        # 2. Check Saved User Memory Rules
        # Exact party match in saved mappings
        if party and party.upper().strip() in self.saved_mappings:
            mapped = self.saved_mappings[party.upper().strip()]
            return mapped, 100.0, "Previously Mapped", [(mapped, 100.0)]

        # Substring pattern match in narration
        upper_narration = narration.upper()
        for pattern, ledger in self.saved_mappings.items():
            if pattern in upper_narration:
                return ledger, 95.0, "Previously Mapped", [(ledger, 95.0)]

        # 3. Check GSTIN match directly against imported master GSTINs
        if self._gstin_ledger_index:
            gstin_match = re.search(r'\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b', upper_narration)
            if gstin_match and gstin_match.group(0) in self._gstin_ledger_index:
                mapped_gstin = self._gstin_ledger_index[gstin_match.group(0)]
                return mapped_gstin, 99.0, "Auto", [(mapped_gstin, 99.0)]

        # 4. Check against Imported Tally Ledgers (name and aliases)
        candidates: List[Tuple[str, float]] = []
        if party and (self._norm_ledger_index or self._alias_ledger_index):
            party_clean = party.strip()
            party_norm = normalize_ledger_name(party_clean)
            party_tokens = set(party_norm.split())

            # Priority 1: Check for exact match, while collecting related candidates
            exact_match = None
            for norm, exact_name in self._norm_ledger_index.items():
                if exact_name.strip().upper() == party_clean.upper() or norm == party_norm:
                    exact_match = exact_name
                elif party_norm in norm or norm in party_norm:
                    candidates.append((exact_name, 88.0))
                else:
                    norm_tokens = set(norm.split())
                    common = party_tokens.intersection(norm_tokens)
                    if common and len(common) >= min(len(party_tokens), len(norm_tokens)) * 0.5:
                        score = round(60.0 + (len(common) / max(len(party_tokens), len(norm_tokens))) * 25.0, 1)
                        candidates.append((exact_name, score))

            if exact_match:
                candidates.sort(key=lambda x: x[1], reverse=True)
                all_candidates = [(exact_match, 100.0)] + [c for c in candidates if c[0] != exact_match]
                return exact_match, 100.0, "Auto", all_candidates[:5]

            # Priority 2: Exact alias match
            if party_norm in self._alias_ledger_index:
                alias_match = self._alias_ledger_index[party_norm]
                return alias_match, 100.0, "Auto", [(alias_match, 100.0)]

            # Priority 3: Substring / token matching (if no exact match)
            if candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                top_name, top_score = candidates[0]
                if top_score >= 80.0:
                    return top_name, top_score, "Auto", candidates[:5]

        # 5. Direct narration segment/substring matching against imported ledgers
        if not candidates or candidates[0][1] < 80.0:
            narration_parts = [p.strip() for p in re.split(r'[/_\-\:]', upper_narration) if p.strip()]
            for norm, exact_name in self._norm_ledger_index.items():
                if norm in narration_parts:
                    candidates.append((exact_name, 92.0))
                elif len(norm) >= 5 and norm in upper_narration:
                    candidates.append((exact_name, 88.0))
            if candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                top_name, top_score = candidates[0]
                if top_score >= 80.0:
                    return top_name, top_score, "Auto", candidates[:5]

        # 6. Built-in Statutory / Accounting Entities
        # Recognized statutory categories from entity extractor
        statutory_ledgers = {
            "Bank Charges": "Bank Charges",
            "Bank Interest Income": "Bank Interest Income",
            "Bank Interest Expense": "Bank Interest Expense",
            "GST Input Tax Credit": "GST Input Tax Credit",
            "APY Contribution": "APY Contribution",
            "Clearing": "Clearing",
        }
        if party and party in statutory_ledgers:
            # Check if imported ledgers contain this exact statutory name
            party_norm = normalize_ledger_name(party)
            if party_norm in self._norm_ledger_index:
                return self._norm_ledger_index[party_norm], 95.0, "Auto", [(self._norm_ledger_index[party_norm], 95.0)]
            # Also try common alternative names in imported ledgers
            alt_names = {
                "Bank Charges": ["bank charges", "bank commission", "bank service charges"],
                "Bank Interest Income": ["bank interest", "interest received", "interest on fd"],
                "Bank Interest Expense": ["interest paid", "interest on od"],
            }
            for alt in alt_names.get(party, []):
                alt_norm = normalize_ledger_name(alt)
                if alt_norm in self._norm_ledger_index:
                    return self._norm_ledger_index[alt_norm], 92.0, "Auto", [(self._norm_ledger_index[alt_norm], 92.0)]
            return party, 90.0, "Auto", [(party, 90.0)]

        # 5. STRICT MANDATORY DEFAULT TO SUSPENSE (PRD Section 9)
        # Any transaction that cannot be confidently mapped defaults to Suspense
        return self.suspense_ledger_name, 0.0, "Suspense", candidates[:3]

    def map_transaction_ledger(self, tx: TransactionItem, default_bank_ledger: Optional[str] = None) -> str:
        """
        Enriches a TransactionItem with complete metadata and returns the mapped ledger name.
        """
        is_debit = tx.debit > Decimal("0.00")
        
        # 1. Extract Party and Metadata
        party, category = NarrationEntityExtractor.extract_party_from_narration(tx.narration, is_debit)
        cheque_no = NarrationEntityExtractor.extract_cheque_or_instrument_number(tx.narration, tx.reference)
        upi_ref = NarrationEntityExtractor.extract_upi_reference(tx.narration)
        utr = NarrationEntityExtractor.extract_utr_reference(tx.narration)
        is_cash, cash_type = NarrationEntityExtractor.identify_cash_transaction(tx.narration, is_debit)

        # 2. Preserve raw/original values
        if not tx.original_narration:
            tx.original_narration = tx.narration
        tx.party_name = party
        if cheque_no:
            tx.cheque_number = cheque_no
            tx.instrument_number = cheque_no
        if upi_ref:
            tx.upi_ref = upi_ref
        if utr:
            tx.utr = utr
        tx.is_cash_transaction = is_cash
        tx.cash_transaction_type = cash_type

        # 3. If user already provided or confirmed a ledger, preserve it
        if tx.ledger_name and tx.ledger_name != self.suspense_ledger_name:
            tx.mapping_status = "User Confirmed"
            tx.mapping_confidence = 100.0
            return tx.ledger_name

        # 4. Determine Best Match
        best_ledger, confidence, status, _ = self.find_best_ledger_match(party, tx.narration, is_debit)
        
        tx.ledger_name = best_ledger
        tx.original_ledger_name = best_ledger
        tx.suggested_ledger = best_ledger if status != "Suspense" else None
        tx.mapping_confidence = confidence
        tx.mapping_status = status

        # Suspense is tracked via mapping_status, leaving mathematical validation_status intact
        return best_ledger
