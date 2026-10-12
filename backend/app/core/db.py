import os
import sqlite3
import json
import uuid
import logging
import threading
from datetime import datetime, timezone, timedelta
import pytz
from decimal import Decimal
from typing import Dict, Any, List, Optional

logger = logging.getLogger("kangra_hub.db")

_LOCK = threading.Lock()

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

            # 8. Subscription Plan Configurations Table (PRD Section 1 & 2)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscription_plan_configs (
                plan_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price_inr REAL NOT NULL,
                price_paise INTEGER NOT NULL,
                bills_limit INTEGER NOT NULL,
                duration_days INTEGER DEFAULT 30,
                is_unlimited INTEGER DEFAULT 0,
                description TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            """)

            # 9. Membership Payments Table (PRD Section 3 - Razorpay & Subscription Payments)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS membership_payments (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                user_email TEXT NOT NULL,
                user_name TEXT,
                customer_phone TEXT,
                payment_id TEXT UNIQUE NOT NULL,
                order_id TEXT,
                payment_amount REAL NOT NULL,
                amount_paise INTEGER NOT NULL,
                payment_status TEXT NOT NULL,
                payment_verified_at TEXT NOT NULL,
                captured_at TEXT,
                plan_id TEXT DEFAULT 'basic',
                plan_name TEXT DEFAULT 'Basic',
                bills_limit INTEGER DEFAULT 50,
                duration_days INTEGER DEFAULT 30,
                created_at TEXT NOT NULL
            );
            """)

            # 10. Staff Memberships Table (Persistent subscription state per firm)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS staff_memberships (
                id TEXT PRIMARY KEY,
                user_id TEXT UNIQUE NOT NULL,
                user_email TEXT NOT NULL,
                user_name TEXT,
                role TEXT DEFAULT 'STAFF',
                is_unlimited INTEGER DEFAULT 0,
                plan_id TEXT DEFAULT 'basic',
                plan_name TEXT DEFAULT 'Basic',
                bills_limit INTEGER DEFAULT 50,
                membership_started_at TEXT,
                membership_expires_at TEXT NOT NULL,
                last_valid_day TEXT,
                last_payment_id TEXT,
                is_active INTEGER DEFAULT 1,
                price_paid_inr REAL DEFAULT 199.0,
                created_at TEXT,
                updated_at TEXT
            );
            """)

            # 11. Membership Renewal History
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

            # 12. PRD Oct 12, 2026: Daily Quota Usage Table (Independent counters: PDF_PAGE & IMAGE)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_quota_usage (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                quota_date TEXT NOT NULL,
                type TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                updated_at TEXT,
                UNIQUE(user_id, quota_date, type)
            );
            """)

            # 13. PRD Oct 12, 2026: Quota Reservations Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS quota_reservations (
                reservation_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                quota_date TEXT NOT NULL,
                type TEXT NOT NULL,
                reserved_count INTEGER DEFAULT 0,
                consumed_count INTEGER DEFAULT 0,
                released_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'RESERVED',
                created_at TEXT NOT NULL
            );
            """)

            # 14. PRD Oct 12, 2026: Job Pages Tracking Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_pages (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                file_id TEXT,
                page_number INTEGER NOT NULL,
                status TEXT NOT NULL,
                error_reason TEXT,
                transaction_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # 15. PRD Oct 12, 2026: Quota Exceptions Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS quota_exceptions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                limit_type TEXT NOT NULL,
                limit_value INTEGER,
                starts_at TEXT NOT NULL,
                ends_at TEXT,
                reason TEXT,
                granted_by TEXT NOT NULL,
                granted_at TEXT NOT NULL,
                revoked_at TEXT,
                revoked_by TEXT
            );
            """)

            # 16. PRD Oct 12, 2026: Quota Audit Log Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS quota_audit_log (
                id TEXT PRIMARY KEY,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                target_user TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                created_at TEXT NOT NULL
            );
            """)

            # Schema migrations for users table (subscription columns)
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN subscription_plan_id TEXT;")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN subscription_bill_limit INTEGER DEFAULT 0;")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN subscription_expiry TEXT;")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN is_gold INTEGER DEFAULT 0;")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN staff_source TEXT;")
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
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mem_payments_user ON membership_payments(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_staff_memberships_user ON staff_memberships(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_quota_usage_lookup ON daily_quota_usage(user_id, quota_date, type);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quota_reservations_job ON quota_reservations(job_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_pages_job_id ON job_pages(job_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quota_exceptions_user ON quota_exceptions(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quota_audit_log_target ON quota_audit_log(target_user);")

            conn.commit()

            # Seed default subscription plans (Basic ₹199/50 bills, Standard ₹299/150 bills, Premium ₹499/Unlimited)
            _seed_default_subscription_plans(cursor)

            # Seed standard platform users if not present
            _seed_default_users(cursor)
            conn.commit()
            logger.info("Kangra Hub SQLite database initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite database: {e}", exc_info=True)
            conn.rollback()
        finally:
            conn.close()

def _seed_default_users(cursor: sqlite3.Cursor):
    """Seeds baseline development and demo accounts."""
    now_iso = datetime.now(timezone.utc).isoformat()
    defaults = [
        {
            "id": "test-admin-id",
            "email": "admin@tallyxml.in",
            "full_name": "Admin TallyXML",
            "username": "admin",
            "mobile_number": "+919418250639",
            "role": "ADMIN",
            "is_unlimited": 1,
            "account_status": "ACTIVE",
            "email_verified": 1,
            "mobile_verified": 1,
            "registration_date": "2024-01-01T00:00:00Z"
        },
        {
            "id": "test-user-id",
            "email": "user@example.com",
            "full_name": "Test Standard User",
            "username": "testuser",
            "mobile_number": "+919876543210",
            "role": "USER",
            "is_unlimited": 0,
            "account_status": "ACTIVE",
            "email_verified": 1,
            "mobile_verified": 1,
            "registration_date": "2024-01-10T10:00:00Z"
        },
        {
            "id": "test-unlimited-id",
            "email": "unlimited@example.com",
            "full_name": "Test Unlimited User",
            "username": "unlimiteduser",
            "mobile_number": "+919876543299",
            "role": "USER",
            "is_unlimited": 1,
            "account_status": "ACTIVE",
            "email_verified": 1,
            "mobile_verified": 1,
            "registration_date": "2024-01-12T10:00:00Z"
        },
        {
            "id": "usr-demo-1",
            "email": "customer@example.com",
            "full_name": "Rajesh Sharma",
            "username": "rajeshsharma",
            "mobile_number": "+919876543211",
            "role": "USER",
            "is_unlimited": 0,
            "account_status": "ACTIVE",
            "email_verified": 1,
            "mobile_verified": 1,
            "registration_date": "2024-01-15T10:00:00Z"
        },
        {
            "id": "usr-demo-2",
            "email": "vip@example.com",
            "full_name": "Priya Verma",
            "username": "priyaverma",
            "mobile_number": "+919876543212",
            "role": "USER",
            "is_unlimited": 1,
            "account_status": "ACTIVE",
            "email_verified": 1,
            "mobile_verified": 1,
            "registration_date": "2024-02-01T12:00:00Z"
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

def _seed_default_subscription_plans(cursor: sqlite3.Cursor):
    """
    Seeds baseline plans per PRD:
    - Basic: ₹199 (50 bills / month)
    - Standard: ₹299 (150 bills / month)
    - Premium: ₹499 (Unlimited bills / month)
    Zero tax labels, exact pricing.
    """
    from app.core.plans import DEFAULT_SUBSCRIPTION_PLANS
    now_iso = datetime.now(timezone.utc).isoformat()
    for p in DEFAULT_SUBSCRIPTION_PLANS:
        cursor.execute("SELECT plan_id FROM subscription_plan_configs WHERE plan_id = ?", (p["id"],))
        if not cursor.fetchone():
            cursor.execute("""
            INSERT INTO subscription_plan_configs (
                plan_id, name, price_inr, price_paise, bills_limit, duration_days, is_unlimited, description, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p["id"],
                p["name"],
                p["price_inr"],
                p["price_paise"],
                p["bills_limit"],
                p["duration_days"],
                1 if p["is_unlimited"] else 0,
                p.get("tagline", ""),
                now_iso,
                now_iso
            ))

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
                updated = {
                    "full_name": data.get("full_name") if data.get("full_name") is not None else existing_dict["full_name"],
                    "username": data.get("username") if data.get("username") is not None else (existing_dict.get("username") or clean_email.split("@")[0]),
                    "mobile_number": data.get("mobile_number") if data.get("mobile_number") is not None else existing_dict["mobile_number"],
                    "role": data.get("role") if data.get("role") is not None else existing_dict["role"],
                    "is_unlimited": int(bool(data.get("is_unlimited"))) if "is_unlimited" in data else existing_dict["is_unlimited"],
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
        "total_debit": float(job.get("total_debit") or 0.0),
        "total_credit": float(job.get("total_credit") or 0.0),
        "opening_balance": float(job.get("opening_balance")) if job.get("opening_balance") is not None else None,
        "closing_balance": float(job.get("closing_balance")) if job.get("closing_balance") is not None else None,
        "excel_path": job.get("excel_path"),
        "xml_path": job.get("xml_path"),
        "excel_filename": job.get("excel_filename"),
        "xml_filename": job.get("xml_filename"),
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
# SUBSCRIPTION & PAYMENT OPERATIONS (PRD Section 1 & 2)
# ============================================================================

def get_all_subscription_plan_configs() -> Dict[str, Dict[str, Any]]:
    """Returns all subscription plan configs from SQLite."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM subscription_plan_configs")
            return {r["plan_id"]: dict(r) for r in cursor.fetchall()}
        except Exception:
            return {}
        finally:
            conn.close()

def upsert_subscription_plan_config(
    plan_id: str,
    name: Optional[str] = None,
    price_inr: Optional[float] = None,
    bills_limit: Optional[int] = None,
    duration_days: int = 30,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """Updates or inserts a plan configuration."""
    from app.core.plans import DEFAULT_SUBSCRIPTION_PLANS, resolve_plan_id
    canonical = resolve_plan_id(plan_id)
    def_plan = next((p for p in DEFAULT_SUBSCRIPTION_PLANS if p["id"] == canonical), DEFAULT_SUBSCRIPTION_PLANS[0])

    effective_name = name or def_plan["name"]
    effective_price = price_inr if price_inr is not None else def_plan["price_inr"]
    effective_limit = bills_limit if bills_limit is not None else def_plan["bills_limit"]
    price_paise = int(round(effective_price * 100))
    is_unlim = 1 if effective_limit == -1 else 0
    now_iso = datetime.now(timezone.utc).isoformat()

    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO subscription_plan_configs (
                plan_id, name, price_inr, price_paise, bills_limit,
                duration_days, is_unlimited, description, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(plan_id) DO UPDATE SET
                name = excluded.name,
                price_inr = excluded.price_inr,
                price_paise = excluded.price_paise,
                bills_limit = excluded.bills_limit,
                duration_days = excluded.duration_days,
                is_unlimited = excluded.is_unlimited,
                description = coalesce(excluded.description, subscription_plan_configs.description),
                updated_at = excluded.updated_at
            """, (
                canonical, effective_name, effective_price, price_paise, effective_limit,
                duration_days, is_unlim, description, now_iso, now_iso
            ))
            conn.commit()
            return {
                "plan_id": canonical,
                "name": effective_name,
                "price_inr": effective_price,
                "price_paise": price_paise,
                "bills_limit": effective_limit,
                "duration_days": duration_days,
                "is_unlimited": bool(is_unlim)
            }
        finally:
            conn.close()

