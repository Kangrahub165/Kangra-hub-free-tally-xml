import os
import sqlite3
import json
import uuid
import logging
import threading
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional

logger = logging.getLogger("kangra_hub.db")

_LOCK = threading.RLock()

# Data directory path
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
DB_PATH = os.path.join(DATA_DIR, "kangra_hub.db")

def _get_connection() -> sqlite3.Connection:
    """Returns a connection to SQLite with row_factory set to sqlite3.Row."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes SQLite schema and indexes, and seeds standard platform accounts if missing."""
    with _LOCK:
        os.makedirs(DATA_DIR, exist_ok=True)
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            # Enable WAL mode for high concurrency
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")

            # 1. Users Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                full_name TEXT,
                username TEXT,
                mobile_number TEXT,
                role TEXT DEFAULT 'USER',
                is_unlimited INTEGER DEFAULT 0,
                account_status TEXT DEFAULT 'ACTIVE',
                email_verified INTEGER DEFAULT 1,
                mobile_verified INTEGER DEFAULT 0,
                registration_date TEXT,
                last_login TEXT,
                suspended_at TEXT,
                suspension_reason TEXT,
                suspension_delete_at TEXT,
                suspension_reviewed_at TEXT,
                suspension_reviewed_by TEXT,
                avatar_url TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            """)

            # 2. Daily Page Usage Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_usage (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                date_str TEXT NOT NULL,
                pages_used INTEGER DEFAULT 0,
                updated_at TEXT,
                UNIQUE(user_id, date_str)
            );
            """)

            # 3. Conversions Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                user_email TEXT,
                file_name TEXT,
                bank_name TEXT,
                total_pdf_pages INTEGER DEFAULT 0,
                pages_processed INTEGER DEFAULT 0,
                pages_skipped INTEGER DEFAULT 0,
                free_quota_used INTEGER DEFAULT 0,
                additional_quota_used INTEGER DEFAULT 0,
                transaction_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'COMPLETED',
                is_partial_conversion INTEGER DEFAULT 0,
                created_at TEXT,
                metadata_json TEXT
            );
            """)

            # 4. User Additional Pages Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_additional_pages (
                user_id TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                updated_at TEXT
            );
            """)

            # 5. User Custom Quotas Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_custom_quotas (
                user_id TEXT PRIMARY KEY,
                quota INTEGER,
                updated_at TEXT
            );
            """)

            # 6. Payment Requests Table (Permanent SQLite persistence)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_requests (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                user_email TEXT NOT NULL,
                user_name TEXT,
                requested_pages INTEGER NOT NULL,
                granted_pages INTEGER NOT NULL,
                amount_paid REAL NOT NULL,
                job_id TEXT,
                notes TEXT,
                screenshot_path TEXT,
                screenshot_filename TEXT,
                status TEXT DEFAULT 'PENDING',
                created_at TEXT,
                updated_at TEXT,
                admin_notes TEXT,
                approved_by TEXT,
                approved_at TEXT
            );
            """)

            # 7. Page Credit Audit Log Table (Permanent server-side audit traceability)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS page_credit_audit_log (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                conversion_id TEXT,
                payment_id TEXT,
                amount REAL DEFAULT 0.0,
                pages_requested INTEGER DEFAULT 0,
                pages_approved INTEGER DEFAULT 0,
                pages_credited INTEGER DEFAULT 0,
                admin_id TEXT,
                source TEXT DEFAULT 'AUTO_PAYMENT',
                timestamp TEXT,
                previous_balance INTEGER DEFAULT 0,
                new_balance INTEGER DEFAULT 0
            );
            """)

            # 8. User Activity Logs Table (PRD Section 8 - WHO did WHAT, WHEN, WHERE)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_activity_logs (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                user_email TEXT,
                action TEXT NOT NULL,
                module TEXT,
                resource_id TEXT,
                status TEXT DEFAULT 'SUCCESS',
                metadata TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TEXT NOT NULL
            );
            """)

            # 9. Security Audit Logs Table (PRD Section 18 - Security & Administrative events)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_audit_logs (
                id TEXT PRIMARY KEY,
                actor_id TEXT,
                actor_email TEXT,
                event_type TEXT NOT NULL,
                severity TEXT DEFAULT 'INFO',
                module TEXT,
                details TEXT,
                ip_address TEXT,
                created_at TEXT NOT NULL
            );
            """)

            # 10. Ratings & Reviews Table (PRD Section 9, 10, 11, 12 - 1 to 5 stars + moderation)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ratings_reviews (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                user_name TEXT,
                user_email TEXT,
                rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
                review_text TEXT,
                moderation_status TEXT DEFAULT 'APPROVED',
                moderator_notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # 11. Admin Real-Time Notifications Table (PRD Section 13, 14)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_notifications (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT DEFAULT 'INFO',
                is_read INTEGER DEFAULT 0,
                related_user_id TEXT,
                created_at TEXT NOT NULL
            );
            """)

            # 12. Developer Change Requests Table (PRD Section 16, 17)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS developer_change_requests (
                id TEXT PRIMARY KEY,
                developer_email TEXT NOT NULL,
                change_title TEXT NOT NULL,
                description TEXT,
                diff_content TEXT,
                status TEXT DEFAULT 'PENDING',
                reviewed_by TEXT,
                reviewed_at TEXT,
                created_at TEXT NOT NULL
            );
            """)

            # 13. Pending Signups & OTP Verification State (PRD 10-Minute Recovery)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_signups (
                email TEXT PRIMARY KEY,
                mobile_number TEXT NOT NULL,
                full_name TEXT,
                gender TEXT,
                password_hash TEXT,
                otp_issued_at REAL NOT NULL,
                otp_expires_at REAL NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # 14. Devices Table (PRD Section 6 Anti-Abuse & Device Pool)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                user_id TEXT,
                ip_address TEXT,
                user_agent TEXT,
                is_whitelisted INTEGER DEFAULT 0,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                UNIQUE(device_id, user_id)
            );
            """)

            # 15. Converted Bills Table (PRD Section 5 Bill Identity & Deduplication)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS converted_bills (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                bill_number TEXT,
                bill_date TEXT,
                company_name TEXT,
                total_amount REAL DEFAULT 0.0,
                fingerprint_hash TEXT NOT NULL,
                page_count INTEGER DEFAULT 1,
                date_ist TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # 16. Subscriptions Table (PRD Section 8, 9 Paid Verified Gold Staff)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                user_email TEXT,
                user_name TEXT,
                plan_name TEXT DEFAULT 'STAFF_MONTHLY',
                amount REAL DEFAULT 299.0,
                status TEXT DEFAULT 'PENDING_APPROVAL',
                payment_method TEXT DEFAULT 'UPI_MANUAL',
                gateway_ref TEXT,
                txn_id TEXT,
                screenshot_path TEXT,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                grace_until TEXT,
                autopay INTEGER DEFAULT 0,
                approved_by TEXT,
                approved_at TEXT,
                admin_notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # 17. Staff Audit Logs Table (PRD Section 7, 8 Staff Group Management)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS staff_audit_logs (
                id TEXT PRIMARY KEY,
                admin_id TEXT NOT NULL,
                admin_name TEXT,
                action TEXT NOT NULL,
                target_user_id TEXT NOT NULL,
                target_user_email TEXT,
                details TEXT,
                created_at TEXT NOT NULL
            );
            """)

            # 18. Razorpay Staff Memberships Table (PRD: Rs 499, Manual Renewal, IST Midnight Expiry)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS staff_memberships (
                id TEXT PRIMARY KEY,
                user_id TEXT UNIQUE NOT NULL,
                user_email TEXT,
                user_name TEXT,
                customer_phone TEXT,
                staff_status TEXT DEFAULT 'ACTIVE',
                membership_started_at TEXT NOT NULL,
                membership_expires_at TEXT NOT NULL,
                last_valid_day TEXT NOT NULL,
                last_payment_id TEXT,
                is_gold INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # 19. Razorpay Membership Payments Table (Unique payment_id prevents duplicate processing/replay)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS membership_payments (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                user_email TEXT,
                payment_id TEXT UNIQUE NOT NULL,
                order_id TEXT,
                payment_amount INTEGER NOT NULL DEFAULT 49900,
                currency TEXT DEFAULT 'INR',
                payment_status TEXT NOT NULL,
                payment_verified_at TEXT NOT NULL,
                captured_at TEXT,
                raw_response TEXT,
                created_at TEXT NOT NULL,
                customer_phone TEXT,
                customer_name TEXT
            );
            """)

            # 20. Membership Renewal History Table (Tracks previous and new expiries per payment)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS membership_renewal_history (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                payment_id TEXT NOT NULL,
                renewal_type TEXT NOT NULL,
                previous_expiry TEXT,
                new_expiry TEXT NOT NULL,
                days_added INTEGER DEFAULT 30,
                created_at TEXT NOT NULL
            );
            """)

            # 21. Membership Expiry Notification Logs Table (Prevents duplicate reminder deliveries)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS membership_notification_logs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                notification_type TEXT NOT NULL,
                membership_expires_at TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                UNIQUE(user_id, notification_type, membership_expires_at)
            );
            """)

            # Schema migrations for users table
            for col, dtype in [
                ("gender", "TEXT DEFAULT 'Not specified'"),
                ("staff_source", "TEXT DEFAULT NULL"),
                ("is_gold", "INTEGER DEFAULT 0"),
                ("subscription_expiry", "TEXT DEFAULT NULL"),
                ("device_id", "TEXT DEFAULT NULL"),
                ("avatar_url", "TEXT DEFAULT NULL")
            ]:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype};")
                except Exception:
                    pass

            # Schema migrations for staff_memberships table
            try:
                cursor.execute("ALTER TABLE staff_memberships ADD COLUMN customer_phone TEXT DEFAULT NULL;")
            except Exception:
                pass

            # Schema migrations for membership_payments table
            for p_col, p_dtype in [
                ("customer_phone", "TEXT DEFAULT NULL"),
                ("customer_name", "TEXT DEFAULT NULL")
            ]:
                try:
                    cursor.execute(f"ALTER TABLE membership_payments ADD COLUMN {p_col} {p_dtype};")
                except Exception:
                    pass

            # Indexes for ultra-fast querying
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_usage_user_date ON daily_usage(user_id, date_str);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversions_user_id ON conversions(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversions_created_at ON conversions(created_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_payment_requests_user_id ON payment_requests(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_payment_requests_status ON payment_requests(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_payment_requests_created_at ON payment_requests(created_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON page_credit_audit_log(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON page_credit_audit_log(timestamp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_activity_user_id ON user_activity_logs(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_activity_created_at ON user_activity_logs(created_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_security_audit_created_at ON security_audit_logs(created_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ratings_status ON ratings_reviews(moderation_status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_signups_email ON pending_signups(email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_notifications_unread ON admin_notifications(is_read);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_user_id ON devices(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_converted_bills_lookup ON converted_bills(user_id, fingerprint_hash, date_ist);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_converted_bills_user ON converted_bills(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_staff_audit_target ON staff_audit_logs(target_user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_staff_memberships_user ON staff_memberships(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_membership_payments_pid ON membership_payments(payment_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_membership_payments_user ON membership_payments(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_membership_renewal_user ON membership_renewal_history(user_id);")

            conn.commit()

            # Seed standard platform administrator if missing (Zero fake/demo users)
            _seed_default_users(cursor)
            conn.commit()
            logger.info("Kangra Hub SQLite database initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite database: {e}", exc_info=True)
            conn.rollback()
        finally:
            conn.close()

def _seed_default_users(cursor: sqlite3.Cursor):
    """Seeds baseline administrator account only. No fake or demo accounts."""
    now_iso = datetime.now(timezone.utc).isoformat()
    defaults = [
        {
            "id": "c4eb4938-895b-4b09-a362-db5ea1189315",
            "email": "admin@kangrahub.sales",
            "full_name": "Kangra Hub Administrator",
            "username": "admin",
            "mobile_number": "+919418250639",
            "gender": "Not specified",
            "role": "ADMIN",
            "is_unlimited": 1,
            "account_status": "ACTIVE",
            "email_verified": 1,
            "mobile_verified": 1,
            "registration_date": "2024-01-01T00:00:00Z"
        }
    ]

    for d in defaults:
        cursor.execute("SELECT id FROM users WHERE id = ? OR email = ?", (d["id"], d["email"]))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
            INSERT INTO users (
                id, email, full_name, username, mobile_number, role, is_unlimited,
                account_status, email_verified, mobile_verified, registration_date,
                last_login, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                d["id"], d["email"], d["full_name"], d["username"], d["mobile_number"],
                d["role"], d["is_unlimited"], d["account_status"], d["email_verified"],
                d["mobile_verified"], d["registration_date"], now_iso, now_iso, now_iso
            ))
        else:
            # Authoritatively ensure admin privileges and active status
            cursor.execute("""
            UPDATE users SET
                id = ?,
                email = ?,
                role = 'ADMIN',
                is_unlimited = 1,
                account_status = 'ACTIVE',
                email_verified = 1,
                mobile_verified = 1,
                updated_at = ?
            WHERE id = ? OR email = ?
            """, (d["id"], d["email"], now_iso, d["id"], d["email"]))

# ============================================================================
# USER OPERATIONS
# ============================================================================

def upsert_user(data: Dict[str, Any]) -> Dict[str, Any]:
    """Inserts or updates a user in the database."""
    now_iso = datetime.now(timezone.utc).isoformat()
    uid = str(data.get("id") or f"usr-{data.get('email', '').split('@')[0]}").strip()
    clean_email = str(data.get("email") or "").strip().lower()

    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ? OR email = ?", (uid, clean_email))
            existing = cursor.fetchone()

            if existing:
                existing_dict = dict(existing)
                target_role = data.get("role") if data.get("role") is not None else existing_dict["role"]
                target_is_unlim = int(bool(data.get("is_unlimited"))) if "is_unlimited" in data else existing_dict["is_unlimited"]

                # If user is currently an active STAFF member, prevent unintentional downgrades
                if existing_dict.get("role") == "STAFF" and target_role != "STAFF" and target_role not in ("ADMIN", "SUPER_ADMIN"):
                    active_mem = get_staff_membership_with_status_eval(user_id=uid, user_email=clean_email)
                    if active_mem and active_mem.get("is_active"):
                        target_role = "STAFF"
                        target_is_unlim = 1

                updated = {
                    "full_name": data.get("full_name") if data.get("full_name") is not None else existing_dict["full_name"],
                    "username": data.get("username") if data.get("username") is not None else (existing_dict.get("username") or clean_email.split("@")[0]),
                    "mobile_number": (
                        str(data.get("mobile_number")).strip()
                        if (data.get("mobile_number") and str(data.get("mobile_number")).strip())
                        else (existing_dict.get("mobile_number") or "")
                    ),
                    "role": target_role,
                    "is_unlimited": target_is_unlim,
                    "account_status": data.get("account_status") if data.get("account_status") is not None else existing_dict["account_status"],
                    "email_verified": int(bool(data.get("email_verified"))) if "email_verified" in data else existing_dict["email_verified"],
                    "mobile_verified": int(bool(data.get("mobile_verified"))) if "mobile_verified" in data else existing_dict["mobile_verified"],
                    "last_login": data.get("last_login") or now_iso,
                    "suspended_at": data.get("suspended_at") if "suspended_at" in data else existing_dict["suspended_at"],
                    "suspension_reason": data.get("suspension_reason") if "suspension_reason" in data else existing_dict["suspension_reason"],
                    "suspension_delete_at": data.get("suspension_delete_at") if "suspension_delete_at" in data else existing_dict["suspension_delete_at"],
                    "suspension_reviewed_at": data.get("suspension_reviewed_at") if "suspension_reviewed_at" in data else existing_dict["suspension_reviewed_at"],
                    "suspension_reviewed_by": data.get("suspension_reviewed_by") if "suspension_reviewed_by" in data else existing_dict["suspension_reviewed_by"],
                    "updated_at": now_iso
                }
                cursor.execute("""
                UPDATE users SET
                    full_name = :full_name,
                    username = :username,
                    mobile_number = :mobile_number,
                    role = :role,
                    is_unlimited = :is_unlimited,
                    account_status = :account_status,
                    email_verified = :email_verified,
                    mobile_verified = :mobile_verified,
                    last_login = :last_login,
                    suspended_at = :suspended_at,
                    suspension_reason = :suspension_reason,
                    suspension_delete_at = :suspension_delete_at,
                    suspension_reviewed_at = :suspension_reviewed_at,
                    suspension_reviewed_by = :suspension_reviewed_by,
                    updated_at = :updated_at
                WHERE id = :target_id
                """, {**updated, "target_id": existing_dict["id"]})
                conn.commit()
                existing_dict.update(updated)
                existing_dict["is_unlimited"] = bool(existing_dict["is_unlimited"])
                existing_dict["email_verified"] = bool(existing_dict["email_verified"])
                existing_dict["mobile_verified"] = bool(existing_dict["mobile_verified"])
                return existing_dict
            else:
                new_user = {
                    "id": uid,
                    "email": clean_email,
                    "full_name": data.get("full_name") or clean_email.split("@")[0].capitalize(),
                    "username": data.get("username") or clean_email.split("@")[0],
                    "mobile_number": data.get("mobile_number") or "",
                    "role": data.get("role") or "USER",
                    "is_unlimited": int(bool(data.get("is_unlimited"))),
                    "account_status": data.get("account_status") or "ACTIVE",
                    "email_verified": int(bool(data.get("email_verified", True))),
                    "mobile_verified": int(bool(data.get("mobile_verified", False))),
                    "registration_date": data.get("registration_date") or now_iso,
                    "last_login": data.get("last_login") or now_iso,
                    "suspended_at": data.get("suspended_at"),
                    "suspension_reason": data.get("suspension_reason"),
                    "suspension_delete_at": data.get("suspension_delete_at"),
                    "suspension_reviewed_at": data.get("suspension_reviewed_at"),
                    "suspension_reviewed_by": data.get("suspension_reviewed_by"),
                    "created_at": now_iso,
                    "updated_at": now_iso
                }
                cursor.execute("""
                INSERT INTO users (
                    id, email, full_name, username, mobile_number, role, is_unlimited,
                    account_status, email_verified, mobile_verified, registration_date,
                    last_login, suspended_at, suspension_reason, suspension_delete_at,
                    suspension_reviewed_at, suspension_reviewed_by, created_at, updated_at
                ) VALUES (
                    :id, :email, :full_name, :username, :mobile_number, :role, :is_unlimited,
                    :account_status, :email_verified, :mobile_verified, :registration_date,
                    :last_login, :suspended_at, :suspension_reason, :suspension_delete_at,
                    :suspension_reviewed_at, :suspension_reviewed_by, :created_at, :updated_at
                )
                """, new_user)
                conn.commit()
                res = dict(new_user)
                res["is_unlimited"] = bool(res["is_unlimited"])
                res["email_verified"] = bool(res["email_verified"])
                res["mobile_verified"] = bool(res["mobile_verified"])
                return res
        finally:
            conn.close()

def get_all_users(search: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all registered users from SQLite, sorted descending by registration date."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            if search:
                term = f"%{search.strip().lower()}%"
                cursor.execute("""
                SELECT * FROM users
                WHERE lower(email) LIKE ?
                   OR lower(coalesce(full_name, '')) LIKE ?
                   OR lower(coalesce(username, '')) LIKE ?
                   OR lower(id) LIKE ?
                   OR lower(coalesce(mobile_number, '')) LIKE ?
                ORDER BY registration_date DESC
                """, (term, term, term, term, term))
            else:
                cursor.execute("SELECT * FROM users ORDER BY registration_date DESC")

            rows = cursor.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["is_unlimited"] = bool(d.get("is_unlimited"))
                d["email_verified"] = bool(d.get("email_verified"))
                d["mobile_verified"] = bool(d.get("mobile_verified"))
                results.append(d)
            return results
        finally:
            conn.close()

def get_user_by_id_or_email(identifier: str) -> Optional[Dict[str, Any]]:
    """Looks up user by ID or Email."""
    if not identifier:
        return None
    clean = identifier.strip().lower()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE lower(id) = ? OR lower(email) = ?", (clean, clean))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["is_unlimited"] = bool(d.get("is_unlimited"))
                d["email_verified"] = bool(d.get("email_verified"))
                d["mobile_verified"] = bool(d.get("mobile_verified"))
                return d
            return None
        finally:
            conn.close()

# ============================================================================
# PENDING SIGNUPS & OTP SESSION RECOVERY (PRD 10-Minute Recovery)
# ============================================================================

def save_pending_signup(
    email: str,
    mobile_number: str,
    full_name: str,
    gender: str = "Male",
    password_hash: str = "",
    otp_issued_at: float = 0.0,
    otp_expires_at: float = 0.0
) -> None:
    """Stores or refreshes a pending user signup state with authoritative 10-minute validity."""
    clean_email = email.strip().lower()
    clean_phone = "".join(c for c in (mobile_number or "") if c.isdigit())[-10:]
    now_iso = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO pending_signups (
                email, mobile_number, full_name, gender, password_hash,
                otp_issued_at, otp_expires_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                mobile_number = excluded.mobile_number,
                full_name = excluded.full_name,
                gender = excluded.gender,
                password_hash = excluded.password_hash,
                otp_issued_at = excluded.otp_issued_at,
                otp_expires_at = excluded.otp_expires_at,
                created_at = excluded.created_at;
            """, (
                clean_email, clean_phone, full_name, gender, password_hash,
                otp_issued_at, otp_expires_at, now_iso
            ))
            conn.commit()
        finally:
            conn.close()

def get_pending_signup(email: str) -> Optional[Dict[str, Any]]:
    """Retrieves pending signup record by email."""
    clean_email = email.strip().lower()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pending_signups WHERE email = ?", (clean_email,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

def delete_pending_signup(email: str) -> None:
    """Removes pending signup record upon verification completion or cleanup."""
    clean_email = email.strip().lower()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pending_signups WHERE email = ?", (clean_email,))
            conn.commit()
        finally:
            conn.close()

# ============================================================================
# DAILY USAGE OPERATIONS
# ============================================================================

def record_daily_usage(user_id: str, date_str: str, pages: int) -> int:
    """Atomically increments pages used for a user on a given Kolkata date."""
    if pages <= 0:
        return get_daily_usage(user_id, date_str)
    uid = str(user_id).strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    record_id = f"{uid}:{date_str}"

    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO daily_usage (id, user_id, date_str, pages_used, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, date_str) DO UPDATE SET
                pages_used = daily_usage.pages_used + excluded.pages_used,
                updated_at = excluded.updated_at
            """, (record_id, uid, date_str, pages, now_iso))
            conn.commit()

            cursor.execute("SELECT pages_used FROM daily_usage WHERE user_id = ? AND date_str = ?", (uid, date_str))
            row = cursor.fetchone()
            return row["pages_used"] if row else pages
        finally:
            conn.close()

def get_daily_usage(user_id: str, date_str: str) -> int:
    """Returns total pages used for user on date_str."""
    uid = str(user_id).strip()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT pages_used FROM daily_usage WHERE user_id = ? AND date_str = ?", (uid, date_str))
            row = cursor.fetchone()
            return row["pages_used"] if row else 0
        finally:
            conn.close()

def reset_daily_usage(user_id: str, date_str: str) -> bool:
    """Resets daily usage to 0 for a user on date_str."""
    uid = str(user_id).strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    record_id = f"{uid}:{date_str}"
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO daily_usage (id, user_id, date_str, pages_used, updated_at)
            VALUES (?, ?, ?, 0, ?)
            ON CONFLICT(user_id, date_str) DO UPDATE SET
                pages_used = 0,
                updated_at = excluded.updated_at
            """, (record_id, uid, date_str, now_iso))
            conn.commit()
            return True
        finally:
            conn.close()

# ============================================================================
# CONVERSIONS PERSISTENCE
# ============================================================================

def save_conversion(job: Dict[str, Any]) -> None:
    """Persists a statement conversion record with page telemetry."""
    job_id = str(job.get("id") or "").strip()
    if not job_id:
        return
    uid = str(job.get("user_id") or "").strip()
    c_at = job.get("created_at")
    created_str = c_at.isoformat() if hasattr(c_at, "isoformat") else str(c_at or datetime.now(timezone.utc).isoformat())

    # Extract clean metadata and serialize transactions for workspace persistence
    tx_list = job.get("transactions") or []
    serialized_txs = []
    for tx in tx_list:
        if hasattr(tx, "dict"):
            t_dict = tx.dict()
        elif hasattr(tx, "model_dump"):
            t_dict = tx.model_dump()
        elif isinstance(tx, dict):
            t_dict = dict(tx)
        else:
            continue
        for k, v in list(t_dict.items()):
            if isinstance(v, Decimal):
                t_dict[k] = float(v)
            elif hasattr(v, "isoformat"):
                t_dict[k] = v.isoformat()
        serialized_txs.append(t_dict)

    meta = {
        "confidence_score": job.get("confidence_score"),
        "confidence_tier": job.get("confidence_tier"),
        "parser_name": job.get("parser_name"),
        "bank_ledger_name": job.get("bank_ledger_name"),
        "cash_ledger_name": job.get("cash_ledger_name"),
        "is_partial_conversion": job.get("is_partial_conversion", False),
        "pages_skipped": job.get("pages_skipped", 0),
        "pages_pending": job.get("pages_pending", job.get("pages_skipped", 0)),
        "page_statuses": job.get("page_statuses", {}),
        "pages_processed": job.get("pages_processed", job.get("page_count", 0)),
        "total_pdf_pages": job.get("total_pdf_pages", job.get("page_count", 0)),
        "transactions": serialized_txs,
        "pdf_path": job.get("pdf_path"),
        "password": job.get("password")
    }

    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO conversions (
                id, user_id, user_email, file_name, bank_name,
                total_pdf_pages, pages_processed, pages_skipped,
                free_quota_used, additional_quota_used, transaction_count,
                status, is_partial_conversion, created_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                pages_processed = excluded.pages_processed,
                pages_skipped = excluded.pages_skipped,
                free_quota_used = excluded.free_quota_used,
                additional_quota_used = excluded.additional_quota_used,
                transaction_count = excluded.transaction_count,
                status = excluded.status,
                is_partial_conversion = excluded.is_partial_conversion,
                metadata_json = excluded.metadata_json
            """, (
                job_id,
                uid,
                job.get("user_email") or "",
                job.get("file_name") or "",
                job.get("bank_name") or "",
                int(job.get("total_pdf_pages") or job.get("page_count") or 0),
                int(job.get("pages_processed") or 0),
                int(job.get("pages_skipped") or 0),
                int(job.get("free_quota_used") or 0),
                int(job.get("additional_quota_used") or 0),
                int(job.get("transaction_count") or 0),
                str(job.get("status") or "COMPLETED"),
                1 if job.get("is_partial_conversion") else 0,
                created_str,
                json.dumps(meta)
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist conversion {job_id}: {e}", exc_info=True)
            conn.rollback()
        finally:
            conn.close()

def get_conversion_by_id(job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves single conversion job by ID."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM conversions WHERE id = ?", (str(job_id).strip(),))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

# Ergonomic alias
get_conversion = get_conversion_by_id

def get_latest_active_conversion(user_id_or_email: str) -> Optional[Dict[str, Any]]:
    """Retrieves the latest conversion for session restoration."""
    target = str(user_id_or_email).strip().lower()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM conversions
            WHERE (lower(user_id) = ? OR lower(user_email) = ?)
              AND status IN ('COMPLETED', 'PARTIALLY_COMPLETED', 'NEEDS_REVIEW')
            ORDER BY created_at DESC LIMIT 1
            """, (target, target))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

def get_user_conversions(user_id_or_email: str) -> List[Dict[str, Any]]:
    """Retrieves all conversion records for a user."""
    target = str(user_id_or_email).strip().lower()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM conversions
            WHERE lower(user_id) = ? OR lower(user_email) = ?
            ORDER BY created_at DESC
            """, (target, target))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

def get_all_conversions() -> List[Dict[str, Any]]:
    """Retrieves all conversions sorted descending by date."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM conversions ORDER BY created_at DESC")
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

def get_user_conversion_stats(user_id: str, email: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes accurate conversion aggregates for a user:
    - total_conversions: total count of conversion jobs
    - successful_conversions: COMPLETED + PARTIALLY_COMPLETED
    - failed_conversions: FAILED
    - total_pages_processed: SUM(pages_processed) across all COMPLETED/PARTIALLY_COMPLETED/NEEDS_REVIEW
    - last_conversion_at: timestamp of most recent job
    """
    uid = str(user_id).strip().lower()
    uemail = str(email or "").strip().lower()

    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT
                COUNT(*) as total_conversions,
                SUM(CASE WHEN status IN ('COMPLETED', 'PARTIALLY_COMPLETED') THEN 1 ELSE 0 END) as successful_conversions,
                SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed_conversions,
                SUM(CASE WHEN status IN ('COMPLETED', 'PARTIALLY_COMPLETED', 'NEEDS_REVIEW') THEN pages_processed ELSE 0 END) as total_pages_processed,
                MAX(created_at) as last_conversion_at
            FROM conversions
            WHERE lower(user_id) = ? OR (lower(user_email) = ? AND ? != '')
            """, (uid, uemail, uemail))
            row = cursor.fetchone()
            if row:
                return {
                    "total_conversions": row["total_conversions"] or 0,
                    "successful_conversions": row["successful_conversions"] or 0,
                    "failed_conversions": row["failed_conversions"] or 0,
                    "total_pages_processed": row["total_pages_processed"] or 0,
                    "last_conversion_at": row["last_conversion_at"]
                }
            return {
                "total_conversions": 0,
                "successful_conversions": 0,
                "failed_conversions": 0,
                "total_pages_processed": 0,
                "last_conversion_at": None
            }
        finally:
            conn.close()

# ============================================================================
# ADDITIONAL PAGES & CUSTOM QUOTAS
# ============================================================================

def get_additional_pages(user_id: str) -> int:
    """Returns persistent additional page balance."""
    uid = str(user_id).strip()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM user_additional_pages WHERE user_id = ?", (uid,))
            row = cursor.fetchone()
            return row["balance"] if row else 0
        finally:
            conn.close()

def set_additional_pages(user_id: str, balance: int) -> int:
    """Sets persistent additional page balance."""
    uid = str(user_id).strip()
    bal = max(0, balance)
    now_iso = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO user_additional_pages (user_id, balance, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                balance = excluded.balance,
                updated_at = excluded.updated_at
            """, (uid, bal, now_iso))
            conn.commit()
            return bal
        finally:
            conn.close()

def grant_additional_pages(user_id: str, pages: int) -> int:
    """Adds pages to persistent additional page balance."""
    curr = get_additional_pages(user_id)
    new_bal = curr + max(0, pages)
    return set_additional_pages(user_id, new_bal)

def deduct_additional_pages(user_id: str, pages: int) -> int:
    """Deducts pages from persistent additional page balance."""
    curr = get_additional_pages(user_id)
    new_bal = max(0, curr - max(0, pages))
    return set_additional_pages(user_id, new_bal)

def get_custom_quota(user_id: str) -> Optional[int]:
    """Returns custom quota override if configured."""
    uid = str(user_id).strip()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT quota FROM user_custom_quotas WHERE user_id = ?", (uid,))
            row = cursor.fetchone()
            return row["quota"] if row else None
        finally:
            conn.close()

def set_custom_quota(user_id: str, quota: Optional[int]) -> None:
    """Configures or deletes custom quota override."""
    uid = str(user_id).strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            if quota is None:
                cursor.execute("DELETE FROM user_custom_quotas WHERE user_id = ?", (uid,))
            else:
                cursor.execute("""
                INSERT INTO user_custom_quotas (user_id, quota, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    quota = excluded.quota,
                    updated_at = excluded.updated_at
                """, (uid, quota, now_iso))
            conn.commit()
        finally:
            conn.close()

# ============================================================================
# DAILY USAGE PERSISTENCE
# ============================================================================

def get_daily_usage(user_id: str, date_str: str) -> int:
    """Returns persistent daily pages used for a user on a specific date."""
    uid = str(user_id).strip()
    d_str = str(date_str).strip()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT pages_used FROM daily_usage WHERE user_id = ? AND date_str = ?", (uid, d_str))
            row = cursor.fetchone()
            return row["pages_used"] if row else 0
        finally:
            conn.close()

def set_daily_quota_usage(user_id: str, date_str: str, pages: int) -> int:
    """Sets persistent daily pages used for a user on a specific date."""
    uid = str(user_id).strip()
    d_str = str(date_str).strip()
    p = max(0, int(pages))
    rec_id = f"{uid}:{d_str}"
    now_iso = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO daily_usage (id, user_id, date_str, pages_used, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, date_str) DO UPDATE SET
                pages_used = excluded.pages_used,
                updated_at = excluded.updated_at
            """, (rec_id, uid, d_str, p, now_iso))
            conn.commit()
            return p
        finally:
            conn.close()

def increment_daily_usage(user_id: str, date_str: str, pages: int) -> int:
    """Increments persistent daily pages used for a user on a specific date."""
    curr = get_daily_usage(user_id, date_str)
    new_pages = curr + max(0, int(pages))
    return set_daily_quota_usage(user_id, date_str, new_pages)

def increment_daily_quota_usage(user_id: str, date_str: str, pages: int) -> int:
    """Alias for increment_daily_usage."""
    return increment_daily_usage(user_id, date_str, pages)

def reset_daily_usage(user_id: str, date_str: str) -> None:
    """Resets daily usage for a user on a specific date."""
    uid = str(user_id).strip()
    d_str = str(date_str).strip()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM daily_usage WHERE user_id = ? AND date_str = ?", (uid, d_str))
            conn.commit()
        finally:
            conn.close()

# ============================================================================
# PAYMENT REQUESTS PERSISTENCE
# ============================================================================

def save_payment_request(r: Dict[str, Any]) -> None:
    """Inserts or updates a payment request in SQLite."""
    now_iso = datetime.now(timezone.utc).isoformat()
    req_id = str(r["id"]).strip()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO payment_requests (
                id, user_id, user_email, user_name, requested_pages, granted_pages,
                amount_paid, job_id, notes, screenshot_path, screenshot_filename,
                status, created_at, updated_at, admin_notes, approved_by, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                granted_pages = excluded.granted_pages,
                status = excluded.status,
                updated_at = excluded.updated_at,
                admin_notes = excluded.admin_notes,
                approved_by = excluded.approved_by,
                approved_at = excluded.approved_at
            """, (
                req_id,
                r.get("user_id", ""),
                r.get("user_email", ""),
                r.get("user_name", ""),
                int(r.get("requested_pages", 0)),
                int(r.get("granted_pages", r.get("requested_pages", 0))),
                float(r.get("amount_paid", 0.0)),
                r.get("job_id"),
                r.get("notes"),
                r.get("screenshot_path", ""),
                r.get("screenshot_filename", ""),
                r.get("status", "PENDING"),
                r.get("created_at") or now_iso,
                r.get("updated_at") or now_iso,
                r.get("admin_notes"),
                r.get("approved_by"),
                r.get("approved_at")
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist payment request {req_id}: {e}", exc_info=True)
            conn.rollback()
        finally:
            conn.close()

def get_payment_request(request_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves payment request by ID."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM payment_requests WHERE id = ?", (str(request_id).strip(),))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

def get_user_payment_requests(user_id_or_email: str) -> List[Dict[str, Any]]:
    """Retrieves all payment requests for a user ordered newest first."""
    target = str(user_id_or_email).strip().lower()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM payment_requests
            WHERE lower(user_id) = ? OR lower(user_email) = ?
            ORDER BY created_at DESC
            """, (target, target))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

def get_all_payment_requests(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all payment requests with optional status filter."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            if status and status.upper() != "ALL":
                cursor.execute("SELECT * FROM payment_requests WHERE upper(status) = ? ORDER BY created_at DESC", (status.upper(),))
            else:
                cursor.execute("SELECT * FROM payment_requests ORDER BY created_at DESC")
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

def update_payment_request_status(
    request_id: str,
    status: str,
    admin_email: str,
    granted_pages: Optional[int] = None,
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Updates status of payment request (e.g. APPROVED or REJECTED)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    req_id = str(request_id).strip()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM payment_requests WHERE id = ?", (req_id,))
            row = cursor.fetchone()
            if not row:
                return None
            current = dict(row)
            g_pages = granted_pages if granted_pages is not None else current["granted_pages"]
            cursor.execute("""
            UPDATE payment_requests SET
                status = ?,
                granted_pages = ?,
                admin_notes = ?,
                approved_by = ?,
                approved_at = ?,
                updated_at = ?
            WHERE id = ?
            """, (status, g_pages, notes, admin_email, now_iso if status == "APPROVED" else current.get("approved_at"), now_iso, req_id))
            conn.commit()
            cursor.execute("SELECT * FROM payment_requests WHERE id = ?", (req_id,))
            updated_row = cursor.fetchone()
            return dict(updated_row) if updated_row else None
        finally:
            conn.close()

# ============================================================================
# PAGE CREDIT AUDIT LOGGING
# ============================================================================

def log_page_credit_event(
    user_id: str,
    pages_credited: int,
    previous_balance: int,
    new_balance: int,
    conversion_id: Optional[str] = None,
    payment_id: Optional[str] = None,
    amount: float = 0.0,
    pages_requested: int = 0,
    pages_approved: int = 0,
    admin_id: Optional[str] = None,
    source: str = "ADMIN_APPROVAL"
) -> Dict[str, Any]:
    """Records an immutable audit entry for every page credit/adjustment event."""
    record_id = f"audit-{uuid.uuid4().hex[:10]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    record = {
        "id": record_id,
        "user_id": str(user_id).strip(),
        "conversion_id": str(conversion_id).strip() if conversion_id else None,
        "payment_id": str(payment_id).strip() if payment_id else None,
        "amount": float(amount or 0.0),
        "pages_requested": int(pages_requested or 0),
        "pages_approved": int(pages_approved or 0),
        "pages_credited": int(pages_credited or 0),
        "admin_id": str(admin_id).strip() if admin_id else None,
        "source": str(source).strip(),
        "timestamp": now_iso,
        "previous_balance": int(previous_balance or 0),
        "new_balance": int(new_balance or 0)
    }
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO page_credit_audit_log (
                id, user_id, conversion_id, payment_id, amount,
                pages_requested, pages_approved, pages_credited,
                admin_id, source, timestamp, previous_balance, new_balance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record["id"], record["user_id"], record["conversion_id"], record["payment_id"],
                record["amount"], record["pages_requested"], record["pages_approved"], record["pages_credited"],
                record["admin_id"], record["source"], record["timestamp"], record["previous_balance"], record["new_balance"]
            ))
            conn.commit()
            return record
        finally:
            conn.close()

def get_page_credit_audit_logs(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves immutable audit logs for auditing and dispute prevention."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            if user_id:
                cursor.execute("SELECT * FROM page_credit_audit_log WHERE user_id = ? ORDER BY timestamp DESC", (str(user_id).strip(),))
            else:
                cursor.execute("SELECT * FROM page_credit_audit_log ORDER BY timestamp DESC")
            rows = []
            for r in cursor.fetchall():
                d = dict(r)
                d["pages_granted"] = d.get("pages_credited", 0)
                d["amount_paid"] = d.get("amount", 0.0)
                d["event_type"] = d.get("source", "ADMIN_APPROVAL")
                rows.append(d)
            return rows
        finally:
            conn.close()

# ============================================================================
# USER ACTIVITY & AUDIT LOGGING (PRD Section 8)
# ============================================================================

def log_user_activity(
    user_id: Optional[str],
    user_email: Optional[str],
    action: str,
    module: Optional[str] = "Sales & Purchase",
    resource_id: Optional[str] = None,
    status: str = "SUCCESS",
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Dict[str, Any]:
    """Records an activity entry documenting WHO did WHAT, WHEN, in WHICH MODULE."""
    act_id = f"act-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    meta_str = json.dumps(metadata) if metadata else None
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO user_activity_logs (
                id, user_id, user_email, action, module, resource_id, status, metadata, ip_address, user_agent, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                act_id, str(user_id or ""), str(user_email or ""), action, module,
                str(resource_id or "") if resource_id else None, status, meta_str, ip_address, user_agent, now_iso
            ))
            conn.commit()
            return {
                "id": act_id,
                "user_id": user_id,
                "user_email": user_email,
                "action": action,
                "module": module,
                "resource_id": resource_id,
                "status": status,
                "metadata": metadata,
                "created_at": now_iso
            }
        finally:
            conn.close()

# Alias for backwards compatibility
add_user_activity_log = log_user_activity

def get_user_activity_logs(
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    module: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Retrieves user activity audit trail for administration or user history."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM user_activity_logs WHERE 1=1"
            params = []
            if user_id:
                query += " AND (user_id = ? OR user_email = ?)"
                params.extend([str(user_id).strip(), str(user_id).strip()])
            elif user_email:
                query += " AND user_email = ?"
                params.append(str(user_email).strip().lower())
            if module:
                query += " AND module = ?"
                params.append(module)
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = []
            for r in cursor.fetchall():
                d = dict(r)
                if d.get("metadata"):
                    try:
                        d["metadata"] = json.loads(d["metadata"])
                    except Exception:
                        pass
                rows.append(d)
            return rows
        finally:
            conn.close()

# ============================================================================
# SECURITY AUDIT LOGGING (PRD Section 18)
# ============================================================================

def log_security_event(
    actor_id: Optional[str],
    actor_email: Optional[str],
    event_type: str,
    severity: str = "INFO",
    module: Optional[str] = "Security",
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> Dict[str, Any]:
    """Records security-critical events like unauthorized admin access attempts or abuse."""
    sec_id = f"sec-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    det_str = json.dumps(details) if details else None
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO security_audit_logs (
                id, actor_id, actor_email, event_type, severity, module, details, ip_address, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sec_id, str(actor_id or ""), str(actor_email or ""), event_type, severity, module, det_str, ip_address, now_iso
            ))
            conn.commit()

            # Auto-generate admin notification for WARNING or CRITICAL severity
            if severity.upper() in ("WARNING", "HIGH", "CRITICAL"):
                create_admin_notification(
                    type="SECURITY_ALERT",
                    title=f"Security Alert: {event_type}",
                    message=f"Event '{event_type}' detected from {actor_email or actor_id or 'unknown'} ({severity}).",
                    severity=severity.upper(),
                    related_user_id=actor_id
                )

            return {
                "id": sec_id,
                "actor_id": actor_id,
                "actor_email": actor_email,
                "event_type": event_type,
                "severity": severity,
                "created_at": now_iso
            }
        finally:
            conn.close()

# Alias for security logging
add_security_audit_log = log_security_event

def get_security_audit_logs(
    severity: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Retrieves security audit logs."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM security_audit_logs WHERE 1=1"
            params = []
            if severity:
                query += " AND severity = ?"
                params.append(severity.upper())
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cursor.execute(query, params)
            rows = []
            for r in cursor.fetchall():
                d = dict(r)
                if d.get("details"):
                    try:
                        d["details"] = json.loads(d["details"])
                    except Exception:
                        pass
                rows.append(d)
            return rows
        finally:
            conn.close()

# ============================================================================
# RATINGS & REVIEWS (PRD Section 9, 10, 11, 12)
# ============================================================================

def submit_rating_review(
    user_id: str,
    user_name: str,
    user_email: str,
    rating: int,
    review_text: Optional[str] = None,
    moderation_status: str = "APPROVED"
) -> str:
    """Creates or updates a user rating & review. Returns review ID."""
    clean_rating = max(1, min(5, int(rating)))
    text = (review_text or "").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    lower_text = text.lower()
    abuse_keywords = ["abuse", "scam", "fraud", "hacker", "attack", "kill", "threat"]
    has_flag = any(k in lower_text for k in abuse_keywords)
    final_status = "PENDING" if has_flag else moderation_status.upper()

    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM ratings_reviews WHERE user_id = ? OR user_email = ?", (str(user_id), user_email))
            existing = cursor.fetchone()
            if existing:
                rev_id = existing["id"]
                cursor.execute("""
                UPDATE ratings_reviews
                SET rating = ?, review_text = ?, moderation_status = ?, user_name = ?, updated_at = ?
                WHERE id = ?
                """, (clean_rating, text, final_status, user_name, now_iso, rev_id))
            else:
                rev_id = f"rev-{uuid.uuid4().hex[:12]}"
                cursor.execute("""
                INSERT INTO ratings_reviews (
                    id, user_id, user_name, user_email, rating, review_text, moderation_status, moderator_notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (rev_id, str(user_id), user_name, user_email, clean_rating, text, final_status, None, now_iso, now_iso))
            conn.commit()

            create_admin_notification(
                type="NEW_RATING",
                title=f"Rating ({clean_rating}★) from {user_name}",
                message=f"{user_email} submitted {clean_rating} stars: {text[:60]}...",
                severity="WARNING" if (clean_rating <= 2 or has_flag) else "INFO",
                related_user_id=user_id
            )

            return rev_id
        finally:
            conn.close()

def create_rating_review(
    user_id: str,
    user_name: str,
    user_email: str,
    rating: int,
    review_text: Optional[str] = None
) -> Dict[str, Any]:
    """Compatibility wrapper for submit_rating_review."""
    rev_id = submit_rating_review(user_id, user_name, user_email, rating, review_text)
    return {
        "id": rev_id,
        "user_id": user_id,
        "user_name": user_name,
        "rating": rating,
        "review_text": review_text
    }

def get_ratings_reviews(
    status: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Retrieves ratings and reviews with optional status or user_id filtering."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            conditions = []
            params = []
            if status:
                conditions.append("moderation_status = ?")
                params.append(status.upper())
            if user_id:
                conditions.append("user_id = ?")
                params.append(str(user_id))
            
            where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            query = f"SELECT * FROM ratings_reviews {where_clause} ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

def moderate_rating_review(
    review_id: str,
    new_status: str,
    moderator_notes: Optional[str] = None
) -> bool:
    """Updates moderation status (APPROVED, HIDDEN, DELETED)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE ratings_reviews
            SET moderation_status = ?, moderator_notes = ?, updated_at = ?
            WHERE id = ?
            """, (new_status.upper(), moderator_notes, now_iso, review_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

def update_user_profile(
    user_id: str,
    full_name: Optional[str] = None,
    mobile_number: Optional[str] = None,
    gender: Optional[str] = None,
    avatar_url: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Updates a user's editable profile fields in SQLite users table."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ? OR LOWER(email) = ?", (user_id, user_id.lower()))
            user = cursor.fetchone()
            if not user:
                return None
            
            updates = ["updated_at = ?"]
            params = [now_iso]

            if full_name is not None and full_name.strip():
                updates.append("full_name = ?")
                params.append(full_name.strip())
            if mobile_number is not None and mobile_number.strip():
                clean_mobile = "".join(c for c in mobile_number if c.isdigit())
                updates.append("mobile_number = ?")
                params.append(clean_mobile)
                updates.append("mobile_verified = 1")
            if gender is not None and gender.strip():
                updates.append("gender = ?")
                params.append(gender.strip())
            if avatar_url is not None:
                updates.append("avatar_url = ?")
                params.append(avatar_url.strip() if avatar_url.strip() else None)

            params.append(user["id"])
            cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()

            cursor.execute("SELECT * FROM users WHERE id = ?", (user["id"],))
            updated_row = cursor.fetchone()
            if updated_row:
                d = dict(updated_row)
                d["is_unlimited"] = bool(d.get("is_unlimited"))
                d["email_verified"] = bool(d.get("email_verified"))
                d["mobile_verified"] = bool(d.get("mobile_verified"))
                return d
            return None
        finally:
            conn.close()

def set_user_avatar(user_id: str, avatar_url: Optional[str]) -> bool:
    """Updates or removes the user's avatar URL in SQLite users table."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE users SET avatar_url = ?, updated_at = ?
            WHERE id = ? OR LOWER(email) = ?
            """, (avatar_url, now_iso, user_id, user_id.lower()))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

# ============================================================================
# ADMIN REAL-TIME NOTIFICATIONS (PRD Section 13, 14)
# ============================================================================

def create_admin_notification(
    type: str,
    title: str,
    message: str,
    severity: str = "INFO",
    related_user_id: Optional[str] = None
) -> Dict[str, Any]:
    """Generates an administrative alert."""
    notif_id = f"notif-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO admin_notifications (
                id, type, title, message, severity, is_read, related_user_id, created_at
            ) VALUES (?, ?, ?, ?, ?, 0, ?, ?)
            """, (notif_id, type, title, message, severity.upper(), str(related_user_id or ""), now_iso))
            conn.commit()
            return {
                "id": notif_id,
                "type": type,
                "title": title,
                "message": message,
                "severity": severity,
                "created_at": now_iso
            }
        finally:
            conn.close()

def get_admin_notifications(
    unread_only: bool = False,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Retrieves notifications for the admin console."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            if unread_only:
                cursor.execute(
                    "SELECT * FROM admin_notifications WHERE is_read = 0 ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
            else:
                cursor.execute(
                    "SELECT * FROM admin_notifications ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

def mark_notification_read(notification_id: str) -> bool:
    """Marks a notification as read."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE admin_notifications SET is_read = 1 WHERE id = ?", (notification_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

# ============================================================================
# 14. DEVICE FINGERPRINTING & ANTI-ABUSE POOL (PRD Section 6)
# ============================================================================

def record_device_activity(
    device_id: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Dict[str, Any]:
    """Records device activity, attaches user account, and tracks last-seen."""
    if not device_id:
        return {}
    clean_dev = device_id.strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    record_id = f"dev-{uuid.uuid4().hex}"

    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM devices WHERE device_id = ? AND user_id = ?", (clean_dev, user_id))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("""
                UPDATE devices SET
                    last_seen = ?,
                    ip_address = coalesce(?, ip_address),
                    user_agent = coalesce(?, user_agent)
                WHERE device_id = ? AND user_id = ?
                """, (now_iso, ip_address, user_agent, clean_dev, user_id))
            else:
                cursor.execute("""
                INSERT INTO devices (
                    id, device_id, user_id, ip_address, user_agent, is_whitelisted, first_seen, last_seen
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                """, (record_id, clean_dev, user_id, ip_address, user_agent, now_iso, now_iso))

            # Also associate device_id on user record if user_id is provided
            if user_id:
                cursor.execute("UPDATE users SET device_id = ? WHERE id = ? AND (device_id IS NULL OR device_id = '')", (clean_dev, user_id))

            conn.commit()
            return {"device_id": clean_dev, "user_id": user_id, "last_seen": now_iso}
        finally:
            conn.close()

def is_device_whitelisted(device_id: str) -> bool:
    """Checks whether a device is whitelisted by an administrator for shared usage."""
    if not device_id:
        return False
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT is_whitelisted FROM devices WHERE device_id = ? AND is_whitelisted = 1 LIMIT 1", (device_id.strip(),))
            return cursor.fetchone() is not None
        finally:
            conn.close()

def set_device_whitelist(device_id: str, whitelisted: bool) -> bool:
    """Whitelists or un-whitelists a device for shared genuine shop computer usage."""
    if not device_id:
        return False
    val = 1 if whitelisted else 0
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE devices SET is_whitelisted = ? WHERE device_id = ?", (val, device_id.strip()))
            conn.commit()
            return True
        finally:
            conn.close()

def get_device_users(device_id: str) -> List[str]:
    """Retrieves all distinct user IDs linked to a specific device."""
    if not device_id:
        return []
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT user_id FROM devices WHERE device_id = ? AND user_id IS NOT NULL", (device_id.strip(),))
            return [r[0] for r in cursor.fetchall() if r[0]]
        finally:
            conn.close()

def get_device_daily_usage(device_id: str, date_ist: str) -> int:
    """
    Computes shared daily pool usage across all non-whitelisted accounts on a device.
    PRD Section 6: If the same device is used to log in to several accounts,
    all of them share one daily pool of 5 credits.
    """
    if not device_id:
        return 0
    if is_device_whitelisted(device_id):
        return 0  # Whitelisted devices get independent account quotas

    users = get_device_users(device_id)
    if not users:
        return 0

    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in users)
            cursor.execute(f"""
            SELECT coalesce(sum(pages_used), 0) FROM daily_usage
            WHERE user_id IN ({placeholders}) AND date_str = ?
            """, (*users, date_ist))
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        finally:
            conn.close()

# ============================================================================
# 15. CONVERTED BILLS & DEDUPLICATION (PRD Section 4 & 5)
# ============================================================================

def record_converted_bill(
    user_id: str,
    bill_number: str,
    bill_date: str,
    company_name: str,
    total_amount: float,
    fingerprint_hash: str,
    page_count: int,
    date_ist: str
) -> str:
    """Persists record of converted bill identity for re-upload deduplication."""
    bill_id = f"bill-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO converted_bills (
                id, user_id, bill_number, bill_date, company_name, total_amount,
                fingerprint_hash, page_count, date_ist, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bill_id, user_id, bill_number, bill_date, company_name,
                float(total_amount), fingerprint_hash, int(page_count), date_ist, now_iso
            ))
            conn.commit()
            return bill_id
        finally:
            conn.close()

def is_bill_already_converted_today(user_id: str, fingerprint_hash: str, date_ist: str) -> bool:
    """
    Checks if this exact bill identity was already converted today by this account.
    PRD Section 4 & 5: Same bill uploaded again later the same day costs 0 credits.
    """
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT id FROM converted_bills
            WHERE user_id = ? AND fingerprint_hash = ? AND date_ist = ?
            LIMIT 1
            """, (user_id, fingerprint_hash, date_ist))
            return cursor.fetchone() is not None
        finally:
            conn.close()

def get_user_converted_bills(user_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Retrieves bill history for Staff and Normal users."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM converted_bills
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """, (user_id, limit, offset))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

# ============================================================================
# 16. SUBSCRIPTIONS & VERIFIED GOLD TIER (PRD Section 8 & 9)
# ============================================================================

def create_subscription(
    user_id: str,
    user_email: str,
    user_name: str,
    amount: float = 299.0,
    payment_method: str = "UPI_MANUAL",
    txn_id: Optional[str] = None,
    screenshot_path: Optional[str] = None,
    status: str = "PENDING_APPROVAL"
) -> Dict[str, Any]:
    """Creates a new Staff subscription record."""
    sub_id = f"sub-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    # 30 calendar days duration
    from datetime import timedelta
    end_date = (now + timedelta(days=30)).isoformat()
    grace_until = (now + timedelta(days=33)).isoformat()  # 3-day grace period

    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO subscriptions (
                id, user_id, user_email, user_name, plan_name, amount, status,
                payment_method, txn_id, screenshot_path, start_date, end_date,
                grace_until, autopay, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'STAFF_MONTHLY', ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """, (
                sub_id, user_id, user_email, user_name, float(amount), status,
                payment_method, txn_id, screenshot_path, now_iso, end_date,
                grace_until, now_iso, now_iso
            ))
            conn.commit()
            return {
                "id": sub_id,
                "user_id": user_id,
                "user_email": user_email,
                "amount": amount,
                "status": status,
                "start_date": now_iso,
                "end_date": end_date,
                "grace_until": grace_until
            }
        finally:
            conn.close()

def get_user_subscription(user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves active or latest subscription for a user."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM subscriptions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """, (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

def get_all_subscriptions(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves subscriptions for Admin console."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            if status and status.upper() != "ALL":
                cursor.execute("SELECT * FROM subscriptions WHERE status = ? ORDER BY created_at DESC", (status.upper(),))
            else:
                cursor.execute("SELECT * FROM subscriptions ORDER BY created_at DESC")
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

def approve_subscription(sub_id: str, admin_id: str, admin_name: str, notes: Optional[str] = None) -> bool:
    """
    Approves subscription payment:
    1. Updates subscription to ACTIVE.
    2. Elevates user to role='STAFF', staff_source='SUBSCRIPTION', is_gold=1, sets subscription_expiry.
    3. Logs staff audit action.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,))
            sub = cursor.fetchone()
            if not sub:
                return False
            sub_dict = dict(sub)
            user_id = sub_dict["user_id"]
            user_email = sub_dict["user_email"]
            end_date = sub_dict["end_date"]

            # Update subscription
            cursor.execute("""
            UPDATE subscriptions SET
                status = 'ACTIVE',
                approved_by = ?,
                approved_at = ?,
                admin_notes = ?,
                updated_at = ?
            WHERE id = ?
            """, (admin_name, now_iso, notes, now_iso, sub_id))

            # Elevate user to Staff with Gold Tick
            cursor.execute("""
            UPDATE users SET
                role = 'STAFF',
                staff_source = 'SUBSCRIPTION',
                is_gold = 1,
                subscription_expiry = ?,
                updated_at = ?
            WHERE id = ? OR email = ?
            """, (end_date, now_iso, user_id, user_email))

            conn.commit()

            # Record audit log
            log_staff_action(
                admin_id=admin_id,
                admin_name=admin_name,
                action="APPROVE_SUBSCRIPTION",
                target_user_id=user_id,
                target_user_email=user_email,
                details=f"Approved monthly subscription ({sub_id}). Granted Staff role and Gold Verified Tick until {end_date}."
            )
            return True
        finally:
            conn.close()

def reject_subscription(sub_id: str, admin_id: str, admin_name: str, reason: Optional[str] = None) -> bool:
    """Rejects pending subscription request."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,))
            sub = cursor.fetchone()
            if not sub:
                return False
            sub_dict = dict(sub)
            user_id = sub_dict["user_id"]
            user_email = sub_dict["user_email"]

            cursor.execute("""
            UPDATE subscriptions SET
                status = 'REJECTED',
                approved_by = ?,
                approved_at = ?,
                admin_notes = ?,
                updated_at = ?
            WHERE id = ?
            """, (admin_name, now_iso, reason or "Payment verification declined", now_iso, sub_id))
            conn.commit()

            log_staff_action(
                admin_id=admin_id,
                admin_name=admin_name,
                action="REJECT_SUBSCRIPTION",
                target_user_id=user_id,
                target_user_email=user_email,
                details=f"Rejected subscription ({sub_id}). Reason: {reason or 'Payment verification declined'}."
            )
            return True
        finally:
            conn.close()

# ============================================================================
# 17. STAFF GROUP MANAGEMENT (PRD Section 7 & 8)
# ============================================================================

def get_all_staff_users(search: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all users in the Staff group with source, Gold Tick status, and expiry."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            if search:
                term = f"%{search.strip().lower()}%"
                cursor.execute("""
                SELECT * FROM users
                WHERE role = 'STAFF' AND (
                    lower(email) LIKE ? OR lower(coalesce(full_name, '')) LIKE ? OR lower(id) LIKE ?
                )
                ORDER BY created_at DESC
                """, (term, term, term))
            else:
                cursor.execute("SELECT * FROM users WHERE role = 'STAFF' ORDER BY created_at DESC")

            rows = cursor.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["is_gold"] = bool(d.get("is_gold"))
                d["is_unlimited"] = True
                results.append(d)
            return results
        finally:
            conn.close()

def add_user_to_staff(
    user_id: str,
    admin_id: str,
    admin_name: str,
    source: str = "ADMIN",
    is_gold: bool = False,
    expiry: Optional[str] = None
) -> bool:
    """
    Adds user to Staff group:
    PRD Section 7: Staff added manually by admin = Staff without Gold Tick (unless is_gold=True).
    Unlimited bills, no admin powers, no daily limit counters.
    Authoritatively persists to SQLite users table, staff_memberships table, in-memory cache, and Supabase.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    effective_expiry = expiry or "2099-12-31T23:59:59+00:00"
    last_valid = (expiry[:10] if expiry else "2099-12-31")
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ? OR LOWER(email) = ?", (user_id, user_id.lower()))
            u = cursor.fetchone()
            if not u:
                return False
            u_dict = dict(u)
            uid = u_dict["id"]
            email = u_dict["email"]
            name = u_dict.get("full_name") or u_dict.get("username") or email.split("@")[0]
            phone = u_dict.get("mobile_number") or ""

            # 1. Update users table
            cursor.execute("""
            UPDATE users SET
                role = 'STAFF',
                staff_source = ?,
                is_gold = ?,
                is_unlimited = 1,
                subscription_expiry = ?,
                updated_at = ?
            WHERE id = ?
            """, (source, 1 if is_gold else 0, expiry, now_iso, uid))

            # 2. Upsert staff_memberships table
            cursor.execute("SELECT id FROM staff_memberships WHERE user_id = ? OR LOWER(user_email) = ?", (uid, email.lower()))
            existing_mem = cursor.fetchone()
            if existing_mem:
                cursor.execute("""
                UPDATE staff_memberships SET
                    user_id = ?,
                    user_email = ?,
                    user_name = ?,
                    staff_status = 'ACTIVE',
                    membership_started_at = ?,
                    membership_expires_at = ?,
                    last_valid_day = ?,
                    is_gold = ?,
                    updated_at = ?
                WHERE id = ?
                """, (
                    uid, email, name, now_iso, effective_expiry, last_valid,
                    1 if is_gold else 0, now_iso, existing_mem["id"]
                ))
            else:
                mem_id = f"mem_adm_{uuid.uuid4().hex[:12]}"
                cursor.execute("""
                INSERT INTO staff_memberships (
                    id, user_id, user_email, user_name, customer_phone, staff_status,
                    membership_started_at, membership_expires_at, last_valid_day,
                    is_gold, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?)
                """, (
                    mem_id, uid, email, name, phone,
                    now_iso, effective_expiry, last_valid,
                    1 if is_gold else 0, now_iso, now_iso
                ))

            conn.commit()

            # 3. Synchronize in-memory cache and active sessions immediately
            try:
                from app.core import user_store
                with user_store._LOCK:
                    if uid in user_store.REGISTERED_USERS:
                        user_store.REGISTERED_USERS[uid].update({
                            "role": "STAFF",
                            "is_unlimited": True,
                            "is_gold": bool(is_gold),
                            "staff_source": source,
                            "subscription_expiry": expiry
                        })
                    for token, sess in list(user_store.ACTIVE_SESSIONS.items()):
                        if sess.get("user_id") == uid or (sess.get("email") and sess.get("email").lower() == email.lower()):
                            sess["role"] = "STAFF"
                            sess["is_unlimited"] = True
                            sess["is_gold"] = bool(is_gold)
                            sess["staff_source"] = source
                            sess["subscription_expiry"] = expiry
            except Exception as _sync_err:
                logger.warning(f"Error syncing in-memory staff state: {_sync_err}")

            # 4. Synchronize Supabase profile
            try:
                from app.core.supabase_service import SupabaseService
                if SupabaseService.is_configured():
                    SupabaseService.upsert_profile({
                        "id": uid,
                        "role": "STAFF",
                        "is_gold": bool(is_gold),
                        "is_unlimited": True
                    })
            except Exception as _sb_err:
                logger.warning(f"Error syncing staff status to Supabase: {_sb_err}")

            log_staff_action(
                admin_id=admin_id,
                admin_name=admin_name,
                action="ADD_STAFF",
                target_user_id=uid,
                target_user_email=email,
                details=f"Added to Staff group (source={source}, gold_tick={is_gold}, expiry={expiry or 'unlimited'})."
            )
            return True
        finally:
            conn.close()

def remove_user_from_staff(user_id: str, admin_id: str, admin_name: str) -> bool:
    """
    Removes user from Staff group:
    Reverts role to 'USER', strips Gold Tick, restores 5 bills/day limit immediately.
    Authoritatively updates SQLite users, staff_memberships table, in-memory cache, and Supabase.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ? OR LOWER(email) = ?", (user_id, user_id.lower()))
            u = cursor.fetchone()
            if not u:
                return False
            u_dict = dict(u)
            uid = u_dict["id"]
            email = u_dict["email"]

            # 1. Update users table
            cursor.execute("""
            UPDATE users SET
                role = 'USER',
                staff_source = NULL,
                is_gold = 0,
                is_unlimited = 0,
                subscription_expiry = NULL,
                updated_at = ?
            WHERE id = ?
            """, (now_iso, uid))

            # 2. Update staff_memberships table to CANCELLED
            cursor.execute("""
            UPDATE staff_memberships SET
                staff_status = 'CANCELLED',
                is_gold = 0,
                updated_at = ?
            WHERE user_id = ? OR LOWER(user_email) = ?
            """, (now_iso, uid, email.lower()))

            conn.commit()

            # 3. Synchronize in-memory cache and active sessions immediately
            try:
                from app.core import user_store
                with user_store._LOCK:
                    if uid in user_store.REGISTERED_USERS:
                        user_store.REGISTERED_USERS[uid].update({
                            "role": "USER",
                            "is_unlimited": False,
                            "is_gold": False,
                            "staff_source": None,
                            "subscription_expiry": None
                        })
                    for token, sess in list(user_store.ACTIVE_SESSIONS.items()):
                        if sess.get("user_id") == uid or (sess.get("email") and sess.get("email").lower() == email.lower()):
                            sess["role"] = "USER"
                            sess["is_unlimited"] = False
                            sess["is_gold"] = False
                            sess["staff_source"] = None
                            sess["subscription_expiry"] = None
            except Exception as _sync_err:
                logger.warning(f"Error syncing in-memory staff state: {_sync_err}")

            # 4. Synchronize Supabase profile
            try:
                from app.core.supabase_service import SupabaseService
                if SupabaseService.is_configured():
                    SupabaseService.upsert_profile({
                        "id": uid,
                        "role": "USER",
                        "is_gold": False,
                        "is_unlimited": False
                    })
            except Exception as _sb_err:
                logger.warning(f"Error syncing staff removal to Supabase: {_sb_err}")

            log_staff_action(
                admin_id=admin_id,
                admin_name=admin_name,
                action="REMOVE_STAFF",
                target_user_id=uid,
                target_user_email=email,
                details="Removed from Staff group. Reverted to standard 5 bills/day plan."
            )
            return True
        finally:
            conn.close()

def set_user_gold_tick(user_id: str, is_gold: bool, admin_id: str, admin_name: str) -> bool:
    """Manually grants or revokes the Kangra Hub Gold Tick for a Staff user."""
    now_iso = datetime.now(timezone.utc).isoformat()
    val = 1 if is_gold else 0
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ? OR email = ?", (user_id, user_id.lower()))
            u = cursor.fetchone()
            if not u:
                return False
            u_dict = dict(u)
            uid = u_dict["id"]
            email = u_dict["email"]

            cursor.execute("UPDATE users SET is_gold = ?, updated_at = ? WHERE id = ?", (val, now_iso, uid))
            conn.commit()

            log_staff_action(
                admin_id=admin_id,
                admin_name=admin_name,
                action="TOGGLE_GOLD_TICK",
                target_user_id=uid,
                target_user_email=email,
                details=f"{'Granted' if is_gold else 'Revoked'} Gold Verified Tick."
            )
            return True
        finally:
            conn.close()

def extend_user_subscription(user_id: str, days: int, admin_id: str, admin_name: str) -> bool:
    """Extends a Staff user's subscription expiry date by N days."""
    now_iso = datetime.now(timezone.utc).isoformat()
    from datetime import timedelta
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ? OR email = ?", (user_id, user_id.lower()))
            u = cursor.fetchone()
            if not u:
                return False
            u_dict = dict(u)
            uid = u_dict["id"]
            email = u_dict["email"]

            curr_exp = u_dict.get("subscription_expiry")
            if curr_exp:
                try:
                    exp_dt = datetime.fromisoformat(curr_exp.replace("Z", "+00:00"))
                except Exception:
                    exp_dt = datetime.now(timezone.utc)
            else:
                exp_dt = datetime.now(timezone.utc)

            new_exp = (exp_dt + timedelta(days=days)).isoformat()
            cursor.execute("UPDATE users SET subscription_expiry = ?, updated_at = ? WHERE id = ?", (new_exp, now_iso, uid))
            conn.commit()

            log_staff_action(
                admin_id=admin_id,
                admin_name=admin_name,
                action="EXTEND_SUBSCRIPTION",
                target_user_id=uid,
                target_user_email=email,
                details=f"Extended subscription by {days} days to {new_exp}."
            )
            return True
        finally:
            conn.close()

def log_staff_action(
    admin_id: str,
    admin_name: str,
    action: str,
    target_user_id: str,
    target_user_email: str,
    details: str
):
    """Writes an entry to the staff audit log."""
    log_id = f"stf-log-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO staff_audit_logs (
                id, admin_id, admin_name, action, target_user_id, target_user_email, details, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (log_id, admin_id, admin_name, action, target_user_id, target_user_email, details, now_iso))
            conn.commit()
        finally:
            conn.close()

def get_staff_audit_logs(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Retrieves staff audit log entries."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM staff_audit_logs ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

def get_suspicious_activity_logs() -> List[Dict[str, Any]]:
    """
    Detects anti-abuse risk signals for Admin review:
    1. Multiple accounts using the same non-whitelisted device ID.
    2. Multiple signups from the same IP address.
    3. Cross-account duplicate bill fingerprint uploads.
    """
    suspicious = []
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            # 1. Multi-account devices
            cursor.execute("""
            SELECT device_id, count(DISTINCT user_id) as acc_count, group_concat(user_id, ', ') as user_ids, max(last_seen) as latest
            FROM devices
            WHERE is_whitelisted = 0 AND user_id IS NOT NULL
            GROUP BY device_id
            HAVING count(DISTINCT user_id) > 1
            ORDER BY acc_count DESC LIMIT 20;
            """)
            for r in cursor.fetchall():
                suspicious.append({
                    "type": "MULTI_ACCOUNT_DEVICE",
                    "severity": "WARNING",
                    "device_id": r["device_id"],
                    "accounts_count": r["acc_count"],
                    "details": f"Device {r['device_id'][:12]}... is associated with {r['acc_count']} accounts ({r['user_ids'][:30]}...).",
                    "timestamp": r["latest"]
                })

            # 2. Duplicate bill uploads across different accounts
            cursor.execute("""
            SELECT fingerprint_hash, bill_number, company_name, count(DISTINCT user_id) as user_count, max(created_at) as latest
            FROM converted_bills
            GROUP BY fingerprint_hash
            HAVING count(DISTINCT user_id) > 1
            ORDER BY user_count DESC LIMIT 20;
            """)
            for r in cursor.fetchall():
                suspicious.append({
                    "type": "CROSS_ACCOUNT_BILL_DUPLICATION",
                    "severity": "ALERT",
                    "bill_number": r["bill_number"],
                    "company_name": r["company_name"],
                    "details": f"Identical bill #{r['bill_number']} ({r['company_name']}) was converted across {r['user_count']} different user accounts.",
                    "timestamp": r["latest"]
                })

            return suspicious
        finally:
            conn.close()

# ==============================================================================
# RAZORPAY STAFF MEMBERSHIP OPERATIONS (PRD Section 3, 4, 5, 6, 7, 8)
# ==============================================================================

def get_staff_membership(user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves raw Staff Membership record for a user."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM staff_memberships WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

def update_staff_membership_status(user_id: str, status: str) -> bool:
    """Updates the staff_status of a user's staff membership record."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE staff_memberships SET
                staff_status = ?,
                updated_at = ?
            WHERE user_id = ?
            """, (status, now_iso, user_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

def get_staff_membership_with_status_eval(
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    server_now_utc: Optional[datetime] = None
) -> Optional[Dict[str, Any]]:
    """
    Evaluates Staff Membership validity against trusted server UTC time (Section 4 & 6).
    Searches by user_id or user_email (case-insensitive).
    If server_now >= membership_expires_at:
      - Automatically sets staff_status = 'EXPIRED'
      - Removes Gold Tick and Staff role, reverting to standard USER with 5 free bills/day
      - Returns status with is_active = False
    """
    from app.core.staff_membership import parse_iso_to_utc, ensure_utc, format_expiry_display, IST

    clean_email = user_email.strip().lower() if user_email else None
    now_utc = ensure_utc(server_now_utc)
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            if user_id and clean_email:
                cursor.execute("""
                    SELECT * FROM staff_memberships 
                    WHERE user_id = ? OR LOWER(user_email) = ? 
                    ORDER BY id DESC LIMIT 1
                """, (user_id, clean_email))
            elif user_id:
                cursor.execute("""
                    SELECT * FROM staff_memberships 
                    WHERE user_id = ? 
                    ORDER BY id DESC LIMIT 1
                """, (user_id,))
            elif clean_email:
                cursor.execute("""
                    SELECT * FROM staff_memberships 
                    WHERE LOWER(user_email) = ? 
                    ORDER BY id DESC LIMIT 1
                """, (clean_email,))
            else:
                return None

            row = cursor.fetchone()
            if not row:
                return None

            mem = dict(row)
            mem_id = mem["id"]
            matched_user_id = mem["user_id"]

            # If user_id was provided and differs from row's user_id, synchronize user_id across tables
            if user_id and matched_user_id != user_id:
                try:
                    cursor.execute("UPDATE staff_memberships SET user_id = ? WHERE id = ?", (user_id, mem_id))
                    cursor.execute("UPDATE membership_renewal_history SET user_id = ? WHERE user_id = ?", (user_id, matched_user_id))
                    cursor.execute("UPDATE users SET id = ? WHERE LOWER(email) = ?", (user_id, clean_email or ""))
                    conn.commit()
                    mem["user_id"] = user_id
                except Exception as sync_err:
                    logger.debug(f"Error syncing user_id across membership tables: {sync_err}")

            # Respect cancelled or revoked admin actions
            if mem.get("staff_status") in ("CANCELLED", "REVOKED", "EXPIRED", "SUSPENDED"):
                mem["is_active"] = False
                return mem

            exp_utc = parse_iso_to_utc(mem.get("membership_expires_at"))
            if not exp_utc:
                mem["is_active"] = (mem.get("staff_status") == "ACTIVE")
                return mem

            # Re-evaluate status against server time
            if now_utc >= exp_utc:
                # Expiry boundary reached or passed!
                if mem["staff_status"] != "EXPIRED":
                    now_iso = now_utc.isoformat()
                    cursor.execute("""
                    UPDATE staff_memberships SET
                        staff_status = 'EXPIRED',
                        updated_at = ?
                    WHERE id = ?
                    """, (now_iso, mem_id))

                    # Revert user to standard USER in SQLite
                    effective_uid = user_id or matched_user_id
                    cursor.execute("""
                    UPDATE users SET
                        role = 'USER',
                        is_gold = 0,
                        is_unlimited = 0,
                        updated_at = ?
                    WHERE (id = ? OR (email IS NOT NULL AND LOWER(email) = ?)) AND staff_source = 'RAZORPAY_STAFF'
                    """, (now_iso, effective_uid, clean_email or ""))

                    conn.commit()
                    mem["staff_status"] = "EXPIRED"

                    try:
                        from app.core.supabase_service import SupabaseService
                        if SupabaseService.is_configured():
                            SupabaseService.upsert_profile({
                                "id": effective_uid,
                                "role": "USER",
                                "is_gold": False,
                                "is_unlimited": False
                            })
                    except Exception as _sb_err:
                        logger.warning(f"Could not sync expired staff profile to Supabase: {_sb_err}")

                mem["is_active"] = False
            else:
                mem["is_active"] = (mem.get("staff_status") == "ACTIVE")
                if mem.get("staff_status") != "CANCELLED":
                    mem["staff_status"] = "ACTIVE"

            # Compute standardized display wording
            exp_ist = exp_utc.astimezone(IST)
            next_day = exp_ist.date()
            last_valid = next_day - timedelta(days=1)
            mem["display_wording"] = format_expiry_display(last_valid, next_day)
            mem["last_valid_day_str"] = last_valid.isoformat()
            mem["next_day_str"] = next_day.isoformat()

            return mem
        finally:
            conn.close()

def process_verified_membership_payment(
    user_id: str,
    user_email: str,
    user_name: str,
    payment_id: str,
    order_id: Optional[str],
    amount_paise: int,
    payment_status: str,
    captured_at_utc: datetime,
    verified_at_utc: datetime,
    raw_response: Optional[Dict[str, Any]] = None,
    customer_phone: Optional[str] = None,
    customer_name: Optional[str] = None,
    customer_email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Atomically processes a verified Razorpay payment for Staff Membership (Section 3, 5, 7):
    1. Enforces idempotency via unique payment_id (never extends twice).
    2. Enforces the One Exact 30-Day and IST Midnight rule (Section 4).
    3. Handles initial activation, early renewal (stacks 30 days onto existing expiry),
       and renewal after expiry (starts fresh 30-day period from payment date).
    4. Elevates user in users table and records renewal audit history.
    5. Saves submitted customer contact details for this specific subscription/order
       WITHOUT overwriting the user's permanent signup/profile mobile number.
    """
    from app.core.staff_membership import (
        ensure_utc,
        parse_iso_to_utc,
        compute_initial_membership,
        compute_renewal_membership,
        STAFF_MEMBERSHIP_DURATION_DAYS
    )

    clean_pid = payment_id.strip()
    captured_utc = ensure_utc(captured_at_utc)
    verified_utc = ensure_utc(verified_at_utc)
    now_iso = verified_utc.isoformat()
    raw_str = json.dumps(raw_response or {})
    effective_name = (customer_name or "").strip() or user_name
    effective_email = (customer_email or "").strip().lower() or user_email
    clean_cust_phone = (customer_phone or "").strip() or None

    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()

            # 1. Idempotency Check: Check if this payment was already processed
            cursor.execute("SELECT * FROM membership_payments WHERE payment_id = ?", (clean_pid,))
            existing_pay = cursor.fetchone()
            if existing_pay:
                logger.info(f"Idempotent hit: payment {clean_pid} already processed for user {existing_pay['user_id']}")
                # Return current membership without duplicating extension
                cursor.execute("SELECT * FROM staff_memberships WHERE user_id = ?", (user_id,))
                cur_mem = cursor.fetchone()
                return {
                    "success": True,
                    "idempotent": True,
                    "message": "Payment has already been processed and membership is active.",
                    "membership": dict(cur_mem) if cur_mem else None
                }

            # 2. Check current membership to determine renewal mode
            cursor.execute("SELECT * FROM staff_memberships WHERE user_id = ?", (user_id,))
            mem_row = cursor.fetchone()

            if mem_row:
                old_mem = dict(mem_row)
                old_exp_utc = parse_iso_to_utc(old_mem["membership_expires_at"])
                calc = compute_renewal_membership(
                    existing_expires_at_utc=old_exp_utc,
                    payment_captured_utc=captured_utc,
                    payment_verified_utc=verified_utc
                )
                renewal_type = calc["renewal_type"]
                new_expiry_iso = calc["new_expiry"]
                last_valid_day = calc["last_valid_day"]
                previous_expiry_iso = calc.get("previous_expiry")
                display_wording = calc["display_wording"]
                started_at_iso = old_mem["membership_started_at"] if renewal_type == "EARLY_RENEWAL" else now_iso
            else:
                # Brand new membership
                calc = compute_initial_membership(verified_utc)
                renewal_type = "NEW"
                new_expiry_iso = calc["membership_expires_at"]
                last_valid_day = calc["last_valid_day"]
                previous_expiry_iso = None
                display_wording = calc["display_wording"]
                started_at_iso = now_iso

            # 3. Insert payment record (Unique constraint prevents races)
            pay_uuid = f"pay-{uuid.uuid4().hex[:12]}"
            cursor.execute("""
            INSERT INTO membership_payments (
                id, user_id, user_email, payment_id, order_id, payment_amount,
                currency, payment_status, payment_verified_at, captured_at,
                raw_response, created_at, customer_phone, customer_name
            ) VALUES (?, ?, ?, ?, ?, ?, 'INR', ?, ?, ?, ?, ?, ?, ?)
            """, (
                pay_uuid, user_id, effective_email, clean_pid, order_id,
                amount_paise, payment_status, now_iso,
                captured_utc.isoformat(), raw_str, now_iso,
                clean_cust_phone, effective_name
            ))

            # 4. Upsert staff_memberships
            mem_uuid = mem_row["id"] if mem_row else f"mem-{uuid.uuid4().hex[:12]}"
            if mem_row:
                cursor.execute("""
                UPDATE staff_memberships SET
                    user_email = ?,
                    user_name = ?,
                    customer_phone = coalesce(?, customer_phone),
                    staff_status = 'ACTIVE',
                    membership_started_at = ?,
                    membership_expires_at = ?,
                    last_valid_day = ?,
                    last_payment_id = ?,
                    is_gold = 1,
                    updated_at = ?
                WHERE user_id = ?
                """, (
                    user_email, user_name, clean_cust_phone, started_at_iso, new_expiry_iso,
                    last_valid_day, clean_pid, now_iso, user_id
                ))
            else:
                cursor.execute("""
                INSERT INTO staff_memberships (
                    id, user_id, user_email, user_name, customer_phone, staff_status,
                    membership_started_at, membership_expires_at, last_valid_day,
                    last_payment_id, is_gold, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, 1, ?, ?)
                """, (
                    mem_uuid, user_id, user_email, user_name, clean_cust_phone,
                    started_at_iso, new_expiry_iso, last_valid_day,
                    clean_pid, now_iso, now_iso
                ))

            # 5. Insert renewal history log
            ren_uuid = f"ren-{uuid.uuid4().hex[:12]}"
            cursor.execute("""
            INSERT INTO membership_renewal_history (
                id, user_id, payment_id, renewal_type, previous_expiry,
                new_expiry, days_added, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 30, ?)
            """, (
                ren_uuid, user_id, clean_pid, renewal_type,
                previous_expiry_iso, new_expiry_iso, now_iso
            ))

            # 6. Elevate user in users table
            clean_email_lower = user_email.strip().lower()
            cursor.execute("""
            UPDATE users SET
                role = 'STAFF',
                staff_source = 'RAZORPAY_STAFF',
                is_gold = 1,
                is_unlimited = 1,
                subscription_expiry = ?,
                updated_at = ?
            WHERE id = ? OR LOWER(email) = ?
            """, (new_expiry_iso, now_iso, user_id, clean_email_lower))

            if cursor.rowcount == 0:
                cursor.execute("""
                INSERT INTO users (
                    id, email, full_name, mobile_number, role, is_unlimited,
                    is_gold, staff_source, subscription_expiry,
                    account_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'STAFF', 1, 1, 'RAZORPAY_STAFF', ?, 'ACTIVE', ?, ?)
                """, (user_id, clean_email_lower, user_name, clean_cust_phone, new_expiry_iso, now_iso, now_iso))

            # 7. Log to staff audit
            log_id = f"stf-log-{uuid.uuid4().hex[:12]}"
            audit_details = f"Razorpay payment {clean_pid} (Rs 499) verified. Type: {renewal_type}. {display_wording}"
            cursor.execute("""
            INSERT INTO staff_audit_logs (id, admin_id, admin_name, action, target_user_id, target_user_email, details, created_at)
            VALUES (?, 'RAZORPAY_GATEWAY', 'Razorpay Automated Verification', 'MEMBERSHIP_ACTIVATED', ?, ?, ?, ?)
            """, (log_id, user_id, user_email, audit_details, now_iso))

            conn.commit()

            try:
                from app.core.supabase_service import SupabaseService
                if SupabaseService.is_configured():
                    SupabaseService.upsert_profile({
                        "id": user_id,
                        "email": user_email,
                        "role": "STAFF",
                        "is_gold": True,
                        "is_unlimited": True,
                        "staff_source": "RAZORPAY_STAFF",
                        "staff_status": "ACTIVE",
                        "subscription_expiry": new_expiry_iso
                    })
            except Exception as _sb_err:
                logger.warning(f"Could not sync activated staff profile to Supabase: {_sb_err}")

            return {
                "success": True,
                "idempotent": False,
                "message": f"Staff Membership successfully activated! {display_wording}",
                "renewal_type": renewal_type,
                "membership_expires_at": new_expiry_iso,
                "last_valid_day": last_valid_day,
                "display_wording": display_wording,
                "payment_id": clean_pid
            }
        finally:
            conn.close()

def get_user_membership_renewal_history(user_id: Optional[str] = None, user_email: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves complete renewal history for a user by user_id or user_email."""
    clean_email = user_email.strip().lower() if user_email else None
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            if user_id and clean_email:
                cursor.execute("""
                SELECT * FROM membership_renewal_history
                WHERE user_id = ? OR user_id IN (SELECT user_id FROM staff_memberships WHERE LOWER(user_email) = ?)
                ORDER BY created_at DESC
                """, (user_id, clean_email))
            elif user_id:
                cursor.execute("""
                SELECT * FROM membership_renewal_history
                WHERE user_id = ?
                ORDER BY created_at DESC
                """, (user_id,))
            elif clean_email:
                cursor.execute("""
                SELECT * FROM membership_renewal_history
                WHERE user_id IN (SELECT user_id FROM staff_memberships WHERE LOWER(user_email) = ?)
                ORDER BY created_at DESC
                """, (clean_email,))
            else:
                return []
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

def get_all_staff_memberships_admin() -> List[Dict[str, Any]]:
    """Admin view: returns all membership records and latest payment info."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT m.*, p.payment_amount, p.payment_status, p.payment_verified_at, p.captured_at
            FROM staff_memberships m
            LEFT JOIN membership_payments p ON m.last_payment_id = p.payment_id
            ORDER BY m.updated_at DESC
            """)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

def log_membership_notification(
    user_id: str,
    notification_type: str,
    membership_expires_at: str
) -> bool:
    """
    Logs an expiry notification attempt. Returns True if logged, False if already sent.
    (Ensures deduplication per user, notification_type, and expiry timestamp).
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    log_id = f"notif-{uuid.uuid4().hex[:12]}"
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR IGNORE INTO membership_notification_logs (
                id, user_id, notification_type, membership_expires_at, sent_at
            ) VALUES (?, ?, ?, ?, ?)
            """, (log_id, user_id, notification_type, membership_expires_at, now_iso))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

def has_membership_notification_been_sent(
    user_id: str,
    notification_type: str,
    membership_expires_at: str
) -> bool:
    """Checks whether an expiry notification was already sent."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT 1 FROM membership_notification_logs
            WHERE user_id = ? AND notification_type = ? AND membership_expires_at = ?
            """, (user_id, notification_type, membership_expires_at))
            return cursor.fetchone() is not None
        finally:
            conn.close()

# Auto-initialize database on import
init_db()
