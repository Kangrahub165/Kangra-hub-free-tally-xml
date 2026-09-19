# Supabase Complete Foundation & Architecture Guide
**Kangra Hub Free Tally XML**

This document provides the authoritative, step-by-step instructions for provisioning, configuring, and verifying the PostgreSQL database and Supabase Auth foundation for **Kangra Hub Free Tally XML** from a fresh Supabase project through full production/local testing.

---

## 1. Single Authoritative SQL Script

The entire database architecture, schemas, tables, constraints, security-definer functions, triggers, row-level security (RLS) policies, and seed data are consolidated into one self-contained, idempotent file:

👉 **[`database/supabase_complete.sql`](file:///d:/KANGRA%20HUB%20FREE%20TALLY%20XML/database/supabase_complete.sql)**

### Safe Execution Guarantee
- **Zero Circular Dependencies**: Executes in a strictly ordered sequence: Extensions → Enums/Types → Base Tables → Performance Indexes → Security Definer Functions → Automated Triggers → RLS Enablement → Fine-Grained Policies → System Settings Seed → 38 Bank Parsers Seed → Bank Signatures Seed → Global Ledger Mappings Seed → Admin Promotion Procedures → Read-Only Verification Queries.
- **Fresh Project Ready**: Safe to execute on a brand new Supabase project without any prior manual setup.
- **Idempotent / Upgrade Safe**: Includes `IF NOT EXISTS` and `ON CONFLICT DO UPDATE` handling to allow safe re-execution.

---

## 2. Step-by-Step Supabase Setup

### Step 1: Create a Fresh Supabase Project
1. Log in to [Supabase Console](https://supabase.com/dashboard).
2. Click **New Project**.
3. Choose an Organization, enter a project name (e.g. `kangra-hub-tally-xml`), and generate/store a secure Database Password.
4. Select your preferred Region (e.g. `ap-south-1` Mumbai for Indian accounting latency).
5. Click **Create new project** and wait ~1-2 minutes for provisioning to finish.

### Step 2: Execute `database/supabase_complete.sql`
1. In your Supabase project dashboard, click **SQL Editor** in the left navigation sidebar.
2. Click **New Query**.
3. Open [`database/supabase_complete.sql`](file:///d:/KANGRA%20HUB%20FREE%20TALLY%20XML/database/supabase_complete.sql) in your code editor, copy the entire file (1,150+ lines), and paste it into the Supabase SQL Editor.
4. Click **Run** (or press `Cmd/Ctrl + Enter`).
5. Verify that execution completes with **Success**. The 7 verification queries at the end of the script will display summary statistics confirming the installation.

---

## 3. Supabase Dashboard Configuration

Certain authentication and project settings cannot be set via SQL because they are managed directly by the Supabase infrastructure. Configure the following in your Supabase Project Dashboard:

### A. Authentication -> Providers -> Email
1. Navigate to **Authentication** -> **Providers** -> **Email**.
2. Ensure **Email** is **Enabled**.
3. **Confirm email** toggle:
   - For **Localhost Testing**: You can turn **Confirm email** **OFF** so newly registered test users can log in immediately without waiting for an email verification link.
   - For **Production**: Turn **Confirm email** **ON** and configure your custom SMTP provider (SendGrid, Resend, or AWS SES).
4. Ensure **Secure email change** is enabled.

### B. Authentication -> URL Configuration
1. Navigate to **Authentication** -> **URL Configuration**.
2. Set **Site URL**:
   ```
   http://localhost:3000
   ```
3. Under **Redirect URLs**, add the following allowed redirect paths:
   ```
   http://localhost:3000/**
   http://localhost:3000/dashboard
   http://localhost:3000/login
   http://localhost:3000/admin
   http://localhost:3000/convert
   ```

### C. Authentication -> Password Settings
1. Navigate to **Authentication** -> **Password Protection** / **Policies**.
2. Set minimum password length to **6 characters** (matching the frontend form validation).

---

## 4. Environment Variables Specification

To connect both the Next.js Frontend and FastAPI Backend to your Supabase project, configure your local environment files as follows.

> [!IMPORTANT]
> **Strict Security Isolation**: Never expose `SUPABASE_SERVICE_ROLE_KEY` or database passwords to the Next.js browser bundle (`NEXT_PUBLIC_*`). Only the `anon` key is public.

### 1. Frontend Environment File: `frontend/.env.local`
```env
# Public Supabase Connection
NEXT_PUBLIC_SUPABASE_URL=https://your-project-ref.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...your-anon-key

# Backend API Endpoint
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 2. Backend Environment File: `backend/.env`
```env
# Application Settings
APP_ENV=development
API_PREFIX=/api
DEFAULT_TIMEZONE=Asia/Kolkata

# Supabase Server Credentials
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...your-anon-key
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...your-service-role-key

# Platform Configuration
SITE_MODE=FREE
FREE_DAILY_PAGE_LIMIT=50
MAX_UPLOAD_SIZE_MB=25
MAX_PAGES_PER_FILE=200
MAINTENANCE_MODE=false
ALLOW_NEW_SIGNUPS=true
FILE_RETENTION_MINUTES=60

# Voluntary Developer Support (Admin Console)
BUY_COFFEE_ENABLED=true
BUY_COFFEE_UPI_ID=sanyaguleria@okaxis
BUY_COFFEE_PAYMENT_URL=
```

---

## 5. First Administrator Setup (No Hardcoded Credentials)

We never hard-code administrator passwords or universal accounts into the schema. Admin access is granted by promoting an authenticated user account:

### Step 1: Register Normal User Account
1. Start your local application or open your live website.
2. Go to `http://localhost:3000/signup`.
3. Complete registration with your administrator email (e.g. `admin@tallyxml.in`).

### Step 2: Promote to Admin in Supabase SQL Editor
In the Supabase SQL Editor, execute **Option A** (recommended):

```sql
-- OPTION A: Promote directly by Email
SELECT public.promote_user_to_admin('admin@tallyxml.in');
```

Or execute **Option B** (direct SQL update):
```sql
-- OPTION B: Direct SQL update
UPDATE public.profiles
SET role = 'ADMIN', updated_at = now()
WHERE LOWER(email) = LOWER('admin@tallyxml.in');

UPDATE public.user_access
SET unlimited = true, access_type = 'UNLIMITED', updated_at = now()
WHERE user_id = (SELECT id FROM auth.users WHERE LOWER(email) = LOWER('admin@tallyxml.in'));

UPDATE auth.users
SET raw_user_meta_data = COALESCE(raw_user_meta_data, '{}'::jsonb) || '{"role": "ADMIN", "is_admin": true, "is_unlimited": true}'::jsonb
WHERE LOWER(email) = LOWER('admin@tallyxml.in');
```

### What this achieves:
1. User role set to `'ADMIN'` in `public.profiles`.
2. Access tier set to `'UNLIMITED'` in `public.user_access` (bypasses 50-page daily limit server-side).
3. Auth user metadata updated with `role = 'ADMIN'`, ensuring JWT tokens grant admin API permissions.
4. Security audit entry logged in `public.audit_logs`.
5. Full server-verified access to `/admin`, `/admin/convert`, `/admin/users`, `/admin/parsers`, `/admin/settings`, and `/admin/logs`.

---

## 6. Schema Architecture: 13 Base Tables

| # | Table Name | Description | Key Constraints & Notes |
|---|------------|-------------|-------------------------|
| 1 | `system_settings` | Dynamic platform configuration & Section 129 flags | Key-value JSONB, public vs private flags |
| 2 | `profiles` | User identity records synced 1:1 with `auth.users` | Auto-created by `on_auth_user_created` trigger |
| 3 | `user_access` | Quota entitlements and tier management | `daily_page_limit` (50), `unlimited` flag |
| 4 | `usage_daily` | Atomic daily page usage tracking (Asia/Kolkata basis) | Unique `(user_id, usage_date)`, row-locked |
| 5 | `bank_parsers` | 38 supported Indian banking institutions | Unique `bank_name` & `parser_key`, confidence score |
| 6 | `bank_signatures` | Multi-factor bank identification patterns | Weighted rules (Header, IFSC, Domain, Account) |
| 7 | `conversion_jobs` | Full conversion lifecycle records | Stores PDF, Excel, and XML paths + snapshot JSONB |
| 8 | `user_ledgers` | User imported Tally master ledgers (XML/JSON/HTML) | Unique `(user_id, normalized_name)` |
| 9 | `bank_ledger_configs`| User-configured exact "Bank Ledger As Tally" | Preserves exact user bank ledger name verbatim |
| 10| `transactions` | Individual double-entry rows with audit status | Financial precision, validation status, voucher type |
| 11| `ledger_mappings` | User-specific and global recurring party rules | Pattern matching with priority scoring |
| 12| `audit_logs` | Immutable administrative security log | Tracks admin operations, IPs, and telemetry |
| 13| `notifications` | User notifications and global system announcements | Direct user targeted or global broadcasts |

---

## 7. Atomic Quota System & Concurrency Safety

The daily quota system strictly enforces:
- **Free User Limit**: 50 pages per day.
- **Calendar Boundary**: Resets at 00:00:00 midnight **Asia/Kolkata (IST)** time.
- **Admin & Approved Unlimited Users**: Permanent server-side bypass (`999999` pages).
- **Zero Extra Deduction**: Excel generation/download and XML export consume **zero** extra quota.
- **Concurrency Protection**: The stored procedure `public.check_and_record_usage(p_user_id UUID, p_pages INT)` executes `SELECT ... FOR UPDATE` row-level locking on `public.usage_daily`, preventing race conditions during simultaneous upload requests.

---

## 8. Row Level Security (RLS) Policy Matrix

| Table | Normal Authenticated User | Administrator | Service Role (Backend API) |
|---|---|---|---|
| `profiles` | Read & update own profile | Read & update all profiles | Full Access |
| `user_access` | Read own tier & quota | Manage all entitlements | Full Access |
| `usage_daily` | Read own daily usage | Read all user usage logs | Full Access |
| `conversion_jobs` | Select, insert, update own jobs | Read & inspect all jobs | Full Access |
| `transactions` | View & update own job transactions | View all transactions | Full Access |
| `user_ledgers` | Manage own imported ledgers | View & manage all ledgers | Full Access |
| `bank_ledger_configs` | Manage own bank ledger names | View & manage all configs | Full Access |
| `ledger_mappings` | Manage own rules + read global rules | Manage all mapping rules | Full Access |
| `bank_parsers` | Read active parsers | Read & write all parsers | Full Access |
| `bank_signatures` | Read active signatures | Read & write all signatures | Full Access |
| `system_settings` | Read public settings | Read & write all settings | Full Access |
| `audit_logs` | No access | View & insert logs | Full Access |
| `notifications` | View own & active global alerts | Manage all announcements | Full Access |

---

## 9. Post-Execution Verification Queries

Execute these queries in the Supabase SQL Editor after running `supabase_complete.sql`:

```sql
-- 1. Check all 38 commercial banks are seeded
SELECT count(*) AS total_registered_banks FROM public.bank_parsers;
-- Expected: 38

-- 2. Verify all bank detection signatures are seeded
SELECT count(*) AS total_signatures FROM public.bank_signatures;
-- Expected: >= 114 (currently 216)

-- 3. Confirm RLS is enabled on all 13 tables
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY tablename;
-- Expected: rowsecurity = true for all 13 tables

-- 4. Check system settings are seeded
SELECT setting_key, setting_value FROM public.system_settings;
-- Expected: 15 default system configuration keys

-- 5. Verify atomic quota stored procedure exists
SELECT routine_name, routine_type, security_type
FROM information_schema.routines 
WHERE routine_schema = 'public' AND routine_name = 'check_and_record_usage';
-- Expected: check_and_record_usage, FUNCTION, DEFINER

-- 6. Verify automated auth signup trigger is active
SELECT trigger_name, event_manipulation, event_object_table, action_statement
FROM information_schema.triggers
WHERE event_object_table = 'users';
-- Expected: on_auth_user_created trigger on auth.users
```
