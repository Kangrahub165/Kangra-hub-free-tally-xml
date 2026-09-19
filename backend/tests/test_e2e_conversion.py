import pytest
import os
import sys
from io import BytesIO
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from app.tally.xml_validator import validate_tally_xml

client = TestClient(app)

def create_sample_pnb_pdf() -> bytes:
    """Generates a synthetic realistic PNB bank statement PDF with table and multi-line narrations."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Header
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "PUNJAB NATIONAL BANK")
    c.setFont("Helvetica", 9)
    c.drawString(50, 735, "Branch: NAGROTA SURIAN (DISTT. KANGRA)")
    c.drawString(50, 720, "Account Number : 0033000100123456")
    c.drawString(50, 705, "Customer Name : KANGRA HUB TEST USER")
    c.drawString(50, 690, "Statement Period : 01/04/2024 to 30/04/2024")
    
    # Table header
    c.setFont("Helvetica-Bold", 8)
    c.drawString(50, 660, "Date")
    c.drawString(120, 660, "Particulars / Narration")
    c.drawString(350, 660, "Chq/Ref No")
    c.drawString(420, 660, "Withdrawal (Dr)")
    c.drawString(490, 660, "Deposit (Cr)")
    c.drawString(540, 660, "Balance")
    c.line(50, 655, 590, 655)

    # Row 1: APY Contribution Payment
    c.setFont("Helvetica", 8)
    c.drawString(50, 640, "02/04/2024")
    c.drawString(120, 640, "APY CONTRI:01-04-2024 to 30-06-2024")
    c.drawString(350, 640, "4461001")
    c.drawString(430, 640, "3,928.00")
    c.drawString(500, 640, "0.00")
    c.drawString(545, 640, "46,072.00")

    # Row 2: UPI Receipt
    c.drawString(50, 620, "04/04/2024")
    c.drawString(120, 620, "UPI/446130236270/P2V/9418250639@ybl/RAKESH KUMAR S")
    c.drawString(350, 620, "446130236270")
    c.drawString(430, 620, "0.00")
    c.drawString(500, 620, "3,500.00")
    c.drawString(545, 620, "49,572.00")

    # Row 3: Cash Deposit Contra
    c.drawString(50, 600, "26/06/2024")
    c.drawString(120, 600, "Cash Deposit At : NAGROTA SURIAN(DISTT. KANGRA)")
    c.drawString(350, 600, "CSH001")
    c.drawString(430, 600, "0.00")
    c.drawString(500, 600, "5,500.00")
    c.drawString(545, 600, "55,072.00")

    c.line(50, 585, 590, 585)
    c.showPage()
    c.save()
    
    return buffer.getvalue()

def test_full_end_to_end_conversion_flow():
    # 1. Generate synthetic PDF
    pdf_bytes = create_sample_pnb_pdf()
    assert len(pdf_bytes) > 0

    # 2. Upload statement to API
    files = {"file": ("pnb_statement.pdf", pdf_bytes, "application/pdf")}
    res = client.post(
        "/api/conversions/upload",
        files=files,
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert res.status_code == 200, f"Upload failed: {res.text}"
    job_data = res.json()
    job_id = job_data["id"]

    # Verify detection
    assert "Punjab National Bank" in job_data["bank_name"]
    assert job_data["confidence_score"] >= 80.0
    assert len(job_data["transactions"]) >= 2

    # 3. Review transactions
    review_payload = {
        "transactions": job_data["transactions"],
        "bank_ledger_name": "PNB SAVING A/C 0033"
    }
    res_review = client.post(
        f"/api/conversions/{job_id}/review",
        json=review_payload,
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert res_review.status_code == 200

    # 4. Generate Tally XML
    res_gen = client.post(
        f"/api/conversions/{job_id}/generate",
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert res_gen.status_code == 200, f"Generate failed: {res_gen.text}"
    gen_data = res_gen.json()
    assert gen_data["success"] is True
    assert gen_data["filename"].endswith(".xml")

    # 5. Download and inspect XML
    res_dl = client.get(
        f"/api/conversions/{job_id}/download",
        headers={"Authorization": "Bearer mock-user-token"}
    )
    assert res_dl.status_code == 200
    xml_content = res_dl.text

    # 6. Validate Tally XML against SAMPLE.xml specs
    is_valid, errors = validate_tally_xml(xml_content)
    assert is_valid is True, f"Tally XML validation failed: {errors}"
    assert '<VOUCHER VCHTYPE="Payment"' in xml_content or '<VOUCHER VCHTYPE="Receipt"' in xml_content
    assert '<LEDGERNAME>PNB SAVING A/C 0033</LEDGERNAME>' in xml_content
    assert '<TALLYREQUEST>Import Data</TALLYREQUEST>' in xml_content
