import unittest
from datetime import datetime, timezone
from app.core import db
from app.core.security import CurrentUser
from app.api.usage import get_user_usage_data, get_user_daily_limit, get_user_quota_mode

class TestStaffEntitlementFix(unittest.TestCase):
    def test_current_user_staff_attributes(self):
        user = CurrentUser(
            id="test-staff-1",
            email="staff@example.com",
            role="STAFF",
            full_name="Staff Test"
        )
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_gold)
        self.assertTrue(user.is_unlimited)
        self.assertTrue(user.has_quota_bypass)

    def test_usage_data_for_staff(self):
        user = CurrentUser(
            id="test-staff-1",
            email="staff@example.com",
            role="STAFF",
            is_unlimited=True,
            full_name="Staff Test"
        )
        self.assertEqual(get_user_daily_limit(user), 999999)
        self.assertEqual(get_user_quota_mode(user), "UNLIMITED")
        usage = get_user_usage_data(user)
        self.assertTrue(usage.is_unlimited)
        self.assertEqual(usage.daily_limit, 999999)
        self.assertEqual(usage.effective_daily_quota, 999999)
        self.assertEqual(usage.bills_remaining_today, 999999)
        self.assertEqual(usage.account_status, "Staff Membership (Unlimited)")

    def test_get_staff_membership_by_email_fallback(self):
        # kangrahub622@gmail.com should be found even if an alternate user_id is queried
        mem = db.get_staff_membership_with_status_eval(
            user_id="arbitrary-alt-id",
            user_email="kangrahub622@gmail.com",
            server_now_utc=datetime.now(timezone.utc)
        )
        self.assertIsNotNone(mem)
        self.assertTrue(mem.get("is_active"))
        self.assertEqual(mem.get("user_email"), "kangrahub622@gmail.com")

if __name__ == "__main__":
    unittest.main()
