import os
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import uuid4
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status, Response, Request
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import get_current_user, CurrentUser
from app.accounting.ledger_importer import global_ledger_store
from app.accounting.stock_item_importer import global_stock_item_store
from app.invoices.model import (
    InvoiceDocument,
    FinalInvoiceSnapshot,
    InvoiceBatchResult,
    LedgerMappingConfig
)
from app.invoices.extractor import InvoiceExtractor
from app.invoices.validator import (
    validate_invoice_document,
    detect_batch_duplicates,
    compute_batch_summary
)
from app.invoices.bill_identity import (
    group_and_merge_invoice_documents,
    compute_bill_fingerprint
)
from app.invoices.xml_generator import InvoiceTallyXMLGenerator
from app.invoices.xml_validator import validate_invoice_tally_xml
from app.utils.logger import app_logger
from app.core import db

router = APIRouter(prefix="/invoices", tags=["Sales & Purchase Invoices"])

def confirm_bill_credits_deduction(user: CurrentUser, docs: List[InvoiceDocument]) -> Dict[str, Any]:
    """
    Enforces credit deduction strictly upon conversion confirmation (XML generation).
    1. Multi-page bills consolidated into 1 bill costing 1 credit.
    2. Re-uploading an already converted bill today costs 0 credits.
    3. Deducts 1 credit per new distinct bill from daily free pool (5/day) or additional pages.
    4. Bypasses limits for Staff and Admin.
    5. Records each converted bill in SQLite converted_bills table with its cryptographic fingerprint.
    """
    from app.api.usage import get_kolkata_today, get_user_daily_limit, get_user_additional_pages, deduct_user_additional_pages

    today_str = get_kolkata_today()
    is_unlimited = user.has_quota_bypass or user.is_admin or user.is_staff or user.is_unlimited

    new_bills_to_charge: List[InvoiceDocument] = []
    already_converted_bills: List[InvoiceDocument] = []

    for doc in docs:
        comp_name = doc.supplier.name or doc.buyer.name or ""
        fp = getattr(doc, "fingerprint_hash", None)
        if not fp:
            fp = compute_bill_fingerprint(
                user_id=user.id,
                bill_number=doc.invoice_number or doc.bill_number or "",
                bill_date=str(doc.invoice_date),
                company_name=comp_name,
                total_amount=float(doc.grand_total or 0.0)
            )
            setattr(doc, "fingerprint_hash", fp)

        if db.is_bill_already_converted_today(user.id, fp, today_str):
            already_converted_bills.append(doc)
            setattr(doc, "is_free_reconversion", True)
        else:
            new_bills_to_charge.append(doc)
            setattr(doc, "is_free_reconversion", False)

    charge_count = len(new_bills_to_charge)

    if not is_unlimited and charge_count > 0:
        daily_limit = get_user_daily_limit(user)
        user_used = db.get_daily_usage(user.id, today_str)
        if user_used == 0 and getattr(user, "email", None):
            user_used = db.get_daily_usage(user.email, today_str)

        # Anti-abuse device pool check
        dev_used = 0
        if getattr(user, "device_id", None) and not db.is_device_whitelisted(user.device_id):
            dev_used = db.get_device_daily_usage(user.device_id, today_str)

        effective_used = max(user_used, dev_used)
        rem_free = max(0, daily_limit - effective_used)
        add_bal = get_user_additional_pages(user)
        total_avail = rem_free + add_bal

        if total_avail < charge_count:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your daily free bill limit has been reached. Please upgrade to a Staff Membership subscription for higher conversion limits."
            )

        free_deduct = min(charge_count, rem_free)
        add_deduct = max(0, charge_count - rem_free)

        if free_deduct > 0:
            db.record_daily_usage(user.id, today_str, free_deduct)
            if getattr(user, "email", None):
                db.record_daily_usage(user.email, today_str, free_deduct)
        if add_deduct > 0:
            deduct_user_additional_pages(user.id, add_deduct)
            if getattr(user, "email", None):
                deduct_user_additional_pages(user.email, add_deduct)

    # Persist every converted bill in converted_bills table for zero-charge re-uploads & audit
    for doc in new_bills_to_charge:
        comp_name = doc.supplier.name or doc.buyer.name or ""
        fp = getattr(doc, "fingerprint_hash", None)
        try:
            db.record_converted_bill(
                user_id=user.id,
                bill_number=doc.invoice_number or doc.bill_number or "UNKNOWN",
                bill_date=str(doc.invoice_date),
                company_name=comp_name,
                total_amount=float(doc.grand_total or 0.0),
                fingerprint_hash=fp or "",
                page_count=getattr(doc, "source_page_count", 1),
                date_ist=today_str
            )
        except Exception as e:
            app_logger.warning(f"Failed to record converted bill in SQLite: {e}")

    return {
        "new_bills_charged": charge_count,
        "already_converted_free": len(already_converted_bills),
        "total_bills": len(docs)
    }

