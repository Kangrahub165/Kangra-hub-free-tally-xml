import os
import pytest
from decimal import Decimal
from datetime import date
from app.accounting.ledger_importer import (
    import_ledgers_from_text,
    sanitize_xml_content,
    parse_xml_masters,
    detect_ledger_format,
    UserLedgerStore,
    global_ledger_store
)
from app.api.ledgers import decode_ledger_file
from app.accounting.mapper import LedgerMapper
from app.transactions.model import TransactionItem

MASTER_XML_PATH = r"d:\KANGRA HUB FREE TALLY XML\Master.xml"

def test_master_xml_exists():
    assert os.path.exists(MASTER_XML_PATH), "Master.xml must exist at root directory"

def test_decode_ledger_file_utf16le():
    with open(MASTER_XML_PATH, "rb") as f:
        raw_bytes = f.read()
    text = decode_ledger_file(raw_bytes)
    assert "<ENVELOPE>" in text
    assert len(text) > 100000

def test_sanitize_xml_content():
    sample_bad = "<TEST><STATE>&#4; Any</STATE><NAME>Test&#0;&#8;&#31; Name</NAME></TEST>"
    cleaned = sanitize_xml_content(sample_bad)
    assert "&#4;" not in cleaned
    assert "<STATE> Any</STATE>" in cleaned
    assert "<NAME>Test Name</NAME>" in cleaned

def test_import_master_xml_full():
    with open(MASTER_XML_PATH, "rb") as f:
        raw_bytes = f.read()
    text = decode_ledger_file(raw_bytes)
    result = import_ledgers_from_text(text, filename="Master.xml")

    assert result.detected_format == "XML"
    assert result.error is None
    assert result.total_ledgers == 267
    assert result.total_groups == 28
    assert result.total_imported == 267
    assert len(result.ledgers) == 267
    assert len(result.groups) == 28
    assert result.duplicates == 0
    assert len(result.conflicts) == 0

def test_master_xml_ledger_metadata():
    with open(MASTER_XML_PATH, "rb") as f:
        raw_bytes = f.read()
    text = decode_ledger_file(raw_bytes)
    result = import_ledgers_from_text(text, filename="Master.xml")

    ledger_map = {l.name: l for l in result.ledgers}

    # Verify AB Sai Steel Work
    assert "AB Sai Steel Work" in ledger_map
    ab = ledger_map["AB Sai Steel Work"]
    assert ab.group == "Sundry Creditors"
    assert ab.parent_group == "Current Liabilities"
    assert ab.opening_balance == Decimal("56200.00")
    assert ab.party_gstin == "02AWFPT1382H1ZL"
    assert ab.state == "Himachal Pradesh"
    assert ab.country == "India"
    assert ab.pincode == "176216"
    assert ab.guid == "12a1ce31-b72c-4cfa-b999-fd8259049894-000000ed"

    # Verify SBI Bank CCLimit
    assert "SBI Bank CCLimitA/C 40885239623" in ledger_map
    sbi = ledger_map["SBI Bank CCLimitA/C 40885239623"]
    assert sbi.group == "Bank OD A/c"
    assert sbi.parent_group == "Loans (Liability)"
    assert sbi.opening_balance == Decimal("951021.24")

    # Verify Nav Durga Steel
    assert "Nav Durga Steel" in ledger_map
    nds = ledger_map["Nav Durga Steel"]
    assert nds.group == "Sundry Creditors"
    assert nds.parent_group == "Current Liabilities"
    assert nds.party_gstin == "03AIBPG9510A2Z3"
    assert nds.state == "Punjab"
    assert nds.pincode == "147301"

def test_master_xml_group_hierarchy():
    with open(MASTER_XML_PATH, "rb") as f:
        raw_bytes = f.read()
    text = decode_ledger_file(raw_bytes)
    result = import_ledgers_from_text(text, filename="Master.xml")

    group_map = {g.name: g for g in result.groups}
    assert "Sundry Creditors" in group_map
    assert group_map["Sundry Creditors"].parent == "Current Liabilities"

    assert "Sundry Debtors" in group_map
    assert group_map["Sundry Debtors"].parent == "Current Assets"

    assert "Bank Accounts" in group_map
    assert group_map["Bank Accounts"].parent == "Current Assets"

