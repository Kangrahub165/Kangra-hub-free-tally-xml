from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Dict, Literal, Any
from uuid import uuid4
from pydantic import BaseModel, Field

def to_decimal(val: any, default: str = "0.00") -> Decimal:
    """Safely converts input to Decimal with standard 2 decimal places."""
    if val is None or val == "":
        return Decimal(default)
    if isinstance(val, Decimal):
        return val
    try:
        clean = str(val).replace(",", "").strip()
        return Decimal(clean).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal(default)

class PartyInfo(BaseModel):
    name: str = ""
    gstin: Optional[str] = None
    address: Optional[str] = None
    state: Optional[str] = None
    state_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    pan: Optional[str] = None
    role_evidence: Optional[str] = None
    source_text: Optional[str] = None
    repaired_gstin: Optional[str] = None
    matched_ledger_name: Optional[str] = None
    requires_ledger_creation: bool = False
    mapping_confidence: Literal["HIGH", "MEDIUM", "LOW", "UNMATCHED"] = "UNMATCHED"
    mapping_status: Literal["AUTO_MAPPED", "PLEASE_CHECK", "POSSIBLE_MATCH", "UNMATCHED", "NEW_LEDGER"] = "UNMATCHED"
    match_suggestions: List[Dict[str, Any]] = Field(default_factory=list)

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v)
        }

class InvoiceItem(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    item_index: int = 1
    serial: Optional[str] = None
    item_name: str = ""
    description: Optional[str] = None
    hsn_sac: Optional[str] = None
    quantity: Decimal = Decimal("1.00")
    invoice_qty: Optional[Decimal] = None
    pack_multiplier: Optional[Decimal] = None
    effective_qty: Optional[Decimal] = None
    shipped_qty: Optional[Decimal] = None
    billed_qty: Optional[Decimal] = None
    uom: str = "NOS"
    invoice_uom: Optional[str] = None
    tally_uom: Optional[str] = None
    rate: Decimal = Decimal("0.00")
    gross_amount: Decimal = Decimal("0.00")
    discount: Decimal = Decimal("0.00")
    discount_pct: Decimal = Decimal("0.00")
    discount_amount: Decimal = Decimal("0.00")
    taxable_amount: Decimal = Decimal("0.00")
    gst_rate: Optional[Decimal] = None
    cgst_rate: Decimal = Decimal("0.00")
    cgst_amount: Decimal = Decimal("0.00")
    sgst_rate: Decimal = Decimal("0.00")
    sgst_amount: Decimal = Decimal("0.00")
    igst_rate: Decimal = Decimal("0.00")
    igst_amount: Decimal = Decimal("0.00")
    cess_rate: Decimal = Decimal("0.00")
    cess_amount: Decimal = Decimal("0.00")
    other_charges: Decimal = Decimal("0.00")
    total_amount: Decimal = Decimal("0.00")
    confidence_level: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH"
    field_confidences: Dict[str, float] = Field(default_factory=dict)
    matched_stock_item: Optional[str] = None
    requires_item_creation: bool = False
    is_description_wrapped: bool = False
    tax_mode: Literal["exclusive", "inclusive", "unknown"] = "exclusive"
    is_tax_inclusive: bool = False
    raw_row_text: Optional[str] = None
    mrp: Optional[Decimal] = None
    pack_size: Optional[str] = None
    item_size: Optional[str] = None
    secondary_quantity: Optional[Decimal] = None
    secondary_unit: Optional[str] = None
    free_qty: Optional[Decimal] = None
    unit_source: Optional[str] = None
    printed_rate: Optional[Decimal] = None
    printed_taxable: Optional[Decimal] = None
    validation_errors: List[str] = Field(default_factory=list)
    source_text: Optional[str] = None
    mapping_confidence: Literal["HIGH", "MEDIUM", "LOW", "UNMATCHED"] = "UNMATCHED"
    mapping_status: Literal["AUTO_MAPPED", "VERIFIED", "PLEASE_CHECK", "POSSIBLE_MATCH", "UNMATCHED", "NEW_ITEM"] = "UNMATCHED"
    match_suggestions: List[Dict[str, Any]] = Field(default_factory=list)

    # Dual Quantity Column Options (PRD §1-11)
    quantity_option_a: Optional[Decimal] = None
    uom_option_a: Optional[str] = None
    rate_option_a: Optional[Decimal] = None
    quantity_option_b: Optional[Decimal] = None
    uom_option_b: Optional[str] = None
    rate_option_b: Optional[Decimal] = None
    selected_qty_option: Optional[Literal["A", "B"]] = None
    has_dual_qty: bool = False
    alternate_quantity: Optional[Decimal] = None
    alternate_uom: Optional[str] = None

    # PRD Oct 2026 Engine Fields (§5, §6, §7, §13)
    needs_review: bool = False
    review_reason: Optional[str] = None
    is_reconstructed: bool = False
    math_check_passed: bool = False
    rate_source: Optional[str] = None
    gst_rate_source: Optional[str] = None
    can_convert_to_pieces: bool = False
    pack_size_multiplier: Optional[int] = None
    is_converted_to_pieces: bool = False
    is_tax_inclusive: bool = False
    discount_pattern: Optional[str] = None
    is_free_item: bool = False

    def __init__(self, **data: Any):
        if "item_size" in data and data["item_size"] and not data.get("pack_size"):
            data["pack_size"] = data["item_size"]
        elif "pack_size" in data and data["pack_size"] and not data.get("item_size"):
            data["item_size"] = data["pack_size"]
        sz = data.get("item_size") or data.get("pack_size")
        if sz:
            from app.invoices.table_engine import merge_size_into_item_name
            if "item_name" in data and data["item_name"]:
                data["item_name"] = merge_size_into_item_name(str(data["item_name"]), sz)
            if "description" in data and data["description"]:
                data["description"] = merge_size_into_item_name(str(data["description"]), sz)
            elif "item_name" in data and data["item_name"]:
                data["description"] = data["item_name"]

        for f in (
            "quantity", "rate", "gross_amount", "discount", "discount_pct", "discount_amount",
            "taxable_amount", "cgst_rate", "cgst_amount", "sgst_rate", "sgst_amount",
            "igst_rate", "igst_amount", "cess_rate", "cess_amount", "other_charges", "total_amount"
        ):
            if f in data:
                val = data[f]
                if val is None or val == "":
                    data[f] = Decimal("0.00")
                elif not isinstance(val, Decimal):
                    data[f] = to_decimal(val)

        super().__init__(**data)

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }

