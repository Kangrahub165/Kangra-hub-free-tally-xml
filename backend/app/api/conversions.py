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
from app.pdf.validator import validate_pdf_file
from app.pdf.extractor import extract_pdf_data
from app.detector.bank_detector import detect_bank_from_document
from app.parsers.registry import parser_registry
from app.accounting.mapper import LedgerMapper
from app.accounting.voucher_classifier import classify_voucher_type
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

@router.post("/upload", response_model=ConversionJobSummary)
async def upload_statement(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    bank_override: Optional[str] = Form(None),
    bank_ledger_name: Optional[str] = Form(None),
    cash_ledger_name: Optional[str] = Form(None),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Step 1: Upload and parse bank statement PDF.
    Enforces daily 50-page quota check BEFORE processing begins.
    Preserves exact configured Bank Ledger and Cash Ledger names without normalization.
    """
    job_id = f"job-{uuid.uuid4().hex[:10]}"
    app_logger.info(f"Starting conversion job {job_id} for user {current_user.email}, file: {file.filename}")

    # Persist uploaded file to permanent CONVERSION_STORAGE_DIR
    saved_pdf_path = os.path.join(CONVERSION_STORAGE_DIR, f"{job_id}.pdf")
    content = await file.read()
    with open(saved_pdf_path, "wb") as f:
        f.write(content)

    # 1. Validate PDF structure, password, page count (Metadata inspection ONLY)
    page_count, is_encrypted = validate_pdf_file(saved_pdf_path, password=password)

    # 2. Check available page limit (Free Daily Quota + Additional Purchased Balance)
    usage = get_user_usage_data(current_user)
    is_unlimited = usage.is_unlimited or current_user.has_quota_bypass or current_user.is_admin or current_user.role in ("ADMIN", "SUPER_ADMIN")
    
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
        # User has exhausted quota entirely (Case E: 0 pages remaining)
        job_record = {
            "id": job_id,
            "user_id": current_user.id,
            "file_name": file.filename or "statement.pdf",
            "pdf_path": saved_pdf_path,
            "password": password,
            "bank_name": "Pending Quota",
            "statement_format": "PDF Statement",
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

    # Quota Priority:
    # 1) Daily free quota first (resets at midnight IST)
    # 2) Additional purchased balance second (never resets)
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

    # 3. Extract text and layout for only allowed pages_to_process
    extracted_doc = extract_pdf_data(saved_pdf_path, password=password, max_pages=pages_to_process, start_page=1)

    # 4. Detect bank or use override
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

        # When detection confidence is ambiguous or low (<70%), do not guess
        if is_ambiguous or confidence_tier in ("AMBIGUOUS", "LOW") or detection_confidence < 70.0:
            configured_bank_ledger = bank_ledger_name or USER_BANK_CONFIGS.get(current_user.id, {}).get(detected_bank_name) or f"{detected_bank_name} A/C"
            configured_cash_ledger = cash_ledger_name or USER_BANK_CONFIGS.get(current_user.id, {}).get("__cash__") or "Cash"
            job_record = {
                "id": job_id,
                "user_id": current_user.id,
                "file_name": file.filename or "statement.pdf",
                "pdf_path": saved_pdf_path,
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

    # 5. Parse canonical statement
    statement: CanonicalStatement = parser.parse(extracted_doc)
    statement.account_number_masked = account_num

    # STRICT SERVER-SIDE GATE: Never allow transactions beyond authorized pages_to_process
    allowed_page_set = set(range(1, pages_to_process + 1))
    statement.transactions = [
        tx for tx in statement.transactions
        if getattr(tx, "source_page", None) is None or tx.source_page in allowed_page_set
    ]
    raw_count = len(statement.transactions)

    # 6. Apply intelligent ledger mapping and voucher classification
    # EXACT bank and cash ledger names preserved verbatim
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

    # Calculate Suspense count and Mapped count
    suspense_count = sum(1 for t in statement.transactions if (t.ledger_name == "Suspense" or t.mapping_status == "Suspense"))
    mapped_count = raw_count - suspense_count

    statement.bank_ledger_name = configured_bank_ledger
    statement.cash_ledger_name = configured_cash_ledger
    statement.suspense_count = suspense_count
    statement.mapped_count = mapped_count

    # 7. Zero-Silent-Loss Accounting Diagnostics & Duplicate Candidate Detection
    detect_duplicate_candidates(statement)
    compile_page_diagnostics(statement, extracted_doc)

    # Balance validation audit check
    if is_partial and statement.transactions:
        # Reconcile closing balance to last processed transaction's running balance
        last_tx_balance = statement.transactions[-1].balance
        if last_tx_balance is not None:
            statement.closing_balance = last_tx_balance
        elif statement.opening_balance is not None:
            statement.closing_balance = statement.opening_balance + statement.total_credit - statement.total_debit

    has_mismatch = any(t.validation_status == "ERROR" for t in statement.transactions)
    if not is_partial and statement.opening_balance is not None and statement.closing_balance is not None:
        expected_closing = (statement.opening_balance + statement.total_credit - statement.total_debit).quantize(Decimal("0.01"))
        actual_closing = statement.closing_balance.quantize(Decimal("0.01"))
        if expected_closing != actual_closing:
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

    # 8. Store job in memory
    job_record = {
        "id": job_id,
        "user_id": current_user.id,
        "file_name": file.filename or "statement.pdf",
        "pdf_path": saved_pdf_path,
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

