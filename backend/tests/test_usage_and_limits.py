import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.security import CurrentUser
from app.api.usage import (
    get_user_usage_data,
    record_user_page_usage,
    _IN_MEMORY_DAILY_USAGE
)

def test_daily_free_limit_calculation():
    # Setup test user
    user = CurrentUser(id="test-user-limit", email="limit@test.com", role="USER", is_unlimited=False)
    
    # Clean test state
    for k in list(_IN_MEMORY_DAILY_USAGE.keys()):
        if k.startswith("test-user-limit:"):
            del _IN_MEMORY_DAILY_USAGE[k]

    usage = get_user_usage_data(user)
    assert usage.daily_limit == 50
    assert usage.pages_used_today == 0
    assert usage.pages_remaining_today == 50
    assert usage.is_unlimited is False

    # Simulate 12 page conversion
    record_user_page_usage(user, 12)
    usage = get_user_usage_data(user)
    assert usage.pages_used_today == 12
    assert usage.pages_remaining_today == 38

    # Simulate 20 page conversion
    record_user_page_usage(user, 20)
    usage = get_user_usage_data(user)
    assert usage.pages_used_today == 32
    assert usage.pages_remaining_today == 18

    # Simulate 18 page conversion (now 50/50 used)
    record_user_page_usage(user, 18)
    usage = get_user_usage_data(user)
    assert usage.pages_used_today == 50
    assert usage.pages_remaining_today == 0

def test_unlimited_user_bypass():
    unlimited_user = CurrentUser(id="test-unlim", email="unlim@test.com", role="USER", is_unlimited=True)
    usage = get_user_usage_data(unlimited_user)
    assert usage.is_unlimited is True
    assert usage.pages_remaining_today > 50

def test_admin_unlimited_bypass():
    admin_user = CurrentUser(id="test-admin", email="admin@test.com", role="ADMIN", is_unlimited=False)
    usage = get_user_usage_data(admin_user)
    assert usage.is_unlimited is True
    assert usage.account_status == "Admin Unlimited"
