"""
Test Suite: PRD Require Login to View Plans and PRD Subscription Pricing and Bill Limits Update
Project: Kangra Hub Bank Statement Recovery (feature/bs-gemini-jpg-cors-fixes)
"""

import pytest
from datetime import datetime, timezone
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app
from app.core import db, plans, user_store
from app.core.security import CurrentUser
from app.api.usage import get_user_usage_data

client = TestClient(app)

def test_require_login_to_view_plans_unauthenticated():
    """PRD Requirement: Users must log in before they can view subscription plans and their details."""
    # Without Authorization header: must return 401 Unauthorized
    resp = client.get("/api/subscriptions/plans")
    assert resp.status_code == 401
    assert "authentication required" in str(resp.json()).lower()

def test_view_plans_when_authenticated_exact_pricing_and_bill_limits():
    """
    PRD Requirement:
    - Logged-in user can view plans
    - Basic: ₹199, 50 bills
    - Standard: ₹299, 150 bills
    - Premium: ₹499, Unlimited bills
    - Exact pricing, ZERO tax added, no tax breakdown.
    """
    now = datetime.now(timezone.utc)
    uid = f"usr-view-plans-{int(now.timestamp())}"
    sess = user_store.create_user_session(uid, f"{uid}@example.com", role="USER")
    token = sess["token"]

    resp = client.get("/api/subscriptions/plans", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    plan_list = data["plans"]
    assert len(plan_list) == 3

    plans_by_id = {p["id"]: p for p in plan_list}
    
    # 1. Basic Plan
    basic = plans_by_id["basic"]
    assert basic["price_inr"] == 199.0
    assert basic["price_paise"] == 19900
    assert basic["bills_limit"] == 50
    assert basic["is_unlimited"] is False

    # 2. Standard Plan
    standard = plans_by_id["standard"]
    assert standard["price_inr"] == 299.0
    assert standard["price_paise"] == 29900
    assert standard["bills_limit"] == 150
    assert standard["is_unlimited"] is False

    # 3. Premium Plan
    premium = plans_by_id["premium"]
    assert premium["price_inr"] == 499.0
    assert premium["price_paise"] == 49900
    assert premium["bills_limit"] == -1
    assert premium["is_unlimited"] is True

    # Validate that Standard > Basic
    assert standard["bills_limit"] > basic["bills_limit"]

    # Validate that no tax text appears in feature descriptions
    for p in plan_list:
        for f in p.get("features", []):
            assert "tax" not in f.lower()
            assert "gst" not in f.lower()

def test_subscription_activation_and_idempotency():
    """PRD Requirement: Atomic activation with 30-day IST validity and duplicate callback protection."""
    now = datetime.now(timezone.utc)
    uid = f"usr-act-{int(now.timestamp())}"
    email = f"{uid}@firm.com"
    pid = f"pay_test_{int(now.timestamp())}"

    # First activation: Basic (50 bills)
    act1 = db.process_verified_membership_payment(
        user_id=uid,
        user_email=email,
        user_name="Firm User",
        payment_id=pid,
        order_id="order_123",
        amount_paise=19900,
        payment_status="captured",
        captured_at_utc=now,
        verified_at_utc=now,
        plan_id="basic"
    )
    assert act1["success"] is True
    assert act1["idempotent"] is False
    assert act1["bills_limit"] == 50
    assert act1["plan_id"] == "basic"
    assert "Valid through" in act1["display_wording"]

    # Duplicate call with identical payment_id returns idempotent success without duplicate activation
    act2 = db.process_verified_membership_payment(
        user_id=uid,
        user_email=email,
        user_name="Firm User",
        payment_id=pid,
        order_id="order_123",
        amount_paise=19900,
        payment_status="captured",
        captured_at_utc=now,
        verified_at_utc=now,
        plan_id="basic"
    )
    assert act2["success"] is True
    assert act2["idempotent"] is True

def test_usage_reporting_for_subscribed_user():
    """PRD Requirement: Usage reporting reflects subscription limits per firm."""
    now = datetime.now(timezone.utc)
    uid = f"usr-rep-{int(now.timestamp())}"
    email = f"{uid}@company.com"
    pid = f"pay_rep_{int(now.timestamp())}"

    db.process_verified_membership_payment(
        user_id=uid,
        user_email=email,
        user_name="Reporting User",
        payment_id=pid,
        order_id="order_rep",
        amount_paise=29900,
        payment_status="captured",
        captured_at_utc=now,
        verified_at_utc=now,
        plan_id="standard"
    )

    user = CurrentUser(
        id=uid,
        email=email,
        role="STAFF",
        subscription_plan_id="standard",
        subscription_plan_name="Standard",
        subscription_bill_limit=150,
        is_unlimited=False
    )

    usage = get_user_usage_data(user)
    assert usage.subscription_plan_id == "standard"
    assert usage.subscription_bill_limit == 150
    assert usage.bills_remaining_this_cycle == 150
    assert "Standard Active" in usage.account_status
