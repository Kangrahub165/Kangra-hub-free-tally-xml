import io
import pytest
from unittest.mock import patch
from PIL import Image
from fastapi.testclient import TestClient
from main import app
from app.gemini.extractor import GeminiExtractor
from app.transactions.model import CanonicalStatement, TransactionItem
from decimal import Decimal
from datetime import date

client = TestClient(app)

USER_HEADERS = {"Authorization": "Bearer mock-user-token"}
ADMIN_HEADERS = {"Authorization": "Bearer mock-admin-token"}

def make_dummy_jpeg_bytes() -> bytes:
    """Generate minimal valid JPEG bytes with resolution >= 100x100."""
    buf = io.BytesIO()
    img = Image.new("RGB", (120, 120), color=(240, 240, 240))
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_normal_user_batch_limit_exceeded_11_images():
    """Verify normal user uploading 11 JPG images is blocked with HTTP 400 and clear message."""
    jpeg_data = make_dummy_jpeg_bytes()
    files = [("files", (f"page_{i}.jpg", io.BytesIO(jpeg_data), "image/jpeg")) for i in range(1, 12)]

    resp = client.post(
        "/api/conversions/upload",
        files=files,
        headers=USER_HEADERS
    )
    assert resp.status_code == 400
    msg = resp.json().get("detail") or resp.json().get("message", "")
    assert "Upload limit exceeded: Normal users can upload up to 10 JPG/JPEG images per batch" in msg
    assert "You selected 11 images" in msg
    assert "Please reduce your selection to 10 images or fewer" in msg


def test_admin_user_batch_limit_exceeded_51_images():
    """Verify administrator uploading 51 JPG images is blocked with HTTP 400 and clear message."""
    jpeg_data = make_dummy_jpeg_bytes()
    files = [("files", (f"page_{i}.jpg", io.BytesIO(jpeg_data), "image/jpeg")) for i in range(1, 52)]

    resp = client.post(
        "/api/conversions/upload",
        files=files,
        headers=ADMIN_HEADERS
    )
    assert resp.status_code == 400
    msg = resp.json().get("detail") or resp.json().get("message", "")
    assert "Upload limit exceeded: Administrators can upload up to 50 JPG/JPEG images per batch" in msg
    assert "You selected 51 images" in msg
    assert "Please reduce your selection to 50 images or fewer" in msg


def test_mixed_file_types_blocked():
    """Verify uploading a mixed batch of PDF and JPG is rejected with HTTP 400."""
    jpeg_data = make_dummy_jpeg_bytes()
    files = [
        ("files", ("statement.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")),
        ("files", ("statement_p2.jpg", io.BytesIO(jpeg_data), "image/jpeg")),
    ]

    resp = client.post(
        "/api/conversions/upload",
        files=files,
        headers=USER_HEADERS
    )
    assert resp.status_code == 400
    msg = resp.json().get("detail") or resp.json().get("message", "")
    assert "Mixed file types are not supported" in msg


def test_multiple_pdfs_blocked():
    """Verify uploading multiple PDFs in one batch is rejected with HTTP 400."""
    files = [
        ("files", ("statement1.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")),
        ("files", ("statement2.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")),
    ]

    resp = client.post(
        "/api/conversions/upload",
        files=files,
        headers=USER_HEADERS
    )
    assert resp.status_code == 400
    msg = resp.json().get("detail") or resp.json().get("message", "")
    assert "Multiple PDF upload is not supported" in msg


def test_unsupported_file_extension_blocked():
    """Verify non-PDF, non-JPG files are rejected with HTTP 400."""
    files = [
        ("files", ("statement.txt", io.BytesIO(b"Hello world"), "text/plain")),
    ]

    resp = client.post(
        "/api/conversions/upload",
        files=files,
        headers=USER_HEADERS
    )
    assert resp.status_code == 400
    msg = resp.json().get("detail") or resp.json().get("message", "")
    assert "Unsupported file type" in msg


