import os
import sys
import json
import logging
from decimal import Decimal
import xml.etree.ElementTree as ET

# Configure UTF-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure backend path
sys.path.insert(0, os.path.abspath("backend"))

# Silence noisy HTTP logs
logging.getLogger("httpx").setLevel(logging.WARNING)

from app.gemini.extractor import GeminiExtractor, _get_api_key
from app.pdf.validator import validate_image_file
from app.transactions.validator import validate_statement_balances
from app.tally.xml_generator import TallyXMLGenerator
from app.tally.xml_validator import validate_tally_xml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jpg_verifier")

def run_jpg_sample_tests():
    sample_dir = "JPG BANK STATEMENT SAMPLES"
    files = sorted([f for f in os.listdir(sample_dir) if f.lower().endswith(('.jpg', '.jpeg'))])
    
    print(f"============================================================")
    print(f"VERIFYING {len(files)} JPG BANK STATEMENT SAMPLES WITH GEMINI VISION")
    print(f"============================================================")
    
    generator = TallyXMLGenerator()
    results = []
    
    for fn in files:
        file_path = os.path.join(sample_dir, fn)
        file_size_kb = os.path.getsize(file_path) / 1024
        print(f"\n--> Testing file: {fn} ({file_size_kb:.1f} KB)...")
        
        # 1. Validation check
        try:
            w, h = validate_image_file(file_path)
            print(f"    Image dimensions: {w}x{h} (VALID)")
        except Exception as e:
            print(f"    Validation FAILED: {e}")
            results.append({"file": fn, "error": f"Validation failed: {e}", "status": "FAILED"})
            continue
            
        with open(file_path, "rb") as f:
            content = f.read()
            
        # 2. Gemini Multimodal Extraction
        try:
            stmt = GeminiExtractor.extract_from_image_bytes(content, mime_type="image/jpeg")
            if not stmt or len(stmt.transactions) == 0:
                print(f"    Gemini Extraction returned 0 transactions!")
                results.append({"file": fn, "error": "Zero transactions returned", "status": "FAILED"})
                continue
                
            tx_count = len(stmt.transactions)
            total_dr = sum(tx.debit for tx in stmt.transactions)
            total_cr = sum(tx.credit for tx in stmt.transactions)
            print(f"    Gemini Extracted: {tx_count} transactions | Dr: INR {total_dr:,.2f} | Cr: INR {total_cr:,.2f}")
            
            # 3. Balance Audit
            validated_stmt = validate_statement_balances(stmt)
            valid_count = sum(1 for tx in validated_stmt.transactions if getattr(tx, "validation_status", "VALID") == "VALID")
            warn_count = sum(1 for tx in validated_stmt.transactions if getattr(tx, "validation_status", "VALID") == "WARNING")
            err_count = sum(1 for tx in validated_stmt.transactions if getattr(tx, "validation_status", "VALID") == "ERROR")
            print(f"    Balance Audit: {valid_count} VALID, {warn_count} WARNING, {err_count} ERROR")
            
            # 4. Tally XML Generation & Validation
            xml_str = generator.generate_xml(
                validated_stmt,
                bank_ledger_name="Bank Account",
                cash_ledger_name="Cash"
            )
            
            is_valid, errors = validate_tally_xml(xml_str)
            root = ET.fromstring(xml_str)
            voucher_count = len(root.findall(".//VOUCHER"))
            print(f"    Tally XML: Valid={is_valid}, Vouchers={voucher_count}, Errors={errors}")
            
            results.append({
                "file": fn,
                "dimensions": f"{w}x{h}",
                "size_kb": round(file_size_kb, 1),
                "bank": stmt.bank or "Detected Bank",
                "tx_count": tx_count,
                "total_dr": str(total_dr),
                "total_cr": str(total_cr),
                "balance_status": f"{valid_count} Valid, {warn_count} Warn, {err_count} Err",
                "xml_vouchers": voucher_count,
                "xml_valid": is_valid,
                "errors": errors,
                "status": "SUCCESS" if is_valid else "XML_INVALID"
            })
            
        except Exception as e:
            print(f"    Pipeline FAILED: {e}")
            results.append({"file": fn, "error": str(e), "status": "FAILED"})
            
    out_json = "backend/jpg_sample_verification_report.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        
    print(f"\n============================================================")
    print(f"REPORT SAVED TO {out_json}")
    print(f"============================================================")

if __name__ == "__main__":
    run_jpg_sample_tests()
