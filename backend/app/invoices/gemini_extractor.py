"""
Gemini AI Document Understanding & Intelligence Layer for Indian Invoices.
PRD Compliant:
- Google Gemini Free Tier optimization & circuit breaker (429 handling, timeouts, no runaway retries)
- Multimodal extraction (Images & PDFs) + OCR text cross-referencing
- Strict separation: Qty vs Secondary Qty, Qty vs Product Weight/Volume, MRP vs Rate
- Description preservation without stripping codes, sizes, or variants
- Strict JSON output structure integrated with existing InvoiceDocument data model
- Fallback to deterministic OCR/validation when AI is unavailable or fails
- Never exposes API keys
"""

import os
import io
import re
import json
import base64
import time
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Optional, Dict, Any, List, Tuple

import httpx
from PIL import Image

from app.core.config import settings

try:
    from app.utils.logger import app_logger
except ImportError:
    import logging
    app_logger = logging.getLogger("kangra_hub.gemini")
from app.invoices.model import InvoiceDocument, InvoiceItem, PartyInfo, to_decimal
from app.invoices.table_engine import detect_pack_multiplier, pack_size_from_description, merge_size_into_item_name
from app.invoices.gstin_utils import gstin_valid, gstin_repair

def _clean_and_repair_gstin(raw: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Validates or repairs a candidate GSTIN using Mod-36 checksum. Returns (final_gstin, repaired_gstin)."""
    if not raw:
        return None, None
    g = re.sub(r'[^0-9A-Za-z]', '', str(raw)).strip().upper()
    if len(g) != 15:
        return (raw.strip(), None) if len(raw.strip()) >= 5 else (None, None)
    if gstin_valid(g):
        return g, None
    rep = gstin_repair(g)
    if rep and gstin_valid(rep):
        return rep, rep
    return g, None

# In-memory circuit breaker for Free Tier rate limit protection
_CIRCUIT_BREAKER = {
    "cooldown_until": 0.0,
    "last_error": None,
    "daily_request_count": 0,
    "last_reset_day": None
}

SYSTEM_INSTRUCTION = """You are an expert Indian GST Tax Invoice and Accounting Document Understanding AI.
Your job is to read purchase and sales invoices (images, scans, digital PDFs) and extract structured, verified data.

MANDATORY EXTRACTION RULES:
1. ITEM DESCRIPTION PRESERVATION:
   - Preserve the complete original item description as printed on the invoice.
   - NEVER strip or remove meaningful details like pack sizes, weights, volume (e.g., 500ML, 6.2G), MRP tags (e.g., RS.10/-), variants, barcodes, or manufacturer codes.
   - Example: 'MC BURBON 144x4 6.2G BISCUIT RS.10/-' must remain 'MC BURBON 144x4 6.2G BISCUIT RS.10/-'.

2. QUANTITY AND 'TOTAL UNITS' DUAL COLUMN EXTRACTION:
   - Read the invoice table headers first:
     * Check for explicit quantity columns such as:
       - 'QTY.' / 'QTY' / 'BILLED QTY' / 'CASE' / 'BOX' (outer package quantity)
       - 'TOTAL UNITS' / 'TOTAL PIECES' / 'TOTAL QTY' / 'TOT UNITS' / 'PCS' (inner/total unit quantity)
     * When BOTH 'QTY' and 'TOTAL UNITS' columns are present:
       - 'quantity': Extract the outer quantity exactly as printed in the 'QTY' column (e.g. 1.0).
       - 'unit': Extract the outer unit matching 'quantity' (e.g. 'CASE' or 'BOX').
       - 'total_units': Extract the total/inner quantity exactly as printed in the 'TOTAL UNITS' column (e.g. 240.0). NEVER ignore 'TOTAL UNITS'.
       - 'total_units_uom': Extract the unit for total units from context or column header (e.g. 'PCS', 'NOS', 'UNITS').
       - NEVER overwrite 'quantity' with 'total_units' or vice versa. Keep them as separate source values.
     * When ONLY ONE quantity column is present:
       - Extract 'quantity' and its 'unit'.
       - Set 'total_units' to null. Do NOT create, guess, or synthesize a second quantity.
   - CRITICAL PROHIBITIONS:
     * Never invent a second quantity from OCR assumptions, arithmetic guesses, MRP, rate, amount, tax, or any unrelated field.
     * Do NOT generate values such as '1.185 CASE' or '1 PCS' unless those exact values are actually present/derivable from the invoice's explicit quantity fields.
     * The value from 'total_units' must remain exactly as extracted from the invoice.
     * Do not use MRP, rate, taxable value, discount, tax, total amount, or any other column to calculate or fabricate 'total_units'.

3. QUANTITY VS PRODUCT WEIGHT/VOLUME:
   - Measurements in the item name (e.g., 'SHAMPOO 10ML', 'OIL 1LTR', 'BISCUIT 6.2G') are product description text.
   - NEVER treat 10 ML or 6.2 G as transaction quantity unless explicitly in the Qty column.

4. MRP VS RATE:
   - Distinguish MRP (Maximum Retail Price) from transaction Rate.
   - If description contains 'RS.10/-' and Rate column is '7.76':
     * mrp = 10.0
     * rate = 7.76
   - NEVER use MRP as the transaction rate.

5. TABLE COLUMNS & LAYOUT:
   - Understand the visual columns: Description | HSN/SAC | Case/Billed Qty | Pcs/Secondary Qty | Unit | Rate | Taxable | CGST | SGST | IGST | Amount.
   - Disambiguate duplicate 'Rate' columns (e.g. GST Rate vs Item Rate).
   - Identify Discount columns (percentage or amount) if present.

6. GST TAX COLUMN STRUCTURE AND RATE EXTRACTION:
   - Identify the table column structure for taxes:
     * STRUCTURE 1: TWO SEPARATE TAX/GST COLUMNS (Component columns, e.g. 'CGST' + 'SGST' or 'CGST Rate' + 'SGST Rate'):
       - The rate shown in each component column represents a HALF-RATE of the total GST.
       - The rate shown in one component column must be combined with the other (or doubled) to obtain the total GST rate:
         * 2.50% + 2.50% -> Total GST = 5%
         * 6% + 6% -> Total GST = 12%
         * 9% + 9% -> Total GST = 18%
         * 14% + 14% -> Total GST = 28%
         * 20% + 20% -> Total GST = 40%
       - Set 'cgst_rate' to the printed CGST rate (e.g. 2.50, 6.0, 9.0, 14.0, 20.0).
       - Set 'sgst_rate' to the printed SGST rate (e.g. 2.50, 6.0, 9.0, 14.0, 20.0).
       - Set 'gst_rate' to the combined total GST rate (e.g. 5.0, 12.0, 18.0, 28.0, 40.0).
       - Set 'tax_column_structure' to "two_columns".

     * STRUCTURE 2: SINGLE GST/TAX RATE COLUMN (e.g. 'GST %', 'GST Rate', 'Tax Rate', 'Tax %', 'Rate of Tax', or 'IGST'):
       - The invoice directly shows the FULL total GST rate in a single column (e.g. 5%, 12%, 18%, 28%, 40%).
       - CRITICAL RULE: DO NOT DOUBLE IT!
         * 'GST 5%' -> total GST rate = 5% (NEVER double to 10%)
         * 'GST 12%' -> total GST rate = 12% (NEVER double to 24%)
         * 'GST 18%' -> total GST rate = 18% (NEVER double to 36%)
         * 'GST 28%' -> total GST rate = 28% (NEVER double to 56%)
         * 'GST 40%' -> total GST rate = 40% (NEVER double to 80%)
       - Set 'gst_rate' to the exact printed rate (e.g. 18.0).
       - For intra-state supply (CGST+SGST): split this single rate equally:
         * 18% total -> cgst_rate = 9.0, sgst_rate = 9.0 (NEVER set cgst_rate=18 and sgst_rate=18)
         * 5% total -> cgst_rate = 2.5, sgst_rate = 2.5 (NEVER set cgst_rate=5 and sgst_rate=5)
         * 12% total -> cgst_rate = 6.0, sgst_rate = 6.0 (NEVER set cgst_rate=12 and sgst_rate=12)
         * 28% total -> cgst_rate = 14.0, sgst_rate = 14.0 (NEVER set cgst_rate=28 and sgst_rate=28)
         * 40% total -> cgst_rate = 20.0, sgst_rate = 20.0 (NEVER set cgst_rate=40 and sgst_rate=40)
       - For inter-state supply: set igst_rate = gst_rate, cgst_rate = 0.0, sgst_rate = 0.0.
       - Set 'tax_column_structure' to "single_column".

   - IMPORTANT: The presence of two tax columns is the primary condition for treating a displayed rate as a half-rate component.
     Never guess from the percentage value alone. Always recognize the tax column structure first!
   - Separate Round-Off (-0.45 or +0.12) from item totals and grand total.

7. ITEM SIZE / WEIGHT COLUMN EXTRACTION:
   - When the invoice contains a dedicated SIZE column (e.g., '51 ML', '22 ML', '90 ML', '75 GM', '95 ML', '50 GM', '40 GM'):
     * Extract it into the "size" field of that item (e.g., "51 ML", "75 GM").
     * Never confuse size/weight with quantity, total units, rate, or MRP.
     * Example: 'C2 AMLA HAIR OIL' with Size column '51 ML' -> size: '51 ML'.
     * Example: 'C2 GLUCOSE D' with Size column '75 GM' -> size: '75 GM'.

8. DISCOUNT AND TAXABLE VALUE ARITHMETIC:
   - When the invoice shows a DISCOUNT column (e.g. 742.50, 186.50, 627.90):
     * Extract the discount value into "discount".
     * TAXABLE VALUE MUST SUBTRACT DISCOUNT: Taxable Amount = (Quantity * Rate) - Discount.
     * Never ignore discount during taxable-value calculation.
     * Never copy pre-discount gross amount into taxable_amount.
     * Verify: GST Amount = Taxable Amount * (GST Rate / 100).

9. MULTI-PAGE INVOICES:
   - Treat multi-page invoices as ONE single invoice.
   - Combine all line items across pages in order.
   - Ignore repeated table headers and footers on continuation pages.
   - Take the final totals, taxes, and round-off from the summary section.

10. NO GUESSING:
   - If any field is unclear, unreadable, or not present, return null.
   - Never invent or fabricate invoice numbers, dates, parties, or numbers.

OUTPUT FORMAT:
Return strictly a valid JSON object matching the requested schema. No markdown explanations outside the JSON."""

def _check_circuit_breaker() -> Tuple[bool, str]:
    """Checks if Gemini calls are currently blocked due to cooldown or daily limit."""
    now = time.time()
    today_str = date.today().isoformat()

    if _CIRCUIT_BREAKER["last_reset_day"] != today_str:
        _CIRCUIT_BREAKER["last_reset_day"] = today_str
        _CIRCUIT_BREAKER["daily_request_count"] = 0

    if not settings.ai_enabled:
        return False, "AI extraction is disabled in configuration."

    if not settings.gemini_api_key or not settings.gemini_api_key.strip():
        return False, "Gemini API key is not configured."

    if now < _CIRCUIT_BREAKER["cooldown_until"]:
        remaining = int(_CIRCUIT_BREAKER["cooldown_until"] - now)
        return False, f"AI assistance is in cooldown ({remaining}s remaining). Standard OCR fallback in use."

    if _CIRCUIT_BREAKER["daily_request_count"] >= settings.ai_daily_request_limit:
        return False, "Daily AI request limit reached. Standard OCR fallback in use."

    return True, "OK"

def _record_circuit_breaker_failure(status_code: int, error_msg: str):
    """Sets cooldown when rate limits or severe API errors occur."""
    now = time.time()
    if status_code == 429:
        # Rate limit / Resource exhausted: 20-second cooldown
        _CIRCUIT_BREAKER["cooldown_until"] = now + 20.0
        _CIRCUIT_BREAKER["last_error"] = "RESOURCE_EXHAUSTED (429)"
        app_logger.warning("Gemini 429 Resource Exhausted. Circuit breaker activated for 20s.")
    elif status_code in (403, 401):
        # Invalid key or auth: 300-second cooldown
        _CIRCUIT_BREAKER["cooldown_until"] = now + 300.0
        _CIRCUIT_BREAKER["last_error"] = f"AUTH_ERROR ({status_code})"
        app_logger.error(f"Gemini API authentication failed (HTTP {status_code}). Please verify GEMINI_API_KEY.")
    else:
        _CIRCUIT_BREAKER["last_error"] = error_msg[:100]

def _record_circuit_breaker_success():
    """Records a successful AI call."""
    _CIRCUIT_BREAKER["daily_request_count"] += 1
    _CIRCUIT_BREAKER["last_error"] = None


class GeminiInvoiceExtractor:
    """
    Intelligent document understanding layer backed by Google Gemini Free Tier.
    Takes image bytes or PDF bytes + optional OCR text, and produces structured invoice data.
    """

    def __init__(self):
        self.api_key = settings.gemini_api_key
        raw_m = settings.gemini_model or "gemini-3.1-flash-lite"
        self.model = "gemini-3.1-flash-lite" if "gemini-2.5-flash" in raw_m else raw_m
        self.timeout = float(settings.ai_timeout_seconds or 30)
        self.max_retries = int(settings.ai_max_retries or 2)

    def extract_invoice_intelligence(
        self,
        file_bytes: bytes,
        filename: str,
        ocr_text_context: Optional[str] = None,
        known_company_gstin: Optional[str] = None,
        type_hint: Optional[str] = None
    ) -> Optional[InvoiceDocument]:
        """
        Main entry point for Gemini document understanding.
        Returns InvoiceDocument if successful, or None to fall back to OCR pipeline.
        """
        can_run, reason = _check_circuit_breaker()
        if not can_run:
            app_logger.info(f"Gemini AI bypassed: {reason}")
            return None

        fn_lower = filename.lower()
        mime_type = "application/pdf"
        if fn_lower.endswith(('.jpg', '.jpeg')):
            mime_type = "image/jpeg"
        elif fn_lower.endswith('.png'):
            mime_type = "image/png"
        elif fn_lower.endswith('.webp'):
            mime_type = "image/webp"

        prompt = self._build_prompt(filename, ocr_text_context, known_company_gstin, type_hint)
        raw_json_str = self._call_gemini_api(file_bytes, mime_type, prompt)

        if not raw_json_str:
            return None

        # Parse and validate structured output
        try:
            doc = self._parse_gemini_json_to_document(
                raw_json_str,
                filename=filename,
                known_company_gstin=known_company_gstin,
                type_hint=type_hint,
                ocr_text_context=ocr_text_context
            )
            if doc and doc.items:
                _record_circuit_breaker_success()
                return doc
        except Exception as e:
            app_logger.warning(f"Failed to parse Gemini structured JSON: {str(e)}", exc_info=True)

        return None

    def _build_prompt(
        self,
        filename: str,
        ocr_text: Optional[str],
        known_company_gstin: Optional[str],
        type_hint: Optional[str]
    ) -> str:
        prompt_parts = [
            f"Analyze this Indian GST tax invoice document ('{filename}').",
            "Extract all header fields, parties, line items, taxes, round-off, and totals into strict JSON.",
        ]
        if type_hint:
            prompt_parts.append(f"Expected Voucher/Invoice Type: {type_hint.upper()}.")
        if known_company_gstin:
            prompt_parts.append(f"Our Company GSTIN: {known_company_gstin} (Use this to correctly distinguish Buyer vs Supplier).")

        if ocr_text and len(ocr_text.strip()) > 30:
            prompt_parts.append("\nReference OCR Text Extracted from Document (Use as secondary reference):")
            prompt_parts.append("--- BEGIN OCR TEXT ---")
            prompt_parts.append(ocr_text[:8000])
            prompt_parts.append("--- END OCR TEXT ---")

        prompt_parts.append("""
Return JSON in exactly this schema:
{
  "voucher_type": "Purchase" or "Sales",
  "tax_column_structure": "two_columns" or "single_column",
  "invoice_number": "string or null",
  "invoice_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "place_of_supply": "string or null",
  "po_number": "string or null",
  "supplier": {
    "name": "string",
    "gstin": "string or null",
    "address": "string or null",
    "state": "string or null",
    "pan": "string or null"
  },
  "buyer": {
    "name": "string",
    "gstin": "string or null",
    "address": "string or null",
    "state": "string or null",
    "pan": "string or null"
  },
  "items": [
    {
      "description": "Full original item name including pack/weights/mrp tags",
      "size": "51 ML or null",
      "hsn_sac": "string or null",
      "quantity": 1.0,
      "unit": "CASE/BOX/PCS/etc",
      "total_units": 240.0,
      "total_units_uom": "PCS or null",
      "rate": 150.0,
      "mrp": 200.0 or null,
      "discount": 0.0,
      "taxable_amount": 1500.0,
      "gst_rate": 18.0,
      "cgst_rate": 9.0,
      "cgst_amount": 135.0,
      "sgst_rate": 9.0,
      "sgst_amount": 135.0,
      "igst_rate": 0.0,
      "igst_amount": 0.0,
      "cess_amount": 0.0,
      "total_amount": 1770.0
    }
  ],
  "taxable_total": 1500.0,
  "cgst_total": 135.0,
  "sgst_total": 135.0,
  "igst_total": 0.0,
  "cess_total": 0.0,
  "other_charges": 0.0,
  "round_off": 0.0,
  "grand_total": 1770.0,
  "notes": "string or null"
}
""")
        return "\n".join(prompt_parts)

    def _call_gemini_api(self, file_bytes: bytes, mime_type: str, prompt_text: str) -> Optional[str]:
        """Calls Google Generative Language REST API with retries and timeout."""
        b64_data = base64.b64encode(file_bytes).decode("utf-8")

        if not self.model or "gemini-2.5-flash" in self.model:
            self.model = "gemini-3.1-flash-lite"

        candidate_models = [self.model]
        for m in ("gemini-3.1-flash-lite", "gemini-flash-latest"):
            if m not in candidate_models:
                candidate_models.append(m)

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": b64_data
                            }
                        },
                        {
                            "text": prompt_text
                        }
                    ]
                }
            ],
            "systemInstruction": {
                "parts": [
                    {
                        "text": SYSTEM_INSTRUCTION
                    }
                ]
            },
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }

        headers = {
            "Content-Type": "application/json"
        }

        for model_name in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            for attempt in range(self.max_retries + 1):
                try:
                    with httpx.Client(timeout=self.timeout) as client:
                        resp = client.post(url, json=payload, headers=headers)

                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                self.model = model_name
                                return parts[0].get("text", "")
                        return None

                    elif resp.status_code == 429:
                        app_logger.warning(f"Gemini model '{model_name}' rate limited (429). Attempt {attempt + 1}/{self.max_retries + 1}.")
                        if attempt < self.max_retries:
                            time.sleep(2.0 * (attempt + 1))
                            continue
                        _record_circuit_breaker_failure(429, "Rate limit exceeded (429)")
                        return None

                    elif resp.status_code in (401, 403):
                        _record_circuit_breaker_failure(resp.status_code, "Invalid or unauthorized API key")
                        return None

                    elif resp.status_code == 503:
                        app_logger.warning(f"Gemini model '{model_name}' returned 503 (Overloaded / Service Unavailable). Attempt {attempt + 1}/{self.max_retries + 1}. Retrying with backoff...")
                        if attempt < self.max_retries:
                            time.sleep(2.0 * (attempt + 1))
                            continue
                        break  # Try next candidate model after retries exhausted

                    elif resp.status_code == 404:
                        app_logger.warning(f"Gemini model '{model_name}' returned 404 (Not Found / Deprecated). Trying next candidate model.")
                        break  # Try next candidate model immediately

                    else:
                        app_logger.warning(f"Gemini API returned status {resp.status_code}: {resp.text[:200]}")
                        if attempt < self.max_retries:
                            time.sleep(1.0 * (attempt + 1))
                            continue
                        break

                except httpx.TimeoutException:
                    app_logger.warning(f"Gemini API timed out after {self.timeout}s on '{model_name}'.")
                    if attempt < self.max_retries:
                        time.sleep(1.0)
                        continue
                    break
                except Exception as e:
                    app_logger.warning(f"Gemini API request failed: {str(e)}")
                    if attempt < self.max_retries:
                        time.sleep(1.0)
                        continue
                    break

        return None

    def _parse_gemini_json_to_document(
        self,
        raw_json_str: str,
        filename: str,
        known_company_gstin: Optional[str] = None,
        type_hint: Optional[str] = None,
        ocr_text_context: Optional[str] = None
    ) -> Optional[InvoiceDocument]:
        """Converts validated Gemini JSON to the authoritative InvoiceDocument data model."""
        clean_json = raw_json_str.strip()
        if clean_json.startswith("```"):
            clean_json = re.sub(r"^```(?:json)?", "", clean_json, flags=re.MULTILINE)
            clean_json = re.sub(r"```$", "", clean_json, flags=re.MULTILINE).strip()

        data = json.loads(clean_json)
        if not isinstance(data, dict):
            return None

        # Parse Invoice Date safely
        inv_date = date.today()
        raw_date = data.get("invoice_date")
        if raw_date and isinstance(raw_date, str):
            try:
                # Handle YYYY-MM-DD, DD-MM-YYYY, etc.
                clean_d = re.sub(r"[^\d-]", "-", raw_date)
                parts = [int(p) for p in clean_d.split("-") if p.isdigit()]
                if len(parts) == 3:
                    if parts[0] > 1900:
                        inv_date = date(parts[0], parts[1], parts[2])
                    elif parts[2] > 1900:
                        inv_date = date(parts[2], parts[1], parts[0])
            except Exception:
                pass

        # Supplier & Buyer Parties
        sup_data = data.get("supplier") or {}
        buy_data = data.get("buyer") or {}

        sup_raw_g = sup_data.get("gstin")
        sup_g, sup_rep_g = _clean_and_repair_gstin(sup_raw_g)
        supplier = PartyInfo(
            name=str(sup_data.get("name") or "Unknown Supplier").strip(),
            gstin=sup_g,
            repaired_gstin=sup_rep_g,
            address=sup_data.get("address"),
            state=sup_data.get("state"),
            pan=sup_data.get("pan"),
            mapping_confidence="HIGH" if sup_g and gstin_valid(sup_g) else ("MEDIUM" if sup_g else "LOW")
        )

        buy_raw_g = buy_data.get("gstin")
        buy_g, buy_rep_g = _clean_and_repair_gstin(buy_raw_g)
        buyer = PartyInfo(
            name=str(buy_data.get("name") or "Our Company").strip(),
            gstin=buy_g,
            repaired_gstin=buy_rep_g,
            address=buy_data.get("address"),
            state=buy_data.get("state"),
            pan=buy_data.get("pan"),
            mapping_confidence="HIGH" if buy_g and gstin_valid(buy_g) else ("MEDIUM" if buy_g else "LOW")
        )

        # Voucher / Invoice Type
        inv_type = "PURCHASE"
        v_type_raw = str(data.get("voucher_type") or "").upper()
        if type_hint in ("SALES", "PURCHASE"):
            inv_type = type_hint
        elif "SALE" in v_type_raw:
            inv_type = "SALES"
        elif "PURCHASE" in v_type_raw:
            inv_type = "PURCHASE"
        elif known_company_gstin:
            k = known_company_gstin.upper()
            if supplier.gstin and supplier.gstin.upper() == k:
                inv_type = "SALES"
            elif buyer.gstin and buyer.gstin.upper() == k:
                inv_type = "PURCHASE"

        # Line Items
        raw_items = data.get("items") or []
        items: List[InvoiceItem] = []

        for idx, it_data in enumerate(raw_items):
            desc = str(it_data.get("description") or f"Item {idx + 1}").strip()
            if not desc or desc.lower() in ("total", "sub total", "grand total", "round off"):
                continue

            # 1. Primary Quantity & Unit
            qty = to_decimal(it_data.get("quantity"), "1.00")
            uom = str(it_data.get("unit") or "NOS").strip().upper()

            # 2. Total Units / Secondary Quantity (from explicit invoice column)
            raw_tot_units = it_data.get("total_units")
            if raw_tot_units is None or str(raw_tot_units).strip() in ("", "null", "None"):
                raw_tot_units = it_data.get("secondary_quantity")
            tot_units = to_decimal(raw_tot_units) if (raw_tot_units is not None and str(raw_tot_units).strip() not in ("", "null", "None")) else None

            raw_tot_uom = it_data.get("total_units_uom") or it_data.get("secondary_unit")
            tot_units_uom = str(raw_tot_uom).strip().upper() if (raw_tot_uom and str(raw_tot_uom).strip() not in ("", "null", "None")) else None

            # 2b. Item Size / Weight (dedicated column e.g. 51 ML, 75 GM)
            raw_size = it_data.get("size") or it_data.get("pack_size") or it_data.get("item_size")
            clean_size = str(raw_size).strip() if (raw_size and str(raw_size).strip() not in ("", "null", "None")) else None

            rate = to_decimal(it_data.get("rate"), "0.00")
            taxable = to_decimal(it_data.get("taxable_amount"), "0.00")
            mrp = to_decimal(it_data.get("mrp"), "0.00") if it_data.get("mrp") else None
            disc = to_decimal(it_data.get("discount") or it_data.get("discount_amount"), "0.00")

            gross = (qty * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if (qty > Decimal("0.00") and rate > Decimal("0.00")) else (taxable + disc)

            if taxable == Decimal("0.00") and qty > Decimal("0.00") and rate > Decimal("0.00"):
                taxable = max(Decimal("0.00"), (gross - disc).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            elif taxable > Decimal("0.00") and disc > Decimal("0.00"):
                # If model mistakenly reported gross amount as taxable amount
                if abs(taxable - gross) <= Decimal("0.10") and abs(gross - disc - taxable) > Decimal("0.10"):
                    taxable = max(Decimal("0.00"), (gross - disc).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

            # Recover rate ONLY when rate is completely missing/zero and taxable > 0 and qty > 0
            if rate <= Decimal("0.00") and taxable > Decimal("0.00") and qty > Decimal("0.00"):
                rate = ((taxable + disc) / qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            # --- GENERIC PACK MULTIPLIER DETECTION ---
            pack_mult_val = None
            pack_mult_res = detect_pack_multiplier(desc)
            if pack_mult_res and pack_mult_res.multiplier:
                pack_mult_val = pack_mult_res.multiplier

            # --- GST RATE RESOLUTION & STRUCTURE-AWARE DOUBLING LOGIC ---
            tax_struct = str(data.get("tax_column_structure") or "").lower().strip()
            raw_comb_gst = it_data.get("gst_rate")
            comb_gst = to_decimal(raw_comb_gst) if raw_comb_gst is not None else None

            cgst_r = to_decimal(it_data.get("cgst_rate"), "0.00")
            cgst_a = to_decimal(it_data.get("cgst_amount"), "0.00")
            sgst_r = to_decimal(it_data.get("sgst_rate"), "0.00")
            sgst_a = to_decimal(it_data.get("sgst_amount"), "0.00")
            igst_r = to_decimal(it_data.get("igst_rate"), "0.00")
            igst_a = to_decimal(it_data.get("igst_amount"), "0.00")

            is_interstate = (supplier.state and buyer.state and supplier.state != buyer.state) or igst_r > Decimal("0.00") or igst_a > Decimal("0.00")

            # Determine whether invoice has a single GST rate column or two separate component columns
            is_single_col = False
            if tax_struct == "single_column":
                is_single_col = True
            elif cgst_r == Decimal("0.00") and sgst_r == Decimal("0.00") and igst_r == Decimal("0.00") and comb_gst is not None and comb_gst > Decimal("0.00"):
                is_single_col = True
            elif comb_gst is not None and comb_gst > Decimal("0.00") and cgst_r == comb_gst and sgst_r == comb_gst:
                # Model extracted single rate e.g. 18% and mistakenly duplicated it into both CGST and SGST
                is_single_col = True
            elif (cgst_r in (Decimal("5.00"), Decimal("12.00"), Decimal("18.00"), Decimal("28.00"), Decimal("40.00")) 
                  and cgst_r == sgst_r and comb_gst is None and tax_struct != "two_columns"):
                # Disambiguation: check tax amount vs taxable to verify if cgst_r is total rate or component
                if taxable > Decimal("0.00") and cgst_a > Decimal("0.00"):
                    expected_half_tax = (taxable * (cgst_r / Decimal("2.00")) / Decimal("100.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    if abs(cgst_a - expected_half_tax) <= Decimal("0.50"):
                        is_single_col = True
                    elif sgst_a > Decimal("0.00"):
                        expected_full_tax = (taxable * cgst_r / Decimal("100.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        if abs((cgst_a + sgst_a) - expected_full_tax) <= Decimal("0.50"):
                            is_single_col = True

            if is_single_col:
                # SINGLE GST/TAX COLUMN: DO NOT DOUBLE IT!
                # Total GST rate is kept exactly as printed (e.g. 5%, 12%, 18%, 28%, 40%)
                single_rate = comb_gst if (comb_gst is not None and comb_gst > Decimal("0.00")) else (cgst_r if cgst_r > Decimal("0.00") else igst_r)
                if is_interstate:
                    igst_r = single_rate
                    cgst_r = Decimal("0.00")
                    sgst_r = Decimal("0.00")
                    if igst_a == Decimal("0.00") and taxable > Decimal("0.00"):
                        igst_a = (taxable * igst_r / Decimal("100.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                else:
                    # Intra-state: split the single rate into half CGST and half SGST
                    cgst_r = (single_rate / Decimal("2.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    sgst_r = single_rate - cgst_r
                    igst_r = Decimal("0.00")
                    if taxable > Decimal("0.00"):
                        expected_cgst_a = (taxable * cgst_r / Decimal("100.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        expected_sgst_a = (taxable * sgst_r / Decimal("100.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        if cgst_a == Decimal("0.00") or abs(cgst_a - expected_cgst_a * Decimal("2.00")) <= Decimal("0.10"):
                            cgst_a = expected_cgst_a
                        if sgst_a == Decimal("0.00") or abs(sgst_a - expected_sgst_a * Decimal("2.00")) <= Decimal("0.10"):
                            sgst_a = expected_sgst_a
                tot_gst_r = single_rate
            else:
                # TWO SEPARATE TAX/GST COLUMNS (Component columns e.g. CGST + SGST):
                # The rate in one component column is doubled / combined:
                # 2.50% + 2.50% -> 5%, 6% + 6% -> 12%, 9% + 9% -> 18%, 14% + 14% -> 28%, 20% + 20% -> 40%
                if cgst_r > Decimal("0.00") and sgst_r == Decimal("0.00") and not is_interstate:
                    sgst_r = cgst_r
                elif sgst_r > Decimal("0.00") and cgst_r == Decimal("0.00") and not is_interstate:
                    cgst_r = sgst_r

                if cgst_a == Decimal("0.00") and taxable > Decimal("0.00") and cgst_r > Decimal("0.00"):
                    cgst_a = (taxable * cgst_r / Decimal("100.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if sgst_a == Decimal("0.00") and taxable > Decimal("0.00") and sgst_r > Decimal("0.00"):
                    sgst_a = (taxable * sgst_r / Decimal("100.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if igst_a == Decimal("0.00") and taxable > Decimal("0.00") and igst_r > Decimal("0.00"):
                    igst_a = (taxable * igst_r / Decimal("100.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                tot_gst_r = igst_r if igst_r > Decimal("0.00") else (cgst_r + sgst_r)

            tot_amt = to_decimal(it_data.get("total_amount"), "0.00")
            if tot_amt == Decimal("0.00"):
                tot_amt = taxable + cgst_a + sgst_a + igst_a

            # --- DUAL QUANTITY HANDLING (PRD Rules 1 - 10) ---
            has_dual = False
            qty_a = qty
            uom_a = uom
            rate_a = rate
            qty_b = None
            uom_b = None
            rate_b = None
            selected_opt = None
            alt_qty = None
            alt_uom = None

            if (
                tot_units is not None 
                and tot_units > Decimal("0.00") 
                and qty > Decimal("0.00") 
                and tot_units != qty
            ):
                # Genuine two different quantity columns present on the invoice!
                has_dual = True

                is_tot_units_outer = tot_units_uom in ("CASE", "CASES", "BOX", "BOXES", "CTN", "CARTON", "CARTONS", "BAG", "BAGS", "CS", "BX")
                is_qty_outer = uom in ("CASE", "CASES", "BOX", "BOXES", "CTN", "CARTON", "CARTONS", "BAG", "BAGS", "CS", "BX")

                if is_tot_units_outer and not is_qty_outer:
                    # Model placed outer container in tot_units and piece count in qty
                    qty_a = tot_units
                    uom_a = tot_units_uom
                    qty_b = qty
                    uom_b = uom
                else:
                    qty_a = qty
                    uom_a = uom
                    qty_b = tot_units
                    uom_b = tot_units_uom or ("PCS" if is_qty_outer else "UNITS")

                # Recalculate or preserve rates for Option A and Option B:
                if abs(qty_a * rate - (taxable + disc)) <= Decimal("0.10"):
                    rate_a = rate
                else:
                    rate_a = ((taxable + disc) / qty_a).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if qty_a > Decimal("0.00") else Decimal("0.00")

                if abs(qty_b * rate - (taxable + disc)) <= Decimal("0.10"):
                    rate_b = rate
                else:
                    rate_b = ((taxable + disc) / qty_b).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if qty_b > Decimal("0.00") else Decimal("0.00")

                selected_opt = "A"
                alt_qty = qty_b
                alt_uom = uom_b

                # Primary item fields default to Option A
                qty = qty_a
                uom = uom_a
                rate = rate_a
            else:
                has_dual = False
                tot_units = None
                tot_units_uom = None

            effective_desc = merge_size_into_item_name(desc, clean_size or pack_size_from_description(desc))

            item_obj = InvoiceItem(
                item_index=len(items) + 1,
                item_name=effective_desc,
                description=effective_desc,
                hsn_sac=str(it_data.get("hsn_sac") or "") if it_data.get("hsn_sac") else None,
                quantity=qty,
                uom=uom,
                secondary_quantity=qty_b if has_dual else None,
                secondary_unit=uom_b if has_dual else None,
                rate=rate,
                mrp=mrp,
                discount=disc,
                discount_amount=disc,
                taxable_amount=taxable,
                gross_amount=gross,
                gst_rate=tot_gst_r,
                cgst_rate=cgst_r,
                cgst_amount=cgst_a,
                sgst_rate=sgst_r,
                sgst_amount=sgst_a,
                igst_rate=igst_r,
                igst_amount=igst_a,
                total_amount=tot_amt,
                pack_size=clean_size or pack_size_from_description(desc),
                item_size=clean_size or pack_size_from_description(desc),
                confidence_level="HIGH",
                quantity_option_a=qty_a if has_dual else None,
                uom_option_a=uom_a if has_dual else None,
                rate_option_a=rate_a if has_dual else None,
                quantity_option_b=qty_b if has_dual else None,
                uom_option_b=uom_b if has_dual else None,
                rate_option_b=rate_b if has_dual else None,
                selected_qty_option=selected_opt,
                has_dual_qty=has_dual,
                alternate_quantity=alt_qty,
                alternate_uom=alt_uom,
                pack_multiplier=pack_mult_val,
                invoice_qty=qty if pack_mult_val else None,
                effective_qty=(qty * pack_mult_val).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP) if pack_mult_val else None
            )
            items.append(item_obj)

        if not items:
            return None

        # Document Totals
        taxable_total = to_decimal(data.get("taxable_total"), str(sum(it.taxable_amount for it in items)))
        cgst_total = to_decimal(data.get("cgst_total"), str(sum(it.cgst_amount for it in items)))
        sgst_total = to_decimal(data.get("sgst_total"), str(sum(it.sgst_amount for it in items)))
        igst_total = to_decimal(data.get("igst_total"), str(sum(it.igst_amount for it in items)))
        cess_total = to_decimal(data.get("cess_total"), "0.00")
        other_charges = to_decimal(data.get("other_charges"), "0.00")
        round_off = to_decimal(data.get("round_off"), "0.00")

        expected_grand = taxable_total + cgst_total + sgst_total + igst_total + cess_total + other_charges + round_off
        grand_total = to_decimal(data.get("grand_total"), str(expected_grand))

        # Check round-off derivation if grand_total provided directly
        if round_off == Decimal("0.00") and abs(grand_total - expected_grand) <= Decimal("1.00") and grand_total != expected_grand:
            round_off = grand_total - expected_grand

        # Check for page continuation indicators in text or notes (PRD Section 14)
        has_cont = False
        cont_note = None
        notes_str = str(data.get("notes") or "").lower()
        ocr_str = (ocr_text_context or "").lower()
        if "continued to page" in notes_str or "continued to page" in ocr_str or "continue to page" in ocr_str:
            has_cont = True
            cont_note = "Document continued to page number 2"
        elif data.get("has_page_continuation") is True:
            has_cont = True
            cont_note = "Document continued to next page"

        warnings_list = []
        if has_cont:
            warnings_list.append("Document continues to page 2 (multi-page invoice detected).")

        if getattr(settings, "enable_prd_invoice_ocr_v2", True):
            from app.invoices.prd_engine import (
                apply_prd_quantity_rules,
                resolve_prd_gst_rates,
                reconcile_invoice_document,
                resolve_sales_vs_purchase
            )
            for it in items:
                apply_prd_quantity_rules(it)
                resolve_prd_gst_rates(it, is_interstate=is_interstate, single_column_mode=is_single_col)

            vch_type, _ = resolve_sales_vs_purchase(supplier, buyer, known_company_gstin)
            if type_hint in ("SALES", "PURCHASE"):
                inv_type = type_hint
            elif vch_type:
                inv_type = vch_type

        doc = InvoiceDocument(
            invoice_number=str(data.get("invoice_number") or "").strip(),
            invoice_date=inv_date,
            invoice_type=inv_type,
            place_of_supply=data.get("place_of_supply"),
            po_number=data.get("po_number"),
            voucher_type=data.get("voucher_type"),
            supplier=supplier,
            buyer=buyer,
            items=items,
            items_detected_count=len(items),
            taxable_total=taxable_total,
            cgst_total=cgst_total,
            sgst_total=sgst_total,
            igst_total=igst_total,
            cess_total=cess_total,
            other_charges=other_charges,
            round_off=round_off,
            grand_total=grand_total,
            has_page_continuation=has_cont,
            continuation_note=cont_note,
            warnings=warnings_list,
            source_filename=filename,
            ai_extracted=True,
            ai_model_used=self.model,
            ai_status_message=f"Intelligently extracted with Google {self.model}",
            confidence_level="HIGH"
        )

        if getattr(settings, "enable_prd_invoice_ocr_v2", True):
            from app.invoices.prd_engine import reconcile_invoice_document
            reconcile_invoice_document(doc, full_text=ocr_text_context)

        return doc


# Global singleton instance
global_gemini_extractor = GeminiInvoiceExtractor()