@router.get("/config", response_model=LedgerMappingConfig)
async def get_default_config():
    """Returns default ledger mapping configuration."""
    return LedgerMappingConfig()

@router.post("/upload", response_model=InvoiceBatchResult)
async def upload_invoice_files(
    files: List[UploadFile] = File(...),
    default_invoice_type: Optional[str] = Form("AUTO"),
    company_gstin: Optional[str] = Form(None),
    user: CurrentUser = Depends(get_current_user)
):
    """
    Accepts JPG, JPEG, and PDF invoice files.
    Runs extraction, applies Smart Multi-Page Bill Grouping (merging pages of the same bill into 1),
    matches against imported Tally masters, and computes batch metrics.
    PRD Rule: Does NOT deduct credits on upload. Deduction occurs on conversion confirmation.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No invoice files uploaded."
        )

    from app.api.usage import get_kolkata_today, get_user_daily_limit, get_user_additional_pages

    today_str = get_kolkata_today()
    is_unlimited = user.has_quota_bypass or user.is_admin or user.is_staff or user.is_unlimited

    extractor = InvoiceExtractor()
    extracted_docs: List[InvoiceDocument] = []

    # Retrieve user's known ledgers for matching
    user_id = user.id
    user_ledgers = global_ledger_store.get_user_ledgers(user_id)
    known_ledgers = [l.dict() if hasattr(l, 'dict') else l.model_dump() for l in user_ledgers]

    for uploaded_file in files:
        fn = uploaded_file.filename or "invoice.pdf"
        fn_lower = fn.lower()
        if not fn_lower.endswith(('.jpg', '.jpeg', '.png', '.webp', '.pdf')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format for '{fn}'. Please upload JPG, JPEG, or PDF."
            )

        content = await uploaded_file.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{fn}' is empty."
            )

        try:
            docs = extractor.extract_from_file(
                file_bytes=content,
                filename=fn,
                known_company_gstin=company_gstin,
                type_hint=default_invoice_type if default_invoice_type in ("SALES", "PURCHASE") else None
            )
            stock_uid = user_id if global_stock_item_store.get_items(user_id) else "default_session"
            ledger_uid = user_id if global_ledger_store.get_user_ledgers(user_id) else "default_session"

            for d in docs:
                if default_invoice_type in ("PURCHASE", "SALES"):
                    d.invoice_type = default_invoice_type
                    d.is_type_manual_override = True

                # 1. Match line items against user's imported stock items
                for it in d.items:
                    match_sug = global_stock_item_store.match_item(stock_uid, it.item_name, it.hsn_sac)
                    it.mapping_confidence = match_sug.confidence
                    it.mapping_status = match_sug.mapping_status
                    it.match_suggestions = match_sug.suggestions
                    if match_sug.matched_stock_item:
                        it.matched_stock_item = match_sug.matched_stock_item.name
                        it.requires_item_creation = False
                        tally_unit = match_sug.matched_stock_item.base_units or "NOS"
                        it.invoice_uom = it.invoice_uom or it.uom
                        it.tally_uom = tally_unit

                        # Align dual quantity representation with Tally UOM
                        if it.has_dual_qty:
                            t_norm = tally_unit.strip().upper()
                            uom_b_norm = (it.uom_option_b or "").strip().upper()
                            uom_a_norm = (it.uom_option_a or "").strip().upper()
                            pcs_family = ("PCS", "NOS", "PIECES", "PIECE", "PCE", "UNIT", "UNITS")
                            case_family = ("CASE", "CASES", "BOX", "BOXES", "CTN", "CARTON", "CARTONS", "BAG", "BAGS")

                            if t_norm == uom_b_norm or (t_norm in pcs_family and uom_b_norm in pcs_family):
                                it.selected_qty_option = "B"
                                it.quantity = it.quantity_option_b
                                it.uom = it.uom_option_b
                                it.rate = it.rate_option_b
                                it.alternate_quantity = it.quantity_option_a
                                it.alternate_uom = it.uom_option_a
                            elif t_norm == uom_a_norm or (t_norm in case_family and uom_a_norm in case_family):
                                it.selected_qty_option = "A"
                                it.quantity = it.quantity_option_a
                                it.uom = it.uom_option_a
                                it.rate = it.rate_option_a
                                it.alternate_quantity = it.quantity_option_b
                                it.alternate_uom = it.uom_option_b
                            else:
                                it.uom = tally_unit
                        else:
                            it.uom = tally_unit
                    else:
                        it.requires_item_creation = True
                        it.invoice_uom = it.invoice_uom or it.uom
                        it.tally_uom = it.invoice_uom

                # 2. Match external Party against imported ledgers
                party_to_match = d.buyer if d.invoice_type == "SALES" else d.supplier
                if party_to_match and party_to_match.name:
                    ledger_match = global_ledger_store.match_ledger(
                        ledger_uid,
                        party_to_match.name,
                        party_to_match.gstin,
                        party_to_match.pan
                    )
                    party_to_match.mapping_confidence = ledger_match["confidence"]
                    party_to_match.mapping_status = ledger_match["mapping_status"]
                    party_to_match.match_suggestions = ledger_match["suggestions"]
                    if ledger_match["matched_ledger_name"]:
                        party_to_match.matched_ledger_name = ledger_match["matched_ledger_name"]
                        party_to_match.requires_ledger_creation = False
                    else:
                        party_to_match.requires_ledger_creation = True

                extracted_docs.append(d)
        except Exception as e:
            app_logger.error(f"Error parsing invoice file '{fn}': {str(e)}", exc_info=True)
            err_doc = InvoiceDocument(
                invoice_number="UNKNOWN",
                source_filename=fn,
                errors=[f"Failed to extract invoice from '{fn}': {str(e)}"],
                is_valid=False
            )
            extracted_docs.append(err_doc)

    # Apply Smart Bill Grouping & Multi-Page Consolidation (PRD Section 1, 3, 5)
    # Merges pages with matching (Bill No + Date + Company) into 1 distinct bill
    consolidated_docs = group_and_merge_invoice_documents(
        docs=extracted_docs,
        user_id=user.id,
        today_ist=today_str
    )

    # Validate each consolidated invoice and match masters
    for doc in consolidated_docs:
        validate_invoice_document(doc, known_ledgers=known_ledgers)

    # Detect duplicates in the batch
    detect_batch_duplicates(consolidated_docs)

    # Compute batch summary
    summary = compute_batch_summary(consolidated_docs)
    job_id = uuid4().hex

    # Calculate distinct bills and credits required
    distinct_bills_count = len(consolidated_docs)
    credits_required = sum(1 for d in consolidated_docs if not getattr(d, "is_free_reconversion", False))

    # Quota check for preview: check if user has enough quota available
    daily_limit = get_user_daily_limit(user)
    user_used = db.get_daily_usage(user.id, today_str)
    if user_used == 0 and getattr(user, "email", None):
        user_used = db.get_daily_usage(user.email, today_str)

    dev_used = 0
    if getattr(user, "device_id", None) and not db.is_device_whitelisted(user.device_id):
        dev_used = db.get_device_daily_usage(user.device_id, today_str)

    effective_used = max(user_used, dev_used)
    remaining_free = max(0, daily_limit - effective_used)
    additional_bal = get_user_additional_pages(user)
    total_avail = remaining_free + additional_bal

    if not is_unlimited and credits_required > 0 and total_avail < credits_required:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your daily free bill limit has been reached. Please upgrade to a Staff Membership subscription for higher conversion limits."
        )

    return InvoiceBatchResult(
        job_id=job_id,
        invoices=consolidated_docs,
        summary=summary,
        ledger_mapping=LedgerMappingConfig(),
        distinct_bills_count=distinct_bills_count,
        credits_required=credits_required,
        remaining_free_credits=remaining_free if not is_unlimited else 9999,
        user_role=user.role,
        is_staff=user.is_staff,
        is_gold=user.is_gold
    )

@router.post("/validate", response_model=InvoiceBatchResult)
async def validate_invoice_batch(
    snapshot: FinalInvoiceSnapshot,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Re-validates an edited snapshot of invoices and recalculates batch summary.
    Enforces authentication.
    """
    user_ledgers = global_ledger_store.get_user_ledgers(user.id)
    known_ledgers = [l.dict() if hasattr(l, 'dict') else l.model_dump() for l in user_ledgers]

    for doc in snapshot.invoices:
        validate_invoice_document(doc, known_ledgers=known_ledgers)

    detect_batch_duplicates(snapshot.invoices)
    summary = compute_batch_summary(snapshot.invoices)

    from app.api.usage import get_kolkata_today, get_user_daily_limit
    today_str = get_kolkata_today()
    user_used = db.get_daily_usage(user.id, today_str)
    daily_limit = get_user_daily_limit(user)
    remaining_free = max(0, daily_limit - user_used)

    distinct_count = len(snapshot.invoices)
    credits_req = sum(1 for d in snapshot.invoices if not getattr(d, "is_free_reconversion", False))

    return InvoiceBatchResult(
        job_id=uuid4().hex,
        invoices=snapshot.invoices,
        summary=summary,
        ledger_mapping=snapshot.ledger_mapping,
        distinct_bills_count=distinct_count,
        credits_required=credits_req,
        remaining_free_credits=remaining_free if not user.has_quota_bypass else 9999,
        user_role=user.role,
        is_staff=user.is_staff,
        is_gold=user.is_gold
    )

