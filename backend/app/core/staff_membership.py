"""
Staff Membership Engine & The One Exact 30-Day IST Midnight Rule
Kangra Hub — Sales & Purchase
Oct 5, 2026 · PRD: Razorpay Staff Membership (Rs 499, Manual Renewal)

Rule (Section 4):
1. Take the trusted server/database timestamp of verified payment (in UTC) and convert to its IST calendar date: start_date.
2. The membership is valid for 30 IST calendar days: start_date is day 1 and start_date + 29 days is the last valid day.
3. membership_expires_at = 00:00:00 IST on start_date + 30 days, stored as a UTC timestamp (timestamptz). Exclusive boundary.
4. Access is allowed while server_now < membership_expires_at, and denied when server_now >= membership_expires_at.

Display Wording (Section 4):
"Valid until end of {last valid day} (expires 12:00 AM IST on {next day})"
Example: "Valid until end of 3 Nov 2026 (expires 12:00 AM IST on 4 Nov 2026)"
"""

from datetime import datetime, date, time, timedelta, timezone
from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger("kangra_hub.staff_membership")

# Fixed Asia/Kolkata (IST) Timezone: UTC + 05:30
IST = timezone(timedelta(hours=5, minutes=30))

STAFF_MEMBERSHIP_PRICE_INR = 499.0
STAFF_MEMBERSHIP_PRICE_PAISE = 49900
STAFF_MEMBERSHIP_DURATION_DAYS = 30


