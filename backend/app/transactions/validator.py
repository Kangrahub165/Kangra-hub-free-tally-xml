"""
Statement Balance Validator.

Validates row-by-row running balance integrity and assigns severity-based
validation statuses:
- VALID: Balance math checks out perfectly
- INFO: Minor cosmetic or informational note (does not affect accounting correctness)
- WARNING: Potential issue that may need user review (e.g., balance discrepancy < 1.00)
- ERROR: Definite mathematical error or data integrity problem (e.g., large balance mismatch)
"""
from decimal import Decimal
from typing import List, Tuple
from app.transactions.model import CanonicalStatement, TransactionItem

# Thresholds for severity classification
_TOLERANCE = Decimal("0.01")  # Rounding tolerance (exact match)
_WARNING_THRESHOLD = Decimal("1.00")  # Small discrepancies are WARNINGs
# Everything above _WARNING_THRESHOLD is an ERROR


def normalize_statement_chronology(statement: CanonicalStatement) -> CanonicalStatement:
    """
    Detects if statement transactions are extracted in reverse-chronological order (newest-to-oldest).
    If so, reverses the transaction list to chronological order (oldest-to-newest) so running-balance
    audits, ledger review, and Tally XML exports progress forward in time sequentially.
    """
    if not statement.transactions or len(statement.transactions) < 2:
        return statement

    txs = statement.transactions
    desc_dates = sum(1 for i in range(len(txs) - 1) if txs[i].date > txs[i + 1].date)
    asc_dates = sum(1 for i in range(len(txs) - 1) if txs[i].date < txs[i + 1].date)

    is_reverse = False
    if desc_dates > asc_dates and desc_dates >= 2:
        is_reverse = True
    elif desc_dates == 0 and asc_dates == 0:
        # Transactions on same day or dates tied, test running balance progression
        fwd_matches = 0
        rev_matches = 0
        for i in range(min(len(txs) - 1, 25)):
            b0, b1 = txs[i].balance, txs[i + 1].balance
            if b0 is not None and b1 is not None:
                if abs(b0 + txs[i + 1].credit - txs[i + 1].debit - b1) <= Decimal("0.05"):
                    fwd_matches += 1
                if abs(b1 + txs[i].credit - txs[i].debit - b0) <= Decimal("0.05"):
                    rev_matches += 1
        if rev_matches > fwd_matches and rev_matches >= 2:
            is_reverse = True

    if is_reverse:
        statement.transactions = list(reversed(txs))

        # In chronological order, transactions[0] is the oldest and transactions[-1] is newest
        first_oldest = statement.transactions[0]
        if first_oldest.balance is not None:
            if first_oldest.credit > Decimal("0.00"):
                statement.opening_balance = (first_oldest.balance - first_oldest.credit).quantize(Decimal("0.01"))
            elif first_oldest.debit > Decimal("0.00"):
                statement.opening_balance = (first_oldest.balance + first_oldest.debit).quantize(Decimal("0.01"))
            else:
                statement.opening_balance = first_oldest.balance

        last_newest = statement.transactions[-1]
        if last_newest.balance is not None:
            statement.closing_balance = last_newest.balance

        # Re-index row numbers sequentially 1..N
        for idx, t in enumerate(statement.transactions):
            t.row_index = idx + 1
            if t.id and "-tx-" in t.id:
                prefix = t.id.split("-tx-")[0]
                t.id = f"{prefix}-tx-{idx + 1}"
            elif t.id and t.id.startswith("tx-"):
                t.id = f"tx-{idx + 1}"

    return statement


