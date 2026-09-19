import pytest
from datetime import date
from decimal import Decimal
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.transactions.normalizer import (
    normalize_date,
    normalize_amount,
    clean_narration,
    extract_reference_number
)

def test_normalize_date_formats():
    assert normalize_date("01/04/2026") == date(2026, 4, 1)
    assert normalize_date("15-09-2025") == date(2025, 9, 15)
    assert normalize_date("02.05.2024") == date(2024, 5, 2)
    assert normalize_date("01-Apr-2026") == date(2026, 4, 1)
    assert normalize_date("12 Oct 2025") == date(2025, 10, 12)
    assert normalize_date("2026-04-01") == date(2026, 4, 1)

def test_normalize_amount_precision():
    # Retains decimal precision and handles commas and symbols
    assert normalize_amount("5,000") == Decimal("5000.00")
    assert normalize_amount("₹5,000.50") == Decimal("5000.50")
    assert normalize_amount("1,23,456.75") == Decimal("123456.75")
    assert normalize_amount("Rs. 350.00 Cr") == Decimal("350.00")
    assert normalize_amount("(450.00)") == Decimal("-450.00")
    assert normalize_amount("") == Decimal("0.00")

def test_clean_narration_multiline():
    raw = "UPI/ABC TRADERS/\n INV NO 12345/\n   PAYMENT FOR GOODS"
    cleaned = clean_narration(raw)
    assert cleaned == "UPI/ABC TRADERS/ INV NO 12345/ PAYMENT FOR GOODS"

def test_extract_reference_number():
    assert extract_reference_number("UPI/446130236270/P2V/9418250639@ybl/RAKESH") == "446130236270"
    assert extract_reference_number("NEFT/N1234567890ABC/PAYMENT") == "N1234567890ABC"