def test_user_ledger_store_with_master_xml():
    with open(MASTER_XML_PATH, "rb") as f:
        raw_bytes = f.read()
    text = decode_ledger_file(raw_bytes)
    result = import_ledgers_from_text(text, filename="Master.xml")

    store = UserLedgerStore()
    user_id = "test_admin_user"
    store.add_ledgers(user_id, result.ledgers)
    store.add_groups(user_id, result.groups)

    assert len(store.get_user_ledgers(user_id)) == 267
    assert len(store.get_user_groups(user_id)) == 28

    # Search by name
    res_name = store.search_ledgers(user_id, "AB Sai")
    assert any(l.name == "AB Sai Steel Work" for l in res_name)

    # Search by GSTIN
    res_gstin = store.search_ledgers(user_id, "02AWFPT1382H1ZL")
    assert any(l.name == "AB Sai Steel Work" for l in res_gstin)

    # Search by group
    res_group = store.search_ledgers(user_id, "Bank OD A/c")
    assert any(l.name == "SBI Bank CCLimitA/C 40885239623" for l in res_group)

def test_ledger_mapper_matching_with_master_xml():
    with open(MASTER_XML_PATH, "rb") as f:
        raw_bytes = f.read()
    text = decode_ledger_file(raw_bytes)
    result = import_ledgers_from_text(text, filename="Master.xml")

    mapper = LedgerMapper(imported_ledgers=result.ledgers)

    # 1. Matching by party name in narration
    tx1 = TransactionItem(
        date=date(2024, 4, 1),
        narration="NEFT/12345/AB Sai Steel Work/Payment for supplies",
        debit=Decimal("15000.00")
    )
    mapped_name1 = mapper.map_transaction_ledger(tx1)
    assert mapped_name1 == "AB Sai Steel Work"
    assert tx1.mapping_confidence >= 80.0
    assert tx1.mapping_status == "Auto"

    # 2. Matching by GSTIN in narration
    tx2 = TransactionItem(
        date=date(2024, 4, 2),
        narration="RTGS/TRANSFER/03AIBPG9510A2Z3/PAYMENT",
        debit=Decimal("50000.00")
    )
    mapped_name2 = mapper.map_transaction_ledger(tx2)
    assert mapped_name2 == "Nav Durga Steel"
    assert tx2.mapping_confidence >= 95.0

    # 3. Unmatched party falls back to Suspense
    tx3 = TransactionItem(
        date=date(2024, 4, 3),
        narration="RANDOM UNKNOWN PARTY TRANSACTION 999",
        debit=Decimal("2000.00")
    )
    mapped_name3 = mapper.map_transaction_ledger(tx3)
    assert mapped_name3 == "Suspense"
    assert tx3.mapping_status == "Suspense"
    assert tx3.mapping_confidence == 0.0

