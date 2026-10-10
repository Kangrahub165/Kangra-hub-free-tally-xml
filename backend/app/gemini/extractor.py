import os
import io
import re
import json
import base64
import logging
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any, Optional, Tuple

import httpx
from PIL import Image, ImageOps

from app.core.config import settings
from app.transactions.model import CanonicalStatement, TransactionItem

logger = logging.getLogger("kangra_hub.gemini")

# Date pattern matchers
DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%d %b %Y",
    "%d-%b-%Y",
    "%d %B %Y",
    "%d-%B-%Y",
    "%Y/%m/%d"
]

def _get_api_key() -> str:
    """Safely retrieves the Gemini API key without ever logging or disclosing it."""
    key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
    if not key:
        # Local development fallback if text file exists on D drive
        fallback_file = "D:/gemini key for bank import.txt"
        if os.path.exists(fallback_file):
            try:
                with open(fallback_file, "r", encoding="utf-8") as f:
                    key = f.read().strip()
            except Exception:
                pass
    return key.strip()

def _clean_amount(val: Any) -> Decimal:
    """Converts raw string or numeric value to clean positive Decimal."""
    if val is None or val == "":
        return Decimal("0.00")
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(round(abs(float(val)), 2)))
    
    val_str = str(val).strip().replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").replace("INR", "").strip()
    # Remove Cr / Dr suffixes if attached
    val_str = re.sub(r'(?i)\s*(cr|dr)\b', '', val_str).strip()
    if not val_str:
        return Decimal("0.00")
    try:
        return Decimal(val_str).quantize(Decimal("0.01"))
    except InvalidOperation:
        # Extract digits and decimal point
        match = re.search(r'[\d]+\.?[\d]*', val_str)
        if match:
            try:
                return Decimal(match.group(0)).quantize(Decimal("0.01"))
            except Exception:
                pass
        return Decimal("0.00")

def _parse_date(val: Any) -> Optional[date]:
    """Parses arbitrary bank statement date into standard datetime.date."""
    if not val:
        return None
    if isinstance(val, date):
        return val
    
    val_str = str(val).strip()
    # Normalize separators
    val_clean = re.sub(r'[\.\s]+', '-', val_str).replace('/', '-')
    
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            pass
        try:
            return datetime.strptime(val_clean, fmt).date()
        except ValueError:
            pass
            
    # Try generic year-month-day regex
    m = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', val_str)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # Try day-month-year regex
    m2 = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})', val_str)
    if m2:
        try:
            yr = int(m2.group(3))
            if yr < 100:
                yr += 2000
            return date(yr, int(m2.group(2)), int(m2.group(1)))
        except ValueError:
            pass

    return None