def ensure_utc(dt: Optional[datetime]) -> datetime:
    """Ensures a datetime object is timezone-aware in UTC."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_iso_to_utc(iso_str: Optional[str]) -> Optional[datetime]:
    """Safely parses an ISO string into a UTC datetime object."""
    if not iso_str:
        return None
    try:
        clean = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return ensure_utc(dt)
    except Exception as e:
        logger.warning(f"Failed to parse datetime '{iso_str}': {e}")
        return None


def format_ist_date(d: date) -> str:
    """
    Formats an IST calendar date as 'D Mon YYYY' (e.g., '3 Nov 2026' or '4 Nov 2026').
    """
    # %b gives short month name (Jan, Feb, Mar, etc.)
    return f"{d.day} {d.strftime('%b')} {d.year}"


def format_expiry_display(last_valid_day: date, next_day: date) -> str:
    """
    Returns the exact wording mandated by Section 4:
    'Valid until end of {last valid day} (expires 12:00 AM IST on {next day})'
    """
    last_str = format_ist_date(last_valid_day)
    next_str = format_ist_date(next_day)
    return f"Valid until end of {last_str} (expires 12:00 AM IST on {next_str})"


def compute_initial_membership(payment_verified_utc: datetime) -> Dict[str, Any]:
    """
    Computes exact 30-day membership boundaries starting from verified payment date.
    
    1. start_date = payment_verified_utc in IST calendar date (day 1)
    2. last_valid_day = start_date + 29 days (30 days total)
    3. next_day = start_date + 30 days
    4. membership_expires_at = 00:00:00 IST on next_day, stored in UTC
    """
    verified_utc = ensure_utc(payment_verified_utc)
    dt_ist = verified_utc.astimezone(IST)
    start_date = dt_ist.date()

    last_valid_day = start_date + timedelta(days=29)
    next_day = start_date + timedelta(days=30)

    # 12:00:00 AM IST on next_day
    expires_at_ist = datetime.combine(next_day, time(0, 0, 0), tzinfo=IST)
    expires_at_utc = expires_at_ist.astimezone(timezone.utc)

    return {
        "start_date": start_date.isoformat(),
        "last_valid_day": last_valid_day.isoformat(),
        "next_day": next_day.isoformat(),
        "membership_started_at": verified_utc.isoformat(),
        "membership_expires_at": expires_at_utc.isoformat(),
        "expires_at_ist": expires_at_ist.isoformat(),
        "expires_at_utc_dt": expires_at_utc,
        "display_wording": format_expiry_display(last_valid_day, next_day),
        "last_valid_day_formatted": format_ist_date(last_valid_day),
        "next_day_formatted": format_ist_date(next_day)
    }


def compute_renewal_membership(
    existing_expires_at_utc: datetime,
    payment_captured_utc: datetime,
    payment_verified_utc: datetime
) -> Dict[str, Any]:
    """
    Computes membership renewal boundaries according to Section 5:
    
    - Active Staff renews before expiry:
      Decided by Razorpay's trusted captured time.
      If payment_captured_utc < existing_expires_at_utc:
        Do not restart from payment date.
        new_expiry = existing_expiry + 30 IST calendar days.
        User never loses already-paid time!
        renewal_type = 'EARLY_RENEWAL'
        
    - Expired Staff renews after expiry:
      If payment_captured_utc >= existing_expires_at_utc:
        Start new period from verified payment date using section 4 rule.
        Do not restore old expired period or add to old expired timestamp.
        renewal_type = 'RENEWAL_AFTER_EXPIRY'
    """
    existing_utc = ensure_utc(existing_expires_at_utc)
    captured_utc = ensure_utc(payment_captured_utc)
    verified_utc = ensure_utc(payment_verified_utc)

    # Check if captured before existing expiry boundary
    if captured_utc < existing_utc:
        # Renewal before expiry: Add 30 IST calendar days to existing expiry
        existing_ist = existing_utc.astimezone(IST)
        new_expires_at_ist = existing_ist + timedelta(days=STAFF_MEMBERSHIP_DURATION_DAYS)
        new_expires_at_utc = new_expires_at_ist.astimezone(timezone.utc)

        new_next_day = new_expires_at_ist.date()
        new_last_valid_day = new_next_day - timedelta(days=1)

        return {
            "renewal_type": "EARLY_RENEWAL",
            "previous_expiry": existing_utc.isoformat(),
            "new_expiry": new_expires_at_utc.isoformat(),
            "new_expires_at_utc_dt": new_expires_at_utc,
            "last_valid_day": new_last_valid_day.isoformat(),
            "next_day": new_next_day.isoformat(),
            "display_wording": format_expiry_display(new_last_valid_day, new_next_day),
            "last_valid_day_formatted": format_ist_date(new_last_valid_day),
            "next_day_formatted": format_ist_date(new_next_day),
            "days_added": STAFF_MEMBERSHIP_DURATION_DAYS
        }
    else:
        # Renewal after expiry: Start new period from verified payment server date
        init_data = compute_initial_membership(verified_utc)
        return {
            "renewal_type": "RENEWAL_AFTER_EXPIRY",
            "previous_expiry": existing_utc.isoformat(),
            "new_expiry": init_data["membership_expires_at"],
            "new_expires_at_utc_dt": init_data["expires_at_utc_dt"],
            "last_valid_day": init_data["last_valid_day"],
            "next_day": init_data["next_day"],
            "display_wording": init_data["display_wording"],
            "last_valid_day_formatted": init_data["last_valid_day_formatted"],
            "next_day_formatted": init_data["next_day_formatted"],
            "days_added": STAFF_MEMBERSHIP_DURATION_DAYS
        }


def is_membership_active(expires_at_utc: datetime, server_now_utc: Optional[datetime] = None) -> bool:
    """
    Exclusive boundary check (Section 4):
    Access allowed while server_now < membership_expires_at.
    Denied when server_now >= membership_expires_at.
    """
    now_utc = ensure_utc(server_now_utc)
    exp_utc = ensure_utc(expires_at_utc)
    return now_utc < exp_utc


def get_notification_milestone(
    expires_at_utc: datetime,
    server_now_utc: Optional[datetime] = None
) -> Optional[str]:
    """
    Determines if an expiry notification milestone applies (Section 9):
    - 7 days before expiry: '7_DAYS_BEFORE'
    - 3 days before expiry: '3_DAYS_BEFORE'
    - 1 day before expiry:  '1_DAY_BEFORE'
    - At or after expiry:   'AT_EXPIRY'
    Evaluated with server time and IST calendar dates.
    """
    now_utc = ensure_utc(server_now_utc)
    exp_utc = ensure_utc(expires_at_utc)

    if now_utc >= exp_utc:
        return "AT_EXPIRY"

    now_ist_date = now_utc.astimezone(IST).date()
    exp_ist_date = exp_utc.astimezone(IST).date()

    diff_days = (exp_ist_date - now_ist_date).days

    if diff_days == 1:
        return "1_DAY_BEFORE"
    elif diff_days <= 3:
        return "3_DAYS_BEFORE"
    elif diff_days <= 7:
        return "7_DAYS_BEFORE"

    return None


def get_notification_message(milestone: str, display_wording: str) -> str:
    """
    Returns the exact notification messages defined in Section 9.
    """
    if milestone == "7_DAYS_BEFORE":
        return f"Friendly reminder: Your Staff Membership is {display_wording}. Renew now to maintain uninterrupted access."
    elif milestone == "3_DAYS_BEFORE":
        return f"Reminder: Your Staff Membership is {display_wording}. Renew early to keep all your remaining time."
    elif milestone == "1_DAY_BEFORE":
        return "Urgent reminder: Your Staff Membership expires tonight at 12:00 AM IST. Please renew your membership."
    elif milestone == "AT_EXPIRY":
        return "Your Staff Membership has expired. Please renew your membership to continue Staff benefits."
    return ""