def test_api_endpoints_return_all_masters():
    from fastapi.testclient import TestClient
    from main import app
    from app.core.security import get_current_user, CurrentUser

    mock_user = CurrentUser(id="test_xml_client_user", email="test@kangrahub.com", role="USER")
    app.dependency_overrides[get_current_user] = lambda: mock_user

    client = TestClient(app)
    try:
        with open(MASTER_XML_PATH, "rb") as f:
            response = client.post(
                "/api/ledgers/import",
                files={"file": ("Master.xml", f, "text/xml")}
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total_ledgers"] == 267
        assert data["total_groups"] == 28
        assert data["total_imported"] == 267

        # Test GET /api/ledgers returns ALL 267 without limit truncation
        get_ledgers_resp = client.get("/api/ledgers")
        assert get_ledgers_resp.status_code == 200
        ledgers = get_ledgers_resp.json()
        assert len(ledgers) == 267, f"Expected all 267 ledgers, got {len(ledgers)}"

        # Test GET /api/ledgers/groups returns ALL 28 groups
        get_groups_resp = client.get("/api/ledgers/groups")
        assert get_groups_resp.status_code == 200
        groups = get_groups_resp.json()
        assert len(groups) == 28, f"Expected all 28 groups, got {len(groups)}"

        # Test search filter works
        search_resp = client.get("/api/ledgers?search=Sai")
        assert search_resp.status_code == 200
        search_results = search_resp.json()
        assert len(search_results) > 0
        assert any(l["name"] == "AB Sai Steel Work" for l in search_results)
    finally:
        app.dependency_overrides.pop(get_current_user, None)

def test_bulk_assign_ledger_precise_targeting():
    from fastapi.testclient import TestClient
    from main import app
    from app.core.security import get_current_user, CurrentUser
    from app.transactions.model import TransactionItem
    from app.parsers.base import CanonicalStatement
    from app.api.conversions import IN_MEMORY_JOBS
    from datetime import datetime

    mock_admin = CurrentUser(id="test_bulk_admin_user", email="admin@kangrahub.com", role="ADMIN", is_unlimited=True)
    app.dependency_overrides[get_current_user] = lambda: mock_admin

    client = TestClient(app)
    try:
        t1 = TransactionItem(id="tx-1", row_index=1, date=date(2024, 4, 1), narration="PAYMENT TO VENDOR A", debit=Decimal("100.00"), ledger_name="Suspense", voucher_type="Payment")
        t2 = TransactionItem(id="tx-2", row_index=2, date=date(2024, 4, 2), narration="PAYMENT TO VENDOR B", debit=Decimal("200.00"), ledger_name="Suspense", voucher_type="Payment")
        t3 = TransactionItem(id="tx-3", row_index=3, date=date(2024, 4, 3), narration="PAYMENT TO VENDOR C", debit=Decimal("300.00"), ledger_name="Suspense", voucher_type="Payment")

        stmt = CanonicalStatement(
            bank="Test Bank",
            account_number_masked="12345",
            statement_from=date(2024, 4, 1),
            statement_to=date(2024, 4, 3),
            opening_balance=Decimal("1000.00"),
            closing_balance=Decimal("400.00"),
            total_debit=Decimal("600.00"),
            total_credit=Decimal("0.00"),
            bank_ledger_name="Bank Account",
            cash_ledger_name="Cash",
            transactions=[t1, t2, t3]
        )

        job_id = "test-precise-bulk-job"
        IN_MEMORY_JOBS[job_id] = {
            "id": job_id,
            "user_id": "test_bulk_admin_user",
            "file_name": "test.pdf",
            "pdf_path": None,
            "password": None,
            "bank_name": "Test Bank",
            "statement_format": "STANDARD",
            "page_count": 1,
            "transaction_count": 3,
            "rejected_transaction_count": 0,
            "raw_transaction_count": 3,
            "suspense_count": 3,
            "mapped_count": 0,
            "duplicate_count": 0,
            "page_diagnostics": [],
            "status": "COMPLETED",
            "confidence_score": 95.0,
            "confidence_tier": "HIGH",
            "is_ambiguous": False,
            "parser_name": "Test Parser",
            "detected_ifsc": None,
            "runner_up_bank": None,
            "runner_up_confidence": None,
            "detection_reasons": [],
            "balance_status": "VALID",
            "statement_from": date(2024, 4, 1),
            "statement_to": date(2024, 4, 3),
            "opening_balance": Decimal("1000.00"),
            "closing_balance": Decimal("400.00"),
            "total_debit": Decimal("600.00"),
            "total_credit": Decimal("0.00"),
            "created_at": datetime.now(),
            "statement": stmt,
            "xml_content": None,
            "xml_filename": None,
            "bank_ledger_name": "Bank Account",
            "cash_ledger_name": "Cash",
            "transactions": [t1, t2, t3]
        }

        # User selects ONLY row 1 (the second row, tx-2)
        resp = client.post(
            f"/api/conversions/{job_id}/bulk-assign-ledger",
            json={
                "row_indices": [1],
                "ledger_name": "AB Sai Steel Work",
                "voucher_type": "Payment",
                "apply_to_similar": False,
                "tx_ids": ["tx-2"]
            }
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        tx_res = data["transactions"]
        assert len(tx_res) == 3
        # ONLY tx-2 should be assigned; tx-1 and tx-3 must remain Suspense!
        assert tx_res[0]["ledger_name"] == "Suspense", "tx-1 was not selected, must remain Suspense"
        assert tx_res[1]["ledger_name"] == "AB Sai Steel Work", "tx-2 was selected and must be updated"
        assert tx_res[2]["ledger_name"] == "Suspense", "tx-3 was not selected, must remain Suspense"

        # Admin bulk assign test: assign tx-3
        admin_resp = client.post(
            f"/api/admin/conversions/{job_id}/bulk-assign-ledger",
            json={
                "row_indices": [2],
                "ledger_name": "Nav Durga Steel",
                "voucher_type": "Payment",
                "apply_to_similar": False,
                "tx_ids": ["tx-3"]
            }
        )
        assert admin_resp.status_code == 200, admin_resp.text
        admin_data = admin_resp.json()
        admin_txs = admin_data["transactions"]
        assert admin_txs[0]["ledger_name"] == "Suspense"
        assert admin_txs[1]["ledger_name"] == "AB Sai Steel Work"
        assert admin_txs[2]["ledger_name"] == "Nav Durga Steel"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


