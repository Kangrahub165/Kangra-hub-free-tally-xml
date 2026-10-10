import os
import uuid
import re
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import (
    QuotaExceededException,
    InvalidPDFException,
    PasswordProtectedPDFException,
    UnsupportedBankException,
    XMLGenerationException
)
from app.core.security import get_current_user, CurrentUser
from app.pdf.validator import validate_pdf_file, validate_image_file
from app.gemini.extractor import GeminiExtractor
from app.pdf.extractor import extract_pdf_data
from app.detector.bank_detector import detect_bank_from_document
from app.parsers.registry import parser_registry
from app.accounting.mapper import LedgerMapper
from app.accounting.voucher_classifier import classify_voucher_type
from app.accounting.reversal_detector import ReversalDetector
from app.accounting.ledger_importer import global_ledger_store
from app.api.ledgers import USER_BANK_CONFIGS
from app.tally.xml_generator import TallyXMLGenerator
from app.excel.excel_generator import TallyExcelGenerator
from app.excel.consistency_validator import validate_conversion_consistency
from app.tally.xml_validator import validate_tally_xml
from app.utils.temp_files import TEMP_PROCESSING_DIR
from app.utils.logger import app_logger
from app.transactions.model import CanonicalStatement, TransactionItem
from app.transactions.validator import compile_page_diagnostics, detect_duplicate_candidates
from app.transactions.snapshot import FinalConversionSnapshot, validate_conversion_snapshot
from app.api.usage import get_user_usage_data, record_user_page_usage, get_user_additional_pages, deduct_user_additional_pages, grant_user_additional_pages
from app.core import db
import json
import asyncio

# Permanent storage directory for conversion PDF workspace documents
CONVERSION_STORAGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "uploads",
    "conversion_pdfs"
)
os.makedirs(CONVERSION_STORAGE_DIR, exist_ok=True)

# Per-job/user async lock to prevent race conditions & double quota consumption from concurrent browser tabs
JOB_PROCESSING_LOCKS: Dict[str, asyncio.Lock] = {}

def _get_user_lock(user_id: str) -> asyncio.Lock:
    if user_id not in JOB_PROCESSING_LOCKS:
        JOB_PROCESSING_LOCKS[user_id] = asyncio.Lock()
    return JOB_PROCESSING_LOCKS[user_id]

router = APIRouter(prefix="/conversions", tags=["Conversions"])

# In-memory jobs store for reliable execution across server calls, preloaded from SQLite
IN_MEMORY_JOBS: Dict[str, Dict[str, Any]] = {}
try:
    for _conv in db.get_all_conversions():
        _meta = {}
        if _conv.get("metadata_json"):
            try:
                _meta = json.loads(_conv["metadata_json"])
            except Exception:
                pass
        _raw_txs = _meta.get("transactions") or []
        _loaded_txs = []
        for _tr in _raw_txs:
            try:
                _loaded_txs.append(TransactionItem(**_tr))
            except Exception:
                pass

        _job_entry = {
            "id": _conv["id"],
            "user_id": _conv["user_id"],
            "user_email": _conv.get("user_email", ""),
            "file_name": _conv["file_name"],
            "bank_name": _conv["bank_name"],
            "statement_format": _meta.get("parser_name", _conv["bank_name"]),
            "page_count": _conv["total_pdf_pages"],
            "total_pdf_pages": _conv["total_pdf_pages"],
            "pages_processed": _conv["pages_processed"],
            "pages_skipped": _conv["pages_skipped"],
            "free_quota_used": _conv["free_quota_used"],
            "additional_quota_used": _conv["additional_quota_used"],
            "transaction_count": len(_loaded_txs) or _conv["transaction_count"],
            "raw_transaction_count": len(_loaded_txs) or _conv["transaction_count"],
            "status": _conv["status"],
            "is_partial_conversion": bool(_conv["is_partial_conversion"]),
            "created_at": _conv["created_at"],
            "confidence_score": _meta.get("confidence_score", 100.0),
            "confidence_tier": _meta.get("confidence_tier", "HIGH"),
            "parser_name": _meta.get("parser_name", _conv["bank_name"]),
            "bank_ledger_name": _meta.get("bank_ledger_name", "Bank Account"),
            "cash_ledger_name": _meta.get("cash_ledger_name", "Cash"),
            "transactions": _loaded_txs,
            "pdf_path": _meta.get("pdf_path"),
            "password": _meta.get("password")
        }
        if _loaded_txs:
            _job_entry["statement"] = CanonicalStatement(
                bank=_conv["bank_name"],
                statement_format=_meta.get("parser_name", "Standard"),
                transactions=_loaded_txs
            )
        IN_MEMORY_JOBS[_conv["id"]] = _job_entry
except Exception as _e:
    app_logger.warning(f"Unable to preload conversions from SQLite: {_e}")

def _ensure_job_statement(job: Dict[str, Any]) -> CanonicalStatement:
    """Ensures statement object exists on job and is populated with transactions."""
    statement = job.get("statement")
    if statement is not None and hasattr(statement, "transactions") and statement.transactions:
        return statement
    txs = job.get("transactions") or []
    tx_items = []
    for t in txs:
        if isinstance(t, TransactionItem):
            tx_items.append(t)
        elif isinstance(t, dict):
            try:
                tx_items.append(TransactionItem(**t))
            except Exception:
                pass
    statement = CanonicalStatement(
        bank=job.get("bank_name", "Bank"),
        statement_format=job.get("statement_format", "Standard"),
        transactions=tx_items,
        opening_balance=Decimal(str(job["opening_balance"])) if job.get("opening_balance") is not None else None,
        closing_balance=Decimal(str(job["closing_balance"])) if job.get("closing_balance") is not None else None,
        total_debit=Decimal(str(job["total_debit"])) if job.get("total_debit") is not None else Decimal("0.00"),
        total_credit=Decimal(str(job["total_credit"])) if job.get("total_credit") is not None else Decimal("0.00")
    )
    job["statement"] = statement
    job["transactions"] = tx_items
    return statement

USER_SAVED_RULES: Dict[str, Dict[str, str]] = {}

class ReviewTransactionRequest(BaseModel):
    transactions: List[TransactionItem]
    bank_ledger_name: Optional[str] = None
    cash_ledger_name: Optional[str] = None

class SelectBankRequest(BaseModel):
    bank_name: str

class UpdateRowRequest(BaseModel):
    row_index: int
    ledger_name: Optional[str] = None
    voucher_type: Optional[str] = None
    instrument_number: Optional[str] = None
    narration: Optional[str] = None
    save_as_rule: bool = False

class BulkAssignLedgerRequest(BaseModel):
    row_indices: Optional[List[int]] = None
    ledger_name: Optional[str] = None
    voucher_type: Optional[str] = None
    apply_to_similar: bool = False
    tx_ids: Optional[List[str]] = None
    action: Optional[str] = "ASSIGN"  # "ASSIGN" | "AUTO_RESOLVE" | "IGNORE_WARNINGS"

class GenerateExcelRequest(BaseModel):
    bank_ledger_name: Optional[str] = None
    cash_ledger_name: Optional[str] = None

class GenerateTallyXMLRequest(BaseModel):
    bank_ledger_name: Optional[str] = None
    cash_ledger_name: Optional[str] = None
    confirm_suspense: bool = True

class ConversionJobSummary(BaseModel):
    id: str
    user_id: str
    file_name: str
    bank_name: str
    statement_format: str
    page_count: int
    total_pdf_pages: int = 0
    pages_processed: int = 0
    pages_skipped: int = 0
    pages_pending: int = 0
    page_statuses: Dict[str, str] = {}
    free_quota_used: int = 0
    additional_quota_used: int = 0
    is_partial_conversion: bool = False
    remaining_pages: int = 0
    suggested_additional_price: float = 0.0
    transaction_count: int
    rejected_transaction_count: int = 0
    raw_transaction_count: int = 0
    suspense_count: int = 0
    mapped_count: int = 0
    duplicate_count: int = 0
    reverse_entries_count: int = 0
    reverse_pairs_count: int = 0
    reverse_unmatched_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    ready_for_export: bool = True
    page_diagnostics: List[Any] = []
    bank_ledger_name: str = "Bank Account"
    cash_ledger_name: str = "Cash"
    status: str  # "COMPLETED" | "PARTIALLY_COMPLETED" | "NEEDS_REVIEW" | "AMBIGUOUS_BANK" | "QUOTA_EXHAUSTED"
    confidence_score: float
    confidence_tier: str = "HIGH"  # "HIGH" | "MEDIUM" | "LOW" | "AMBIGUOUS"
    is_ambiguous: bool = False
    parser_name: Optional[str] = None
    detected_ifsc: Optional[str] = None
    runner_up_bank: Optional[str] = None
    runner_up_confidence: Optional[float] = None
    detection_reasons: List[str] = []
    balance_status: str = "VALID"  # "VALID" | "MISMATCH" | "PENDING_SELECTION"
    statement_from: Optional[date] = None
    statement_to: Optional[date] = None
    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None
    total_debit: Decimal
    total_credit: Decimal
    created_at: datetime
    override_warning: Optional[str] = None
    candidates: List[Any] = []
    error_message: Optional[str] = None
    transactions: List[TransactionItem] = []

@router.options("/upload")
async def options_upload_statement():
    """Handle preflight OPTIONS request explicitly for browser CORS compliance."""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "https://kangrahubtallyxml.netlify.app",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
        }
    )