def get_staff_membership_with_status_eval(
    user_id: str,
    user_email: Optional[str] = None,
    server_now_utc: Optional[datetime] = None
) -> Optional[Dict[str, Any]]:
    """Evaluates membership status against server time."""
    now = server_now_utc or datetime.now(timezone.utc)
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            if user_email:
                cursor.execute("""
                SELECT * FROM staff_memberships 
                WHERE user_id = ? OR LOWER(user_email) = ?
                """, (user_id, user_email.strip().lower()))
            else:
                cursor.execute("SELECT * FROM staff_memberships WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            m = dict(row)
            try:
                exp_dt = datetime.fromisoformat(m["membership_expires_at"].replace("Z", "+00:00"))
                is_active = (now <= exp_dt)
            except Exception:
                is_active = bool(m.get("is_active", 0))

            m["is_active"] = is_active
            return m
        finally:
            conn.close()

def get_active_staff_membership(user_id: str, user_email: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Returns active subscription / staff membership if active, else None."""
    mem = get_staff_membership_with_status_eval(user_id, user_email=user_email)
    if mem and mem.get("is_active"):
        return mem
    return None

def process_verified_membership_payment(
    user_id: str,
    user_email: str,
    user_name: Optional[str],
    payment_id: str,
    order_id: Optional[str],
    amount_paise: int,
    payment_status: str,
    captured_at_utc: datetime,
    verified_at_utc: datetime,
    plan_id: Optional[str] = "basic",
    customer_phone: Optional[str] = None,
    duration_days: int = 30
) -> Dict[str, Any]:
    """
    Idempotent, atomic transaction activating a user subscription per firm.
    Enforces exact plan price (no tax added), bill limits, and 30-day IST midnight validity.
    """
    from app.core.plans import get_plan_by_id, resolve_plan_id
    canonical_plan_id = resolve_plan_id(plan_id)
    plan_info = get_plan_by_id(canonical_plan_id)
    effective_bills_limit = plan_info["bills_limit"]
    effective_is_unlimited = plan_info["is_unlimited"]
    effective_plan_name = plan_info["name"]
    effective_price_inr = plan_info["price_inr"]

    clean_pid = payment_id.strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    tz_ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(tz_ist)

    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()

            # 1. Idempotency Check: prevent duplicate activation
            cursor.execute("SELECT * FROM membership_payments WHERE payment_id = ?", (clean_pid,))
            existing_pay = cursor.fetchone()
            if existing_pay:
                cursor.execute("SELECT * FROM staff_memberships WHERE user_id = ?", (user_id,))
                existing_mem = cursor.fetchone()
                mem_dict = dict(existing_mem) if existing_mem else {}
                return {
                    "success": True,
                    "idempotent": True,
                    "message": f"Payment {clean_pid} already processed. Subscription active.",
                    "plan_id": canonical_plan_id,
                    "plan_name": effective_plan_name,
                    "bills_limit": effective_bills_limit,
                    "is_unlimited": effective_is_unlimited,
                    "membership_expires_at": mem_dict.get("membership_expires_at"),
                    "last_valid_day": mem_dict.get("last_valid_day"),
                    "payment_id": clean_pid
                }

            # 2. Check existing active subscription to compute expiry extension
            cursor.execute("SELECT * FROM staff_memberships WHERE user_id = ?", (user_id,))
            current_mem = cursor.fetchone()

            previous_expiry_iso = None
            renewal_type = "INITIAL"

            if current_mem and current_mem["membership_expires_at"]:
                try:
                    prev_exp = datetime.fromisoformat(current_mem["membership_expires_at"].replace("Z", "+00:00"))
                    prev_exp_ist = prev_exp.astimezone(tz_ist)
                    if prev_exp_ist > now_ist:
                        # Active: extend from existing expiry date
                        base_date = prev_exp_ist
                        renewal_type = "RENEWAL"
                    else:
                        base_date = now_ist
                        renewal_type = "REACTIVATION"
                    previous_expiry_iso = current_mem["membership_expires_at"]
                except Exception:
                    base_date = now_ist
            else:
                base_date = now_ist

            # Calculate new expiry: base_date + duration_days snapped to 23:59:59 IST
            target_date = base_date + timedelta(days=duration_days)
            new_expiry_ist = target_date.replace(hour=23, minute=59, second=59, microsecond=0)
            new_expiry_utc = new_expiry_ist.astimezone(timezone.utc)
            new_expiry_iso = new_expiry_utc.isoformat()
            last_valid_day = new_expiry_ist.strftime("%d %b %Y")
            display_wording = f"Valid through {last_valid_day} until 11:59 PM IST"

            # 3. Insert membership payment record
            pay_uuid = f"mpay-{uuid.uuid4().hex[:12]}"
            cursor.execute("""
            INSERT INTO membership_payments (
                id, user_id, user_email, user_name, customer_phone, payment_id,
                order_id, payment_amount, amount_paise, payment_status,
                payment_verified_at, captured_at, plan_id, plan_name,
                bills_limit, duration_days, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pay_uuid, user_id, user_email, user_name, customer_phone, clean_pid,
                order_id, effective_price_inr, amount_paise, payment_status,
                verified_at_utc.isoformat(), captured_at_utc.isoformat(),
                canonical_plan_id, effective_plan_name, effective_bills_limit,
                duration_days, now_iso
            ))

            # 4. Upsert staff_memberships table
            mem_uuid = f"smem-{uuid.uuid4().hex[:12]}"
            started_at_iso = (current_mem["membership_started_at"] if current_mem else None) or now_iso
            if current_mem:
                cursor.execute("""
                UPDATE staff_memberships SET
                    user_email = ?, user_name = ?, plan_id = ?, plan_name = ?,
                    bills_limit = ?, is_unlimited = ?, membership_expires_at = ?,
                    last_valid_day = ?, last_payment_id = ?, is_active = 1,
                    price_paid_inr = ?, updated_at = ?
                WHERE user_id = ?
                """, (
                    user_email, user_name, canonical_plan_id, effective_plan_name,
                    effective_bills_limit, 1 if effective_is_unlimited else 0,
                    new_expiry_iso, last_valid_day, clean_pid, effective_price_inr,
                    now_iso, user_id
                ))
            else:
                cursor.execute("""
                INSERT INTO staff_memberships (
                    id, user_id, user_email, user_name, role, is_unlimited,
                    plan_id, plan_name, bills_limit, membership_started_at,
                    membership_expires_at, last_valid_day, last_payment_id,
                    is_active, price_paid_inr, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'STAFF', ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """, (
                    mem_uuid, user_id, user_email, user_name,
                    1 if effective_is_unlimited else 0, canonical_plan_id,
                    effective_plan_name, effective_bills_limit, started_at_iso,
                    new_expiry_iso, last_valid_day, clean_pid, effective_price_inr,
                    now_iso, now_iso
                ))

            # 5. Insert renewal history log
            ren_uuid = f"ren-{uuid.uuid4().hex[:12]}"
            cursor.execute("""
            INSERT INTO membership_renewal_history (
                id, user_id, payment_id, renewal_type, previous_expiry,
                new_expiry, days_added, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ren_uuid, user_id, clean_pid, renewal_type,
                previous_expiry_iso, new_expiry_iso, duration_days, now_iso
            ))

            # 6. Update users table with plan details
            clean_email_lower = user_email.strip().lower()
            cursor.execute("""
            UPDATE users SET
                role = 'STAFF',
                staff_source = 'SUBSCRIPTION_PURCHASE',
                is_gold = 1,
                is_unlimited = ?,
                subscription_plan_id = ?,
                subscription_bill_limit = ?,
                subscription_expiry = ?,
                updated_at = ?
            WHERE id = ? OR LOWER(email) = ?
            """, (
                1 if effective_is_unlimited else 0,
                canonical_plan_id,
                effective_bills_limit,
                new_expiry_iso,
                now_iso,
                user_id,
                clean_email_lower
            ))

            conn.commit()

            return {
                "success": True,
                "idempotent": False,
                "message": f"{effective_plan_name} subscription successfully activated! {display_wording}",
                "renewal_type": renewal_type,
                "plan_id": canonical_plan_id,
                "plan_name": effective_plan_name,
                "bills_limit": effective_bills_limit,
                "is_unlimited": effective_is_unlimited,
                "membership_expires_at": new_expiry_iso,
                "last_valid_day": last_valid_day,
                "display_wording": display_wording,
                "payment_id": clean_pid
            }
        finally:
            conn.close()

def get_user_bills_converted_since(user_id: str, start_date_iso: Optional[str] = None) -> int:
    """Returns count of bank statement / bill conversions completed by this user since start_date_iso."""
    if not user_id:
        return 0
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            if start_date_iso:
                cursor.execute("""
                    SELECT COUNT(*) as cnt FROM conversions
                    WHERE (user_id = ? OR user_email = ?) AND created_at >= ? AND status IN ('COMPLETED', 'PARTIALLY_COMPLETED')
                """, (user_id, user_id, start_date_iso))
            else:
                cursor.execute("""
                    SELECT COUNT(*) as cnt FROM conversions
                    WHERE (user_id = ? OR user_email = ?) AND status IN ('COMPLETED', 'PARTIALLY_COMPLETED')
                """, (user_id, user_id))
            row = cursor.fetchone()
            return int(row["cnt"]) if row and row["cnt"] is not None else 0
        finally:
            conn.close()

def get_ist_now() -> datetime:
    tz = pytz.timezone("Asia/Kolkata")
    return datetime.now(tz)

def get_ist_today() -> str:
    return get_ist_now().strftime("%Y-%m-%d")

def get_daily_quota_used(user_id: str, quota_date: str, quota_type: str) -> int:
    """Returns today's used count for user_id on quota_date (IST) for quota_type (PDF_PAGE or IMAGE)."""
    if not user_id:
        return 0
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT used FROM daily_quota_usage
                WHERE (user_id = ? OR user_id = LOWER(?)) AND quota_date = ? AND type = ?
            """, (user_id, user_id, quota_date, quota_type))
            row = cursor.fetchone()
            if row is not None and row["used"] is not None:
                return int(row["used"])

            # Fallback for PDF_PAGE to legacy daily_usage table if daily_quota_usage has no entry
            if quota_type == "PDF_PAGE":
                cursor.execute("""
                    SELECT pages_used FROM daily_usage
                    WHERE user_id = ? AND date_str = ?
                """, (user_id, quota_date))
                leg_row = cursor.fetchone()
                if leg_row is not None and leg_row["pages_used"] is not None:
                    return int(leg_row["pages_used"])

            return 0
        finally:
            conn.close()

def reserve_quota_atomic(
    job_id: str,
    user_id: str,
    quota_date: str,
    quota_type: str,
    requested_count: int,
    daily_limit: int,
    is_unlimited: bool = False
) -> Dict[str, Any]:
    """
    Atomically checks and reserves quota for a job before any OCR/AI work starts (PRD FR-D-2 & FR-D-3).
    Ensures parallel requests cannot both succeed past the remaining limit.
    """
    if requested_count <= 0:
        return {
            "reservation_id": None,
            "accepted": 0,
            "unprocessed": 0,
            "used_before": 0,
            "remaining_before": daily_limit,
            "limit": daily_limit
        }

    now_iso = get_ist_now().isoformat()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")

            # Read current usage
            cursor.execute("""
                SELECT used FROM daily_quota_usage
                WHERE (user_id = ? OR user_id = LOWER(?)) AND quota_date = ? AND type = ?
            """, (user_id, user_id, quota_date, quota_type))
            row = cursor.fetchone()
            current_used = int(row["used"]) if row and row["used"] is not None else 0

            # Fallback to legacy daily_usage if not in daily_quota_usage yet
            if current_used == 0 and quota_type == "PDF_PAGE":
                cursor.execute("""
                    SELECT pages_used FROM daily_usage
                    WHERE user_id = ? AND date_str = ?
                """, (user_id, quota_date))
                leg = cursor.fetchone()
                if leg and leg["pages_used"] is not None:
                    current_used = int(leg["pages_used"])

            if is_unlimited:
                accepted = requested_count
                remaining_before = 999999
            else:
                remaining_before = max(0, daily_limit - current_used)
                accepted = min(requested_count, remaining_before)

            unprocessed = max(0, requested_count - accepted)
            res_id = f"res-{uuid.uuid4().hex[:12]}"

            if accepted > 0 and not is_unlimited:
                rec_id = f"dqu-{uuid.uuid4().hex[:12]}"
                cursor.execute("""
                    INSERT INTO daily_quota_usage (id, user_id, quota_date, type, used, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, quota_date, type) DO UPDATE SET
                        used = used + excluded.used,
                        updated_at = excluded.updated_at
                """, (rec_id, user_id, quota_date, quota_type, accepted, now_iso))

                # Also keep legacy daily_usage synced for backward compatibility
                if quota_type == "PDF_PAGE":
                    cursor.execute("""
                        INSERT INTO daily_usage (id, user_id, date_str, pages_used, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(user_id, date_str) DO UPDATE SET
                            pages_used = pages_used + excluded.pages_used,
                            updated_at = excluded.updated_at
                    """, (f"du-{uuid.uuid4().hex[:12]}", user_id, quota_date, accepted, now_iso))

            # Record reservation
            cursor.execute("""
                INSERT INTO quota_reservations (
                    reservation_id, job_id, user_id, quota_date, type,
                    reserved_count, consumed_count, released_count, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 'RESERVED', ?)
            """, (res_id, job_id, user_id, quota_date, quota_type, accepted, now_iso))

            conn.commit()
            return {
                "reservation_id": res_id,
                "reserved_count": accepted,
                "accepted": accepted,
                "unprocessed_count": unprocessed,
                "unprocessed": unprocessed,
                "used_before": current_used,
                "remaining_before": remaining_before,
                "limit": daily_limit if not is_unlimited else 999999
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

def reconcile_quota_reservation(
    reservation_id: Optional[str],
    consumed_count: int,
    failed_system_count: int
) -> None:
    """
    Reconciles reservation when job completes or fails (PRD FR-P-2 & FR-D-5).
    Releases back reservation for pages that failed due to system error.
    Idempotent: running twice gives same result.
    """
    if not reservation_id:
        return
    now_iso = get_ist_now().isoformat()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")

            cursor.execute("""
                SELECT user_id, quota_date, type, reserved_count, status
                FROM quota_reservations WHERE reservation_id = ?
            """, (reservation_id,))
            res = cursor.fetchone()
            if not res or res["status"] in ("CONSUMED", "RELEASED"):
                conn.commit()
                return

            user_id = res["user_id"]
            quota_date = res["quota_date"]
            q_type = res["type"]
            reserved_count = res["reserved_count"]

            to_release = min(reserved_count, max(0, failed_system_count))
            actual_consumed = max(0, min(reserved_count - to_release, consumed_count))

            cursor.execute("""
                UPDATE quota_reservations SET
                    consumed_count = ?,
                    released_count = ?,
                    status = 'CONSUMED'
                WHERE reservation_id = ?
            """, (actual_consumed, to_release, reservation_id))

            if to_release > 0:
                cursor.execute("""
                    UPDATE daily_quota_usage SET
                        used = MAX(0, used - ?),
                        updated_at = ?
                    WHERE user_id = ? AND quota_date = ? AND type = ?
                """, (to_release, now_iso, user_id, quota_date, q_type))

                if q_type == "PDF_PAGE":
                    cursor.execute("""
                        UPDATE daily_usage SET
                            pages_used = MAX(0, pages_used - ?),
                            updated_at = ?
                        WHERE user_id = ? AND date_str = ?
                    """, (to_release, now_iso, user_id, quota_date))

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

def save_job_page(
    job_id: str,
    page_number: int,
    status: str,
    file_id: Optional[str] = None,
    error_reason: Optional[str] = None,
    transaction_count: int = 0
) -> str:
    """Saves or updates a job page tracking row (PRD Section 6, 7)."""
    now_iso = get_ist_now().isoformat()
    rec_id = f"jp-{uuid.uuid4().hex[:12]}"
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM job_pages WHERE job_id = ? AND page_number = ?
            """, (job_id, page_number))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("""
                    UPDATE job_pages SET
                        status = ?,
                        error_reason = ?,
                        transaction_count = ?,
                        updated_at = ?
                    WHERE job_id = ? AND page_number = ?
                """, (status, error_reason, transaction_count, now_iso, job_id, page_number))
                conn.commit()
                return existing["id"]
            else:
                cursor.execute("""
                    INSERT INTO job_pages (
                        id, job_id, file_id, page_number, status,
                        error_reason, transaction_count, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (rec_id, job_id, file_id, page_number, status, error_reason, transaction_count, now_iso, now_iso))
                conn.commit()
                return rec_id
        finally:
            conn.close()

def get_job_pages(job_id: str) -> List[Dict[str, Any]]:
    """Retrieves all tracked pages for a job in sequential order (PRD FR-O-11)."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, job_id, file_id, page_number, status, error_reason, transaction_count, created_at, updated_at
                FROM job_pages WHERE job_id = ? ORDER BY page_number ASC
            """, (job_id,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

def get_active_quota_exception(user_id: str, quota_date: str) -> Optional[Dict[str, Any]]:
    """
    Looks up active approved quota exception for a user (PRD FR-A-6).
    Fails safely: returns None if table cannot be read or no active record.
    """
    if not user_id:
        return None
    try:
        with _LOCK:
            conn = _get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, user_id, scope, limit_type, limit_value, starts_at, ends_at, reason, granted_by, granted_at
                    FROM quota_exceptions
                    WHERE (user_id = ? OR user_id = LOWER(?))
                      AND revoked_at IS NULL
                      AND starts_at <= ?
                      AND (ends_at IS NULL OR ends_at >= ?)
                    ORDER BY granted_at DESC LIMIT 1
                """, (user_id, user_id, quota_date, quota_date))
                row = cursor.fetchone()
                return dict(row) if row else None
            finally:
                conn.close()
    except Exception as e:
        logger.warning(f"Error checking quota exception for {user_id}: {e}")
        return None

def grant_quota_exception(
    user_id: str,
    scope: str,
    limit_type: str,
    limit_value: Optional[int],
    starts_at: str,
    ends_at: Optional[str],
    reason: str,
    granted_by: str
) -> Dict[str, Any]:
    """Grants an approved exception record with audit log (PRD FR-A-4, FR-A-5, FR-A-7)."""
    exc_id = f"exc-{uuid.uuid4().hex[:12]}"
    now_iso = get_ist_now().isoformat()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO quota_exceptions (
                    id, user_id, scope, limit_type, limit_value,
                    starts_at, ends_at, reason, granted_by, granted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (exc_id, user_id, scope, limit_type, limit_value, starts_at, ends_at, reason, granted_by, now_iso))

            # Audit log
            audit_id = f"aud-{uuid.uuid4().hex[:12]}"
            new_val = json.dumps({
                "scope": scope,
                "limit_type": limit_type,
                "limit_value": limit_value,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "reason": reason
            })
            cursor.execute("""
                INSERT INTO quota_audit_log (id, actor, action, target_user, old_value, new_value, created_at)
                VALUES (?, ?, 'GRANT_EXCEPTION', ?, NULL, ?, ?)
            """, (audit_id, granted_by, user_id, new_val, now_iso))

            conn.commit()
            return {
                "id": exc_id,
                "user_id": user_id,
                "scope": scope,
                "limit_type": limit_type,
                "limit_value": limit_value,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "reason": reason,
                "granted_by": granted_by,
                "granted_at": now_iso
            }
        finally:
            conn.close()

def revoke_quota_exception(exception_id: str, revoked_by: str) -> bool:
    """Revokes an approved exception with audit log (PRD FR-A-8)."""
    now_iso = get_ist_now().isoformat()
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, scope, limit_type, limit_value FROM quota_exceptions
                WHERE id = ? AND revoked_at IS NULL
            """, (exception_id,))
            row = cursor.fetchone()
            if not row:
                return False

            user_id = row["user_id"]
            old_val = json.dumps(dict(row))

            cursor.execute("""
                UPDATE quota_exceptions SET revoked_at = ?, revoked_by = ? WHERE id = ?
            """, (now_iso, revoked_by, exception_id))

            audit_id = f"aud-{uuid.uuid4().hex[:12]}"
            cursor.execute("""
                INSERT INTO quota_audit_log (id, actor, action, target_user, old_value, new_value, created_at)
                VALUES (?, ?, 'REVOKE_EXCEPTION', ?, ?, NULL, ?)
            """, (audit_id, revoked_by, user_id, old_val, now_iso))

            conn.commit()
            return True
        finally:
            conn.close()

def list_quota_exceptions(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists quota exceptions, optionally filtered by user_id."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            if user_id:
                cursor.execute("""
                    SELECT id, user_id, scope, limit_type, limit_value, starts_at, ends_at, reason, granted_by, granted_at, revoked_at, revoked_by
                    FROM quota_exceptions WHERE (user_id = ? OR user_id = LOWER(?))
                    ORDER BY granted_at DESC
                """, (user_id, user_id))
            else:
                cursor.execute("""
                    SELECT id, user_id, scope, limit_type, limit_value, starts_at, ends_at, reason, granted_by, granted_at, revoked_at, revoked_by
                    FROM quota_exceptions ORDER BY granted_at DESC
                """)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

def get_quota_audit_logs(limit: int = 100) -> List[Dict[str, Any]]:
    """Lists recent quota audit log entries."""
    with _LOCK:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, actor, action, target_user, old_value, new_value, created_at
                FROM quota_audit_log ORDER BY created_at DESC LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

# Auto-initialize database on import
init_db()