def test_normal_user_batch_within_limit_10_images():
    """Verify normal user uploading exactly 10 JPG images passes limit check."""
    jpeg_data = make_dummy_jpeg_bytes()
    files = [("files", (f"page_{i}.jpg", io.BytesIO(jpeg_data), "image/jpeg")) for i in range(1, 11)]

    mock_stmt = CanonicalStatement(
        bank="State Bank of India",
        statement_format="JPG_Batch_Statement",
        account_number_masked="XXXX1234",
        statement_from=date(2024, 1, 1),
        statement_to=date(2024, 1, 31),
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("2000.00"),
        total_debit=Decimal("500.00"),
        total_credit=Decimal("1500.00"),
        confidence_score=99.0,
        transactions=[
            TransactionItem(
                row_index=1,
                date=date(2024, 1, 1),
                narration="Opening Credit Interest",
                withdrawal="",
                deposit="1500.00",
                balance="2500.00",
                debit=Decimal("0.00"),
                credit=Decimal("1500.00"),
                running_balance=Decimal("2500.00"),
                voucher_type="Receipt",
                source_page=1
            ),
            TransactionItem(
                row_index=2,
                date=date(2024, 1, 5),
                narration="ATM Cash Withdrawal",
                withdrawal="500.00",
                deposit="",
                balance="2000.00",
                debit=Decimal("500.00"),
                credit=Decimal("0.00"),
                running_balance=Decimal("2000.00"),
                voucher_type="Payment",
                source_page=10
            )
        ]
    )

    with patch.object(GeminiExtractor, "is_available", return_value=True), \
         patch.object(GeminiExtractor, "extract_from_multiple_image_bytes", return_value=mock_stmt):
        resp = client.post(
            "/api/conversions/upload",
            files=files,
            headers=USER_HEADERS
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["page_count"] == 10
        assert data["transaction_count"] == 2
        assert data["bank_name"] == "State Bank of India"


def test_admin_batch_within_limit_up_to_50_images():
    """Verify admin uploading 50 JPG images passes limit check and succeeds."""
    jpeg_data = make_dummy_jpeg_bytes()
    files = [("files", (f"page_{i}.jpg", io.BytesIO(jpeg_data), "image/jpeg")) for i in range(1, 51)]

    mock_stmt = CanonicalStatement(
        bank="Punjab National Bank",
        statement_format="JPG_Batch_Statement",
        account_number_masked="XXXX5678",
        opening_balance=Decimal("5000.00"),
        closing_balance=Decimal("10000.00"),
        total_debit=Decimal("0.00"),
        total_credit=Decimal("5000.00"),
        confidence_score=99.0,
        transactions=[
            TransactionItem(
                row_index=1,
                date=date(2024, 1, 10),
                narration="NEFT Inward Credit",
                withdrawal="",
                deposit="5000.00",
                balance="10000.00",
                debit=Decimal("0.00"),
                credit=Decimal("5000.00"),
                running_balance=Decimal("10000.00"),
                voucher_type="Receipt",
                source_page=50
            )
        ]
    )

    with patch.object(GeminiExtractor, "is_available", return_value=True), \
         patch.object(GeminiExtractor, "extract_from_multiple_image_bytes", return_value=mock_stmt):
        resp = client.post(
            "/api/conversions/upload",
            files=files,
            headers=ADMIN_HEADERS
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["page_count"] == 50
        assert data["transaction_count"] == 1


def test_multiple_image_extraction_merging_logic():
    """Verify GeminiExtractor.extract_from_multiple_image_bytes tags source_page and re-indexes."""
    stmt_page1 = CanonicalStatement(
        bank="HDFC Bank",
        statement_format="JPG_Statement",
        account_number_masked="XXXX9999",
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("1200.00"),
        total_debit=Decimal("0.00"),
        total_credit=Decimal("200.00"),
        confidence_score=99.0,
        transactions=[
            TransactionItem(
                row_index=1,
                date=date(2024, 2, 1),
                narration="Salary Credit",
                withdrawal="",
                deposit="200.00",
                balance="1200.00",
                debit=Decimal("0.00"),
                credit=Decimal("200.00"),
                running_balance=Decimal("1200.00"),
                voucher_type="Receipt"
            )
        ]
    )
    stmt_page2 = CanonicalStatement(
        bank="HDFC Bank",
        statement_format="JPG_Statement",
        account_number_masked="XXXX9999",
        opening_balance=Decimal("1200.00"),
        closing_balance=Decimal("1100.00"),
        total_debit=Decimal("100.00"),
        total_credit=Decimal("0.00"),
        confidence_score=99.0,
        transactions=[
            TransactionItem(
                row_index=1,
                date=date(2024, 2, 2),
                narration="Debit Card Swipe",
                withdrawal="100.00",
                deposit="",
                balance="1100.00",
                debit=Decimal("100.00"),
                credit=Decimal("0.00"),
                running_balance=Decimal("1100.00"),
                voucher_type="Payment"
            )
        ]
    )

    jpeg_data = make_dummy_jpeg_bytes()
    images_data = [("page1.jpg", jpeg_data), ("page2.jpg", jpeg_data)]

    with patch.object(GeminiExtractor, "is_available", return_value=True), \
         patch.object(GeminiExtractor, "extract_from_image_bytes", side_effect=[stmt_page1, stmt_page2]):
        merged = GeminiExtractor.extract_from_multiple_image_bytes(images_data)
        assert merged is not None
        assert len(merged.transactions) == 2
        # Check source page indexing
        assert merged.transactions[0].source_page == 1
        assert merged.transactions[0].row_index == 1
        assert merged.transactions[1].source_page == 2
        assert merged.transactions[1].row_index == 2
        # Check running balances and totals
        assert merged.opening_balance == Decimal("1000.00")
        assert merged.closing_balance == Decimal("1100.00")
        assert merged.total_debit == Decimal("100.00")
        assert merged.total_credit == Decimal("200.00")
