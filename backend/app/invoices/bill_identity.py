import re
import difflib
import hashlib
from datetime import date, datetime
from typing import List, Optional, Union, Dict, Any
from decimal import Decimal

from app.invoices.model import InvoiceDocument, InvoiceItem, PartyInfo, to_decimal
from app.core import db

def normalize_bill_number(raw_bill_no: Optional[str]) -> str:
    """
    Normalizes invoice/bill numbers by stripping prefixes, punctuation, symbols, leading zeroes,
    and converting to lowercase for strict identity matching.
    e.g. 'INV-00123' -> '123', 'SI/2026/045' -> '2026045'
    """
    if not raw_bill_no:
        return "unknown"
    s = str(raw_bill_no).strip().lower()
    # Strip generic invoice prefix if followed by digits/delimiters
    s = re.sub(r'^(inv|invoice)[-_/\s]*', '', s)
    # Strip non-alphanumeric
    clean = re.sub(r'[^a-z0-9]', '', s)
    if not clean:
        return "unknown"
    # If clean consists of digits only, strip leading zeros
    if clean.isdigit():
        clean_stripped = clean.lstrip('0')
        return clean_stripped if clean_stripped else "0"
    # If it ends with digits preceded by zeros
    clean = re.sub(r'([a-z]+)0+(\d+)', r'\1\2', clean)
    return clean