class InvoiceDocument(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    doc_type: str = "tax_invoice"
    doc_type_evidence: Optional[str] = None
    invoice_type: Literal["PURCHASE", "SALES"] = "PURCHASE"
    type_confidence: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH"
    type_rationale: Optional[str] = None
    is_type_manual_override: bool = False

    # Own Company Profile (PRD 5.9)
    own_company_name: str = "Kartar Singh & Sons"
    own_gstin: str = "02AWLPK8092M1Z0"
    own_state: str = "Himachal Pradesh"

    # Invoice Details
    invoice_number: str = ""
    bill_number: Optional[str] = None
    invoice_date: date = Field(default_factory=date.today)
    due_date: Optional[date] = None
    po_number: Optional[str] = None
    eway_bill_number: Optional[str] = None
    irn: Optional[str] = None
    place_of_supply: Optional[str] = None
    reverse_charge: bool = False
    tax_mode: Literal["exclusive", "inclusive", "unknown"] = "exclusive"
    tax_mode_evidence: Optional[str] = None

    # Parties
    supplier: PartyInfo = Field(default_factory=PartyInfo)
    buyer: PartyInfo = Field(default_factory=PartyInfo)
    detected_gstins: List[Dict[str, Any]] = Field(default_factory=list)
    gstin_role_needs_review: bool = False

    # Line Items
    items: List[InvoiceItem] = Field(default_factory=list)
    table_columns: List[Dict[str, Any]] = Field(default_factory=list)
    items_detected_count: int = 0
    item_count_reconciliation_note: Optional[str] = None

    # Totals
    taxable_total: Decimal = Decimal("0.00")
    cgst_total: Decimal = Decimal("0.00")
    sgst_total: Decimal = Decimal("0.00")
    igst_total: Decimal = Decimal("0.00")
    cess_total: Decimal = Decimal("0.00")
    discount_total: Decimal = Decimal("0.00")
    other_charges: Decimal = Decimal("0.00")
    round_off: Decimal = Decimal("0.00")
    grand_total: Decimal = Decimal("0.00")

    # Field-level Confidences & Review
    field_confidences: Dict[str, float] = Field(default_factory=dict)
    low_confidence_fields: List[str] = Field(default_factory=list)

    # Additional metadata
    amount_in_words: Optional[str] = None
    narration: Optional[str] = None
    payment_terms: Optional[str] = None
    bank_details: Optional[str] = None
    transport_details: Optional[str] = None
    vehicle_number: Optional[str] = None
    page_notes: List[str] = Field(default_factory=list)

    # Status & Diagnostics
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    validation_violations: List[Dict[str, Any]] = Field(default_factory=list)
    is_valid: bool = True
    needs_review: bool = False
    reconciliation_passed: bool = True
    reconciliation_flags: List[str] = Field(default_factory=list)
    has_page_continuation: bool = False
    continuation_note: Optional[str] = None
    duplicate_suspect: bool = False
    duplicate_reason: Optional[str] = None
    source_filename: str = ""
    source_page_count: int = 1
    page_numbers: List[int] = Field(default_factory=lambda: [1])
    raw_text_preview: Optional[str] = None
    voucher_type: Optional[str] = None
    ai_extracted: bool = False
    ai_model_used: Optional[str] = None
    ai_status_message: Optional[str] = None
    fingerprint_hash: Optional[str] = None
    is_free_reconversion: bool = False
    distinct_bill_key: Optional[str] = None
    tax_mode: Optional[str] = None
    tax_mode_evidence: Optional[str] = None
    is_tax_inclusive: bool = False
    discount_pattern: Optional[str] = None
    discount_pattern_note: Optional[str] = None
    post_tax_discount: Decimal = Decimal("0.00")
    pack_quantity_option: Literal["1", "2", "bulk", "pieces"] = "pieces"

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            date: lambda v: v.isoformat()
        }

