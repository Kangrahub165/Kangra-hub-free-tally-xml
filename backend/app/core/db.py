import os
import sqlite3
import json
import uuid
import logging
import threading
from datetime import datetime, timezone
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

            conn.commit()

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

# Auto-initialize database on import
init_db()
