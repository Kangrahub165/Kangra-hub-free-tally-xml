from decimal import Decimal
from typing import List, Optional
from datetime import date
from pydantic import BaseModel, Field

class TransactionItem(BaseModel):
    id: Optional[str] = None
    row_index: int = 0
    date: date
    value_date: Optional[date] = None
    posting_date: Optional[date] = None
    narration: str
    full_narration: Optional[str] = None
    original_narration: Optional[str] = None
    reference: Optional[str] = ""
    cheque_number: Optional[str] = None
    instrument_number: Optional[str] = None
    instrument_date: Optional[date] = None
    utr: Optional[str] = None
    upi_ref: Optional[str] = None
    debit: Decimal = Field(default_factory=lambda: Decimal("0.00"))
    credit: Decimal = Field(default_factory=lambda: Decimal("0.00"))
    balance: Optional[Decimal] = None
    confidence_score: float = 100.0
    
    # Ledger mapping fields
    party_name: Optional[str] = None
    suggested_ledger: Optional[str] = None
    mapping_confidence: float = 0.0
    mapping_status: str = "Suspense"  # "Auto", "Previously Mapped", "Suspense", "User Confirmed"
    ledger_name: Optional[str] = None
    original_ledger_name: Optional[str] = None
    
    # Voucher classification fields
    voucher_type: str = "Payment"  # "Payment", "Receipt", "Contra", "Journal"
    original_voucher_type: Optional[str] = None
    is_cash_transaction: bool = False
    cash_transaction_type: Optional[str] = None  # "CASH_DEPOSIT", "CASH_WITHDRAWAL", None
    
    # Validation & duplicates
    validation_status: str = "VALID"  # "VALID", "WARNING", "ERROR"
    validation_notes: Optional[str] = None
    is_duplicate_suspect: bool = False
    duplicate_reason: Optional[str] = None

    # Source traceability & boundary diagnostics
    source_page: Optional[int] = None
    source_lines: Optional[List[str]] = None
    source_row_index: Optional[int] = None
    parser_name: Optional[str] = None
    boundary_confidence: float = 1.0
    narration_warning: Optional[str] = None

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v),
            date: lambda v: v.isoformat()
        }

class PageDiagnosticSummary(BaseModel):
    page_number: int
    detected_candidate_count: int = 0
    extracted_transaction_count: int = 0
    unparsed_candidate_lines: List[str] = Field(default_factory=list)

class CanonicalStatement(BaseModel):
    bank: str
    statement_format: str = "Standard"
    account_number_masked: Optional[str] = None
    statement_from: Optional[date] = None
    statement_to: Optional[date] = None
    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None
    calculated_closing_balance: Optional[Decimal] = None
    total_debit: Decimal = Field(default_factory=lambda: Decimal("0.00"))
    total_credit: Decimal = Field(default_factory=lambda: Decimal("0.00"))
    confidence_score: float = 100.0
    
    # Configured ledgers
    bank_ledger_name: Optional[str] = "Bank Account"
    cash_ledger_name: Optional[str] = "Cash"
    suspense_count: int = 0
    mapped_count: int = 0
    duplicate_count: int = 0
    
    # Accounting diagnostics
    page_diagnostics: List[PageDiagnosticSummary] = Field(default_factory=list)
    
    transactions: List[TransactionItem] = []

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v),
            date: lambda v: v.isoformat()
        }