def normalize_bill_date(raw_date: Union[date, datetime, str, None]) -> str:
    """
    Normalizes invoice date into canonical YYYY-MM-DD format.
    Handles multiple date representations.
    """
    if not raw_date:
        return date.today().isoformat()
    if isinstance(raw_date, (date, datetime)):
        return raw_date.strftime("%Y-%m-%d")

    s = str(raw_date).strip()
    # Common format matches
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Regex search for YYYY-MM-DD or DD/MM/YYYY
    match_iso = re.search(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', s)
    if match_iso:
        y, m, d = match_iso.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    match_dmy = re.search(r'(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})', s)
    if match_dmy:
        d, m, y = match_dmy.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    return str(raw_date)[:10]

def normalize_company_name(raw_name: Optional[str]) -> str:
    """
    Normalizes company/supplier/buyer name by stripping legal suffix acronyms,
    punctuation, and excessive whitespace.
    """
    if not raw_name:
        return ""
    name = str(raw_name).lower().strip()
    # Remove standard company legal entities
    suffixes = [
        r'\bpvt\.?\s*ltd\.?', r'\bprivate\s*limited\b', r'\bltd\.?', r'\blimited\b',
        r'\bllp\b', r'\binc\.?', r'\bcorp\.?', r'\bco\b', r'\bfirm\b',
        r'\benterprises?\b', r'\btraders?\b', r'\bagencies\b', r'\bagency\b'
    ]
    for sfx in suffixes:
        name = re.sub(sfx, '', name, flags=re.IGNORECASE)
    # Strip non-alphanumeric except spaces
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def company_similarity(name1: str, name2: str) -> float:
    """
    Computes company name similarity ratio (0.0 to 1.0).
    PRD Section 5 requires >= 90% match to group identical companies across multi-page scans.
    """
    n1 = normalize_company_name(name1)
    n2 = normalize_company_name(name2)
    if not n1 and not n2:
        return 1.0
    if not n1 or not n2:
        return 0.0
    if n1 == n2:
        return 1.0
    if (len(n1) > 4 and n1 in n2) or (len(n2) > 4 and n2 in n1):
        return 0.95
    return difflib.SequenceMatcher(None, n1, n2).ratio()

def are_same_company(name1: str, name2: str, threshold: float = 0.90) -> bool:
    """Determines whether two company strings represent the same organization."""
    return company_similarity(name1, name2) >= threshold

def compute_bill_fingerprint(
    user_id: str,
    bill_number: str,
    bill_date: str,
    company_name: str,
    total_amount: float
) -> str:
    """
    Computes a cryptographic SHA-256 fingerprint for bill identity.
    Fingerprint = sha256(user_id:clean_bill:clean_date:clean_company:round(total_amount, 2))
    Prevents duplicate credit charges when re-uploading an already converted bill today.
    """
    clean_bill = normalize_bill_number(bill_number)
    clean_date = normalize_bill_date(bill_date)
    clean_company = normalize_company_name(company_name)
    amt = round(float(total_amount or 0.0), 2)
    raw_key = f"{user_id}:{clean_bill}:{clean_date}:{clean_company}:{amt}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

def get_doc_identity_tuple(doc: InvoiceDocument) -> tuple:
    """
    Extracts the identity key tuple (clean_bill, clean_date, clean_company) for a document.
    """
    bill_no = normalize_bill_number(doc.invoice_number or doc.bill_number)
    bill_dt = normalize_bill_date(doc.invoice_date)
    # Relevant company: supplier in purchase, buyer or supplier in sales
    comp = doc.supplier.name or doc.buyer.name or ""
    clean_comp = normalize_company_name(comp)
    return (bill_no, bill_dt, clean_comp)

def group_and_merge_invoice_documents(
    docs: List[InvoiceDocument],
    user_id: str = "",
    today_ist: Optional[str] = None
) -> List[InvoiceDocument]:
    """
    Smart Multi-Page Bill Grouping Engine (PRD Sections 1, 3, 5).
    Identifies multi-page bills by (Bill Number + Date + Company Name) with >= 90% company match.
    Merges multi-page documents into 1 single bill costing 1 credit.
    Annotates each consolidated document with its fingerprint hash and free-reconversion status.
    """
    if not docs:
        return []

    from app.api.usage import get_kolkata_today
    effective_today = today_ist or get_kolkata_today()

    # Step 1: Cluster documents into groups by identity key
    clusters: List[List[InvoiceDocument]] = []

    for doc in docs:
        d_bill, d_date, d_comp = get_doc_identity_tuple(doc)

        matched_cluster = None
        # Only cluster if bill number is known
        if d_bill != "unknown":
            for cluster in clusters:
                c_lead = cluster[0]
                c_bill, c_date, c_comp = get_doc_identity_tuple(c_lead)

                # Same bill number and same date
                if d_bill == c_bill and d_date == c_date:
                    # Fuzzy match company name >= 90%
                    if not d_comp or not c_comp or are_same_company(d_comp, c_comp, threshold=0.90):
                        matched_cluster = cluster
                        break

        if matched_cluster is not None:
            matched_cluster.append(doc)
        else:
            clusters.append([doc])

    # Step 2: Merge each cluster into a single consolidated InvoiceDocument
    consolidated_docs: List[InvoiceDocument] = []

    for cluster in clusters:
        if len(cluster) == 1:
            master = cluster[0]
            # Annotate fingerprint
            company_name = master.supplier.name or master.buyer.name or ""
            fp = compute_bill_fingerprint(
                user_id=user_id,
                bill_number=master.invoice_number or master.bill_number or "",
                bill_date=str(master.invoice_date),
                company_name=company_name,
                total_amount=float(master.grand_total or 0.0)
            )
            # Check if converted today
            already_converted = db.is_bill_already_converted_today(user_id, fp, effective_today) if user_id else False
            master.raw_text_preview = master.raw_text_preview or ""
            # Set dynamic properties if model allows or via attributes
            setattr(master, "fingerprint_hash", fp)
            setattr(master, "is_free_reconversion", already_converted)
            setattr(master, "distinct_bill_key", f"{normalize_bill_number(master.invoice_number)}|{normalize_bill_date(master.invoice_date)}")
            consolidated_docs.append(master)
            continue

        # Multiple pages detected for the same invoice identity!
        # Pick the best document as primary master (one with party info or most items)
        master = max(cluster, key=lambda d: (len(d.supplier.name or ""), len(d.items)))
        # Create a combined copy
        all_items: List[InvoiceItem] = []
        seen_items = set()

        total_pages = sum(d.source_page_count for d in cluster)
        all_page_numbers = []
        for d in cluster:
            all_page_numbers.extend(d.page_numbers or [1])
        all_filenames = list(dict.fromkeys(d.source_filename for d in cluster if d.source_filename))

        # Collect unique line items across pages
        for d in cluster:
            for item in d.items:
                # Key for deduplicating repeated items across overlapping pages
                item_key = (
                    item.item_name.strip().lower(),
                    str(item.quantity),
                    str(item.rate),
                    str(item.taxable_amount)
                )
                if item_key not in seen_items:
                    seen_items.add(item_key)
                    all_items.append(item)

        # Re-number item indices sequentially
        for idx, item in enumerate(all_items, start=1):
            item.item_index = idx

        # Recompute totals if items were combined from multiple pages
        taxable_sum = sum(it.taxable_amount for it in all_items)
        cgst_sum = sum(it.cgst_amount for it in all_items)
        sgst_sum = sum(it.sgst_amount for it in all_items)
        igst_sum = sum(it.igst_amount for it in all_items)
        cess_sum = sum(it.cess_amount for it in all_items)
        calculated_grand = taxable_sum + cgst_sum + sgst_sum + igst_sum + cess_sum

        # Take max grand total found across pages or calculated
        final_grand = max(master.grand_total, calculated_grand) if calculated_grand > Decimal("0.00") else master.grand_total

        # Collect errors and warnings
        combined_errors = list(dict.fromkeys(err for d in cluster for err in d.errors))
        combined_warnings = list(dict.fromkeys(warn for d in cluster for warn in d.warnings))
        combined_warnings.append(
            f"Multi-page invoice automatically consolidated from {len(cluster)} pages into 1 single bill (1 credit)."
        )

        master.items = all_items
        master.taxable_total = taxable_sum if taxable_sum > Decimal("0.00") else master.taxable_total
        master.cgst_total = cgst_sum if cgst_sum > Decimal("0.00") else master.cgst_total
        master.sgst_total = sgst_sum if sgst_sum > Decimal("0.00") else master.sgst_total
        master.igst_total = igst_sum if igst_sum > Decimal("0.00") else master.igst_total
        master.cess_total = cess_sum if cess_sum > Decimal("0.00") else master.cess_total
        master.grand_total = final_grand
        master.source_page_count = max(len(cluster), total_pages)
        master.page_numbers = sorted(list(set(all_page_numbers)))
        master.source_filename = " + ".join(all_filenames[:3]) + (f" (+{len(all_filenames)-3} more)" if len(all_filenames) > 3 else "")
        master.has_page_continuation = True
        master.continuation_note = f"Multi-page bill merged: {len(cluster)} pages ({len(all_items)} total items)."
        master.errors = combined_errors
        master.warnings = combined_warnings

        # Annotate fingerprint
        company_name = master.supplier.name or master.buyer.name or ""
        fp = compute_bill_fingerprint(
            user_id=user_id,
            bill_number=master.invoice_number or master.bill_number or "",
            bill_date=str(master.invoice_date),
            company_name=company_name,
            total_amount=float(master.grand_total or 0.0)
        )
        already_converted = db.is_bill_already_converted_today(user_id, fp, effective_today) if user_id else False

        setattr(master, "fingerprint_hash", fp)
        setattr(master, "is_free_reconversion", already_converted)
        setattr(master, "distinct_bill_key", f"{normalize_bill_number(master.invoice_number)}|{normalize_bill_date(master.invoice_date)}")

        consolidated_docs.append(master)

    return consolidated_docs