def validate_statement_balances(statement: CanonicalStatement) -> CanonicalStatement:
    """
    Validates statement balances row-by-row:
    Previous Balance + Credit - Debit == Current Balance.
    
    Assigns severity-based validation statuses instead of blanket WARNING:
    - VALID: Math checks out (within rounding tolerance)
    - WARNING: Small discrepancy (< 1.00) that may be a rounding artifact, or zero-amount row
    - ERROR: Large discrepancy indicating debit/credit misclassification or data error
    
    Also calculates overall and row-level confidence scores.
    """
    if not statement.transactions:
        statement.confidence_score = 0.0
        return statement

    # Normalize chronological order before running balance evaluation
    normalize_statement_chronology(statement)

    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")
    discrepancies = 0
    errors = 0

    # Ensure opening balance is populated if first transaction has running balance
    if statement.opening_balance is None and statement.transactions and statement.transactions[0].balance is not None:
        first_tx = statement.transactions[0]
        if first_tx.credit > Decimal("0.00"):
            statement.opening_balance = (first_tx.balance - first_tx.credit).quantize(Decimal("0.01"))
        elif first_tx.debit > Decimal("0.00"):
            statement.opening_balance = (first_tx.balance + first_tx.debit).quantize(Decimal("0.01"))
        else:
            statement.opening_balance = first_tx.balance

    previous_balance = statement.opening_balance

    for idx, tx in enumerate(statement.transactions):
        tx.row_index = idx + 1
        total_debit += tx.debit
        total_credit += tx.credit

        # Check for zero amount row (neither debit nor credit)
        if tx.debit == Decimal("0.00") and tx.credit == Decimal("0.00"):
            tx.validation_status = "WARNING"
            tx.validation_notes = "Both debit and credit amounts are zero."
            discrepancies += 1
        # Check row math if running balance is available
        elif tx.balance is not None and previous_balance is not None:
            expected_balance = previous_balance + tx.credit - tx.debit
            diff = abs(expected_balance - tx.balance)
            
            if diff <= _TOLERANCE:
                # Perfect match (within rounding tolerance)
                tx.validation_status = "VALID"
                tx.validation_notes = None
                tx.confidence_score = min(100.0, tx.confidence_score + 10.0)
            elif diff <= _WARNING_THRESHOLD:
                # Small discrepancy — likely rounding, not a classification error
                tx.validation_status = "WARNING"
                tx.validation_notes = (
                    f"Minor balance discrepancy: expected {expected_balance:.2f}, "
                    f"got {tx.balance:.2f} (diff: {diff:.2f})."
                )
                tx.confidence_score = max(70.0, tx.confidence_score - 10.0)
                discrepancies += 1
            else:
                # Large discrepancy — possible debit/credit misclassification or missing row
                tx.validation_status = "ERROR"
                tx.validation_notes = (
                    f"Balance mismatch: expected {expected_balance:.2f}, "
                    f"got {tx.balance:.2f} (diff: {diff:.2f}). "
                    f"Possible debit/credit misclassification."
                )
                tx.confidence_score = max(30.0, tx.confidence_score - 50.0)
                discrepancies += 1
                errors += 1
        else:
            # No balance data to validate — mark as valid (not a warning)
            if tx.validation_status != "VALID":
                tx.validation_status = "VALID"

        # Update previous balance for next row
        if tx.balance is not None:
            previous_balance = tx.balance
        elif previous_balance is not None:
            previous_balance = previous_balance + tx.credit - tx.debit

    statement.total_debit = total_debit
    statement.total_credit = total_credit

    # Update statement_from and statement_to accurately based on normalized list
    if statement.transactions:
        statement.statement_from = min(t.date for t in statement.transactions)
        statement.statement_to = max(t.date for t in statement.transactions)
        if statement.closing_balance is None and statement.transactions[-1].balance is not None:
            statement.closing_balance = statement.transactions[-1].balance

    # Calculate overall confidence score
    total_tx = len(statement.transactions)
    if total_tx > 0:
        clean_ratio = (total_tx - discrepancies) / total_tx
        base_confidence = float(clean_ratio * 100.0)
        # Penalize extra for ERRORs
        error_penalty = (errors / total_tx) * 20.0
        statement.confidence_score = round(max(0.0, base_confidence - error_penalty), 2)
    else:
        statement.confidence_score = 100.0

    # Non-destructive duplicate detection (flags duplicates without dropping any transaction)
    detect_duplicate_candidates(statement)

    return statement


def detect_duplicate_candidates(statement: CanonicalStatement) -> CanonicalStatement:
    """
    Identifies duplicate candidates based on (date, debit, credit, clean_narration, reference).
    NON-DESTRUCTIVE: Flags transactions with is_duplicate_suspect=True and duplicate_reason,
    WITHOUT discarding or deleting any transactions from the statement.
    """
    seen_fingerprints = {}
    dup_count = 0
    for idx, tx in enumerate(statement.transactions):
        clean_narr = (tx.narration or "").strip().upper()
        clean_narr = " ".join(clean_narr.split())
        ref = (tx.reference or "").strip().upper()
        
        fingerprint = (
            tx.date,
            tx.debit,
            tx.credit,
            clean_narr,
            ref
        )
        if fingerprint in seen_fingerprints:
            original_row = seen_fingerprints[fingerprint]
            tx.is_duplicate_suspect = True
            tx.duplicate_reason = f"Duplicate candidate: Identical date, amount, and narration to row #{original_row}"
            dup_count += 1
        else:
            seen_fingerprints[fingerprint] = tx.row_index or (idx + 1)
            tx.is_duplicate_suspect = False
            tx.duplicate_reason = None
            
    statement.duplicate_count = dup_count
    return statement


def compile_page_diagnostics(statement: CanonicalStatement, doc: any = None) -> CanonicalStatement:
    """
    Compiles page-by-page transaction accounting diagnostics.
    Reconciles candidate detected lines vs extracted transactions.
    Guarantees Zero Silent Loss visibility.
    """
    import re
    from collections import defaultdict
    from app.transactions.model import PageDiagnosticSummary
    
    page_extracted = defaultdict(int)
    for tx in statement.transactions:
        pg = tx.source_page or 1
        page_extracted[pg] += 1

    date_rx = re.compile(r'^\s*\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b')
    diagnostics = []

    if doc and hasattr(doc, 'pages') and doc.pages:
        for page in doc.pages:
            pg_num = page.page_number
            detected_candidates = 0
            unparsed = []
            for line in page.lines:
                line_s = line.strip()
                if date_rx.match(line_s):
                    detected_candidates += 1
                    matched = any(
                        tx.source_page == pg_num and 
                        any(line_s in s for s in (tx.source_lines or []))
                        for tx in statement.transactions
                    )
                    if not matched and detected_candidates > page_extracted[pg_num]:
                        unparsed.append(line_s[:120])

            diagnostics.append(
                PageDiagnosticSummary(
                    page_number=pg_num,
                    detected_candidate_count=max(detected_candidates, page_extracted[pg_num]),
                    extracted_transaction_count=page_extracted[pg_num],
                    unparsed_candidate_lines=unparsed[:5]
                )
            )
    else:
        for pg in sorted(page_extracted.keys()):
            diagnostics.append(
                PageDiagnosticSummary(
                    page_number=pg,
                    detected_candidate_count=page_extracted[pg],
                    extracted_transaction_count=page_extracted[pg],
                    unparsed_candidate_lines=[]
                )
            )

    statement.page_diagnostics = diagnostics
    return statement

