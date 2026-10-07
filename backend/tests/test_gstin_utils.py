import pytest
from decimal import Decimal
from app.invoices.gstin_utils import (
    gstin_check_char,
    gstin_valid,
    gstin_repair,
    parse_amount,
    close,
    check_line,
    exclusive_from_inclusive
)

def test_gstin_valid_reference():
    # Appendix C: "checksum of the widely used sample GSTIN 27AAPFU0939F1ZV is valid"
    assert gstin_valid("27AAPFU0939F1ZV") is True

def test_gstin_invalid_checksum():
    # Appendix C: "a changed last character is rejected"
    assert gstin_valid("27AAPFU0939F1ZA") is False
    assert gstin_valid("27AAPFU0939F1Z0") is False

def test_gstin_repair_letter_o_and_i():
    # Appendix C: "27AAPFUO939F1ZV (letter O for zero) and 27AAPFU0939FIZV (letter I for one) both repair to 27AAPFU0939F1ZV"
    assert gstin_repair("27AAPFUO939F1ZV") == "27AAPFU0939F1ZV"
    assert gstin_repair("27AAPFU0939FIZV") == "27AAPFU0939F1ZV"

def test_parse_amount_indian_formatting():
    # Appendix C: "'₹ 1,23,456.50' parses to 123456.50; '(1,200.00)' parses to -1200.00"
    assert parse_amount("₹ 1,23,456.50") == Decimal("123456.50")
    assert parse_amount("Rs. 1,23,456.50/-") == Decimal("123456.50")
    assert parse_amount("(1,200.00)") == Decimal("-1200.00")
    assert parse_amount("-1,200.00") == Decimal("-1200.00")
    assert parse_amount("500") == Decimal("500.00")
    assert parse_amount("") is None
    assert parse_amount(None) is None

def test_exclusive_from_inclusive():
    # Appendix C: "1180 inclusive at 18% gives 1000.00 exclusive"
    assert exclusive_from_inclusive(Decimal("1180.00"), Decimal("18.00")) == Decimal("1000.00")

def test_check_line():
    # Row with qty 10, rate 100, disc 0, taxable 1000, gst 18% (cgst 90, sgst 90) -> valid
    row = {
        "qty": Decimal("10.00"),
        "rate": Decimal("100.00"),
        "discount_amount": Decimal("0.00"),
        "taxable": Decimal("1000.00"),
        "gst_rate": Decimal("18.00"),
        "cgst": Decimal("90.00"),
        "sgst": Decimal("90.00")
    }
    assert check_line(row) == []

    # Row with failing taxable maths
    bad_taxable_row = dict(row, taxable=Decimal("950.00"))
    errs = check_line(bad_taxable_row)
    assert any(err[0] == "V09" for err in errs)