@router.post("/upload", response_model=ConversionJobSummary)
async def upload_statement(
    file: Optional[List[UploadFile]] = File(None),
    files: Optional[List[UploadFile]] = File(None),
    password: Optional[str] = Form(None),
    bank_override: Optional[str] = Form(None),
    bank_ledger_name: Optional[str] = Form(None),
    cash_ledger_name: Optional[str] = Form(None),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Step 1: Upload and parse bank statement (PDF, JPG, JPEG).
    Enforces batch upload limits:
    - Normal users: up to 10 JPG/JPEG images per batch.
    - Administrators: up to 50 JPG/JPEG images per batch.
    Enforces daily page quota check BEFORE processing begins.
    Extracts with Google Gemini AI (~99% accuracy) with seamless fallback to rule-based bank parsers.
    Preserves exact configured Bank Ledger and Cash Ledger names without normalization.
    """
    raw_files = files if (files and len(files) > 0) else (file or [])
    if not raw_files:
        raise HTTPException(status_code=400, detail="No files uploaded. Please select at least one statement file.")

    job_id = f"job-{uuid.uuid4().hex[:10]}"

    is_admin = bool(current_user.is_admin or (current_user.role in ("ADMIN", "SUPER_ADMIN")))
    max_jpg_limit = 50 if is_admin else 10

    pdf_files: List[UploadFile] = []
    image_files: List[UploadFile] = []
    invalid_files: List[str] = []

    for f in raw_files:
        fname = f.filename or "statement"
        ext = os.path.splitext(fname)[1].lower().lstrip(".")
        if ext == "pdf":
            pdf_files.append(f)
        elif ext in ("jpg", "jpeg"):
            image_files.append(f)
        else:
            invalid_files.append(fname)

    if invalid_files:
        raise InvalidPDFException(
            f"Unsupported file type ({', '.join(invalid_files)}). Please upload a PDF, JPG, or JPEG bank statement."
        )

    if pdf_files and image_files:
        raise InvalidPDFException(
            "Mixed file types are not supported. Please upload either a single PDF document or a batch of JPG/JPEG images."
        )

    if len(pdf_files) > 1:
        raise InvalidPDFException(
            f"Multiple PDF upload is not supported. Please upload one PDF bank statement at a time, or up to {max_jpg_limit} JPG/JPEG images in a batch."
        )

    if len(image_files) > max_jpg_limit:
        role_desc = "Administrators" if is_admin else "Normal users"
        raise HTTPException(
            status_code=400,
            detail=f"Upload limit exceeded: {role_desc} can upload up to {max_jpg_limit} JPG/JPEG images per batch. "
                   f"You selected {len(image_files)} images. Please reduce your selection to {max_jpg_limit} images or fewer."
        )

    is_image = len(image_files) > 0
    is_encrypted = False
    image_tuples: List[Tuple[str, bytes]] = []

    if is_image:
        file_ext = "jpg"
        page_count = len(image_files)
        saved_image_paths = []

        for idx, img_file in enumerate(image_files):
            saved_path = os.path.join(CONVERSION_STORAGE_DIR, f"{job_id}_page_{idx+1}.jpg")
            img_content = await img_file.read()
            with open(saved_path, "wb") as f_out:
                f_out.write(img_content)
            validate_image_file(saved_path)
            saved_image_paths.append(saved_path)
            image_tuples.append((img_file.filename or f"image_{idx+1}.jpg", img_content))

        saved_file_path = saved_image_paths[0]
        orig_filename = image_files[0].filename or "image.jpg"
        if len(image_files) > 1:
            orig_filename = f"{len(image_files)} images ({image_files[0].filename}, ...)"
        content = image_tuples[0][1]
    else:
        file_ext = "pdf"
        target_file = pdf_files[0]
        orig_filename = target_file.filename or "statement.pdf"
        saved_file_path = os.path.join(CONVERSION_STORAGE_DIR, f"{job_id}.pdf")
        content = await target_file.read()
        with open(saved_file_path, "wb") as f_out:
            f_out.write(content)
        page_count, is_encrypted = validate_pdf_file(saved_file_path, password=password)

    app_logger.info(f"Starting conversion job {job_id} ({file_ext.upper()}, {page_count} pages) for user {current_user.email}, file: {orig_filename}")

    # 2. Check available page limit (Free Daily Quota + Additional Purchased Balance)
    usage = get_user_usage_data(current_user)
    is_unlimited = usage.is_unlimited or current_user.has_quota_bypass or current_user.is_admin or current_user.role in ("ADMIN", "SUPER_ADMIN")

    # Enforce subscription monthly bill limits (PRD Section 2)
    sub_limit = usage.subscription_bill_limit
    if sub_limit is not None and not (current_user.is_admin or current_user.role in ("ADMIN", "SUPER_ADMIN")):
        if sub_limit == -1 or current_user.is_unlimited:
            # Premium Plan: genuine unlimited conversions without fixed cap
            is_unlimited = True
        else:
            # Basic (50 bills) & Standard (150 bills) plans: check converted bill count
            mem = db.get_active_staff_membership(current_user.id, current_user.email)
            since_time = mem.get("membership_started_at") if mem else None
            bills_used = db.get_user_bills_converted_since(current_user.id, since_time)
            if bills_used >= sub_limit:
                app_logger.warning(f"Subscription bill conversion limit reached for {current_user.email}: {bills_used}/{sub_limit} bills")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Your {usage.subscription_plan_name or 'subscription'} monthly bill conversion limit of {sub_limit} bills has been reached. Please upgrade to Standard or Premium for higher limits."
                )
            is_unlimited = True
    
    remaining_free = usage.pages_remaining_today if not is_unlimited else 999999
    additional_bal = get_user_additional_pages(current_user) if not is_unlimited else 0
    total_available = 999999 if is_unlimited else (remaining_free + additional_bal)
    
    pages_to_process = min(page_count, total_available)
    pages_skipped = max(0, page_count - pages_to_process)
    is_partial = (pages_skipped > 0)
    suggested_price = round(float(pages_skipped * getattr(settings, "page_price_inr", 2.0)), 2)

    page_statuses = {
        str(p): ("PROCESSED" if p <= pages_to_process else "PENDING")
        for p in range(1, page_count + 1)
    }

    configured_bank_ledger = bank_ledger_name if (bank_ledger_name and bank_ledger_name.strip()) else (
        USER_BANK_CONFIGS.get(current_user.id, {}).get("Bank Account") or "Bank Account"
    )
    configured_cash_ledger = cash_ledger_name if (cash_ledger_name and cash_ledger_name.strip()) else (
        USER_BANK_CONFIGS.get(current_user.id, {}).get("__cash__") or "Cash"
    )

    if pages_to_process == 0:
        # User has exhausted quota entirely
        job_record = {
            "id": job_id,
            "user_id": current_user.id,
            "file_name": orig_filename,
            "pdf_path": saved_file_path,
            "password": password,
            "bank_name": "Pending Quota",
            "statement_format": f"{file_ext.upper()} Statement",
            "page_count": page_count,
            "total_pdf_pages": page_count,
            "pages_processed": 0,
            "pages_skipped": page_count,
            "pages_pending": page_count,
            "page_statuses": page_statuses,
            "free_quota_used": 0,
            "additional_quota_used": 0,
            "is_partial_conversion": True,
            "remaining_pages": page_count,
            "suggested_additional_price": suggested_price,
            "transaction_count": 0,
            "rejected_transaction_count": 0,
            "raw_transaction_count": 0,
            "suspense_count": 0,
            "mapped_count": 0,
            "duplicate_count": 0,
            "warning_count": 0,
            "error_count": 0,
            "ready_for_export": False,
            "page_diagnostics": [],
            "status": "QUOTA_EXHAUSTED",
            "confidence_score": 0.0,
            "confidence_tier": "LOW",
            "is_ambiguous": False,
            "parser_name": None,
            "detected_ifsc": None,
            "runner_up_bank": None,
            "runner_up_confidence": None,
            "detection_reasons": ["Daily free quota and additional page balance are exhausted."],
            "balance_status": "PENDING_SELECTION",
            "statement_from": None,
            "statement_to": None,
            "opening_balance": None,
            "closing_balance": None,
            "total_debit": Decimal("0.00"),
            "total_credit": Decimal("0.00"),
            "created_at": datetime.now(),
            "statement": None,
            "xml_content": None,
            "xml_filename": None,
            "bank_ledger_name": configured_bank_ledger,
            "cash_ledger_name": configured_cash_ledger,
            "transactions": []
        }
        job_record["user_email"] = getattr(current_user, "email", "")
        IN_MEMORY_JOBS[job_id] = job_record
        try:
            db.save_conversion(job_record)
        except Exception as _e:
            app_logger.warning(f"Failed to persist conversion {job_id}: {_e}")
        return ConversionJobSummary(**job_record)

    # Deduct quota
    if is_unlimited:
        free_quota_used = 0
        additional_quota_used = 0
    else:
        free_quota_used = min(pages_to_process, remaining_free)
        remaining_to_deduct = pages_to_process - free_quota_used
        additional_quota_used = min(remaining_to_deduct, additional_bal)
        if free_quota_used > 0:
            record_user_page_usage(current_user, free_quota_used)
        if additional_quota_used > 0:
            deduct_user_additional_pages(current_user.id, additional_quota_used)

    # 3. Extraction via Google Gemini AI (~99% accuracy) or fallback parser
    statement: Optional[CanonicalStatement] = None
    extraction_engine = "parser"
    extracted_doc = None
    detected_bank_name = "Bank Account"
    detected_format = f"{file_ext.upper()} Statement"
    detection_confidence = 99.0
    confidence_tier = "HIGH"
    is_ambiguous = False
    account_num = None
    detected_ifsc = None
    runner_up_bank = None
    runner_up_conf = None
    parser_name = "Gemini AI Engine v2.0"
    detection_reasons = []

    if is_image:
        # JPG / JPEG Statements are parsed with Gemini Multimodal AI
        if GeminiExtractor.is_available():
            try:
                images_to_extract = image_tuples[:pages_to_process]
                if len(images_to_extract) == 1:
                    statement = GeminiExtractor.extract_from_image_bytes(images_to_extract[0][1], mime_type="image/jpeg")
                else:
                    statement = GeminiExtractor.extract_from_multiple_image_bytes(images_to_extract, mime_type="image/jpeg")

                if statement and len(statement.transactions) > 0:
                    extraction_engine = "gemini"
                    detected_bank_name = statement.bank or "Bank Account"
                    account_num = statement.account_number_masked
                    detection_reasons = [f"Extracted via Gemini Vision OCR ({len(images_to_extract)} images batch)"]
                    parser_name = f"Gemini Vision Engine ({len(images_to_extract)} images)"
            except Exception as _gem_err:
                app_logger.warning(f"Gemini image extraction error: {_gem_err}")

        if not statement or len(statement.transactions) == 0:
            raise InvalidPDFException(
                "Unable to extract readable transactions from the uploaded image(s). "
                "Please verify that the bank statement photo(s) are clear, focused, and not blurry."
            )
    else:
        # PDF Statements: Extract text & layout
        extracted_doc = extract_pdf_data(saved_file_path, password=password, max_pages=pages_to_process, start_page=1)

        # Attempt Gemini high-accuracy extraction first
        if GeminiExtractor.is_available() and getattr(settings, "gemini_enabled", True):
            try:
                page_texts = [p.text for p in extracted_doc.pages]
                statement = GeminiExtractor.extract_from_pdf_pages(page_texts, file_path=saved_file_path)
                if statement and len(statement.transactions) > 0:
                    extraction_engine = "gemini"
                    detected_bank_name = statement.bank or "Bank Account"
                    account_num = statement.account_number_masked
                    parser_name = "Gemini AI Vision & Math Engine v2.0"
                    detection_reasons = ["Extracted via Gemini Structured AI Engine"]
                    app_logger.info(f"Gemini extraction succeeded for job {job_id} ({len(statement.transactions)} txs).")
            except Exception as _gem_err:
                app_logger.warning(f"Gemini PDF extraction error: {_gem_err}. Falling back to standard parser.")

    # 4. Fallback to standard deterministic rule-based parser if Gemini did not produce a statement
    if not statement:
        if bank_override:
            parser = parser_registry.get_parser_for_bank(bank_override)
            if not parser:
                raise UnsupportedBankException(bank_override)
            detected_bank_name = bank_override
            detected_format = parser.format_name
            detection_confidence = 100.0
            confidence_tier = "HIGH"
            is_ambiguous = False
            account_num = None
            detected_ifsc = None
            runner_up_bank = None
            runner_up_conf = None
            parser_name = f"{parser.bank_name} ({parser.format_name}) v{parser.version}"
            detection_reasons = ["Bank selected manually by user"]
        else:
            detection_result = detect_bank_from_document(extracted_doc)
            detected_bank_name = detection_result.bank_name
            detected_format = detection_result.format_name
            detection_confidence = detection_result.confidence
            confidence_tier = detection_result.confidence_tier
            is_ambiguous = detection_result.is_ambiguous
            account_num = detection_result.account_number_masked
            detected_ifsc = detection_result.detected_ifsc
            runner_up_bank = detection_result.runner_up_bank
            runner_up_conf = detection_result.runner_up_confidence
            detection_reasons = detection_result.detection_reasons

            if is_ambiguous or confidence_tier in ("AMBIGUOUS", "LOW") or detection_confidence < 70.0:
                configured_bank_ledger = bank_ledger_name or USER_BANK_CONFIGS.get(current_user.id, {}).get(detected_bank_name) or f"{detected_bank_name} A/C"
                configured_cash_ledger = cash_ledger_name or USER_BANK_CONFIGS.get(current_user.id, {}).get("__cash__") or "Cash"
                job_record = {
                    "id": job_id,
                    "user_id": current_user.id,
                    "file_name": orig_filename,
                    "pdf_path": saved_file_path,
                    "password": password,
                    "bank_name": detected_bank_name,
                    "statement_format": detected_format,
                    "page_count": page_count,
                    "total_pdf_pages": page_count,
                    "pages_processed": pages_to_process,
                    "pages_skipped": pages_skipped,
                    "free_quota_used": free_quota_used,
                    "additional_quota_used": additional_quota_used,
                    "is_partial_conversion": is_partial,
                    "remaining_pages": pages_skipped,
                    "suggested_additional_price": suggested_price,
                    "transaction_count": 0,
                    "rejected_transaction_count": 0,
                    "raw_transaction_count": 0,
                    "suspense_count": 0,
                    "mapped_count": 0,
                    "status": "AMBIGUOUS_BANK",
                    "confidence_score": detection_confidence,
                    "confidence_tier": confidence_tier,
                    "is_ambiguous": True,
                    "parser_name": None,
                    "detected_ifsc": detected_ifsc,
                    "runner_up_bank": runner_up_bank,
                    "runner_up_confidence": runner_up_conf,
                    "detection_reasons": detection_reasons,
                    "balance_status": "PENDING_SELECTION",
                    "statement_from": None,
                    "statement_to": None,
                    "opening_balance": None,
                    "closing_balance": None,
                    "total_debit": Decimal("0.00"),
                    "total_credit": Decimal("0.00"),
                    "created_at": datetime.now(),
                    "statement": None,
                    "xml_content": None,
                    "xml_filename": None,
                    "bank_ledger_name": configured_bank_ledger,
                    "cash_ledger_name": configured_cash_ledger,
                    "transactions": []
                }
                job_record["user_email"] = getattr(current_user, "email", "")
                IN_MEMORY_JOBS[job_id] = job_record
                try:
                    db.save_conversion(job_record)
                except Exception as _e:
                    app_logger.warning(f"Failed to persist conversion {job_id}: {_e}")
                return ConversionJobSummary(**job_record)

            parser = parser_registry.get_parser(detection_result.parser_key) or parser_registry.get_parser_for_bank(detected_bank_name)
            if not parser:
                raise UnsupportedBankException(detected_bank_name)
            parser_name = f"{parser.bank_name} ({parser.format_name}) v{parser.version}"

        statement = parser.parse(extracted_doc)
        statement.account_number_masked = account_num

    # Filter transactions by authorized page range
    allowed_page_set = set(range(1, pages_to_process + 1))
    statement.transactions = [
        tx for tx in statement.transactions
        if getattr(tx, "source_page", None) is None or tx.source_page in allowed_page_set
    ]
    raw_count = len(statement.transactions)

    # 5. Apply intelligent ledger mapping and voucher classification
    # CRITICAL PRD REQUIREMENT: Narration matching must run on Gemini output verbatim
    configured_bank_ledger = bank_ledger_name if (bank_ledger_name and bank_ledger_name.strip()) else (
        USER_BANK_CONFIGS.get(current_user.id, {}).get(detected_bank_name) or f"{detected_bank_name} A/C"
    )
    configured_cash_ledger = cash_ledger_name if (cash_ledger_name and cash_ledger_name.strip()) else (
        USER_BANK_CONFIGS.get(current_user.id, {}).get("__cash__") or "Cash"
    )

    user_ledgers = global_ledger_store.get_user_ledgers(current_user.id)
    saved_rules = USER_SAVED_RULES.get(current_user.id, {})

    mapper = LedgerMapper(
        user_saved_mappings=saved_rules,
        imported_ledgers=user_ledgers,
        bank_ledger_name=configured_bank_ledger,
        cash_ledger_name=configured_cash_ledger,
        suspense_ledger_name="Suspense"
    )

    for idx, tx in enumerate(statement.transactions):
        tx.id = f"{job_id}-tx-{idx+1}"
        tx.row_index = idx + 1
        if not tx.ledger_name:
            tx.ledger_name = mapper.map_transaction_ledger(tx, configured_bank_ledger)
        tx.voucher_type = classify_voucher_type(tx)

    # PRD Section 11: Detect reversed and rejected entries (Reverse Entries ledger)
    rev_detector = ReversalDetector(
        reverse_ledger_name="Reverse Entries",
        bank_charges_ledger_name="Bank Charges"
    )
    rev_detector.process_statement(statement)

    suspense_count = sum(1 for t in statement.transactions if (t.ledger_name == "Suspense" or t.mapping_status == "Suspense"))
    mapped_count = raw_count - suspense_count

    statement.bank_ledger_name = configured_bank_ledger
    statement.cash_ledger_name = configured_cash_ledger
    statement.suspense_count = suspense_count
    statement.mapped_count = mapped_count

    # 6. Accounting Diagnostics & Duplicate Candidate Detection
    detect_duplicate_candidates(statement)
    if extracted_doc:
        compile_page_diagnostics(statement, extracted_doc)

    # Balance validation audit check
    if is_partial and statement.transactions:
        last_tx_balance = statement.transactions[-1].balance
        if last_tx_balance is not None:
            statement.closing_balance = last_tx_balance
        elif statement.opening_balance is not None:
            statement.closing_balance = statement.opening_balance + statement.total_credit - statement.total_debit

    has_mismatch = any(t.validation_status == "ERROR" for t in statement.transactions)
    if not is_partial and statement.opening_balance is not None and statement.closing_balance is not None:
        expected_closing = (statement.opening_balance + statement.total_credit - statement.total_debit).quantize(Decimal("0.01"))
        actual_closing = statement.closing_balance.quantize(Decimal("0.01"))
        if abs(expected_closing - actual_closing) > Decimal("0.05"):
            has_mismatch = True

    balance_status = "VALID" if not has_mismatch else "MISMATCH"
    if is_partial:
        job_status = "PARTIALLY_COMPLETED"
    elif has_mismatch:
        job_status = "NEEDS_REVIEW"
    else:
        job_status = "COMPLETED"

    warning_count = sum(1 for t in statement.transactions if t.validation_status == "WARNING")
    error_count = sum(1 for t in statement.transactions if t.validation_status == "ERROR")
    ready_for_export = (error_count == 0)

    # 7. Store job in memory & database
    job_record = {
        "id": job_id,
        "user_id": current_user.id,
        "file_name": orig_filename,
        "pdf_path": saved_file_path,
        "password": password,
        "bank_name": detected_bank_name,
        "statement_format": detected_format,
        "page_count": page_count,
        "total_pdf_pages": page_count,
        "pages_processed": pages_to_process,
        "pages_skipped": pages_skipped,
        "pages_pending": pages_skipped,
        "page_statuses": page_statuses,
        "free_quota_used": free_quota_used,
        "additional_quota_used": additional_quota_used,
        "is_partial_conversion": is_partial,
        "remaining_pages": pages_skipped,
        "suggested_additional_price": suggested_price,
        "transaction_count": len(statement.transactions),
        "rejected_transaction_count": 0,
        "raw_transaction_count": raw_count,
        "suspense_count": suspense_count,
        "mapped_count": mapped_count,
        "duplicate_count": getattr(statement, "duplicate_count", 0),
        "reverse_entries_count": getattr(statement, "reverse_entries_count", 0),
        "reverse_pairs_count": getattr(statement, "reverse_pairs_count", 0),
        "reverse_unmatched_count": getattr(statement, "reverse_unmatched_count", 0),
        "warning_count": warning_count,
        "error_count": error_count,
        "ready_for_export": ready_for_export,
        "page_diagnostics": getattr(statement, "page_diagnostics", []),
        "status": job_status,
        "confidence_score": detection_confidence,
        "confidence_tier": confidence_tier,
        "is_ambiguous": is_ambiguous,
        "parser_name": parser_name,
        "detected_ifsc": detected_ifsc,
        "runner_up_bank": runner_up_bank,
        "runner_up_confidence": runner_up_conf,
        "detection_reasons": detection_reasons,
        "balance_status": balance_status,
        "statement_from": statement.statement_from,
        "statement_to": statement.statement_to,
        "opening_balance": statement.opening_balance,
        "closing_balance": statement.closing_balance,
        "total_debit": statement.total_debit,
        "total_credit": statement.total_credit,
        "created_at": datetime.now(),
        "statement": statement,
        "xml_content": None,
        "xml_filename": None,
        "bank_ledger_name": configured_bank_ledger,
        "cash_ledger_name": configured_cash_ledger,
        "transactions": statement.transactions
    }
    job_record["user_email"] = getattr(current_user, "email", "")
    IN_MEMORY_JOBS[job_id] = job_record
    try:
        db.save_conversion(job_record)
    except Exception as _e:
        app_logger.warning(f"Failed to persist conversion {job_id}: {_e}")

    # Synchronize to Supabase bs_conversions (PRD Section 6)
    from app.core.supabase_service import SupabaseService
    if SupabaseService.is_configured():
        try:
            SupabaseService.insert_bs_conversion({
                "id": str(uuid.uuid4()),
                "user_id": current_user.id if (current_user and len(str(current_user.id)) > 30 and "-" in str(current_user.id)) else None,
                "file_name": orig_filename,
                "file_type": file_ext,
                "pages": page_count,
                "rows_extracted": len(statement.transactions),
                "engine": extraction_engine,
                "status": "success" if ready_for_export else "failed",
                "error_message": None if ready_for_export else "Audit warnings on statement",
                "tokens_used": len(statement.transactions) * 15 if extraction_engine == "gemini" else 0
            })
        except Exception as _sb_err:
            app_logger.debug(f"Supabase bs_conversion logging notice: {_sb_err}")

    app_logger.info(
        f"Job {job_id} extracted {len(statement.transactions)} txs for {detected_bank_name}. Mapped: {mapped_count}, Suspense: {suspense_count}, Warnings: {warning_count}, Errors: {error_count}"
    )

    return ConversionJobSummary(**job_record)

@router.post("/{job_id}/select-bank", response_model=ConversionJobSummary)
async def select_bank_manually(
    job_id: str,
    req: SelectBankRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """User manually selects bank after ambiguous detection."""
    job = IN_MEMORY_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Conversion job not found.")
    if job["user_id"] != current_user.id and current_user.role not in ("ADMIN", "SUPER_ADMIN"):
        raise HTTPException(status_code=403, detail="Access denied.")

    pdf_path = job.get("pdf_path")
    password = job.get("password")
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=400, detail="Original PDF file is no longer available. Please upload again.")

    parser = parser_registry.get_parser_for_bank(req.bank_name)
    if not parser:
        raise UnsupportedBankException(req.bank_name)

    pages_to_process = job.get("pages_processed") or 0
    extracted_doc = extract_pdf_data(pdf_path, password=password, max_pages=pages_to_process, start_page=1)
    statement: CanonicalStatement = parser.parse(extracted_doc)

    # STRICT POST-PARSER GATE: Never allow transactions outside authorized page slice
    allowed_page_set = set(range(1, pages_to_process + 1))
    statement.transactions = [
        tx for tx in statement.transactions
        if getattr(tx, "source_page", None) is None or tx.source_page in allowed_page_set
    ]
    raw_count = len(statement.transactions)

    configured_bank_ledger = USER_BANK_CONFIGS.get(current_user.id, {}).get(req.bank_name) or f"{req.bank_name} A/C"
    configured_cash_ledger = USER_BANK_CONFIGS.get(current_user.id, {}).get("__cash__") or "Cash"

    user_ledgers = global_ledger_store.get_user_ledgers(current_user.id)
    saved_rules = USER_SAVED_RULES.get(current_user.id, {})

    mapper = LedgerMapper(
        user_saved_mappings=saved_rules,
        imported_ledgers=user_ledgers,
        bank_ledger_name=configured_bank_ledger,
        cash_ledger_name=configured_cash_ledger,
        suspense_ledger_name="Suspense"
    )

    for idx, tx in enumerate(statement.transactions):
        tx.id = f"{job_id}-tx-{idx+1}"
        tx.row_index = idx + 1
        if not tx.ledger_name:
            tx.ledger_name = mapper.map_transaction_ledger(tx, configured_bank_ledger)
        tx.voucher_type = classify_voucher_type(tx)

    # PRD Section 11: Detect reversed and rejected entries
    rev_detector = ReversalDetector(
        reverse_ledger_name="Reverse Entries",
        bank_charges_ledger_name="Bank Charges"
    )
    rev_detector.process_statement(statement)

    suspense_count = sum(1 for t in statement.transactions if (t.ledger_name == "Suspense" or t.mapping_status == "Suspense"))
    mapped_count = raw_count - suspense_count

    is_partial = job.get("is_partial_conversion", False)
    if is_partial and statement.transactions:
        last_tx_balance = statement.transactions[-1].balance
        if last_tx_balance is not None:
            statement.closing_balance = last_tx_balance
        elif statement.opening_balance is not None:
            statement.closing_balance = statement.opening_balance + statement.total_credit - statement.total_debit

    has_mismatch = any(t.validation_status == "ERROR" for t in statement.transactions)
    balance_status = "VALID" if (is_partial or not has_mismatch) else "MISMATCH"
    job_status = "PARTIALLY_COMPLETED" if is_partial else ("NEEDS_REVIEW" if has_mismatch else "COMPLETED")

    detect_duplicate_candidates(statement)
    compile_page_diagnostics(statement, extracted_doc)

    job["bank_name"] = req.bank_name
    job["statement_format"] = parser.format_name
    job["parser_name"] = f"{parser.bank_name} ({parser.format_name}) v{parser.version}"
    job["status"] = job_status
    job["confidence_score"] = 100.0
    job["confidence_tier"] = "HIGH"
    job["is_ambiguous"] = False
    job["balance_status"] = balance_status
    job["statement"] = statement
    job["statement_from"] = statement.statement_from
    job["statement_to"] = statement.statement_to
    job["opening_balance"] = statement.opening_balance
    job["closing_balance"] = statement.closing_balance
    job["total_debit"] = statement.total_debit
    job["total_credit"] = statement.total_credit
    job["transaction_count"] = len(statement.transactions)
    job["raw_transaction_count"] = raw_count
    job["suspense_count"] = suspense_count
    job["mapped_count"] = mapped_count
    job["duplicate_count"] = getattr(statement, "duplicate_count", 0)
    job["page_diagnostics"] = getattr(statement, "page_diagnostics", [])
    job["bank_ledger_name"] = configured_bank_ledger
    job["cash_ledger_name"] = configured_cash_ledger
    job["transactions"] = statement.transactions
    job.pop("snapshot", None)
    job.pop("excel_path", None)
    job.pop("xml_path", None)

    return ConversionJobSummary(**job)

@router.post("/{job_id}/review", response_model=ConversionJobSummary)
async def review_transactions(
    job_id: str,
    req: ReviewTransactionRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Allows user to edit dates, narrations, amounts, ledger names, and voucher types before XML generation."""
    job = IN_MEMORY_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Conversion job not found.")
    if job["user_id"] != current_user.id and current_user.role not in ("ADMIN", "SUPER_ADMIN"):
        raise HTTPException(status_code=403, detail="Access denied.")

    statement: CanonicalStatement = job["statement"]
    statement.transactions = req.transactions

    if req.bank_ledger_name and req.bank_ledger_name.strip():
        job["bank_ledger_name"] = req.bank_ledger_name.strip()
        statement.bank_ledger_name = req.bank_ledger_name.strip()
    if req.cash_ledger_name and req.cash_ledger_name.strip():
        job["cash_ledger_name"] = req.cash_ledger_name.strip()
        statement.cash_ledger_name = req.cash_ledger_name.strip()

    # Recalculate totals
    total_debit = sum(t.debit for t in req.transactions)
    total_credit = sum(t.credit for t in req.transactions)
    statement.total_debit = total_debit
    statement.total_credit = total_credit

    # Re-validate running balances
    curr_bal = statement.opening_balance
    has_mismatch = False
    for idx, tx in enumerate(req.transactions):
        tx.row_index = idx + 1
        if tx.validation_status == "ERROR":
            has_mismatch = True
            if tx.balance is not None:
                curr_bal = tx.balance
        elif curr_bal is not None and tx.balance is not None:
            expected = (curr_bal + tx.credit - tx.debit).quantize(Decimal("0.01"))
            actual = tx.balance.quantize(Decimal("0.01"))
            diff = abs(expected - actual)
            if diff <= Decimal("0.01"):
                tx.validation_status = "VALID"
                tx.validation_notes = None
            elif diff <= Decimal("1.00"):
                tx.validation_status = "WARNING"
                tx.validation_notes = f"Minor balance discrepancy at row {idx+1}: Expected {expected}, reported {actual}"
                has_mismatch = True
            else:
                tx.validation_status = "ERROR"
                tx.validation_notes = f"Balance mismatch at row {idx+1}: Expected {expected}, reported {actual}"
                has_mismatch = True
            curr_bal = actual
        elif curr_bal is not None:
            curr_bal = (curr_bal + tx.credit - tx.debit).quantize(Decimal("0.01"))
            tx.balance = curr_bal
            tx.validation_status = "VALID"

    suspense_count = sum(1 for t in req.transactions if (t.ledger_name == "Suspense" or t.mapping_status == "Suspense" or not t.ledger_name))
    mapped_count = len(req.transactions) - suspense_count
    warning_count = sum(1 for t in req.transactions if t.validation_status == "WARNING")
    error_count = sum(1 for t in req.transactions if t.validation_status == "ERROR")

    job["total_debit"] = total_debit
    job["total_credit"] = total_credit
    job["transaction_count"] = len(req.transactions)
    job["suspense_count"] = suspense_count
    job["mapped_count"] = mapped_count
    job["warning_count"] = warning_count
    job["error_count"] = error_count
    job["ready_for_export"] = (error_count == 0)
    job["status"] = "NEEDS_REVIEW" if has_mismatch else "COMPLETED"
    job["balance_status"] = "MISMATCH" if has_mismatch else "VALID"
    job["transactions"] = statement.transactions
    job.pop("snapshot", None)
    job.pop("excel_path", None)
    job.pop("xml_path", None)

    try:
        db.save_conversion(job)
    except Exception as _e:
        app_logger.warning(f"Failed to persist reviewed conversion {job.get('id')}: {_e}")

    return ConversionJobSummary(**job)

@router.post("/{job_id}/update-row", response_model=ConversionJobSummary)
async def update_single_row(
    job_id: str,
    req: UpdateRowRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Updates a single transaction row's ledger, voucher type, or instrument number."""
    job = IN_MEMORY_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Conversion job not found.")
    if job["user_id"] != current_user.id and current_user.role not in ("ADMIN", "SUPER_ADMIN"):
        raise HTTPException(status_code=403, detail="Access denied.")

    statement: CanonicalStatement = _ensure_job_statement(job)
    target_tx = None
    for tx in statement.transactions:
        if tx.row_index == req.row_index:
            target_tx = tx
            break

    if not target_tx and 0 <= req.row_index < len(statement.transactions):
        target_tx = statement.transactions[req.row_index]

    if not target_tx:
        raise HTTPException(status_code=404, detail=f"Transaction row {req.row_index} not found.")

    if req.ledger_name is not None:
        clean_ledger = req.ledger_name.strip()
        target_tx.ledger_name = clean_ledger
        target_tx.mapping_status = "User Confirmed"
        target_tx.mapping_confidence = 100.0
        target_tx.validation_status = "VALID"
        target_tx.validation_notes = None

        if req.save_as_rule:
            if current_user.id not in USER_SAVED_RULES:
                USER_SAVED_RULES[current_user.id] = {}
            party = target_tx.party_name or target_tx.narration
            USER_SAVED_RULES[current_user.id][party.upper()] = clean_ledger

    if req.voucher_type is not None:
        target_tx.voucher_type = req.voucher_type
        target_tx.original_voucher_type = req.voucher_type

    if req.instrument_number is not None:
        target_tx.instrument_number = req.instrument_number
        target_tx.cheque_number = req.instrument_number

    if req.narration is not None:
        target_tx.narration = req.narration

    suspense_count = sum(1 for t in statement.transactions if (t.ledger_name == "Suspense" or t.mapping_status == "Suspense"))
    mapped_count = len(statement.transactions) - suspense_count
    job["suspense_count"] = suspense_count
    job["mapped_count"] = mapped_count
    job["transactions"] = statement.transactions
    job.pop("snapshot", None)
    job.pop("excel_path", None)
    job.pop("xml_path", None)

    try:
        db.save_conversion(job)
    except Exception:
        pass

    return ConversionJobSummary(**job)

@router.post("/{job_id}/bulk-assign-ledger", response_model=ConversionJobSummary)
async def bulk_assign_ledger(
    job_id: str,
    req: BulkAssignLedgerRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Assigns a ledger to multiple selected transactions.
    If apply_to_similar is True, propagates to all transactions with similar narrations/parties.
    """
    job = IN_MEMORY_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Conversion job not found.")
    if job["user_id"] != current_user.id and current_user.role not in ("ADMIN", "SUPER_ADMIN"):
        raise HTTPException(status_code=403, detail="Access denied.")

    statement: CanonicalStatement = _ensure_job_statement(job)
    target_indices = set()

    # 1. By explicit unique transaction IDs if supplied
    if req.tx_ids:
        tx_id_set = set(req.tx_ids)
        for i, tx in enumerate(statement.transactions):
            if tx.id in tx_id_set:
                target_indices.add(i)

    # 2. If target_indices still empty or tx_ids not provided, resolve by row_indices:
    if not target_indices and req.row_indices:
        is_zero_based = (0 in req.row_indices) or (
            all(0 <= idx < len(statement.transactions) for idx in req.row_indices)
            and not any(idx == len(statement.transactions) for idx in req.row_indices)
        )
        for idx in req.row_indices:
            if is_zero_based:
                if 0 <= idx < len(statement.transactions):
                    target_indices.add(idx)
            else:
                for i, tx in enumerate(statement.transactions):
                    if tx.row_index == idx:
                        target_indices.add(i)

    action = (req.action or "ASSIGN").upper()
    if req.ledger_name == "__AUTO_RESOLVE__":
        action = "AUTO_RESOLVE"
    elif req.ledger_name == "__IGNORE_WARNINGS__":
        action = "IGNORE_WARNINGS"

    if not target_indices and action in ("AUTO_RESOLVE", "IGNORE_WARNINGS"):
        target_indices = set(range(len(statement.transactions)))

    if action == "AUTO_RESOLVE":
        cash_ledger = job.get("cash_ledger_name") or "Cash"
        for i in target_indices:
            tx = statement.transactions[i]
            # Level 6 Directional Fallback: Debit -> Payment, Credit -> Receipt
            if tx.debit > Decimal("0.00") and tx.credit == Decimal("0.00"):
                tx.voucher_type = "Payment"
            elif tx.credit > Decimal("0.00") and tx.debit == Decimal("0.00"):
                tx.voucher_type = "Receipt"
            elif tx.is_cash_transaction:
                tx.voucher_type = "Contra"
                tx.ledger_name = cash_ledger
            elif tx.debit > tx.credit:
                tx.voucher_type = "Payment"
            else:
                tx.voucher_type = "Receipt"

            if not tx.ledger_name:
                tx.ledger_name = "Suspense"
            # Clear non-critical warnings
            if tx.validation_status == "WARNING" and "zero" not in (tx.validation_notes or "").lower():
                tx.validation_status = "VALID"
                tx.validation_notes = None

    elif action == "IGNORE_WARNINGS":
        for i in target_indices:
            tx = statement.transactions[i]
            tx.validation_status = "VALID"
            tx.validation_notes = None

    else:
        # Standard ASSIGN
        target_parties = set()
        for i in target_indices:
            tx = statement.transactions[i]
            if req.ledger_name:
                tx.ledger_name = req.ledger_name
                tx.mapping_status = "User Confirmed"
                tx.mapping_confidence = 100.0
            if req.voucher_type:
                tx.voucher_type = req.voucher_type
            tx.validation_status = "VALID"
            tx.validation_notes = None
            if tx.party_name:
                target_parties.add(tx.party_name.upper())

        if req.apply_to_similar and target_parties and req.ledger_name:
            if current_user.id not in USER_SAVED_RULES:
                USER_SAVED_RULES[current_user.id] = {}
            for p in target_parties:
                USER_SAVED_RULES[current_user.id][p] = req.ledger_name
                # Propagate to other transactions
                for tx in statement.transactions:
                    if (tx.party_name and tx.party_name.upper() == p) or (p in tx.narration.upper()):
                        tx.ledger_name = req.ledger_name
                        if req.voucher_type:
                            tx.voucher_type = req.voucher_type
                        tx.mapping_status = "User Confirmed"
                        tx.mapping_confidence = 100.0
                        tx.validation_status = "VALID"
                        tx.validation_notes = None

    suspense_count = sum(1 for t in statement.transactions if (t.ledger_name == "Suspense" or t.mapping_status == "Suspense" or not t.ledger_name))
    mapped_count = len(statement.transactions) - suspense_count
    warning_count = sum(1 for t in statement.transactions if t.validation_status == "WARNING")
    error_count = sum(1 for t in statement.transactions if t.validation_status == "ERROR")

    job["suspense_count"] = suspense_count
    job["mapped_count"] = mapped_count
    job["warning_count"] = warning_count
    job["error_count"] = error_count
    job["ready_for_export"] = (error_count == 0)
    job["transactions"] = statement.transactions
    job.pop("snapshot", None)
    job.pop("excel_path", None)
    job.pop("xml_path", None)

    try:
        db.save_conversion(job)
    except Exception:
        pass

    return ConversionJobSummary(**job)

def _get_or_create_final_snapshot(
    job: Dict[str, Any],
    bank_ledger: Optional[str] = None,
    cash_ledger: Optional[str] = None
) -> FinalConversionSnapshot:
    """
    Builds/retrieves the single source of truth FinalConversionSnapshot.
    Enforces sequential voucher numbers 1..N and party ledger resolution.
    """
    statement: CanonicalStatement = _ensure_job_statement(job)
    pages_processed = job.get("pages_processed") or job.get("page_count", 0)

    # EXPORT SECURITY GATE: Ensure only transactions from authorized/processed pages are exported
    authorized_txs = [
        tx for tx in statement.transactions
        if getattr(tx, "source_page", None) is None or tx.source_page <= pages_processed
    ]

    b_ledger = (bank_ledger if (bank_ledger and bank_ledger.strip()) else None) or job.get("bank_ledger_name") or f"{job['bank_name']} A/C"
    c_ledger = (cash_ledger if (cash_ledger and cash_ledger.strip()) else None) or job.get("cash_ledger_name") or "Cash"

    authorized_statement = CanonicalStatement(
        bank=statement.bank,
        statement_format=statement.statement_format,
        account_number_masked=statement.account_number_masked,
        opening_balance=statement.opening_balance,
        closing_balance=statement.closing_balance,
        total_debit=sum(t.debit for t in authorized_txs),
        total_credit=sum(t.credit for t in authorized_txs),
        statement_from=statement.statement_from,
        statement_to=statement.statement_to,
        transactions=authorized_txs,
        suspense_count=sum(1 for t in authorized_txs if (t.ledger_name == "Suspense" or not t.ledger_name)),
        mapped_count=len(authorized_txs) - sum(1 for t in authorized_txs if (t.ledger_name == "Suspense" or not t.ledger_name)),
        bank_ledger_name=b_ledger,
        cash_ledger_name=c_ledger
    )

    snapshot = FinalConversionSnapshot.create_from_statement(
        statement=authorized_statement,
        bank_ledger_name=b_ledger,
        cash_ledger_name=c_ledger,
        job_id=job["id"]
    )
    job["snapshot"] = snapshot
    job["bank_ledger_name"] = snapshot.bank_ledger_name
    job["cash_ledger_name"] = snapshot.cash_ledger_name
    return snapshot

class ManualPairRequest(BaseModel):
    row_index_1: int
    row_index_2: int
    reason: Optional[str] = "Manual pairing"

class UnpairRequest(BaseModel):
    row_index: int

@router.get("/{job_id}/reversals")
async def get_conversion_reversals(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    PRD Section 11.5: Returns Reverse Entries report and detailed paired/unpaired rows.
    """
    job = IN_MEMORY_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Conversion job not found.")
    statement = _ensure_job_statement(job)
    
    pairs_map: Dict[str, Dict[str, Any]] = {}
    unmatched: List[Dict[str, Any]] = []
    linked_charges: List[Dict[str, Any]] = []

    for tx in statement.transactions:
        if getattr(tx, "linked_reversal_ref", None):
            linked_charges.append({
                "row_index": tx.row_index,
                "date": tx.date.isoformat() if tx.date else None,
                "narration": tx.narration,
                "debit": float(tx.debit),
                "credit": float(tx.credit),
                "ledger_name": tx.ledger_name,
                "linked_ref": tx.linked_reversal_ref,
                "notes": tx.validation_notes
            })
        if not getattr(tx, "is_reverse_entry", False):
            continue
        
        pair_id = getattr(tx, "reversal_pair_id", None)
        if pair_id:
            if pair_id not in pairs_map:
                pairs_map[pair_id] = {
                    "pair_id": pair_id,
                    "reason": getattr(tx, "reversal_reason", "Reversal"),
                    "amount": float(tx.debit if tx.debit > Decimal("0.00") else tx.credit),
                    "debit_row": None,
                    "credit_row": None,
                    "net": 0.0
                }
            row_dict = {
                "row_index": tx.row_index,
                "date": tx.date.isoformat() if tx.date else None,
                "narration": tx.narration,
                "debit": float(tx.debit),
                "credit": float(tx.credit),
                "reversal_leg": getattr(tx, "reversal_leg", None),
                "reference": tx.reference or tx.instrument_number or tx.cheque_number,
                "status": tx.mapping_status
            }
            if tx.debit > Decimal("0.00"):
                pairs_map[pair_id]["debit_row"] = row_dict
            else:
                pairs_map[pair_id]["credit_row"] = row_dict
        else:
            unmatched.append({
                "row_index": tx.row_index,
                "date": tx.date.isoformat() if tx.date else None,
                "narration": tx.narration,
                "debit": float(tx.debit),
                "credit": float(tx.credit),
                "reason": getattr(tx, "reversal_reason", "Reversal"),
                "status": tx.mapping_status,
                "notes": tx.validation_notes or "original entry not in this statement"
            })

    pairs_list = list(pairs_map.values())
    for p in pairs_list:
        d_amt = p["debit_row"]["debit"] if p.get("debit_row") else 0.0
        c_amt = p["credit_row"]["credit"] if p.get("credit_row") else 0.0
        p["net"] = round(d_amt - c_amt, 2)

    net_total = sum(p["net"] for p in pairs_list)

    return {
        "job_id": job_id,
        "ledger_name": "Reverse Entries",
        "parent_group": "Suspense A/c",
        "will_auto_create_ledger": True,
        "pairs_count": len(pairs_list),
        "unmatched_count": len(unmatched),
        "total_reverse_rows": (len(pairs_list) * 2) + len(unmatched),
        "net_total": net_total,
        "pairs": pairs_list,
        "unmatched": unmatched,
        "linked_charges": linked_charges
    }

@router.post("/{job_id}/reversals/pair", response_model=ConversionJobSummary)
async def pair_reversal_rows(
    job_id: str,
    req: ManualPairRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Manually pair two rows as reverse entries."""
    job = IN_MEMORY_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Conversion job not found.")
    statement = _ensure_job_statement(job)

    r1 = next((t for t in statement.transactions if t.row_index == req.row_index_1), None)
    r2 = next((t for t in statement.transactions if t.row_index == req.row_index_2), None)
    if not r1 or not r2:
        raise HTTPException(status_code=400, detail="One or both row indices not found.")

    pair_id = f"rev-pair-manual-{uuid.uuid4().hex[:6]}"
    r1.is_reverse_entry = True
    r1.reversal_pair_id = pair_id
    r1.paired_row_index = r2.row_index
    r1.ledger_name = "Reverse Entries"
    r1.suggested_ledger = "Reverse Entries"
    r1.reversal_reason = req.reason or "Manual pairing"
    r1.mapping_status = "Mapped"

    r2.is_reverse_entry = True
    r2.reversal_pair_id = pair_id
    r2.paired_row_index = r1.row_index
    r2.ledger_name = "Reverse Entries"
    r2.suggested_ledger = "Reverse Entries"
    r2.reversal_reason = req.reason or "Manual pairing"
    r2.mapping_status = "Mapped"

    return await get_conversion_job(job_id=job_id, current_user=current_user)

@router.post("/{job_id}/reversals/unpair", response_model=ConversionJobSummary)
async def unpair_reversal_row(
    job_id: str,
    req: UnpairRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Unpairs a reverse entry row."""
    job = IN_MEMORY_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Conversion job not found.")
    statement = _ensure_job_statement(job)

    target_tx = next((t for t in statement.transactions if t.row_index == req.row_index), None)
    if not target_tx:
        raise HTTPException(status_code=400, detail="Row index not found.")

    old_pair_id = target_tx.reversal_pair_id
    for tx in statement.transactions:
        if tx.row_index == req.row_index or (old_pair_id and tx.reversal_pair_id == old_pair_id):
            tx.is_reverse_entry = False
            tx.reversal_pair_id = None
            tx.paired_row_index = None
            tx.reversal_reason = None
            tx.reversal_leg = None
            tx.ledger_name = "Suspense"
            tx.mapping_status = "Suspense"

    return await get_conversion_job(job_id=job_id, current_user=current_user)

@router.post("/{job_id}/generate")
async def generate_tally_xml_endpoint(
    job_id: str,
    req: Optional[GenerateTallyXMLRequest] = None,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Generates and validates final Tally XML directly from FinalConversionSnapshot.
    Verifies transaction count reconciliation, balance integrity, and double-entry balancing.
    Consumes the exact same FinalConversionSnapshot as Excel.
    """
    job = IN_MEMORY_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Conversion job not found.")
    if job["user_id"] != current_user.id and current_user.role not in ("ADMIN", "SUPER_ADMIN"):
        raise HTTPException(status_code=403, detail="Access denied.")

    statement: CanonicalStatement = _ensure_job_statement(job)
    if not statement or not statement.transactions:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "ERR_NO_TRANSACTIONS",
                "message": "Cannot generate XML: No valid transactions found in statement."
            }
        )

    # 1. Transaction Count Reconciliation
    raw_count = job.get("raw_transaction_count", len(statement.transactions))
    if len(statement.transactions) != raw_count:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "ERR_TRANSACTION_COUNT_MISMATCH",
                "message": f"Reconciliation failed: Detected {raw_count} transactions from PDF, but {len(statement.transactions)} included in final conversion."
            }
        )

    # 2. Build and validate FinalConversionSnapshot
    snapshot = _get_or_create_final_snapshot(
        job,
        bank_ledger=req.bank_ledger_name if req else None,
        cash_ledger=req.cash_ledger_name if req else None
    )
    is_valid, validation_errors = validate_conversion_snapshot(snapshot)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "ERR_MATH_VALIDATION_FAILED",
                "message": "Snapshot validation failed: " + "; ".join(validation_errors[:5])
            }
        )

    # 3. Generate XML directly from snapshot
    generator = TallyXMLGenerator(
        default_bank_ledger=snapshot.bank_ledger_name,
        default_cash_ledger=snapshot.cash_ledger_name
    )
    xml_content = generator.generate_xml(
        snapshot,
        bank_ledger_name=snapshot.bank_ledger_name,
        cash_ledger_name=snapshot.cash_ledger_name
    )

    # 4. Structural XML validation
    is_struct_valid, errors = validate_tally_xml(xml_content)
    if not is_struct_valid:
        app_logger.error(f"XML validation failed for job {job_id}: {errors}")
        raise XMLGenerationException("; ".join(errors))

    clean_bank = re.sub(r'[^A-Za-z0-9_]', '', job["bank_name"].split()[0])
    from_str = snapshot.statement_from.strftime("%Y-%m-%d") if snapshot.statement_from else "Statement"
    to_str = snapshot.statement_to.strftime("%Y-%m-%d") if snapshot.statement_to else "Export"
    xml_filename = f"{clean_bank}_Statement_{from_str}_to_{to_str}.xml"

    xml_path = os.path.join(TEMP_PROCESSING_DIR, f"{job_id}.xml")
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml_content)

    job["xml_content"] = xml_content
    job["xml_filename"] = xml_filename
    job["xml_path"] = xml_path
    job["status"] = "COMPLETED"

    return {
        "success": True,
        "job_id": job_id,
        "filename": xml_filename,
        "status": "COMPLETED",
        "download_url": f"/api/conversions/{job_id}/download"
    }

@router.post("/{job_id}/generate-excel")
async def generate_excel_endpoint(
    job_id: str,
    req: Optional[GenerateExcelRequest] = None,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Generates Excel (.xlsx) file directly from the FinalConversionSnapshot.
    ARCHITECTURAL CORRECTIONS APPLIED:
    - Does NOT require or depend on Tally XML generation.
    - Consumes the single source of truth: FinalConversionSnapshot.
    - 11 columns in exact required order.
    - Strict mathematical balance validation.
    - Read-only export: NEVER consumes daily page quota.
    """
    job = IN_MEMORY_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Conversion job not found.")
    if job["user_id"] != current_user.id and current_user.role not in ("ADMIN", "SUPER_ADMIN"):
        raise HTTPException(status_code=403, detail="Access denied.")

    statement: CanonicalStatement = _ensure_job_statement(job)
    if not statement or not statement.transactions:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "ERR_NO_TRANSACTIONS",
                "message": "Cannot generate Excel: No valid transactions found in statement."
            }
        )

    # 1. Transaction Count Reconciliation
    raw_count = job.get("raw_transaction_count", len(statement.transactions))
    if len(statement.transactions) != raw_count:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "ERR_TRANSACTION_COUNT_MISMATCH",
                "message": f"Reconciliation failed: Detected {raw_count} transactions from PDF, but {len(statement.transactions)} included in final conversion."
            }
        )

    # 2. Build and validate FinalConversionSnapshot directly
    snapshot = _get_or_create_final_snapshot(
        job,
        bank_ledger=req.bank_ledger_name if req else None,
        cash_ledger=req.cash_ledger_name if req else None
    )
    is_valid, validation_errors = validate_conversion_snapshot(snapshot)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "ERR_MATH_VALIDATION_FAILED",
                "message": "Snapshot validation failed: " + "; ".join(validation_errors[:5])
            }
        )

    # 3. Generate Excel workbook directly from snapshot (zero XML dependency)
    excel_generator = TallyExcelGenerator(
        default_bank_ledger=snapshot.bank_ledger_name,
        default_cash_ledger=snapshot.cash_ledger_name
    )
    excel_bytes = excel_generator.generate_excel_bytes(snapshot)
    excel_filename = excel_generator.generate_filename(snapshot, bank_name=job.get("bank_name"))

    excel_path = os.path.join(TEMP_PROCESSING_DIR, f"{job_id}.xlsx")
    with open(excel_path, "wb") as f:
        f.write(excel_bytes)

    job["excel_path"] = excel_path
    job["excel_filename"] = excel_filename

    return {
        "success": True,
        "job_id": job_id,
        "filename": excel_filename,
        "status": "COMPLETED",
        "download_url": f"/api/conversions/{job_id}/download-excel"
    }