@router.post("/generate-xml")
async def generate_invoice_xml_endpoint(
    snapshot: FinalInvoiceSnapshot,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Generates Tally XML strictly conforming to PURCHASE SAMPLE.xml and SALES SAMPLE.xml.
    Enforces conversion confirmation credit deduction and deduplication.
    Validates XML syntax, structure, double-entry balance, and returns XML preview.
    """
    if not snapshot.invoices:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No invoices provided in snapshot."
        )

    # Deduct credits strictly upon conversion confirmation
    charge_info = confirm_bill_credits_deduction(user=user, docs=snapshot.invoices)

    generator = InvoiceTallyXMLGenerator()
    try:
        xml_str = generator.generate_xml(snapshot)
    except ValueError as ve:
        summary = compute_batch_summary(snapshot.invoices)
        return {
            "success": False,
            "filename": "error.xml",
            "is_valid": False,
            "validation_errors": [str(ve)],
            "xml_content": "",
            "summary": summary.dict() if hasattr(summary, 'dict') else summary.model_dump(),
            "charge_info": charge_info
        }

    is_valid, validation_errors = validate_invoice_tally_xml(xml_str)
    summary = compute_batch_summary(snapshot.invoices)

    # Formulate meaningful filename
    if len(snapshot.invoices) == 1:
        inv = snapshot.invoices[0]
        inv_clean = re.sub(r'[^A-Za-z0-9_-]', '_', inv.invoice_number or "INV")
        type_prefix = "Purchase" if inv.invoice_type == "PURCHASE" else "Sales"
        filename = f"{type_prefix}_INV_{inv_clean}.xml"
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"KangraHub_Sales_Purchase_Import_{timestamp}.xml"

    # Record conversion history for dashboard tracking
    job_id = uuid4().hex
    try:
        filenames = [d.source_filename for d in snapshot.invoices if d.source_filename]
        display_name = ", ".join(filenames[:2]) + (f" (+{len(filenames)-2} more)" if len(filenames) > 2 else "")
        db.save_conversion({
            "id": job_id,
            "user_id": user.id,
            "user_email": getattr(user, "email", ""),
            "file_name": display_name or filename,
            "bank_name": "Sales & Purchase Invoices",
            "total_pdf_pages": sum(getattr(d, "source_page_count", 1) for d in snapshot.invoices),
            "pages_processed": len(snapshot.invoices),
            "pages_skipped": 0,
            "free_quota_used": charge_info["new_bills_charged"],
            "additional_quota_used": 0,
            "transaction_count": sum(len(d.items) for d in snapshot.invoices),
            "status": "COMPLETED",
            "metadata": {
                "bill_count": len(snapshot.invoices),
                "total_amount": float(summary.total_invoice_amount) if summary else 0.0
            }
        })
    except Exception as e:
        app_logger.warning(f"Unable to record conversion history for invoices: {e}")

    return {
        "success": is_valid,
        "filename": filename,
        "is_valid": is_valid,
        "validation_errors": validation_errors,
        "xml_content": xml_str,
        "summary": summary.dict() if hasattr(summary, 'dict') else summary.model_dump(),
        "charge_info": charge_info
    }

@router.post("/download-xml")
async def download_invoice_xml_endpoint(
    snapshot: FinalInvoiceSnapshot,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Generates and downloads the Tally XML file as an attachment.
    Enforces conversion confirmation credit deduction and pre-export XML validation.
    """
    if not snapshot.invoices:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No invoices provided in snapshot."
        )

    # Deduct credits strictly upon conversion confirmation
    confirm_bill_credits_deduction(user=user, docs=snapshot.invoices)

    generator = InvoiceTallyXMLGenerator()
    try:
        xml_str = generator.generate_xml(snapshot)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )

    is_valid, validation_errors = validate_invoice_tally_xml(xml_str)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pre-export XML safety validation failed: {'; '.join(validation_errors)}"
        )

    if len(snapshot.invoices) == 1:
        inv = snapshot.invoices[0]
        inv_clean = re.sub(r'[^A-Za-z0-9_-]', '_', inv.invoice_number or "INV")
        type_prefix = "Purchase" if inv.invoice_type == "PURCHASE" else "Sales"
        filename = f"{type_prefix}_INV_{inv_clean}.xml"
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"KangraHub_Sales_Purchase_Import_{timestamp}.xml"

    return Response(
        content=xml_str.encode("utf-8"),
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate"
        }
    )