class LedgerMappingConfig(BaseModel):
    purchase_ledger: str = "PURCHASE GST"
    sales_ledger: str = "SALE GST"
    cgst_ledger: str = "CGST"
    sgst_ledger: str = "SGST"
    igst_ledger: str = "IGST"
    cess_ledger: str = "Cess"
    round_off_ledger: str = "Round Off."
    other_charges_ledger: str = "Other Charges"
    discount_ledger: str = "Discount"

class FinalInvoiceSnapshot(BaseModel):
    invoices: List[InvoiceDocument]
    ledger_mapping: LedgerMappingConfig = Field(default_factory=LedgerMappingConfig)
    company_name: Optional[str] = None
    auto_create_items: bool = True
    auto_create_parties: bool = True
    voucher_numbering_mode: Literal["AS_INVOICE", "SEQUENTIAL"] = "AS_INVOICE"
    starting_voucher_number: int = 1

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v),
            date: lambda v: v.isoformat()
        }

class BatchSummary(BaseModel):
    total_documents: int = 0
    total_purchase_invoices: int = 0
    total_sales_invoices: int = 0
    purchase_count: int = 0
    sales_count: int = 0
    total_items: int = 0
    total_taxable_value: Decimal = Decimal("0.00")
    total_taxable: Decimal = Decimal("0.00")
    total_cgst: Decimal = Decimal("0.00")
    total_sgst: Decimal = Decimal("0.00")
    total_igst: Decimal = Decimal("0.00")
    total_cess: Decimal = Decimal("0.00")
    total_invoice_value: Decimal = Decimal("0.00")
    total_grand: Decimal = Decimal("0.00")
    errors_count: int = 0
    warnings_count: int = 0
    missing_masters_count: int = 0
    has_discrepancies: bool = False
    duplicate_candidates_count: int = 0
    items_requiring_creation_count: int = 0
    parties_requiring_creation_count: int = 0

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }

class InvoiceBatchResult(BaseModel):
    job_id: str = Field(default_factory=lambda: uuid4().hex)
    invoices: List[InvoiceDocument]
    summary: BatchSummary
    ledger_mapping: LedgerMappingConfig = Field(default_factory=LedgerMappingConfig)
    distinct_bills_count: int = 0
    credits_required: int = 0
    remaining_free_credits: int = 5
    user_role: str = "USER"
    is_staff: bool = False
    is_gold: bool = False

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v),
            date: lambda v: v.isoformat()
        }
