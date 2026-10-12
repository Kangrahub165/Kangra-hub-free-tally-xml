"""
Authoritative Subscription Plans Configuration — Kangra Hub Bank Statement Recovery
Implements PRD: Subscription Pricing and Bill Limits Update:
- Basic: ₹199 (19900 paise, 50 bills / month)
- Standard: ₹299 (29900 paise, 150 bills / month)
- Premium: ₹499 (49900 paise, Unlimited bills / month)

CRITICAL DIRECTIVES (PRD Sections 1 & 2):
1. Exact pricing with ZERO tax added. No tax labels, breakdowns, or messages anywhere.
2. Bill limits strictly enforced: Basic=50, Standard=150, Premium=Unlimited (-1).
3. Authoritative server-side resolution and admin configurability via SQLite.
"""

from typing import Dict, Any, List, Optional
import copy

DEFAULT_SUBSCRIPTION_PLANS: List[Dict[str, Any]] = [
    {
        "id": "basic",
        "name": "Basic",
        "tagline": "Ideal for small firms & single-branch businesses",
        "price_inr": 199.0,
        "price_paise": 19900,
        "bills_limit": 50,
        "duration_days": 30,
        "is_unlimited": False,
        "badge": "STARTER",
        "features": [
            "50 Statement / Bill Conversions / Month",
            "Bank Statement PDF to Tally XML Export",
            "Auto Ledger & Party Counter-Mapping",
            "38+ Supported Indian & International Banks",
            "30 Days Subscription Validity",
            "Email & In-App Standard Support"
        ]
    },
    {
        "id": "standard",
        "name": "Standard",
        "tagline": "For active firms, retail chains & growing businesses",
        "price_inr": 299.0,
        "price_paise": 29900,
        "bills_limit": 150,
        "duration_days": 30,
        "is_unlimited": False,
        "badge": "MOST POPULAR",
        "features": [
            "150 Statement / Bill Conversions / Month",
            "Bank Statement PDF to Tally XML Export",
            "Auto Ledger & Party Counter-Mapping",
            "Reverse Entries Pairing & Isolation",
            "38+ Supported Indian & International Banks",
            "30 Days Subscription Validity",
            "Priority Processing & Direct Support"
        ]
    },
    {
        "id": "premium",
        "name": "Premium",
        "tagline": "Unlimited power for CAs, accounting practitioners & enterprises",
        "price_inr": 499.0,
        "price_paise": 49900,
        "bills_limit": -1,
        "duration_days": 30,
        "is_unlimited": True,
        "badge": "BEST VALUE",
        "features": [
            "Unlimited Statement / Bill Conversions",
            "Zero Monthly or Daily Conversion Caps",
            "Bank Statement PDF to Tally XML Export",
            "Full Ledger Auto-Creation & Bulk Assignment",
            "Reverse Entries Pairing & Charges Separation",
            "30 Days Subscription Validity",
            "VIP Dedicated Priority Support"
        ]
    }
]

def resolve_plan_id(raw_id: Optional[str]) -> str:
    """Normalizes input plan identifier to canonical plan ID."""
    if not raw_id:
        return "basic"
    cleaned = str(raw_id).strip().lower()
    if "basic" in cleaned or "199" in cleaned or "starter" in cleaned:
        return "basic"
    if "standard" in cleaned or "299" in cleaned or "popular" in cleaned:
        return "standard"
    if "premium" in cleaned or "499" in cleaned or "unlimited" in cleaned or "pro" in cleaned:
        return "premium"
    return "basic"

def get_subscription_plans() -> List[Dict[str, Any]]:
    """
    Returns active plans merged with dynamic admin overrides from SQLite.
    Pricing reflects exact amounts without any tax labels or calculations.
    """
    try:
        from app.core import db
        overrides = db.get_all_subscription_plan_configs()
    except Exception:
        overrides = {}

    plans = []
    for default_plan in DEFAULT_SUBSCRIPTION_PLANS:
        plan_copy = copy.deepcopy(default_plan)
        plan_id = plan_copy["id"]
        if plan_id in overrides:
            ov = overrides[plan_id]
            if ov.get("price_inr") is not None:
                plan_copy["price_inr"] = float(ov["price_inr"])
                plan_copy["price_paise"] = int(round(float(ov["price_inr"]) * 100))
            if ov.get("bills_limit") is not None:
                plan_copy["bills_limit"] = int(ov["bills_limit"])
                plan_copy["is_unlimited"] = int(ov["bills_limit"]) < 0
            if ov.get("name"):
                plan_copy["name"] = str(ov["name"])
            if ov.get("duration_days"):
                plan_copy["duration_days"] = int(ov["duration_days"])
        plans.append(plan_copy)
    return plans

def get_plan_by_id(plan_id: Optional[str]) -> Dict[str, Any]:
    """Retrieves authoritative plan details by ID."""
    canonical = resolve_plan_id(plan_id)
    plans = get_subscription_plans()
    for p in plans:
        if p["id"] == canonical:
            return p
    return copy.deepcopy(DEFAULT_SUBSCRIPTION_PLANS[0])