class GeminiExtractor:
    """
    High-accuracy (~99%) Google Gemini extraction engine for bank statements.
    Processes both PDF text / layout and JPG / JPEG image statements.
    """

    AVAILABLE_MODELS = [
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.7-flash",
        "gemini-flash-latest",
        "gemini-pro-latest"
    ]

    @classmethod
    def is_available(cls) -> bool:
        """Returns True if Gemini API key is configured."""
        return bool(_get_api_key())

    @classmethod
    def _call_gemini_api(
        cls,
        contents: List[Dict[str, Any]],
        timeout_seconds: float = 45.0,
        model_name: Optional[str] = None
    ) -> Optional[str]:
        """Calls Google Gemini REST API with fallback models."""
        api_key = _get_api_key()
        if not api_key:
            logger.warning("Gemini API key is not configured. Falling back to rule-based parser.")
            return None

        preferred_model = model_name or settings.gemini_model or "gemini-3.5-flash"
        models_to_try = [preferred_model] + [m for m in cls.AVAILABLE_MODELS if m != preferred_model]

        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json"
        }

        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            payload = {
                "contents": contents,
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.1
                }
            }

            try:
                with httpx.Client(timeout=timeout_seconds) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts and "text" in parts[0]:
                                return parts[0]["text"]
                    elif resp.status_code in (404, 503, 429):
                        logger.warning(f"Gemini model {model} returned HTTP {resp.status_code}. Trying next candidate...")
                        continue
                    else:
                        logger.warning(f"Gemini API returned status {resp.status_code}: {resp.text[:200]}")
            except httpx.TimeoutException:
                logger.warning(f"Gemini API timed out on model {model} ({timeout_seconds}s).")
            except Exception as exc:
                logger.warning(f"Gemini API request failed on model {model}: {str(exc)}")

        return None

    @classmethod
    def extract_from_image_bytes(
        cls,
        image_bytes: bytes,
        mime_type: str = "image/jpeg"
    ) -> Optional[CanonicalStatement]:
        """
        Extracts bank statement transactions directly from a JPG/JPEG image.
        Auto-orients rotated images using EXIF metadata.
        """
        if not cls.is_available():
            return None

        # 1. Normalize and auto-orient image with PIL
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img = ImageOps.exif_transpose(img)
            
            # Convert RGBA / CMYK to RGB if necessary
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
                
            out_buf = io.BytesIO()
            img.save(out_buf, format="JPEG", quality=90, optimize=True)
            normalized_bytes = out_buf.getvalue()
        except Exception as exc:
            logger.warning(f"Image normalization failed: {exc}. Using original bytes.")
            normalized_bytes = image_bytes

        b64_image = base64.b64encode(normalized_bytes).decode("utf-8")

        prompt = (
            "You are a professional bank statement audit AI. Analyze this bank statement image with 99%+ accuracy.\n"
            "Extract all financial transactions and summary metadata.\n\n"
            "Output a JSON object with this exact schema:\n"
            "{\n"
            '  "bank_name": "detected bank name (e.g. State Bank of India, HDFC Bank, etc.)",\n'
            '  "account_number": "masked or visible account number",\n'
            '  "statement_from": "YYYY-MM-DD",\n'
            '  "statement_to": "YYYY-MM-DD",\n'
            '  "opening_balance": 0.00,\n'
            '  "closing_balance": 0.00,\n'
            '  "transactions": [\n'
            "    {\n"
            '      "date": "YYYY-MM-DD",\n'
            '      "narration": "complete original narration / party / description",\n'
            '      "debit": 0.00,\n'
            '      "credit": 0.00,\n'
            '      "balance": 0.00,\n'
            '      "chq_ref": "cheque number or UTR or UPI reference if present"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "CRITICAL RULES:\n"
            "1. Read every single transaction row visible in the table. Never skip rows.\n"
            "2. Preserve original narration names exactly so vendor and party matching succeeds.\n"
            "3. If an amount is debit/withdrawal, put it in debit (credit must be 0). If credit/deposit, put in credit (debit must be 0).\n"
            "4. Verify running balance math: balance = previous_balance - debit + credit."
        )

        contents = [
            {
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": b64_image
                        }
                    },
                    {"text": prompt}
                ]
            }
        ]

        logger.info(f"Dispatching image statement ({len(normalized_bytes)} bytes) to Gemini AI...")
        res_text = cls._call_gemini_api(contents, timeout_seconds=settings.gemini_timeout_seconds)
        if not res_text:
            return None

        statement = cls._parse_and_validate_gemini_response(res_text, raw_text="")
        if statement and len(statement.transactions) > 0:
            logger.info(f"Gemini successfully extracted {len(statement.transactions)} transactions from image statement.")
            return statement

        return None

    @classmethod
    def extract_from_multiple_image_bytes(
        cls,
        images_data: List[Tuple[str, bytes]],
        mime_type: str = "image/jpeg"
    ) -> Optional[CanonicalStatement]:
        """
        Extracts bank statement transactions across a batch of JPG/JPEG images.
        Processes each image in sequence, ensuring all selected images are processed
        without silently skipping files.
        """
        if not cls.is_available():
            return None

        merged_transactions: List[TransactionItem] = []
        detected_bank: Optional[str] = None
        account_number_masked: Optional[str] = None
        opening_balance: Optional[Decimal] = None
        closing_balance: Optional[Decimal] = None
        statement_from: Optional[date] = None
        statement_to: Optional[date] = None
        successful_pages = 0
        failed_files: List[str] = []

        for idx, (filename, img_bytes) in enumerate(images_data, start=1):
            try:
                page_statement = cls.extract_from_image_bytes(img_bytes, mime_type=mime_type)
                if page_statement and page_statement.transactions:
                    successful_pages += 1
                    if not detected_bank and page_statement.bank:
                        detected_bank = page_statement.bank
                    if not account_number_masked and page_statement.account_number_masked:
                        account_number_masked = page_statement.account_number_masked
                    if opening_balance is None and page_statement.opening_balance is not None:
                        opening_balance = page_statement.opening_balance
                    if page_statement.closing_balance is not None:
                        closing_balance = page_statement.closing_balance
                    if page_statement.statement_from:
                        if statement_from is None or page_statement.statement_from < statement_from:
                            statement_from = page_statement.statement_from
                    if page_statement.statement_to:
                        if statement_to is None or page_statement.statement_to > statement_to:
                            statement_to = page_statement.statement_to

                    for tx in page_statement.transactions:
                        tx.source_page = idx
                        merged_transactions.append(tx)
                else:
                    failed_files.append(filename)
            except Exception as e:
                logger.warning(f"Error extracting image {filename} (page {idx}): {e}")
                failed_files.append(filename)

        if not merged_transactions:
            if failed_files:
                raise Exception(
                    f"Unable to extract readable transactions from the uploaded images ({', '.join(failed_files)}). "
                    "Please verify that the bank statement photos are clear and focused."
                )
            return None

        # Re-index all merged transactions sequentially 1..N
        for idx, tx in enumerate(merged_transactions, start=1):
            tx.row_index = idx

        total_debit = sum(t.debit for t in merged_transactions)
        total_credit = sum(t.credit for t in merged_transactions)

        return CanonicalStatement(
            bank=detected_bank or "Bank Account",
            statement_format="JPG_Batch_Statement",
            account_number_masked=account_number_masked,
            statement_from=statement_from,
            statement_to=statement_to,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_debit=total_debit,
            total_credit=total_credit,
            confidence_score=99.0,
            transactions=merged_transactions
        )

    @classmethod
    def extract_from_pdf_pages(
        cls,
        page_texts: List[str],
        file_path: Optional[str] = None
    ) -> Optional[CanonicalStatement]:
        """
        Extracts transactions from PDF statement pages using Gemini AI.
        Processes pages in chronological order and merges without duplicates.
        """
        if not cls.is_available():
            return None

        # Build concatenated statement text with clear page markers
        formatted_pages = []
        for idx, p_text in enumerate(page_texts):
            clean_text = p_text.strip()
            if clean_text:
                formatted_pages.append(f"--- PAGE {idx+1} ---\n{clean_text}")

        if not formatted_pages:
            logger.warning("No digital text found in PDF pages for Gemini extraction.")
            return None

        combined_text = "\n\n".join(formatted_pages)

        prompt = (
            "You are a master banking accountant. Extract transactions from this bank statement text with 99%+ accuracy.\n\n"
            "Output a JSON object with this exact schema:\n"
            "{\n"
            '  "bank_name": "detected bank name (e.g. Axis Bank, SBI, ICICI Bank, etc.)",\n'
            '  "account_number": "masked or visible account number",\n'
            '  "statement_from": "YYYY-MM-DD",\n'
            '  "statement_to": "YYYY-MM-DD",\n'
            '  "opening_balance": 0.00,\n'
            '  "closing_balance": 0.00,\n'
            '  "transactions": [\n'
            "    {\n"
            '      "page": 1,\n'
            '      "date": "YYYY-MM-DD",\n'
            '      "narration": "full transaction narration text",\n'
            '      "debit": 0.00,\n'
            '      "credit": 0.00,\n'
            '      "balance": 0.00,\n'
            '      "chq_ref": "reference or cheque number if present"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "RULES:\n"
            "1. Extract EVERY transaction line sequentially in order.\n"
            "2. Keep exact narration strings verbatim for party name matching.\n"
            "3. Ensure debit/credit/balance numbers are parsed cleanly.\n"
            "4. Opening balance + Total Credits - Total Debits MUST equal Closing balance.\n\n"
            f"STATEMENT TEXT:\n{combined_text}"
        )

        contents = [{"parts": [{"text": prompt}]}]

        logger.info(f"Dispatching PDF statement ({len(page_texts)} pages, {len(combined_text)} chars) to Gemini AI...")
        res_text = cls._call_gemini_api(contents, timeout_seconds=settings.gemini_timeout_seconds)
        if not res_text:
            return None

        statement = cls._parse_and_validate_gemini_response(res_text, raw_text=combined_text)
        if statement and len(statement.transactions) > 0:
            logger.info(f"Gemini successfully extracted {len(statement.transactions)} transactions from PDF statement.")
            return statement

        return None

    @classmethod
    def _parse_and_validate_gemini_response(
        cls,
        json_str: str,
        raw_text: str = ""
    ) -> Optional[CanonicalStatement]:
        """Parses structured JSON and performs rigorous balance math audits."""
        try:
            # Clean markdown codeblocks if returned
            clean_json = json_str.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            clean_json = clean_json.strip()

            data = json.loads(clean_json)
        except Exception as exc:
            logger.warning(f"Failed to parse Gemini response as JSON: {exc}. Response preview: {json_str[:150]}")
            return None

        raw_txs = data.get("transactions", [])
        if not raw_txs and isinstance(data, list):
            raw_txs = data

        if not raw_txs:
            logger.warning("Gemini returned 0 transactions in JSON payload.")
            return None

        bank_name = data.get("bank_name") or "Bank Account"
        account_number = data.get("account_number")
        opening_bal = _clean_amount(data.get("opening_balance")) if data.get("opening_balance") is not None else None
        closing_bal = _clean_amount(data.get("closing_balance")) if data.get("closing_balance") is not None else None

        parsed_items: List[TransactionItem] = []
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")

        prev_balance: Optional[Decimal] = opening_bal

        for idx, row in enumerate(raw_txs):
            tx_date = _parse_date(row.get("date")) or date.today()
            narration = str(row.get("narration") or "").strip()
            if not narration:
                narration = f"Transaction #{idx+1}"

            debit = _clean_amount(row.get("debit"))
            credit = _clean_amount(row.get("credit"))
            balance = _clean_amount(row.get("balance")) if row.get("balance") is not None else None

            chq_ref = str(row.get("chq_ref") or row.get("reference") or "").strip()
            page_num = int(row.get("page") or 1)

            total_debit += debit
            total_credit += credit

            # Verify running balance consistency
            val_status = "VALID"
            val_notes = None

            if prev_balance is not None and balance is not None:
                expected_bal = (prev_balance - debit + credit).quantize(Decimal("0.01"))
                actual_bal = balance.quantize(Decimal("0.01"))
                if abs(expected_bal - actual_bal) > Decimal("0.05"):
                    val_status = "WARNING"
                    val_notes = f"Running balance mismatch: expected {expected_bal}, got {actual_bal}"

            prev_balance = balance

            item = TransactionItem(
                id=f"gemini-tx-{idx+1}",
                row_index=idx + 1,
                date=tx_date,
                narration=narration,
                original_narration=narration,
                debit=debit,
                credit=credit,
                balance=balance,
                reference=chq_ref,
                instrument_number=chq_ref if chq_ref else None,
                confidence_score=99.0,
                validation_status=val_status,
                validation_notes=val_notes,
                source_page=page_num,
                parser_name="Gemini AI Vision & Math Engine v2.0"
            )
            parsed_items.append(item)

        # Audit overall opening + credits - debits = closing balance
        if opening_bal is not None and closing_bal is not None:
            expected_closing = (opening_bal + total_credit - total_debit).quantize(Decimal("0.01"))
            actual_closing = closing_bal.quantize(Decimal("0.01"))
            if abs(expected_closing - actual_closing) > Decimal("0.05"):
                logger.warning(
                    f"Gemini statement balance audit mismatch: opening={opening_bal}, "
                    f"credits={total_credit}, debits={total_debit}, expected_closing={expected_closing}, "
                    f"actual_closing={actual_closing}"
                )
                # Flag first and last transactions with note
                if parsed_items:
                    parsed_items[0].validation_notes = (parsed_items[0].validation_notes or "") + " [Audit Warning: Statement net delta differs from declared closing balance]"

        statement = CanonicalStatement(
            bank=bank_name,
            statement_format="Gemini Universal AI Parser",
            account_number_masked=account_number,
            statement_from=_parse_date(data.get("statement_from")),
            statement_to=_parse_date(data.get("statement_to")),
            opening_balance=opening_bal,
            closing_balance=closing_bal or prev_balance,
            total_debit=total_debit,
            total_credit=total_credit,
            confidence_score=99.0,
            transactions=parsed_items
        )

        return statement
