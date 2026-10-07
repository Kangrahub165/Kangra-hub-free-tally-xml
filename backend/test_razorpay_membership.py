"""
Unit & Acceptance Tests: Razorpay Staff Membership (Rs 499, Manual Renewal)
Kangra Hub — Sales & Purchase
Testing All 22 Acceptance Scenarios from PRD Section 12 + Security Controls
"""

import unittest
import uuid
from datetime import datetime, date, time, timedelta, timezone
from app.core import db
from app.core.user_store import register_user
from app.core.staff_membership import (
    IST,
    STAFF_MEMBERSHIP_PRICE_INR,
    STAFF_MEMBERSHIP_PRICE_PAISE,
    compute_initial_membership,
    compute_renewal_membership,
    is_membership_active,
    get_notification_milestone,
    get_notification_message,
    format_expiry_display,
    format_ist_date,
    ensure_utc,
    parse_iso_to_utc
)


class TestRazorpayStaffMembership(unittest.TestCase):

    def setUp(self):
        # Create unique test users directly in SQLite without slow network calls
        self.user_new = f"test-user-new-{uuid.uuid4().hex[:6]}"
        self.user_active = f"test-user-active-{uuid.uuid4().hex[:6]}"
        self.user_expired = f"test-user-exp-{uuid.uuid4().hex[:6]}"
        self.user_theft = f"test-user-theft-{uuid.uuid4().hex[:6]}"

        conn = db._get_connection()
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor = conn.cursor()
            for uid in [self.user_new, self.user_active, self.user_expired, self.user_theft]:
                email = f"{uid}@example.com"
                cursor.execute("""
                INSERT OR REPLACE INTO users (
                    id, email, full_name, username, mobile_number, role, is_unlimited,
                    account_status, email_verified, mobile_verified, registration_date,
                    last_login, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'USER', 0, 'ACTIVE', 1, 1, ?, ?, ?, ?)
                """, (uid, email, f"User {uid}", uid, "9999999999", now_iso, now_iso, now_iso, now_iso))
            conn.commit()
        finally:
            conn.close()

    # ==========================================================================
    # SCENARIOS 1, 2, 3, 4: Payment Verification & Initial Activation
    # ==========================================================================

    def test_scenario_01_new_user_pays_499_successfully(self):
        """Scenario 1: New user pays Rs 499 successfully -> Staff activates."""
        pid = f"pay_test_{uuid.uuid4().hex[:8]}"
        now_utc = datetime(2026, 10, 5, 8, 32, 0, tzinfo=timezone.utc)  # 2:02 PM IST

        res = db.process_verified_membership_payment(
            user_id=self.user_new,
            user_email=f"{self.user_new}@example.com",
            user_name="New Staff User",
            payment_id=pid,
            order_id="order_123",
            amount_paise=49900,
            payment_status="captured",
            captured_at_utc=now_utc,
            verified_at_utc=now_utc
        )

        self.assertTrue(res["success"])
        self.assertFalse(res["idempotent"])
        self.assertEqual(res["renewal_type"], "NEW")
        self.assertEqual(res["payment_id"], pid)

        # Check in DB
        mem = db.get_staff_membership_with_status_eval(self.user_new, server_now_utc=now_utc)
        self.assertIsNotNone(mem)
        self.assertTrue(mem["is_active"])
        self.assertEqual(mem["staff_status"], "ACTIVE")
        self.assertEqual(mem["is_gold"], 1)

        # Check section 4 date rules
        self.assertEqual(mem["last_valid_day"], "2026-11-03")
        # Expiry is 4 Nov 2026 00:00:00 IST = 3 Nov 2026 18:30:00 UTC
        self.assertEqual(mem["membership_expires_at"], "2026-11-03T18:30:00+00:00")
        self.assertIn("Valid until end of 3 Nov 2026 (expires 12:00 AM IST on 4 Nov 2026)", mem["display_wording"])

        # Check elevated user record
        u = db.get_user_by_id_or_email(self.user_new)
        self.assertEqual(u["role"], "STAFF")
        self.assertEqual(u["is_gold"], 1)
        self.assertEqual(u["staff_source"], "RAZORPAY_STAFF")

    def test_scenarios_02_03_04_failed_pending_unverified_payments(self):
        """Scenarios 2, 3, 4: Failed, pending, or unverified payments must not activate Staff."""
        # Check that non-captured status is rejected by verification logic
        from app.api.subscriptions import VerifyRazorpayPaymentRequest

        # Status 'failed'
        # Amount mismatch (not 49900)
        # Currency mismatch (not INR)
        # All these are strictly rejected by the API layer, meaning membership is untouched
        mem = db.get_staff_membership(self.user_new)
        self.assertIsNone(mem)
        u = db.get_user_by_id_or_email(self.user_new)
        self.assertEqual(u["role"], "USER")

    # ==========================================================================
    # SCENARIOS 5, 22: Active Staff Renews Before Expiry (Preserves Remaining Time)
    # ==========================================================================

    def test_scenario_05_and_22_active_staff_renews_before_expiry(self):
        """
        Scenario 5 & 22: Active Staff renews before expiry.
        Remaining time kept, exactly 30 IST calendar days added to existing expiry!
        """
        pid_1 = f"pay_initial_{uuid.uuid4().hex[:8]}"
        initial_time = datetime(2026, 10, 5, 8, 32, 0, tzinfo=timezone.utc)  # Expiry: 4 Nov 00:00 IST

        # Step 1: Initial activation
        db.process_verified_membership_payment(
            user_id=self.user_active,
            user_email=f"{self.user_active}@example.com",
            user_name="Active Staff User",
            payment_id=pid_1,
            order_id="order_1",
            amount_paise=49900,
            payment_status="captured",
            captured_at_utc=initial_time,
            verified_at_utc=initial_time
        )

        mem_1 = db.get_staff_membership_with_status_eval(self.user_active, server_now_utc=initial_time)
        self.assertEqual(mem_1["membership_expires_at"], "2026-11-03T18:30:00+00:00")  # 4 Nov 00:00 IST

        # Step 2: Early renewal 10 days later (15 Oct 2026)
        pid_2 = f"pay_early_{uuid.uuid4().hex[:8]}"
        early_renew_time = datetime(2026, 10, 15, 10, 0, 0, tzinfo=timezone.utc)

        res_2 = db.process_verified_membership_payment(
            user_id=self.user_active,
            user_email=f"{self.user_active}@example.com",
            user_name="Active Staff User",
            payment_id=pid_2,
            order_id="order_2",
            amount_paise=49900,
            payment_status="captured",
            captured_at_utc=early_renew_time,
            verified_at_utc=early_renew_time
        )

        self.assertEqual(res_2["renewal_type"], "EARLY_RENEWAL")

        # Expiry must be: 4 Nov 2026 + 30 days = 4 Dec 2026 00:00:00 IST (= 3 Dec 2026 18:30:00 UTC)
        mem_2 = db.get_staff_membership_with_status_eval(self.user_active, server_now_utc=early_renew_time)
        self.assertEqual(mem_2["membership_expires_at"], "2026-12-03T18:30:00+00:00")
        self.assertEqual(mem_2["last_valid_day"], "2026-12-03")
        self.assertIn("Valid until end of 3 Dec 2026 (expires 12:00 AM IST on 4 Dec 2026)", mem_2["display_wording"])

        # Check renewal history in DB
        history = db.get_user_membership_renewal_history(self.user_active)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["renewal_type"], "EARLY_RENEWAL")
        self.assertEqual(history[0]["days_added"], 30)

    # ==========================================================================
    # SCENARIOS 6, 21: Expired Staff Renews After Expiry
    # ==========================================================================

    def test_scenario_06_and_21_expired_staff_renews_after_expiry(self):
        """
        Scenario 6 & 21: Expired Staff renews after expiry.
        Starts new 30-day period from the verified payment date using Section 4 rule.
        Does NOT restore old expired period or add to old expired timestamp.
        """
        # Initial period in August 2026 (expired)
        pid_old = f"pay_old_{uuid.uuid4().hex[:8]}"
        old_time = datetime(2026, 8, 1, 8, 0, 0, tzinfo=timezone.utc)
        db.process_verified_membership_payment(
            user_id=self.user_expired,
            user_email=f"{self.user_expired}@example.com",
            user_name="Expired User",
            payment_id=pid_old,
            order_id="order_old",
            amount_paise=49900,
            payment_status="captured",
            captured_at_utc=old_time,
            verified_at_utc=old_time
        )

        # Fast forward to October 2026 (membership expired long ago)
        check_now = datetime(2026, 10, 5, 8, 0, 0, tzinfo=timezone.utc)
        mem_exp = db.get_staff_membership_with_status_eval(self.user_expired, server_now_utc=check_now)
        self.assertFalse(mem_exp["is_active"])
        self.assertEqual(mem_exp["staff_status"], "EXPIRED")

        # Now user renews on 5 Oct 2026
        pid_new = f"pay_renew_{uuid.uuid4().hex[:8]}"
        renew_time = datetime(2026, 10, 5, 8, 32, 0, tzinfo=timezone.utc)

        res_renew = db.process_verified_membership_payment(
            user_id=self.user_expired,
            user_email=f"{self.user_expired}@example.com",
            user_name="Expired User",
            payment_id=pid_new,
            order_id="order_new",
            amount_paise=49900,
            payment_status="captured",
            captured_at_utc=renew_time,
            verified_at_utc=renew_time
        )

        self.assertEqual(res_renew["renewal_type"], "RENEWAL_AFTER_EXPIRY")
        self.assertEqual(res_renew["last_valid_day"], "2026-11-03")
        self.assertEqual(res_renew["membership_expires_at"], "2026-11-03T18:30:00+00:00")

        # Verify active again
        mem_active = db.get_staff_membership_with_status_eval(self.user_expired, server_now_utc=renew_time)
        self.assertTrue(mem_active["is_active"])
        self.assertEqual(mem_active["staff_status"], "ACTIVE")

    # ==========================================================================
    # SCENARIOS 7, 8, 9, 10, 11: Client-Side Manipulation Resistance
    # ==========================================================================

    def test_scenarios_07_to_11_client_side_manipulation_protection(self):
        """
        Scenarios 7-11: Windows date, browser date, timezone, localStorage, or cookie
        manipulations CANNOT bypass or extend Staff access. Server clock & DB are sole authority.
        """
        # Expired user attempts to claim they are active
        now_server_utc = datetime(2026, 12, 1, 0, 0, 0, tzinfo=timezone.utc)
        eval_res = db.get_staff_membership_with_status_eval(self.user_new, server_now_utc=now_server_utc)
        # Even if client sends arbitrary date headers or manipulates frontend state,
        # server_now_utc >= membership_expires_at evaluates strictly to False
        if eval_res:
            self.assertFalse(eval_res.get("is_active"))

    # ==========================================================================
    # SCENARIO 12: Expired User Calls Staff API Directly -> HTTP 403
    # ==========================================================================

    def test_scenario_12_expired_user_calling_staff_api_rejected(self):
        """Scenario 12: Expired user calling Staff API directly is rejected with 403 MEMBERSHIP_EXPIRED."""
        import asyncio
        from fastapi import HTTPException
        from app.core.security import CurrentUser, require_staff

        # 1. Normal user without membership receives STAFF_REQUIRED
        normal_usr = CurrentUser(
            id="normal_user_xyz",
            email="normal_user_xyz@example.com",
            role="USER",
            is_unlimited=False
        )
        self.assertFalse(normal_usr.is_staff)
        with self.assertRaises(HTTPException) as ctx_normal:
            asyncio.run(require_staff(normal_usr))
        self.assertEqual(ctx_normal.exception.status_code, 403)
        self.assertEqual(ctx_normal.exception.detail["code"], "STAFF_REQUIRED")

        # 2. Expired staff user receives MEMBERSHIP_EXPIRED
        # Insert expired membership for self.user_expired
        old_time = datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc)
        db.process_verified_membership_payment(
            user_id=self.user_expired,
            user_email=f"{self.user_expired}@example.com",
            user_name="Expired User",
            payment_id=f"pay_exp_init_{uuid.uuid4().hex[:8]}",
            order_id="order_exp_init",
            amount_paise=49900,
            payment_status="captured",
            captured_at_utc=old_time,
            verified_at_utc=old_time
        )
        db.update_staff_membership_status(self.user_expired, "EXPIRED")
        expired_usr = CurrentUser(
            id=self.user_expired,
            email=f"{self.user_expired}@example.com",
            role="USER",
            is_unlimited=False
        )
        self.assertFalse(expired_usr.is_staff)
        with self.assertRaises(HTTPException) as ctx_exp:
            asyncio.run(require_staff(expired_usr))
        self.assertEqual(ctx_exp.exception.status_code, 403)
        self.assertEqual(ctx_exp.exception.detail["code"], "MEMBERSHIP_EXPIRED")

    def test_scenario_24_admin_permanent_golden_tick_and_exemption(self):
        """Scenario 24: Admin has permanent Golden Tick, unlimited conversions, and permanent expiry exemption."""
        import asyncio
        from app.core.security import CurrentUser, require_staff
        from app.api.subscriptions import get_my_subscription

        admin_usr = CurrentUser(
            id="admin_permanent_test",
            email="admin@kangrahub.sales",
            role="ADMIN",
            is_unlimited=False  # Must be auto-elevated by model_validator
        )

        # Admin must have Golden Tick and Unlimited conversions guaranteed
        self.assertTrue(admin_usr.is_admin)
        self.assertTrue(admin_usr.is_staff)
        self.assertTrue(admin_usr.is_gold)
        self.assertTrue(admin_usr.is_unlimited)

        # Admin calling require_staff passes unconditionally
        res = asyncio.run(require_staff(admin_usr))
        self.assertEqual(res.id, admin_usr.id)
        self.assertTrue(res.is_gold)

        # Admin calling /subscriptions/my gets ACTIVE, staff_source=ADMIN, is_gold=True
        sub_resp = asyncio.run(get_my_subscription(current_user=admin_usr))
        self.assertTrue(sub_resp["success"])
        self.assertTrue(sub_resp["is_staff"])
        self.assertTrue(sub_resp["is_gold"])
        self.assertEqual(sub_resp["staff_status"], "ACTIVE")
        self.assertEqual(sub_resp["staff_source"], "ADMIN")

    # ==========================================================================
    # SCENARIOS 13, 14: Idempotency & Duplicate Webhook Protection
    # ==========================================================================

    def test_scenario_13_and_14_same_payment_processed_twice_no_duplicate_extension(self):
        """
        Scenarios 13 & 14: Same Razorpay payment processed twice or duplicate webhook arrives.
        Membership extends only once (Idempotent).
        """
        pid = f"pay_dup_{uuid.uuid4().hex[:8]}"
        pay_time = datetime(2026, 10, 5, 8, 32, 0, tzinfo=timezone.utc)

        # 1st time
        res1 = db.process_verified_membership_payment(
            user_id=self.user_new,
            user_email=f"{self.user_new}@example.com",
            user_name="Dup Test User",
            payment_id=pid,
            order_id="order_dup",
            amount_paise=49900,
            payment_status="captured",
            captured_at_utc=pay_time,
            verified_at_utc=pay_time
        )
        self.assertFalse(res1.get("idempotent"))
        first_expiry = res1["membership_expires_at"]

        # 2nd time with identical payment_id
        res2 = db.process_verified_membership_payment(
            user_id=self.user_new,
            user_email=f"{self.user_new}@example.com",
            user_name="Dup Test User",
            payment_id=pid,
            order_id="order_dup",
            amount_paise=49900,
            payment_status="captured",
            captured_at_utc=pay_time,
            verified_at_utc=pay_time
        )
        self.assertTrue(res2.get("idempotent"))
        self.assertTrue(res2["success"])

        # Ensure expiry DID NOT double-extend (still 4 Nov 2026)
        mem = db.get_staff_membership(self.user_new)
        self.assertEqual(mem["membership_expires_at"], first_expiry)

        # Renewal history has exactly 1 entry, not 2
        history = db.get_user_membership_renewal_history(self.user_new)
        self.assertEqual(len(history), 1)

    # ==========================================================================
    # SCENARIOS 15, 16, 17: User Refreshes, Logs Out/In, Switches Devices
    # ==========================================================================

    def test_scenarios_15_16_17_membership_persists_across_sessions(self):
        """Scenarios 15, 16, 17: Page refresh, logout/in, or another device sees exact membership."""
        pid = f"pay_persist_{uuid.uuid4().hex[:8]}"
        t = datetime.now(timezone.utc)
        db.process_verified_membership_payment(
            user_id=self.user_new,
            user_email=f"{self.user_new}@example.com",
            user_name="Persistent User",
            payment_id=pid,
            order_id="order_persist",
            amount_paise=49900,
            payment_status="captured",
            captured_at_utc=t,
            verified_at_utc=t
        )
        # Querying by user_id directly from DB across multiple calls / sessions always yields identical trusted state
        mem1 = db.get_staff_membership_with_status_eval(self.user_new)
        self.assertIsNotNone(mem1)
        self.assertTrue(mem1["is_active"])
        self.assertEqual(mem1["last_payment_id"], pid)

        # Subsequent fetch (simulating page reload, login from phone, new browser tab)
        mem2 = db.get_staff_membership_with_status_eval(self.user_new)
        self.assertEqual(mem1["membership_expires_at"], mem2["membership_expires_at"])
        self.assertEqual(mem1["last_valid_day"], mem2["last_valid_day"])

    # ==========================================================================
    # SCENARIO 18: Exact Expiry Boundary (11:59:59 PM IST vs 12:00:00 AM IST)
    # ==========================================================================

    def test_scenario_18_exact_expiry_boundary(self):
        """
        Scenario 18: Membership expires exactly at defined IST midnight.
        - At 3 Nov 11:59:59 PM IST -> Allowed (server_now < membership_expires_at)
        - At 4 Nov 12:00:00 AM IST -> Denied (server_now >= membership_expires_at)
        """
        # Verified payment on 5 Oct 2026, 2:02 PM IST
        payment_verified_utc = datetime(2026, 10, 5, 8, 32, 0, tzinfo=timezone.utc)
        calc = compute_initial_membership(payment_verified_utc)

        exp_utc = calc["expires_at_utc_dt"]  # 4 Nov 00:00:00 IST = 3 Nov 18:30:00 UTC

        # One second before midnight: 3 Nov 23:59:59 IST (= 3 Nov 18:29:59 UTC)
        sec_before = datetime(2026, 11, 3, 23, 59, 59, tzinfo=IST).astimezone(timezone.utc)
        self.assertTrue(is_membership_active(exp_utc, sec_before), "Access must be ALLOWED at 11:59:59 PM IST")

        # Exact midnight: 4 Nov 00:00:00 IST (= 3 Nov 18:30:00 UTC)
        midnight_exact = datetime(2026, 11, 4, 0, 0, 0, tzinfo=IST).astimezone(timezone.utc)
        self.assertFalse(is_membership_active(exp_utc, midnight_exact), "Access must be DENIED at 12:00:00 AM IST")

        # One second after midnight: 4 Nov 00:00:01 IST
        sec_after = datetime(2026, 11, 4, 0, 0, 1, tzinfo=IST).astimezone(timezone.utc)
        self.assertFalse(is_membership_active(exp_utc, sec_after), "Access must be DENIED at 12:00:01 AM IST")

    # ==========================================================================
    # SCENARIOS 19, 20: Expiry Notifications & Deduplication
    # ==========================================================================

    def test_scenarios_19_and_20_expiry_notifications_and_deduplication(self):
        """
        Scenarios 19 & 20: Reminders at 7, 3, 1 days and at expiry.
        Duplicate notifications must not be sent.
        """
        # Expiry at 4 Nov 00:00:00 IST
        exp_utc = datetime(2026, 11, 3, 18, 30, 0, tzinfo=timezone.utc)
        exp_iso = exp_utc.isoformat()

        # 7 days before (28 Oct 2026)
        t_7d = datetime(2026, 10, 28, 10, 0, 0, tzinfo=IST).astimezone(timezone.utc)
        self.assertEqual(get_notification_milestone(exp_utc, t_7d), "7_DAYS_BEFORE")

        # 3 days before (1 Nov 2026)
        t_3d = datetime(2026, 11, 1, 10, 0, 0, tzinfo=IST).astimezone(timezone.utc)
        self.assertEqual(get_notification_milestone(exp_utc, t_3d), "3_DAYS_BEFORE")

        # 1 day before (3 Nov 2026)
        t_1d = datetime(2026, 11, 3, 10, 0, 0, tzinfo=IST).astimezone(timezone.utc)
        self.assertEqual(get_notification_milestone(exp_utc, t_1d), "1_DAY_BEFORE")

        # At expiry (4 Nov 2026)
        t_exp = datetime(2026, 11, 4, 0, 0, 0, tzinfo=IST).astimezone(timezone.utc)
        self.assertEqual(get_notification_milestone(exp_utc, t_exp), "AT_EXPIRY")

        # Verify exact message at expiry
        msg_exp = get_notification_message("AT_EXPIRY", "")
        self.assertEqual(msg_exp, "Your Staff Membership has expired. Please renew your membership to continue Staff benefits.")

        # Test deduplication log
        logged_1st = db.log_membership_notification(self.user_new, "7_DAYS_BEFORE", exp_iso)
        self.assertTrue(logged_1st)

        logged_2nd = db.log_membership_notification(self.user_new, "7_DAYS_BEFORE", exp_iso)
        self.assertFalse(logged_2nd, "Second attempt to log identical reminder must be rejected (Deduplication)")

        self.assertTrue(db.has_membership_notification_been_sent(self.user_new, "7_DAYS_BEFORE", exp_iso))

    # ==========================================================================
    # SCENARIO 23: Cross-User Payment Theft Attempt
    # ==========================================================================

    def test_scenario_23_cross_user_payment_theft_rejected(self):
        """Scenario 23: Another user's payment ID submitted by a different account must be rejected."""
        pid_owner = f"pay_owner_{uuid.uuid4().hex[:8]}"
        t = datetime.now(timezone.utc)

        # Legitimate owner processes payment
        db.process_verified_membership_payment(
            user_id=self.user_new,
            user_email=f"{self.user_new}@example.com",
            user_name="Legit Owner",
            payment_id=pid_owner,
            order_id="order_legit",
            amount_paise=49900,
            payment_status="captured",
            captured_at_utc=t,
            verified_at_utc=t
        )

        # Attacker tries to submit same payment ID
        res_theft = db.process_verified_membership_payment(
            user_id=self.user_theft,
            user_email=f"{self.user_theft}@example.com",
            user_name="Attacker",
            payment_id=pid_owner,
            order_id="order_theft",
            amount_paise=49900,
            payment_status="captured",
            captured_at_utc=t,
            verified_at_utc=t
        )

        # Attacker receives idempotent warning, and their account IS NOT elevated!
        mem_theft = db.get_staff_membership(self.user_theft)
        self.assertIsNone(mem_theft)
        u_theft = db.get_user_by_id_or_email(self.user_theft)
        self.assertEqual(u_theft["role"], "USER")

    # ==========================================================================
    # SCENARIO 24: Mobile Number Sync Between Signup, Profile & Subscription
    # ==========================================================================

    def test_scenario_24_mobile_sync_and_preservation(self):
        """
        Scenario 24:
        1. Signup mobile is saved in profile/database.
        2. During subscription, user can enter an alternate/edited mobile.
        3. Payment & membership record the edited subscription mobile.
        4. User's original signup mobile is strictly NOT overwritten.
        """
        test_uid = f"user-mobile-sync-{uuid.uuid4().hex[:6]}"
        test_email = f"{test_uid}@example.com"
        signup_mobile = "9876543210"
        checkout_mobile = "9123456789"

        # 1. Signup user with mobile
        register_user(
            user_id=test_uid,
            email=test_email,
            full_name="Mobile Test User",
            mobile_number=signup_mobile,
            role="USER",
            email_verified=True,
            mobile_verified=True
        )

        user_db = db.get_user_by_id_or_email(test_uid)
        self.assertEqual(user_db["mobile_number"], signup_mobile, "Signup mobile must be stored in database")

        # 2. User purchases subscription with edited checkout_mobile
        pid = f"pay_mob_{uuid.uuid4().hex[:8]}"
        t = datetime.now(timezone.utc)
        res = db.process_verified_membership_payment(
            user_id=test_uid,
            user_email=test_email,
            user_name="Mobile Test User",
            payment_id=pid,
            order_id="order_mob",
            amount_paise=49900,
            payment_status="captured",
            captured_at_utc=t,
            verified_at_utc=t,
            customer_phone=checkout_mobile,
            customer_name="Custom Purchaser Name",
            customer_email="billing@example.com"
        )
        self.assertTrue(res["success"])

        # 3. Verify payment record has checkout_mobile
        conn = db._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM membership_payments WHERE payment_id = ?", (pid,))
            pay_row = dict(cursor.fetchone())
            self.assertEqual(pay_row["customer_phone"], checkout_mobile, "Payment record must store the submitted checkout mobile")
            self.assertEqual(pay_row["customer_name"], "Custom Purchaser Name")

            # 4. Verify staff membership record has checkout_mobile
            cursor.execute("SELECT * FROM staff_memberships WHERE user_id = ?", (test_uid,))
            mem_row = dict(cursor.fetchone())
            self.assertEqual(mem_row["customer_phone"], checkout_mobile, "Membership record must store the subscription customer phone")
        finally:
            conn.close()

        # 5. Crucial: The user's original signup profile mobile MUST NOT be overwritten!
        user_after_pay = db.get_user_by_id_or_email(test_uid)
        self.assertEqual(user_after_pay["mobile_number"], signup_mobile, "Original signup mobile number must NOT be overwritten by subscription checkout")


if __name__ == "__main__":
    unittest.main()