@router.get("/{job_id}/download-excel")
async def download_excel_endpoint(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Downloads the verified conversion Excel (.xlsx) file."""
    job = IN_MEMORY_JOBS.get(job_id)
    if not job or not job.get("excel_path") or not os.path.exists(job["excel_path"]):
        raise HTTPException(status_code=404, detail="Generated Excel file not found or expired. Please generate first.")
    if job["user_id"] != current_user.id and current_user.role not in ("ADMIN", "SUPER_ADMIN"):
        raise HTTPException(status_code=403, detail="Access denied.")

    return FileResponse(
        path=job["excel_path"],
        filename=job["excel_filename"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@router.get("/{job_id}/download")
async def download_tally_xml_endpoint(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Downloads the verified Tally XML file."""
    job = IN_MEMORY_JOBS.get(job_id)
    if not job or not job.get("xml_path") or not os.path.exists(job["xml_path"]):
        raise HTTPException(status_code=404, detail="Generated XML file not found or expired.")
    if job["user_id"] != current_user.id and current_user.role not in ("ADMIN", "SUPER_ADMIN"):
        raise HTTPException(status_code=403, detail="Access denied.")

    return FileResponse(
        path=job["xml_path"],
        filename=job["xml_filename"],
        media_type="application/xml"
    )

@router.get("/active/recent", response_model=Optional[ConversionJobSummary])
async def get_recent_active_conversion(current_user: CurrentUser = Depends(get_current_user)):
    """
    Retrieves the user's most recent active conversion workspace.
    Enables instant session continuation across page refresh, token renewal, or route change.
    """
    # 1. Check in-memory jobs first
    user_jobs = [
        j for j in IN_MEMORY_JOBS.values() 
        if (j.get("user_id") == current_user.id or j.get("user_email") == current_user.email)
        and j.get("status") in ("COMPLETED", "PARTIALLY_COMPLETED", "NEEDS_REVIEW")
    ]
    if user_jobs:
        user_jobs.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
        return ConversionJobSummary(**user_jobs[0])

    # 2. Check SQLite persistent store
    db_rec = db.get_latest_active_conversion(current_user.id) or (db.get_latest_active_conversion(current_user.email) if current_user.email else None)
    if db_rec:
        meta = {}
        if db_rec.get("metadata_json"):
            try:
                meta = json.loads(db_rec["metadata_json"])
            except Exception:
                pass
        raw_txs = meta.get("transactions") or []
        tx_items = []
        for t in raw_txs:
            try:
                tx_items.append(TransactionItem(**t))
            except Exception:
                pass

        error_cnt = sum(1 for t in tx_items if t.validation_status == "ERROR")
        job_dict = {
            "id": db_rec["id"],
            "user_id": db_rec["user_id"],
            "user_email": db_rec.get("user_email", ""),
            "file_name": db_rec["file_name"],
            "bank_name": db_rec["bank_name"],
            "statement_format": meta.get("parser_name", "Standard"),
            "page_count": db_rec["total_pdf_pages"],
            "total_pdf_pages": db_rec["total_pdf_pages"],
            "pages_processed": db_rec["pages_processed"],
            "pages_skipped": db_rec["pages_skipped"],
            "pages_pending": db_rec["pages_skipped"],
            "page_statuses": meta.get("page_statuses") or {str(p): ("PROCESSED" if p <= db_rec["pages_processed"] else "PENDING") for p in range(1, db_rec["total_pdf_pages"] + 1)},
            "free_quota_used": db_rec["free_quota_used"],
            "additional_quota_used": db_rec["additional_quota_used"],
            "is_partial_conversion": bool(db_rec["is_partial_conversion"]),
            "remaining_pages": db_rec["pages_skipped"],
            "suggested_additional_price": round(float(db_rec["pages_skipped"] * getattr(settings, "page_price_inr", 2.0)), 2),
            "transaction_count": len(tx_items) or db_rec["transaction_count"],
            "raw_transaction_count": len(tx_items) or db_rec["transaction_count"],
            "suspense_count": sum(1 for t in tx_items if (t.ledger_name == "Suspense" or not t.ledger_name)),
            "mapped_count": sum(1 for t in tx_items if (t.ledger_name and t.ledger_name != "Suspense")),
            "duplicate_count": sum(1 for t in tx_items if getattr(t, "is_duplicate_suspect", False)),
            "warning_count": sum(1 for t in tx_items if t.validation_status == "WARNING"),
            "error_count": error_cnt,
            "ready_for_export": error_cnt == 0,
            "bank_ledger_name": meta.get("bank_ledger_name", "Bank Account"),
            "cash_ledger_name": meta.get("cash_ledger_name", "Cash"),
            "status": db_rec["status"],
            "confidence_score": meta.get("confidence_score", 100.0),
            "confidence_tier": meta.get("confidence_tier", "HIGH"),
            "parser_name": meta.get("parser_name", db_rec["bank_name"]),
            "balance_status": "VALID",
            "created_at": db_rec["created_at"],
            "transactions": tx_items,
            "pdf_path": meta.get("pdf_path"),
            "password": meta.get("password")
        }
        IN_MEMORY_JOBS[db_rec["id"]] = job_dict
        return ConversionJobSummary(**job_dict)

    return None

@router.get("/{job_id}", response_model=ConversionJobSummary)
async def get_conversion_job(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Retrieves conversion job details by ID with SQLite persistence fallback."""
    job = IN_MEMORY_JOBS.get(job_id)
    if not job:
        db_rec = db.get_conversion_by_id(job_id)
        if db_rec:
            meta = {}
            if db_rec.get("metadata_json"):
                try:
                    meta = json.loads(db_rec["metadata_json"])
                except Exception:
                    pass
            raw_txs = meta.get("transactions") or []
            tx_items = []
            for t in raw_txs:
                try:
                    tx_items.append(TransactionItem(**t))
                except Exception:
                    pass
            error_cnt = sum(1 for t in tx_items if t.validation_status == "ERROR")
            job = {
                "id": db_rec["id"],
                "user_id": db_rec["user_id"],
                "user_email": db_rec.get("user_email", ""),
                "file_name": db_rec["file_name"],
                "bank_name": db_rec["bank_name"],
                "statement_format": meta.get("parser_name", "Standard"),
                "page_count": db_rec["total_pdf_pages"],
                "total_pdf_pages": db_rec["total_pdf_pages"],
                "pages_processed": db_rec["pages_processed"],
                "pages_skipped": db_rec["pages_skipped"],
                "pages_pending": db_rec["pages_skipped"],
                "page_statuses": meta.get("page_statuses") or {str(p): ("PROCESSED" if p <= db_rec["pages_processed"] else "PENDING") for p in range(1, db_rec["total_pdf_pages"] + 1)},
                "free_quota_used": db_rec["free_quota_used"],
                "additional_quota_used": db_rec["additional_quota_used"],
                "is_partial_conversion": bool(db_rec["is_partial_conversion"]),
                "remaining_pages": db_rec["pages_skipped"],
                "suggested_additional_price": round(float(db_rec["pages_skipped"] * getattr(settings, "page_price_inr", 2.0)), 2),
                "transaction_count": len(tx_items) or db_rec["transaction_count"],
                "raw_transaction_count": len(tx_items) or db_rec["transaction_count"],
                "suspense_count": sum(1 for t in tx_items if (t.ledger_name == "Suspense" or not t.ledger_name)),
                "mapped_count": sum(1 for t in tx_items if (t.ledger_name and t.ledger_name != "Suspense")),
                "duplicate_count": sum(1 for t in tx_items if getattr(t, "is_duplicate_suspect", False)),
                "reverse_entries_count": sum(1 for t in tx_items if getattr(t, "is_reverse_entry", False)),
                "reverse_pairs_count": len(set(t.reversal_pair_id for t in tx_items if getattr(t, "reversal_pair_id", None))),
                "reverse_unmatched_count": sum(1 for t in tx_items if getattr(t, "is_reverse_entry", False) and getattr(t, "reversal_leg", "") == "UNPAIRED"),
                "warning_count": sum(1 for t in tx_items if t.validation_status == "WARNING"),
                "error_count": error_cnt,
                "ready_for_export": error_cnt == 0,
                "bank_ledger_name": meta.get("bank_ledger_name", "Bank Account"),
                "cash_ledger_name": meta.get("cash_ledger_name", "Cash"),
                "status": db_rec["status"],
                "confidence_score": meta.get("confidence_score", 100.0),
                "confidence_tier": meta.get("confidence_tier", "HIGH"),
                "parser_name": meta.get("parser_name", db_rec["bank_name"]),
                "balance_status": "VALID",
                "created_at": db_rec["created_at"],
                "transactions": tx_items,
                "pdf_path": meta.get("pdf_path"),
                "password": meta.get("password")
            }
            IN_MEMORY_JOBS[db_rec["id"]] = job

    if not job:
        raise HTTPException(status_code=404, detail="Conversion job not found.")
    if job["user_id"] != current_user.id and current_user.role not in ("ADMIN", "SUPER_ADMIN"):
        raise HTTPException(status_code=403, detail="Access denied.")
    return ConversionJobSummary(**job)

@router.post("/{job_id}/process-remaining", response_model=ConversionJobSummary)
async def process_remaining_pages(
    job_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Processes remaining unparsed pages for a partially converted document.
    Does NOT re-process already converted pages (1..N).
    Deducts quota: free quota first, then additional purchased balance.
    """
    job = IN_MEMORY_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Conversion job not found.")
    if job["user_id"] != current_user.id and current_user.role not in ("ADMIN", "SUPER_ADMIN"):
        raise HTTPException(status_code=403, detail="Access denied.")

    pages_skipped = job.get("pages_skipped", 0)
    if pages_skipped <= 0:
        raise HTTPException(status_code=400, detail="This document has no remaining unprocessed pages.")

    pdf_path = job.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=400, detail="Original PDF file is no longer available on the server. Please upload again.")

    # Check user quota
    usage = get_user_usage_data(current_user)
    is_unlimited = usage.is_unlimited or current_user.has_quota_bypass or current_user.is_admin or current_user.role in ("ADMIN", "SUPER_ADMIN")
    remaining_free = usage.pages_remaining_today if not is_unlimited else 999999
    additional_bal = get_user_additional_pages(current_user) if not is_unlimited else 0
    total_available = 999999 if is_unlimited else (remaining_free + additional_bal)

    if total_available <= 0:
        raise HTTPException(
            status_code=403,
            detail="Payment verification required. You do not have sufficient remaining page quota or balance. Please purchase extra pages via Google Pay / UPI."
        )

    # How many pages can we process now?
    pages_to_process = min(pages_skipped, total_available)
    start_page = (job.get("pages_processed", 0) or 0) + 1

    # Extract ONLY the remaining pages without touching the completed ones
    new_doc = extract_pdf_data(
        pdf_path,
        password=job.get("password"),
        max_pages=pages_to_process,
        start_page=start_page
    )

    # Resolve parser
    bank_name = job.get("bank_name")
    if bank_name == "Pending Quota" or not bank_name:
        detection_result = detect_bank_from_document(new_doc)
        bank_name = detection_result.bank_name
        parser = parser_registry.get_parser(detection_result.parser_key) or parser_registry.get_parser_for_bank(bank_name)
        job["bank_name"] = bank_name
        job["statement_format"] = detection_result.format_name
        job["confidence_score"] = detection_result.confidence
        job["confidence_tier"] = detection_result.confidence_tier
    else:
        parser = parser_registry.get_parser_for_bank(bank_name)

    if not parser:
        raise UnsupportedBankException(bank_name or "Unknown")

    new_statement = parser.parse(new_doc)

    # STRICT POST-PARSER GATE: Never allow transactions outside authorized remaining slice
    allowed_remaining_pages = set(range(start_page, start_page + pages_to_process))
    new_txs = [
        tx for tx in new_statement.transactions
        if getattr(tx, "source_page", None) is None or tx.source_page in allowed_remaining_pages
    ]

    # Deduct quota: free first, additional second
    if not is_unlimited:
        free_used = min(pages_to_process, remaining_free)
        rem_to_deduct = pages_to_process - free_used
        additional_used = min(rem_to_deduct, additional_bal)
        if free_used > 0:
            record_user_page_usage(current_user, free_used)
        if additional_used > 0:
            deduct_user_additional_pages(current_user.id, additional_used)
        job["free_quota_used"] = (job.get("free_quota_used") or 0) + free_used
        job["additional_quota_used"] = (job.get("additional_quota_used") or 0) + additional_used

    # Re-number and append transactions
    existing_statement = job.get("statement")
    if existing_statement is None:
        existing_statement = new_statement
        job["statement"] = existing_statement
        statement = existing_statement
    else:
        current_len = len(existing_statement.transactions)
        for idx, tx in enumerate(new_txs):
            tx.id = f"{job_id}-tx-{current_len + idx + 1}"
            tx.row_index = current_len + idx + 1
        existing_statement.transactions.extend(new_txs)
        statement = existing_statement

    # Re-map ledger & voucher types for new transactions
    configured_bank_ledger = job.get("bank_ledger_name") or "Bank Account"
    configured_cash_ledger = job.get("cash_ledger_name") or "Cash"
    user_ledgers = global_ledger_store.get_user_ledgers(current_user.id)
    saved_rules = USER_SAVED_RULES.get(current_user.id, {})

    mapper = LedgerMapper(
        user_saved_mappings=saved_rules,
        imported_ledgers=user_ledgers,
        bank_ledger_name=configured_bank_ledger,
        cash_ledger_name=configured_cash_ledger,
        suspense_ledger_name="Suspense"
    )
    for tx in statement.transactions:
        if not tx.ledger_name:
            tx.ledger_name = mapper.map_transaction_ledger(tx, configured_bank_ledger)
        if not tx.voucher_type:
            tx.voucher_type = classify_voucher_type(tx)

    # PRD Section 11: Detect reversed and rejected entries
    rev_detector = ReversalDetector(
        reverse_ledger_name="Reverse Entries",
        bank_charges_ledger_name="Bank Charges"
    )
    rev_detector.process_statement(statement)

    # Update counts and metrics
    total_processed = (job.get("pages_processed") or 0) + pages_to_process
    rem_skipped = max(0, job["page_count"] - total_processed)
    is_still_partial = (rem_skipped > 0)

    total_debit = sum(t.debit for t in statement.transactions)
    total_credit = sum(t.credit for t in statement.transactions)
    statement.total_debit = total_debit
    statement.total_credit = total_credit

    if is_still_partial:
        if statement.transactions:
            last_bal = statement.transactions[-1].balance
            if last_bal is not None:
                statement.closing_balance = last_bal
            elif statement.opening_balance is not None:
                statement.closing_balance = statement.opening_balance + statement.total_credit - statement.total_debit
        job["status"] = "PARTIALLY_COMPLETED"
    else:
        if new_statement.closing_balance is not None:
            statement.closing_balance = new_statement.closing_balance
        elif statement.opening_balance is not None:
            statement.closing_balance = statement.opening_balance + statement.total_credit - statement.total_debit
        job["status"] = "COMPLETED"

    suspense_count = sum(1 for t in statement.transactions if (t.ledger_name == "Suspense" or t.mapping_status == "Suspense" or not t.ledger_name))
    mapped_count = len(statement.transactions) - suspense_count
    warning_count = sum(1 for t in statement.transactions if t.validation_status == "WARNING")
    error_count = sum(1 for t in statement.transactions if t.validation_status == "ERROR")

    job["pages_processed"] = total_processed
    job["pages_skipped"] = rem_skipped
    job["pages_pending"] = rem_skipped
    p_statuses = dict(job.get("page_statuses") or {})
    for p in range(start_page, start_page + pages_to_process):
        p_statuses[str(p)] = "PROCESSED"
    job["page_statuses"] = p_statuses
    job["is_partial_conversion"] = is_still_partial
    job["remaining_pages"] = rem_skipped
    job["suggested_additional_price"] = round(float(rem_skipped * getattr(settings, "page_price_inr", 2.0)), 2)
    job["transaction_count"] = len(statement.transactions)
    job["raw_transaction_count"] = len(statement.transactions)
    job["suspense_count"] = suspense_count
    job["mapped_count"] = mapped_count
    job["warning_count"] = warning_count
    job["error_count"] = error_count
    job["ready_for_export"] = (error_count == 0)
    job["closing_balance"] = statement.closing_balance
    job["total_debit"] = statement.total_debit
    job["total_credit"] = statement.total_credit
    job["balance_status"] = "VALID"
    job["transactions"] = statement.transactions
    job.pop("snapshot", None)
    job.pop("excel_path", None)
    job.pop("xml_path", None)

    try:
        db.save_conversion(job)
    except Exception:
        pass

    return ConversionJobSummary(**job)

@router.get("", response_model=List[ConversionJobSummary])
async def list_user_conversions(current_user: CurrentUser = Depends(get_current_user)):
    """Lists past conversion jobs for the current user."""
    user_jobs = [j for j in IN_MEMORY_JOBS.values() if j["user_id"] == current_user.id]
    user_jobs.sort(key=lambda x: x["created_at"], reverse=True)
    return [ConversionJobSummary(**j) for j in user_jobs]

@router.post("/unlock-pdf")
async def unlock_pdf_endpoint(
    file: UploadFile = File(...),
    password: str = Form(...),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Decrypts a password-protected bank statement PDF in volatile memory
    and returns the unlocked PDF document for user download.
    Zero permanent disk persistence.
    """
    if not password or not password.strip():
        raise PasswordProtectedPDFException("A valid statement password is required to unlock this PDF.")

    content = await file.read()
    if len(content) == 0:
        raise InvalidPDFException("The uploaded PDF file is empty.")

    import io
    from pypdf import PdfReader, PdfWriter

    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception:
        raise InvalidPDFException("Failed to read the uploaded file as a valid PDF.")

    clean_name = file.filename.rsplit(".", 1)[0] if file.filename else "statement"

    if not reader.is_encrypted:
        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{clean_name}_unlocked.pdf"',
                "X-Unlocked-Pages": str(len(reader.pages)),
                "X-Was-Encrypted": "false"
            }
        )

    # Attempt decryption with provided password
    decrypt_result = reader.decrypt(password.strip())
    if decrypt_result == 0:
        raise InvalidPDFException("Incorrect PDF password. Please check the password and try again.")

    if len(reader.pages) == 0:
        raise InvalidPDFException("The PDF statement contains no pages.")

    if len(reader.pages) > settings.max_pages_per_file:
        raise InvalidPDFException(
            f"The PDF contains {len(reader.pages)} pages, which exceeds the maximum limit of {settings.max_pages_per_file} pages."
        )

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    output_stream = io.BytesIO()
    writer.write(output_stream)
    output_bytes = output_stream.getvalue()

    return Response(
        content=output_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{clean_name}_unlocked.pdf"',
            "X-Unlocked-Pages": str(len(reader.pages)),
            "X-Was-Encrypted": "true"
        }
    )

