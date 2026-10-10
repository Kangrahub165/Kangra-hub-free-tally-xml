import os
import sys
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from decimal import Decimal

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.pdf.extractor import extract_pdf_data
from app.detector.bank_detector import detect_bank_from_document
from app.parsers.registry import parser_registry
from app.accounting.mapper import LedgerMapper
from app.accounting.voucher_classifier import classify_voucher_type
from app.transactions.validator import validate_statement_balances
from app.transactions.snapshot import FinalConversionSnapshot
from app.tally.xml_generator import TallyXMLGenerator

SAMPLE_DIR = Path("D:/KANGRA HUB BANK STATEMENT RECOVERY/Sample pdf")

SAMPLE_FILES = [
    "axis-bank.pdf",
    "HDFC BANK.pdf",
    "icici-bank.pdf",
    "kangra co operative bank.pdf",
    "paypal.pdf",
    "PNB.pdf",
    "SBI-2.pdf",
    "SBI.pdf",
    "the-co-operative-bank.pdf",
    "uco-bank-2.pdf",
    "UCO BANK.pdf",
    "union-bank-of-india.pdf"
]

def verify_sample(filename: str) -> dict:
    file_path = SAMPLE_DIR / filename
    if not file_path.exists():
        return {"filename": filename, "error": "FILE_NOT_FOUND"}

    result = {
        "filename": filename,
        "page_count": 0,
        "bank_detected": None,
        "parser_used": None,
        "txn_count": 0,
        "total_debit": "0.00",
        "total_credit": "0.00",
        "opening_balance": None,
        "closing_balance": None,
        "balance_audit": "PENDING",
        "balance_discrepancies": 0,
        "voucher_counts": {"Payment": 0, "Receipt": 0, "Contra": 0, "Other": 0},
        "voucher_direction_valid": True,
        "contamination_found": 0,
        "xml_valid": False,
        "xml_voucher_count": 0,
        "status": "PASS"
    }

    try:
        # 1. Extract PDF
        doc = extract_pdf_data(str(file_path))
        result["page_count"] = len(doc.pages)

        # 2. Bank Detection
        detection = detect_bank_from_document(doc)
        result["bank_detected"] = detection.bank_name if detection else "Generic/Unknown"

        # 3. Parser Resolution
        parser = None
        if detection and detection.bank_name:
            parser = parser_registry.get_parser_for_bank(detection.bank_name)
        if not parser and detection and detection.parser_key:
            parser = parser_registry.get_parser(detection.parser_key)
        if not parser:
            parser = parser_registry.get_parser("generic_standard")
        result["parser_used"] = getattr(parser, "bank_name", parser.__class__.__name__) if parser else "None"

        if not parser:
            result["status"] = "FAIL"
            result["error"] = "No parser found"
            return result

        # 4. Parse Statement
        statement = parser.parse(doc)
        txns = statement.transactions
        result["txn_count"] = len(txns)

        if statement.opening_balance is not None:
            result["opening_balance"] = str(statement.opening_balance)
        if statement.closing_balance is not None:
            result["closing_balance"] = str(statement.closing_balance)

        # 5. Voucher mapping & direction validation
        bank_ledger = f"{detection.bank_name or 'Bank'} A/C"
        mapper = LedgerMapper(bank_ledger_name=bank_ledger, cash_ledger_name="Cash")

        tot_dr = Decimal("0.00")
        tot_cr = Decimal("0.00")

        for tx in txns:
            tot_dr += tx.debit or Decimal("0.00")
            tot_cr += tx.credit or Decimal("0.00")
            mapper.map_transaction_ledger(tx)
            tx.voucher_type = classify_voucher_type(tx)

            v_type = tx.voucher_type
            if v_type in result["voucher_counts"]:
                result["voucher_counts"][v_type] += 1
            else:
                result["voucher_counts"]["Other"] += 1

            # Direction check
            if tx.debit > Decimal("0.00") and v_type == "Receipt":
                result["voucher_direction_valid"] = False
            if tx.credit > Decimal("0.00") and v_type == "Payment":
                result["voucher_direction_valid"] = False

        result["total_debit"] = str(tot_dr)
        result["total_credit"] = str(tot_cr)

        # 6. Balance chain audit
        validated_stmt = validate_statement_balances(statement)
        error_txns = [t for t in validated_stmt.transactions if t.validation_status == "ERROR"]
        warn_txns = [t for t in validated_stmt.transactions if t.validation_status == "WARNING"]
        result["balance_discrepancies"] = len(error_txns)
        result["confidence_score"] = getattr(validated_stmt, "confidence_score", 100.0)
        if len(error_txns) == 0:
            result["balance_audit"] = f"VERIFIED_CLEAN ({result['confidence_score']}%)"
        else:
            result["balance_audit"] = f"ERRORS: {len(error_txns)} ({result['confidence_score']}%)"

        # 7. Snapshot & Tally XML Generation
        snapshot = FinalConversionSnapshot.create_from_statement(
            statement=statement,
            bank_ledger_name=bank_ledger,
            cash_ledger_name="Cash",
            job_id=f"verify-12-{filename}"
        )
        xml_gen = TallyXMLGenerator(default_bank_ledger=bank_ledger, default_cash_ledger="Cash")
        xml_content = xml_gen.generate_xml(snapshot)

        # Validate XML structure
        root = ET.fromstring(xml_content)
        result["xml_valid"] = (root.tag == "ENVELOPE")
        vouchers = root.findall(".//VOUCHER")
        result["xml_voucher_count"] = len(vouchers)

        if not result["voucher_direction_valid"] or not result["xml_valid"]:
            result["status"] = "FAIL"

    except Exception as e:
        result["status"] = "ERROR"
        result["error"] = str(e)

    return result

def main():
    print("=" * 80)
    print("VERIFICATION OF 12 REAL SAMPLE BANK STATEMENT FILES")
    print("=" * 80)

    all_results = []
    for fname in SAMPLE_FILES:
        print(f"Processing: {fname}...", end="", flush=True)
        res = verify_sample(fname)
        all_results.append(res)
        print(f" Done [{res['status']}] (Txns: {res.get('txn_count', 0)}, XML Vouchers: {res.get('xml_voucher_count', 0)})")

    out_path = backend_dir / "sample_verification_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print("\n" + "=" * 80)
    print("SUMMARY RESULTS TABLE")
    print("=" * 80)
    headers = ["Filename", "Pages", "Bank Detected", "Txns", "Debit Total", "Credit Total", "Bal Audit", "XML Valid"]
    print(f"{'Filename':<30} | {'Pgs':<4} | {'Bank':<16} | {'Txns':<6} | {'Debit Total':<12} | {'Credit Total':<12} | {'Bal Audit':<16} | {'XML'}")
    print("-" * 115)
    for r in all_results:
        bank = (r.get("bank_detected") or "Unknown")[:16]
        print(f"{r['filename']:<30} | {r.get('page_count', 0):<4} | {bank:<16} | {r.get('txn_count', 0):<6} | {r.get('total_debit', '0'):<12} | {r.get('total_credit', '0'):<12} | {r.get('balance_audit', 'N/A'):<16} | {'VALID' if r.get('xml_valid') else 'INVALID'}")

if __name__ == "__main__":
    main()
