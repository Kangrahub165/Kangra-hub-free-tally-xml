-- ============================================================================
-- KANGRA HUB FREE TALLY XML — COMPLETE SUPABASE DATABASE & AUTH FOUNDATION
-- File: database/supabase_complete.sql
-- Description: Single, complete, self-contained, authoritative PostgreSQL script.
-- Safe Execution: Fresh Supabase project (execute in Supabase SQL Editor).
-- Safe Execution Order:
--   1. Extensions
--   2. Types & Enums
--   3. Base Tables & Relationships (13 Tables)
--   4. Performance & Unique Constraints / Indexes
--   5. Security Definer Functions & Quota Logic (Atomic Row-Locking)
--   6. Automated Triggers (Auth Sync & Updated At)
--   7. Row Level Security (RLS) Enablement on All Tables
--   8. Fine-Grained Non-Recursive RLS Policies (User vs Admin vs Public)
--   9. System Settings & Default Seed Data
--  10. 38 Commercial Bank Registry Seed Data
--  11. Multi-Factor Bank Detection Signatures Seed Data
--  12. Global Default Ledger Mappings Seed Data
--  13. First Admin Account Setup Stored Procedures & Instructions
--  14. Read-Only Database Verification Queries
-- ============================================================================

-- ============================================================================
-- 1. EXTENSIONS
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Safe Cleanup of prior function signatures if re-running
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP FUNCTION IF EXISTS public.handle_new_user() CASCADE;
DROP FUNCTION IF EXISTS public.is_admin(UUID) CASCADE;
DROP FUNCTION IF EXISTS public.check_and_record_usage(UUID, INT) CASCADE;
DROP FUNCTION IF EXISTS public.set_updated_at() CASCADE;
DROP FUNCTION IF EXISTS public.assign_admin_role(UUID, TEXT) CASCADE;
DROP FUNCTION IF EXISTS public.assign_admin_role_by_email(TEXT, TEXT) CASCADE;
DROP FUNCTION IF EXISTS public.promote_user_to_admin(TEXT) CASCADE;
DROP FUNCTION IF EXISTS public.reset_user_daily_usage(UUID) CASCADE;

-- ============================================================================
-- 2. TYPES & ENUMS
-- ============================================================================
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        CREATE TYPE public.user_role AS ENUM ('USER', 'ADMIN', 'SUPER_ADMIN');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'access_tier') THEN
        CREATE TYPE public.access_tier AS ENUM ('FREE', 'PAID', 'UNLIMITED');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'account_status') THEN
        CREATE TYPE public.account_status AS ENUM ('ACTIVE', 'SUSPENDED', 'PENDING', 'EXPIRED');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'conversion_status') THEN
        CREATE TYPE public.conversion_status AS ENUM (
            'UPLOADED',
            'PROCESSING',
            'BANK_DETECTED',
            'EXTRACTED',
            'NEEDS_REVIEW',
            'VALIDATED',
            'XML_GENERATED',
            'EXCEL_GENERATED',
            'COMPLETED',
            'FAILED',
            'AMBIGUOUS_BANK'
        );
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'balance_status') THEN
        CREATE TYPE public.balance_status AS ENUM ('VALID', 'WARNING', 'MISMATCH', 'PENDING_SELECTION');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'voucher_type') THEN
        CREATE TYPE public.voucher_type AS ENUM ('Payment', 'Receipt', 'Contra', 'Journal');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'site_mode') THEN
        CREATE TYPE public.site_mode AS ENUM ('FREE', 'PAID');
    END IF;
END $$;

-- ============================================================================
-- 3. BASE TABLES (13 NORMALIZED TABLES)
-- ============================================================================

-- 1. System Settings (Application-wide configuration & Section 129 settings)
CREATE TABLE IF NOT EXISTS public.system_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    setting_key TEXT NOT NULL UNIQUE,
    setting_value JSONB NOT NULL,
    data_type TEXT NOT NULL DEFAULT 'string',
    description TEXT,
    is_public BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by UUID REFERENCES auth.users(id) ON DELETE SET NULL
);

-- 2. Profiles (1:1 with auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL DEFAULT 'User',
    email TEXT NOT NULL,
    mobile_number TEXT,
    country_code TEXT NOT NULL DEFAULT '+91',
    role public.user_role NOT NULL DEFAULT 'USER',
    account_status public.account_status NOT NULL DEFAULT 'ACTIVE',
    terms_accepted BOOLEAN NOT NULL DEFAULT true,
    terms_accepted_at TIMESTAMPTZ DEFAULT now(),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. User Access & Quota Entitlements
CREATE TABLE IF NOT EXISTS public.user_access (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    access_type public.access_tier NOT NULL DEFAULT 'FREE',
    daily_page_limit INT NOT NULL DEFAULT 50 CHECK (daily_page_limit >= 0),
    unlimited BOOLEAN NOT NULL DEFAULT false,
    approved_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. Daily Usage Tracking (Asia/Kolkata Calendar Day Basis)
CREATE TABLE IF NOT EXISTS public.usage_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    usage_date DATE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::DATE,
    pages_processed INT NOT NULL DEFAULT 0 CHECK (pages_processed >= 0),
    files_processed INT NOT NULL DEFAULT 0 CHECK (files_processed >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT unique_user_usage_date UNIQUE (user_id, usage_date)
);

-- 5. Registered Bank Parsers (38 Supported Commercial Institutions)
CREATE TABLE IF NOT EXISTS public.bank_parsers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bank_name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    format_name TEXT NOT NULL DEFAULT 'Standard e-Statement',
    parser_key TEXT NOT NULL UNIQUE,
    version TEXT NOT NULL DEFAULT '1.0',
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_default BOOLEAN NOT NULL DEFAULT true,
    confidence_threshold NUMERIC(5, 2) NOT NULL DEFAULT 80.00,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 6. Bank Detection Signatures
CREATE TABLE IF NOT EXISTS public.bank_signatures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bank_parser_id UUID NOT NULL REFERENCES public.bank_parsers(id) ON DELETE CASCADE,
    signature_type TEXT NOT NULL CHECK (signature_type IN ('HEADER_NAME', 'IFSC_PREFIX', 'DOMAIN', 'HEADER_MARKER', 'ACCOUNT_PATTERN', 'COLUMN_PATTERN')),
    pattern TEXT NOT NULL,
    weight NUMERIC(5, 2) NOT NULL DEFAULT 10.00,
    is_mandatory BOOLEAN NOT NULL DEFAULT false,
    is_negative BOOLEAN NOT NULL DEFAULT false,
    priority INT NOT NULL DEFAULT 10,
    is_active BOOLEAN NOT NULL DEFAULT true,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 7. Conversion Jobs (User & Admin Conversions Stream)
CREATE TABLE IF NOT EXISTS public.conversion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    is_admin_conversion BOOLEAN NOT NULL DEFAULT false,
    quota_exempt BOOLEAN NOT NULL DEFAULT false,
    label TEXT DEFAULT 'STANDARD CONVERSION',
    file_name TEXT NOT NULL,
    pdf_storage_path TEXT,
    bank_name TEXT NOT NULL,
    detected_bank TEXT,
    statement_format TEXT NOT NULL DEFAULT 'Standard',
    parser_key TEXT,
    parser_version TEXT DEFAULT '1.0',
    page_count INT NOT NULL DEFAULT 1 CHECK (page_count > 0),
    transaction_count INT NOT NULL DEFAULT 0 CHECK (transaction_count >= 0),
    rejected_transaction_count INT NOT NULL DEFAULT 0 CHECK (rejected_transaction_count >= 0),
    duplicate_count INT NOT NULL DEFAULT 0 CHECK (duplicate_count >= 0),
    status public.conversion_status NOT NULL DEFAULT 'PROCESSING',
    confidence_score NUMERIC(5, 2) DEFAULT 100.00,
    confidence_tier TEXT DEFAULT 'HIGH',
    is_ambiguous BOOLEAN DEFAULT false,
    detected_ifsc TEXT,
    runner_up_bank TEXT,
    runner_up_confidence NUMERIC(5, 2),
    detection_reasons JSONB DEFAULT '[]'::jsonb,
    candidates JSONB DEFAULT '[]'::jsonb,
    override_warning TEXT,
    balance_status public.balance_status NOT NULL DEFAULT 'VALID',
    statement_from DATE,
    statement_to DATE,
    opening_balance NUMERIC(15, 2),
    closing_balance NUMERIC(15, 2),
    total_debit NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    total_credit NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    bank_ledger_name TEXT NOT NULL DEFAULT 'Bank Account',
    cash_ledger_name TEXT NOT NULL DEFAULT 'Cash',
    raw_transaction_count INT NOT NULL DEFAULT 0,
    suspense_count INT NOT NULL DEFAULT 0,
    mapped_count INT NOT NULL DEFAULT 0,
    xml_storage_path TEXT,
    xml_filename TEXT,
    excel_storage_path TEXT,
    excel_filename TEXT,
    snapshot JSONB,
    duration_ms INT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 8. User Imported Tally Ledgers (XML, JSON, HTML Import Source)
CREATE TABLE IF NOT EXISTS public.user_ledgers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    ledger_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    group_name TEXT NOT NULL DEFAULT 'Primary',
    source_format TEXT NOT NULL DEFAULT 'MANUAL' CHECK (source_format IN ('XML', 'JSON', 'HTML', 'MANUAL')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT unique_user_ledger UNIQUE (user_id, normalized_name)
);

-- 9. User Bank-Specific Ledger Configurations (Exact "Bank Ledger As Tally")
CREATE TABLE IF NOT EXISTS public.bank_ledger_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    bank_name TEXT NOT NULL,
    tally_bank_ledger TEXT NOT NULL,
    tally_cash_ledger TEXT NOT NULL DEFAULT 'Cash',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT unique_user_bank_config UNIQUE (user_id, bank_name)
);

-- 10. Transactions (Individual Extracted Double-Entry Rows with Full Metadata Preservation)
CREATE TABLE IF NOT EXISTS public.transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES public.conversion_jobs(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    row_index INT NOT NULL CHECK (row_index > 0),
    transaction_date DATE NOT NULL,
    value_date DATE,
    posting_date DATE,
    narration TEXT NOT NULL,
    full_narration TEXT,
    original_narration TEXT,
    reference TEXT,
    cheque_reference TEXT,
    instrument_number TEXT,
    cheque_number TEXT,
    instrument_date DATE,
    utr TEXT,
    upi_ref TEXT,
    party_name TEXT,
    suggested_ledger TEXT,
    mapping_confidence NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
    mapping_status TEXT NOT NULL DEFAULT 'Suspense',
    ledger_name TEXT NOT NULL DEFAULT 'Suspense',
    bank_ledger_name TEXT,
    original_ledger_name TEXT,
    voucher_type public.voucher_type NOT NULL DEFAULT 'Payment',
    original_voucher_type TEXT,
    is_cash_transaction BOOLEAN NOT NULL DEFAULT false,
    cash_transaction_type TEXT,
    debit NUMERIC(15, 2) NOT NULL DEFAULT 0.00 CHECK (debit >= 0),
    credit NUMERIC(15, 2) NOT NULL DEFAULT 0.00 CHECK (credit >= 0),
    balance NUMERIC(15, 2),
    is_contra BOOLEAN NOT NULL DEFAULT false,
    validation_status TEXT NOT NULL DEFAULT 'VALID' CHECK (validation_status IN ('VALID', 'WARNING', 'ERROR')),
    validation_notes TEXT,
    is_user_modified BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 11. Ledger Mappings (User & Global Party Categorization Rules)
CREATE TABLE IF NOT EXISTS public.ledger_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    is_global BOOLEAN NOT NULL DEFAULT false,
    keyword TEXT,
    narration_pattern TEXT NOT NULL,
    match_type TEXT NOT NULL DEFAULT 'CONTAINS' CHECK (match_type IN ('EXACT', 'CONTAINS', 'REGEX')),
    mapped_ledger_name TEXT NOT NULL,
    voucher_type public.voucher_type NOT NULL DEFAULT 'Payment',
    confidence NUMERIC(5, 2) NOT NULL DEFAULT 100.00,
    source TEXT NOT NULL DEFAULT 'USER',
    match_count INT NOT NULL DEFAULT 0,
    last_matched_at TIMESTAMPTZ,
    priority INT NOT NULL DEFAULT 10,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 12. Audit Logs (Immutable Administrative Tracking)
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    admin_email TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    target_id TEXT,
    target_type TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 13. Notifications & System Announcements
CREATE TABLE IF NOT EXISTS public.notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    banner_type TEXT NOT NULL DEFAULT 'INFO' CHECK (banner_type IN ('INFO', 'WARNING', 'ALERT', 'MAINTENANCE')),
    is_read BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true,
    link TEXT,
    starts_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ends_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- 4. PERFORMANCE & UNIQUE INDEXES
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON public.profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_profiles_email ON public.profiles(email);
CREATE INDEX IF NOT EXISTS idx_profiles_role ON public.profiles(role);

CREATE INDEX IF NOT EXISTS idx_user_access_user_id ON public.user_access(user_id);
CREATE INDEX IF NOT EXISTS idx_user_access_unlimited ON public.user_access(unlimited);

CREATE INDEX IF NOT EXISTS idx_usage_daily_user_date ON public.usage_daily(user_id, usage_date);

CREATE INDEX IF NOT EXISTS idx_conversion_jobs_user_id ON public.conversion_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_conversion_jobs_created_at ON public.conversion_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversion_jobs_bank_name ON public.conversion_jobs(bank_name);
CREATE INDEX IF NOT EXISTS idx_conversion_jobs_status ON public.conversion_jobs(status);
CREATE INDEX IF NOT EXISTS idx_conversion_jobs_admin ON public.conversion_jobs(is_admin_conversion);

CREATE INDEX IF NOT EXISTS idx_transactions_job_id ON public.transactions(job_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON public.transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON public.transactions(transaction_date);

CREATE INDEX IF NOT EXISTS idx_ledger_mappings_user_id ON public.ledger_mappings(user_id);
CREATE INDEX IF NOT EXISTS idx_ledger_mappings_pattern ON public.ledger_mappings(narration_pattern);

CREATE INDEX IF NOT EXISTS idx_bank_signatures_parser_id ON public.bank_signatures(bank_parser_id);

CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON public.audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_admin ON public.audit_logs(admin_user_id);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON public.notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_active ON public.notifications(is_active);

-- ============================================================================
-- 5. SECURITY DEFINER FUNCTIONS & PROCEDURES
-- ============================================================================

-- Function 1: Check if user has ADMIN role (Security Definer with safe search_path)
CREATE OR REPLACE FUNCTION public.is_admin(p_user_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_role public.user_role;
BEGIN
    IF p_user_id IS NULL THEN
        RETURN false;
    END IF;
    SELECT role INTO v_role FROM public.profiles WHERE user_id = p_user_id;
    RETURN (v_role IN ('ADMIN', 'SUPER_ADMIN'));
END;
$$;

-- Function 2: Automated profile creation upon Supabase auth signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_full_name TEXT;
    v_mobile TEXT;
    v_country_code TEXT := '+91';
    v_terms_accepted BOOLEAN := true;
    v_role public.user_role := 'USER';
    v_is_unlimited BOOLEAN := false;
BEGIN
    v_full_name := COALESCE(new.raw_user_meta_data->>'full_name', 'User');
    v_mobile := COALESCE(new.raw_user_meta_data->>'mobile_number', '');
    v_country_code := COALESCE(new.raw_user_meta_data->>'country_code', '+91');
    v_terms_accepted := COALESCE((new.raw_user_meta_data->>'terms_accepted')::boolean, true);

    -- Check if metadata or email explicitly identifies administrative initialization
    IF (new.raw_user_meta_data->>'role' IN ('ADMIN', 'SUPER_ADMIN') 
        OR LOWER(COALESCE(new.email, '')) IN ('admin@tallyxml.in')) THEN
        v_role := 'ADMIN';
        v_is_unlimited := true;
    END IF;

    -- 1. Insert or update profile
    INSERT INTO public.profiles (
        user_id,
        full_name,
        email,
        mobile_number,
        country_code,
        role,
        account_status,
        terms_accepted,
        is_active
    )
    VALUES (
        new.id,
        v_full_name,
        COALESCE(new.email, ''),
        v_mobile,
        v_country_code,
        v_role,
        'ACTIVE',
        v_terms_accepted,
        true
    )
    ON CONFLICT (user_id) DO UPDATE SET
        full_name = EXCLUDED.full_name,
        email = EXCLUDED.email,
        mobile_number = EXCLUDED.mobile_number,
        updated_at = now();

    -- 2. Insert user access entitlement
    INSERT INTO public.user_access (
        user_id,
        access_type,
        daily_page_limit,
        unlimited,
        notes
    )
    VALUES (
        new.id,
        CASE WHEN v_is_unlimited THEN 'UNLIMITED'::public.access_tier ELSE 'FREE'::public.access_tier END,
        50,
        v_is_unlimited,
        CASE WHEN v_is_unlimited THEN 'Initial Administrator Entitlement' ELSE 'Default 50-Page Free Daily Quota' END
    )
    ON CONFLICT (user_id) DO UPDATE SET
        unlimited = EXCLUDED.unlimited,
        updated_at = now();

    RETURN new;
END;
$$;

-- Function 3: Timestamp updater trigger
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

-- Function 4: Atomic Quota Check & Deduction Procedure (Prevents Race Conditions)
CREATE OR REPLACE FUNCTION public.check_and_record_usage(p_user_id UUID, p_pages INT)
RETURNS TABLE (
    allowed BOOLEAN,
    remaining_pages INT,
    daily_limit INT,
    is_unlimited BOOLEAN,
    message TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_is_admin BOOLEAN;
    v_unlimited BOOLEAN;
    v_limit INT := 50;
    v_used INT := 0;
    v_today DATE := (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::DATE;
BEGIN
    -- 1. Administrators have permanent server-side quota bypass
    SELECT public.is_admin(p_user_id) INTO v_is_admin;
    IF v_is_admin THEN
        RETURN QUERY SELECT true, 999999, 999999, true, 'Admin Unlimited Quota Exemption'::TEXT;
        RETURN;
    END IF;

    -- 2. Check approved unlimited users
    SELECT ua.unlimited, ua.daily_page_limit
    INTO v_unlimited, v_limit
    FROM public.user_access ua
    WHERE ua.user_id = p_user_id;

    IF v_unlimited THEN
        RETURN QUERY SELECT true, 999999, 999999, true, 'Unlimited User Account'::TEXT;
        RETURN;
    END IF;

    IF v_limit IS NULL THEN
        v_limit := 50;
    END IF;

    -- 3. Atomic check and lock on today's usage row
    SELECT COALESCE(pages_processed, 0)
    INTO v_used
    FROM public.usage_daily
    WHERE user_id = p_user_id AND usage_date = v_today
    FOR UPDATE;

    v_used := COALESCE(v_used, 0);

    -- 4. Check if quota exceeded
    IF (v_used + p_pages) > v_limit THEN
        RETURN QUERY SELECT false, GREATEST(0, v_limit - v_used), v_limit, false,
            FORMAT('You have %s pages remaining today. This PDF statement requires %s pages. Daily quota resets at midnight Asia/Kolkata.', GREATEST(0, v_limit - v_used), p_pages)::TEXT;
        RETURN;
    END IF;

    -- 5. Record usage atomically
    INSERT INTO public.usage_daily (user_id, usage_date, pages_processed, files_processed)
    VALUES (p_user_id, v_today, p_pages, 1)
    ON CONFLICT (user_id, usage_date)
    DO UPDATE SET
        pages_processed = public.usage_daily.pages_processed + p_pages,
        files_processed = public.usage_daily.files_processed + 1,
        updated_at = now();

    RETURN QUERY SELECT true, (v_limit - (v_used + p_pages)), v_limit, false, 'Usage recorded successfully'::TEXT;
END;
$$;

-- Function 5: Admin Role Promotion by UUID
CREATE OR REPLACE FUNCTION public.assign_admin_role(p_user_id UUID, p_role TEXT DEFAULT 'ADMIN')
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    -- Update profile role
    UPDATE public.profiles
    SET role = p_role::public.user_role,
        updated_at = now()
    WHERE user_id = p_user_id;

    -- Grant unlimited access
    UPDATE public.user_access
    SET unlimited = true,
        access_type = 'UNLIMITED'::public.access_tier,
        notes = 'System Administrator Privileges',
        updated_at = now()
    WHERE user_id = p_user_id;

    -- Update auth.users metadata for immediate JWT reflection
    UPDATE auth.users
    SET raw_user_meta_data = COALESCE(raw_user_meta_data, '{}'::jsonb) || jsonb_build_object('role', p_role, 'is_admin', true, 'is_unlimited', true)
    WHERE id = p_user_id;

    -- Log action
    INSERT INTO public.audit_logs (admin_user_id, admin_email, action, target, metadata)
    VALUES (p_user_id, 'system-init', 'ADMIN_ROLE_PROMOTED', p_user_id::TEXT, json_build_object('role', p_role));

    RETURN FORMAT('User %s successfully promoted to %s with unlimited conversion quota.', p_user_id, p_role);
END;
$$;

-- Function 6: Admin Role Promotion by Email (Super Convenient!)
CREATE OR REPLACE FUNCTION public.promote_user_to_admin(p_email TEXT)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_user_id UUID;
BEGIN
    SELECT id INTO v_user_id FROM auth.users WHERE LOWER(email) = LOWER(p_email);
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'User with email % not found in auth.users. Please register the account first.', p_email;
    END IF;

    RETURN public.assign_admin_role(v_user_id, 'ADMIN');
END;
$$;

-- ============================================================================
-- 6. AUTOMATED TRIGGERS
-- ============================================================================
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

CREATE TRIGGER trigger_profiles_updated_at BEFORE UPDATE ON public.profiles FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trigger_user_access_updated_at BEFORE UPDATE ON public.user_access FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trigger_usage_daily_updated_at BEFORE UPDATE ON public.usage_daily FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trigger_bank_parsers_updated_at BEFORE UPDATE ON public.bank_parsers FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trigger_conversion_jobs_updated_at BEFORE UPDATE ON public.conversion_jobs FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trigger_transactions_updated_at BEFORE UPDATE ON public.transactions FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trigger_ledger_mappings_updated_at BEFORE UPDATE ON public.ledger_mappings FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trigger_system_settings_updated_at BEFORE UPDATE ON public.system_settings FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trigger_notifications_updated_at BEFORE UPDATE ON public.notifications FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================================
-- 7. ROW LEVEL SECURITY (RLS) ENABLEMENT
-- ============================================================================
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_access ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.usage_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bank_parsers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bank_signatures ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversion_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_ledgers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bank_ledger_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ledger_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- 8. FINE-GRAINED NON-RECURSIVE RLS POLICIES
-- ============================================================================

-- 1. Profiles
CREATE POLICY "Users can view own profile or admin can view all" ON public.profiles
    FOR SELECT USING (auth.uid() = user_id OR public.is_admin(auth.uid()));

CREATE POLICY "Users can update own profile or admin can update all" ON public.profiles
    FOR UPDATE USING (auth.uid() = user_id OR public.is_admin(auth.uid()));

CREATE POLICY "Users can insert own profile or admin can insert" ON public.profiles
    FOR INSERT WITH CHECK (auth.uid() = user_id OR public.is_admin(auth.uid()));

-- 2. User Access
CREATE POLICY "Users can view own access or admin can view all" ON public.user_access
    FOR SELECT USING (auth.uid() = user_id OR public.is_admin(auth.uid()));

CREATE POLICY "Only admins can manage user access" ON public.user_access
    FOR ALL USING (public.is_admin(auth.uid()));

-- 3. Usage Daily
CREATE POLICY "Users can view own usage or admin can view all" ON public.usage_daily
    FOR SELECT USING (auth.uid() = user_id OR public.is_admin(auth.uid()));

CREATE POLICY "Admins can manage usage records" ON public.usage_daily
    FOR ALL USING (public.is_admin(auth.uid()));

-- 4. Bank Parsers & Signatures (Public read, admin write)
CREATE POLICY "Anyone can view active bank parsers" ON public.bank_parsers
    FOR SELECT USING (is_active = true OR public.is_admin(auth.uid()));

CREATE POLICY "Admins can manage bank parsers" ON public.bank_parsers
    FOR ALL USING (public.is_admin(auth.uid()));

CREATE POLICY "Anyone can view active bank signatures" ON public.bank_signatures
    FOR SELECT USING (is_active = true OR public.is_admin(auth.uid()));

CREATE POLICY "Admins can manage bank signatures" ON public.bank_signatures
    FOR ALL USING (public.is_admin(auth.uid()));

-- 5. Conversion Jobs
CREATE POLICY "Users view own conversions or admin view all" ON public.conversion_jobs
    FOR SELECT USING (auth.uid() = user_id OR public.is_admin(auth.uid()));

CREATE POLICY "Users can insert own conversions" ON public.conversion_jobs
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users update own conversions or admin update all" ON public.conversion_jobs
    FOR UPDATE USING (auth.uid() = user_id OR public.is_admin(auth.uid()));

CREATE POLICY "Users delete own conversions or admin delete all" ON public.conversion_jobs
    FOR DELETE USING (auth.uid() = user_id OR public.is_admin(auth.uid()));

-- 6. Transactions
CREATE POLICY "Users view own job transactions or admin view all" ON public.transactions
    FOR SELECT USING (
        user_id = auth.uid() OR
        EXISTS (
            SELECT 1 FROM public.conversion_jobs j
            WHERE j.id = transactions.job_id AND (j.user_id = auth.uid() OR public.is_admin(auth.uid()))
        )
    );

CREATE POLICY "Users manage own job transactions" ON public.transactions
    FOR ALL USING (
        user_id = auth.uid() OR
        EXISTS (
            SELECT 1 FROM public.conversion_jobs j
            WHERE j.id = transactions.job_id AND (j.user_id = auth.uid() OR public.is_admin(auth.uid()))
        )
    );

-- 7. User Imported Ledgers
CREATE POLICY "Users manage own imported ledgers" ON public.user_ledgers
    FOR ALL USING (auth.uid() = user_id OR public.is_admin(auth.uid()));

-- 8. Bank Ledger Configs
CREATE POLICY "Users manage own bank ledger configs" ON public.bank_ledger_configs
    FOR ALL USING (auth.uid() = user_id OR public.is_admin(auth.uid()));

-- 9. Ledger Mappings
CREATE POLICY "Users view own rules and global rules" ON public.ledger_mappings
    FOR SELECT USING (auth.uid() = user_id OR is_global = true OR public.is_admin(auth.uid()));

CREATE POLICY "Users manage own rules" ON public.ledger_mappings
    FOR ALL USING (auth.uid() = user_id OR public.is_admin(auth.uid()));

-- 10. System Settings (Public configuration readable, admin write)
CREATE POLICY "Anyone can read public settings" ON public.system_settings
    FOR SELECT USING (is_public = true OR public.is_admin(auth.uid()));

CREATE POLICY "Admins manage all system settings" ON public.system_settings
    FOR ALL USING (public.is_admin(auth.uid()));

-- 11. Audit Logs (Strictly Admin Only)
CREATE POLICY "Admins can view audit logs" ON public.audit_logs
    FOR SELECT USING (public.is_admin(auth.uid()));

CREATE POLICY "Admins can insert audit logs" ON public.audit_logs
    FOR INSERT WITH CHECK (public.is_admin(auth.uid()));

-- 12. Notifications
CREATE POLICY "Users view own or global notifications" ON public.notifications
    FOR SELECT USING (user_id IS NULL OR user_id = auth.uid() OR public.is_admin(auth.uid()));

CREATE POLICY "Admins manage notifications" ON public.notifications
    FOR ALL USING (public.is_admin(auth.uid()));

-- ============================================================================
-- 9. SEED DATA: SYSTEM SETTINGS
-- ============================================================================
INSERT INTO public.system_settings (setting_key, setting_value, data_type, description, is_public)
VALUES
    ('site_name', '"Kangra Hub Free Tally XML"'::jsonb, 'string', 'Public product title', true),
    ('site_mode', '"FREE"'::jsonb, 'string', 'Platform access model: FREE or PAID', true),
    ('free_daily_page_limit', '50'::jsonb, 'number', 'Default free tier daily page allowance', true),
    ('max_upload_size_mb', '25'::jsonb, 'number', 'Maximum allowed PDF upload size in Megabytes', true),
    ('max_pages_per_file', '200'::jsonb, 'number', 'Maximum allowed statement pages per single file', true),
    ('timezone', '"Asia/Kolkata"'::jsonb, 'string', 'Standard operational and quota reset timezone', true),
    ('maintenance_mode', 'false'::jsonb, 'boolean', 'Global maintenance lock', true),
    ('allow_new_signups', 'true'::jsonb, 'boolean', 'Permit public user registrations', true),
    ('file_retention_minutes', '60'::jsonb, 'number', 'Temporary storage purge lifetime in minutes', false),
    ('buy_coffee_enabled', 'true'::jsonb, 'boolean', 'Show Buy Me a Coffee widget inside Admin Console', false),
    ('buy_coffee_upi_id', '"sanyaguleria@okaxis"'::jsonb, 'string', 'Owner UPI ID for voluntary developer support', false),
    ('buy_coffee_payment_url', '""'::jsonb, 'string', 'Direct UPI payment URI', false),
    ('buy_coffee_button_text', '"Support Project ☕"'::jsonb, 'string', 'Admin support card button label', false),
    ('buy_coffee_message', '"Support ongoing development and server infrastructure for Kangra Hub Free Tally XML."'::jsonb, 'string', 'Admin support message', false),
    ('buy_coffee_qr_path', '"/buy-a-coffee/googlepay_qr.png"'::jsonb, 'string', 'Path to official owner QR code asset', false)
ON CONFLICT (setting_key) DO UPDATE SET
    setting_value = EXCLUDED.setting_value,
    data_type = EXCLUDED.data_type,
    description = EXCLUDED.description,
    is_public = EXCLUDED.is_public;

-- ============================================================================
-- 10. SEED DATA: 38 REGISTERED INDIAN BANK PARSERS
-- ============================================================================
INSERT INTO public.bank_parsers (bank_name, display_name, format_name, parser_key, version, is_active, is_default, confidence_threshold, description)
VALUES
    ('State Bank of India (SBI)', 'State Bank of India (SBI)', 'Standard e-Statement', 'sbi_standard', '1.0', true, true, 80.00, 'Vector extraction parser for State Bank of India (SBI) bank statements'),
    ('Punjab National Bank (PNB)', 'Punjab National Bank (PNB)', 'Standard e-Statement', 'pnb_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Punjab National Bank (PNB) bank statements'),
    ('HDFC Bank', 'HDFC Bank', 'Standard e-Statement', 'hdfc_standard', '1.0', true, true, 80.00, 'Vector extraction parser for HDFC Bank bank statements'),
    ('ICICI Bank', 'ICICI Bank', 'Standard e-Statement', 'icici_standard', '1.0', true, true, 80.00, 'Vector extraction parser for ICICI Bank bank statements'),
    ('Axis Bank', 'Axis Bank', 'Standard e-Statement', 'axis_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Axis Bank bank statements'),
    ('Kotak Mahindra Bank', 'Kotak Mahindra Bank', 'Standard e-Statement', 'kotak_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Kotak Mahindra Bank bank statements'),
    ('Bank of Baroda (BOB)', 'Bank of Baroda (BOB)', 'Standard e-Statement', 'bob_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Bank of Baroda (BOB) bank statements'),
    ('IDFC FIRST Bank', 'IDFC FIRST Bank', 'Standard e-Statement', 'idfc_standard', '1.0', true, true, 80.00, 'Vector extraction parser for IDFC FIRST Bank bank statements'),
    ('YES Bank', 'YES Bank', 'Standard e-Statement', 'yes_standard', '1.0', true, true, 80.00, 'Vector extraction parser for YES Bank bank statements'),
    ('RBL Bank', 'RBL Bank', 'Standard e-Statement', 'rbl_standard', '1.0', true, true, 80.00, 'Vector extraction parser for RBL Bank bank statements'),
    ('DCB Bank', 'DCB Bank', 'Standard e-Statement', 'dcb_standard', '1.0', true, true, 80.00, 'Vector extraction parser for DCB Bank bank statements'),
    ('Union Bank of India', 'Union Bank of India', 'Standard e-Statement', 'union_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Union Bank of India bank statements'),
    ('Canara Bank', 'Canara Bank', 'Standard e-Statement', 'canara_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Canara Bank bank statements'),
    ('Indian Bank', 'Indian Bank', 'Standard e-Statement', 'indian_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Indian Bank bank statements'),
    ('Indian Overseas Bank (IOB)', 'Indian Overseas Bank (IOB)', 'Standard e-Statement', 'iob_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Indian Overseas Bank (IOB) bank statements'),
    ('Bank of India (BOI)', 'Bank of India (BOI)', 'Standard e-Statement', 'boi_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Bank of India (BOI) bank statements'),
    ('Bank of Maharashtra', 'Bank of Maharashtra', 'Standard e-Statement', 'maharashtra_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Bank of Maharashtra bank statements'),
    ('Central Bank of India', 'Central Bank of India', 'Standard e-Statement', 'cbi_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Central Bank of India bank statements'),
    ('UCO Bank', 'UCO Bank', 'Standard e-Statement', 'uco_standard', '1.0', true, true, 80.00, 'Vector extraction parser for UCO Bank bank statements'),
    ('Punjab & Sind Bank', 'Punjab & Sind Bank', 'Standard e-Statement', 'psb_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Punjab & Sind Bank bank statements'),
    ('IndusInd Bank', 'IndusInd Bank', 'Standard e-Statement', 'indusind_standard', '1.0', true, true, 80.00, 'Vector extraction parser for IndusInd Bank bank statements'),
    ('IDBI Bank', 'IDBI Bank', 'Standard e-Statement', 'idbi_standard', '1.0', true, true, 80.00, 'Vector extraction parser for IDBI Bank bank statements'),
    ('Federal Bank', 'Federal Bank', 'Standard e-Statement', 'federal_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Federal Bank bank statements'),
    ('Bandhan Bank', 'Bandhan Bank', 'Standard e-Statement', 'bandhan_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Bandhan Bank bank statements'),
    ('AU Small Finance Bank', 'AU Small Finance Bank', 'Standard e-Statement', 'au_standard', '1.0', true, true, 80.00, 'Vector extraction parser for AU Small Finance Bank bank statements'),
    ('City Union Bank', 'City Union Bank', 'Standard e-Statement', 'cub_standard', '1.0', true, true, 80.00, 'Vector extraction parser for City Union Bank bank statements'),
    ('Karnataka Bank', 'Karnataka Bank', 'Standard e-Statement', 'karnataka_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Karnataka Bank bank statements'),
    ('South Indian Bank', 'South Indian Bank', 'Standard e-Statement', 'sib_standard', '1.0', true, true, 80.00, 'Vector extraction parser for South Indian Bank bank statements'),
    ('Tamilnad Mercantile Bank', 'Tamilnad Mercantile Bank', 'Standard e-Statement', 'tmb_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Tamilnad Mercantile Bank bank statements'),
    ('Jammu & Kashmir Bank', 'Jammu & Kashmir Bank', 'Standard e-Statement', 'jkb_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Jammu & Kashmir Bank bank statements'),
    ('CSB Bank', 'CSB Bank', 'Standard e-Statement', 'csb_standard', '1.0', true, true, 80.00, 'Vector extraction parser for CSB Bank bank statements'),
    ('Dhanlaxmi Bank', 'Dhanlaxmi Bank', 'Standard e-Statement', 'dhanlaxmi_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Dhanlaxmi Bank bank statements'),
    ('Nainital Bank', 'Nainital Bank', 'Standard e-Statement', 'nainital_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Nainital Bank bank statements'),
    ('Equitas Small Finance Bank', 'Equitas Small Finance Bank', 'Standard e-Statement', 'equitas_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Equitas Small Finance Bank bank statements'),
    ('HSBC', 'HSBC', 'Standard e-Statement', 'hsbc_standard', '1.0', true, true, 80.00, 'Vector extraction parser for HSBC bank statements'),
    ('DBS Bank', 'DBS Bank', 'Standard e-Statement', 'dbs_standard', '1.0', true, true, 80.00, 'Vector extraction parser for DBS Bank bank statements'),
    ('Deutsche Bank', 'Deutsche Bank', 'Standard e-Statement', 'deutsche_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Deutsche Bank bank statements'),
    ('Barclays', 'Barclays', 'Standard e-Statement', 'barclays_standard', '1.0', true, true, 80.00, 'Vector extraction parser for Barclays bank statements')
ON CONFLICT (parser_key) DO UPDATE SET
    bank_name = EXCLUDED.bank_name,
    display_name = EXCLUDED.display_name,
    format_name = EXCLUDED.format_name,
    version = EXCLUDED.version,
    is_active = EXCLUDED.is_active,
    description = EXCLUDED.description;

-- ============================================================================
-- 11. SEED DATA: MULTI-FACTOR BANK SIGNATURES
-- ============================================================================
INSERT INTO public.bank_signatures (bank_parser_id, signature_type, pattern, weight, priority)
VALUES
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'sbi_standard'), 'HEADER_NAME', '\bSTATE\s+BANK\s+OF\s+INDIA\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'sbi_standard'), 'HEADER_NAME', '\bSTATE\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'sbi_standard'), 'HEADER_NAME', '\bSBI\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'sbi_standard'), 'IFSC_PREFIX', 'SBIN0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'sbi_standard'), 'DOMAIN', 'onlinesbi.sbi', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'sbi_standard'), 'DOMAIN', 'onlinesbi.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'sbi_standard'), 'DOMAIN', 'sbi.co.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'sbi_standard'), 'HEADER_MARKER', 'CIF\s+No\.?\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'sbi_standard'), 'HEADER_MARKER', 'Drawing\s+Power\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'sbi_standard'), 'HEADER_MARKER', 'Account\s+Description\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'sbi_standard'), 'HEADER_MARKER', 'Balance\s+as\s+on\s+\d{1,2}\s+[A-Za-z]{3}\s+\d{4}', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'sbi_standard'), 'HEADER_MARKER', 'EB-MSME-CC', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'sbi_standard'), 'HEADER_MARKER', 'INB\s+Txn', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'sbi_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|A/c\s*No\.?)\s*[:\-]?\s*(000000[0-9]{11}|[0-9]{11})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'pnb_standard'), 'HEADER_NAME', '\bPUNJAB\s+NATIONAL\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'pnb_standard'), 'HEADER_NAME', '\bPNB\s+PARIVAR\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'pnb_standard'), 'IFSC_PREFIX', 'PUNB0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'pnb_standard'), 'DOMAIN', 'pnbindia.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'pnb_standard'), 'DOMAIN', 'netpnb.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'pnb_standard'), 'DOMAIN', 'pnbindia.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'pnb_standard'), 'HEADER_MARKER', 'Account\s+Statement\s+For\s+Account\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'pnb_standard'), 'HEADER_MARKER', 'Customer\s+ID\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'pnb_standard'), 'HEADER_MARKER', 'Scheme\s+Code\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'pnb_standard'), 'HEADER_MARKER', 'Nomination\s+Registered\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'pnb_standard'), 'HEADER_MARKER', 'Branch\s+Details', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'pnb_standard'), 'HEADER_MARKER', 'Statement\s+Period\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'pnb_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+(?:Number|No\.?)|For\s+Account)\s*[:\-]?\s*([0-9]{16})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'hdfc_standard'), 'HEADER_NAME', '\bHDFC\s+BANK\s+LIMITED\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'hdfc_standard'), 'HEADER_NAME', '\bHDFC\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'hdfc_standard'), 'IFSC_PREFIX', 'HDFC0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'hdfc_standard'), 'DOMAIN', 'hdfcbank.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'hdfc_standard'), 'HEADER_MARKER', 'Cust\s+ID\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'hdfc_standard'), 'HEADER_MARKER', 'Account\s+Branch\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'hdfc_standard'), 'HEADER_MARKER', 'RTGS/NEFT\s+IFSC\s*:\s*HDFC0', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'hdfc_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+No\.?|A/c\s*No\.?)\s*[:\-]?\s*([0-9]{14})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'icici_standard'), 'HEADER_NAME', '\bICICI\s+BANK\s+LIMITED\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'icici_standard'), 'HEADER_NAME', '\bICICI\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'icici_standard'), 'IFSC_PREFIX', 'ICIC0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'icici_standard'), 'DOMAIN', 'icicibank.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'icici_standard'), 'HEADER_MARKER', 'Account\s+Title\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'icici_standard'), 'HEADER_MARKER', 'Base\s+Branch\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'icici_standard'), 'HEADER_MARKER', 'MICR\s+Code\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'icici_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{12})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'axis_standard'), 'HEADER_NAME', '\bAXIS\s+BANK\s+LTD\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'axis_standard'), 'HEADER_NAME', '\bAXIS\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'axis_standard'), 'IFSC_PREFIX', 'UTIB0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'axis_standard'), 'DOMAIN', 'axisbank.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'axis_standard'), 'HEADER_MARKER', 'Customer\s+ID\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'axis_standard'), 'HEADER_MARKER', 'Branch\s+Name\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'axis_standard'), 'HEADER_MARKER', 'IFSC\s*:\s*UTIB0', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'axis_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+No\.?|A/c\s*No\.?)\s*[:\-]?\s*([0-9]{15})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'kotak_standard'), 'HEADER_NAME', '\bKOTAK\s+MAHINDRA\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'kotak_standard'), 'HEADER_NAME', '\bKOTAK\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'kotak_standard'), 'IFSC_PREFIX', 'KKBK0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'kotak_standard'), 'DOMAIN', 'kotak.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'kotak_standard'), 'HEADER_MARKER', 'CRN\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'kotak_standard'), 'HEADER_MARKER', 'Account\s+Entity\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'kotak_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{10,14})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'bob_standard'), 'HEADER_NAME', '\bBANK\s+OF\s+BARODA\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'bob_standard'), 'HEADER_NAME', '\bBARODA\s+CONNECT\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'bob_standard'), 'IFSC_PREFIX', 'BARB0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'bob_standard'), 'DOMAIN', 'bankofbaroda.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'bob_standard'), 'DOMAIN', 'bankofbaroda.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'bob_standard'), 'HEADER_MARKER', 'Customer\s+ID\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'bob_standard'), 'HEADER_MARKER', 'Baroda\s+Connect', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'bob_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{14})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'idfc_standard'), 'HEADER_NAME', '\bIDFC\s+FIRST\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'idfc_standard'), 'HEADER_NAME', '\bIDFC\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'idfc_standard'), 'IFSC_PREFIX', 'IDFB0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'idfc_standard'), 'DOMAIN', 'idfcfirstbank.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'idfc_standard'), 'HEADER_MARKER', 'Customer\s+ID\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'idfc_standard'), 'HEADER_MARKER', 'IDFC\s+FIRST', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'idfc_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{10,14})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'yes_standard'), 'HEADER_NAME', '\bYES\s+BANK\s+LTD\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'yes_standard'), 'HEADER_NAME', '\bYES\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'yes_standard'), 'IFSC_PREFIX', 'YESB0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'yes_standard'), 'DOMAIN', 'yesbank.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'yes_standard'), 'HEADER_MARKER', 'Cust\s+ID\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'yes_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{15})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'rbl_standard'), 'HEADER_NAME', '\bRBL\s+BANK\s+LIMITED\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'rbl_standard'), 'HEADER_NAME', '\bRBL\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'rbl_standard'), 'HEADER_NAME', '\bRATNAKAR\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'rbl_standard'), 'IFSC_PREFIX', 'RATN0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'rbl_standard'), 'DOMAIN', 'rblbank.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'rbl_standard'), 'HEADER_MARKER', 'CIF\s+ID\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'rbl_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{10,16})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'dcb_standard'), 'HEADER_NAME', '\bDCB\s+BANK\s+LIMITED\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'dcb_standard'), 'HEADER_NAME', '\bDCB\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'dcb_standard'), 'IFSC_PREFIX', 'DCBL0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'dcb_standard'), 'DOMAIN', 'dcbbank.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'dcb_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{10,16})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'union_standard'), 'HEADER_NAME', '\bUNION\s+BANK\s+OF\s+INDIA\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'union_standard'), 'IFSC_PREFIX', 'UBIN0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'union_standard'), 'DOMAIN', 'unionbankofindia.co.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'union_standard'), 'DOMAIN', 'unionbankonline.co.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'union_standard'), 'HEADER_MARKER', 'Customer\s+ID\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'union_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{15})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'canara_standard'), 'HEADER_NAME', '\bCANARA\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'canara_standard'), 'IFSC_PREFIX', 'CNRB0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'canara_standard'), 'DOMAIN', 'canarabank.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'canara_standard'), 'HEADER_MARKER', 'Customer\s+ID\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'canara_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{13})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'indian_standard'), 'HEADER_NAME', '\bINDIAN\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'indian_standard'), 'IFSC_PREFIX', 'IDIB0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'indian_standard'), 'DOMAIN', 'indianbank.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'indian_standard'), 'HEADER_MARKER', 'CIF\s+No\.?\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'indian_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{9,17})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'iob_standard'), 'HEADER_NAME', '\bINDIAN\s+OVERSEAS\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'iob_standard'), 'IFSC_PREFIX', 'IOBA0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'iob_standard'), 'DOMAIN', 'iob.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'iob_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{15})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'boi_standard'), 'HEADER_NAME', '(?<!STATE\s)(?<!UNION\s)(?<!CENTRAL\s)\bBANK\s+OF\s+INDIA\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'boi_standard'), 'IFSC_PREFIX', 'BKID0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'boi_standard'), 'DOMAIN', 'bankofindia.co.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'boi_standard'), 'HEADER_MARKER', 'Customer\s+No\.?\s*:', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'boi_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{15})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'maharashtra_standard'), 'HEADER_NAME', '\bBANK\s+OF\s+MAHARASHTRA\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'maharashtra_standard'), 'IFSC_PREFIX', 'MAHB0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'maharashtra_standard'), 'DOMAIN', 'bankofmaharashtra.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'maharashtra_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{11})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'cbi_standard'), 'HEADER_NAME', '\bCENTRAL\s+BANK\s+OF\s+INDIA\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'cbi_standard'), 'IFSC_PREFIX', 'CBIN0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'cbi_standard'), 'DOMAIN', 'centralbankofindia.co.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'cbi_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{10})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'uco_standard'), 'HEADER_NAME', '\bUCO\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'uco_standard'), 'IFSC_PREFIX', 'UCBA0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'uco_standard'), 'DOMAIN', 'ucobank.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'uco_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{14})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'psb_standard'), 'HEADER_NAME', '\bPUNJAB\s+(&|AND)\s+SIND\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'psb_standard'), 'IFSC_PREFIX', 'PSIB0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'psb_standard'), 'DOMAIN', 'punjabandsindbank.co.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'psb_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{14})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'indusind_standard'), 'HEADER_NAME', '\bINDUSIND\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'indusind_standard'), 'IFSC_PREFIX', 'INDB0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'indusind_standard'), 'DOMAIN', 'indusind.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'indusind_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{12,14})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'idbi_standard'), 'HEADER_NAME', '\bIDBI\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'idbi_standard'), 'IFSC_PREFIX', 'IBKL0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'idbi_standard'), 'DOMAIN', 'idbibank.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'idbi_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{16})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'federal_standard'), 'HEADER_NAME', '\bFEDERAL\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'federal_standard'), 'IFSC_PREFIX', 'FDRL0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'federal_standard'), 'DOMAIN', 'federalbank.co.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'federal_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{14})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'bandhan_standard'), 'HEADER_NAME', '\bBANDHAN\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'bandhan_standard'), 'IFSC_PREFIX', 'BDBL0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'bandhan_standard'), 'DOMAIN', 'bandhanbank.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'bandhan_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{14})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'au_standard'), 'HEADER_NAME', '\bAU\s+SMALL\s+FINANCE\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'au_standard'), 'HEADER_NAME', '\bAU\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'au_standard'), 'IFSC_PREFIX', 'AUBL0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'au_standard'), 'DOMAIN', 'aubank.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'au_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{16})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'cub_standard'), 'HEADER_NAME', '\bCITY\s+UNION\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'cub_standard'), 'IFSC_PREFIX', 'CIUB0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'cub_standard'), 'DOMAIN', 'cityunionbank.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'cub_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{15})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'karnataka_standard'), 'HEADER_NAME', '\bKARNATAKA\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'karnataka_standard'), 'IFSC_PREFIX', 'KARB0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'karnataka_standard'), 'DOMAIN', 'karnatakabank.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'karnataka_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{16})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'sib_standard'), 'HEADER_NAME', '\bSOUTH\s+INDIAN\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'sib_standard'), 'IFSC_PREFIX', 'SIBL0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'sib_standard'), 'DOMAIN', 'southindianbank.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'sib_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{16})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'tmb_standard'), 'HEADER_NAME', '\bTAMILNAD\s+MERCANTILE\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'tmb_standard'), 'IFSC_PREFIX', 'TMBL0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'tmb_standard'), 'DOMAIN', 'tmb.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'tmb_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{15})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'jkb_standard'), 'HEADER_NAME', '\bJAMMU\s+(&|AND)\s+KASHMIR\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'jkb_standard'), 'HEADER_NAME', '\bJ&K\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'jkb_standard'), 'IFSC_PREFIX', 'JAKA0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'jkb_standard'), 'DOMAIN', 'jkbank.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'jkb_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{16})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'csb_standard'), 'HEADER_NAME', '\bCSB\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'csb_standard'), 'HEADER_NAME', '\bCATHOLIC\s+SYRIAN\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'csb_standard'), 'IFSC_PREFIX', 'CSBK0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'csb_standard'), 'DOMAIN', 'csb.co.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'csb_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{16})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'dhanlaxmi_standard'), 'HEADER_NAME', '\bDHANLAXMI\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'dhanlaxmi_standard'), 'HEADER_NAME', '\bDHANBANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'dhanlaxmi_standard'), 'IFSC_PREFIX', 'DLXB0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'dhanlaxmi_standard'), 'DOMAIN', 'dhanbank.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'dhanlaxmi_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{15})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'nainital_standard'), 'HEADER_NAME', '\bNAINITAL\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'nainital_standard'), 'IFSC_PREFIX', 'NTBL0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'nainital_standard'), 'DOMAIN', 'nainitalbank.co.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'nainital_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{16})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'equitas_standard'), 'HEADER_NAME', '\bEQUITAS\s+SMALL\s+FINANCE\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'equitas_standard'), 'HEADER_NAME', '\bEQUITAS\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'equitas_standard'), 'IFSC_PREFIX', 'ESFB0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'equitas_standard'), 'DOMAIN', 'equitasbank.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'equitas_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{11,16})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'hsbc_standard'), 'HEADER_NAME', '\bTHE\s+HONGKONG\s+AND\s+SHANGHAI\s+BANKING\s+CORPORATION\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'hsbc_standard'), 'HEADER_NAME', '\bHSBC\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'hsbc_standard'), 'HEADER_NAME', '\bHSBC\s+INDIA\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'hsbc_standard'), 'IFSC_PREFIX', 'HSBC0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'hsbc_standard'), 'DOMAIN', 'hsbc.co.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'hsbc_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{9,12})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'dbs_standard'), 'HEADER_NAME', '\bDBS\s+BANK\s+INDIA\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'dbs_standard'), 'HEADER_NAME', '\bDBS\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'dbs_standard'), 'HEADER_NAME', '\bDEVELOPMENT\s+BANK\s+OF\s+SINGAPORE\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'dbs_standard'), 'IFSC_PREFIX', 'DBSS0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'dbs_standard'), 'DOMAIN', 'dbs.com', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'dbs_standard'), 'DOMAIN', 'dbs.com/in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'dbs_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{10,13})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'deutsche_standard'), 'HEADER_NAME', '\bDEUTSCHE\s+BANK\s+AG\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'deutsche_standard'), 'HEADER_NAME', '\bDEUTSCHE\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'deutsche_standard'), 'IFSC_PREFIX', 'DEUT0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'deutsche_standard'), 'DOMAIN', 'deutschebank.co.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'deutsche_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{10,12})\b', 20.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'barclays_standard'), 'HEADER_NAME', '\bBARCLAYS\s+BANK\s+PLC\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'barclays_standard'), 'HEADER_NAME', '\bBARCLAYS\s+BANK\b', 25.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'barclays_standard'), 'IFSC_PREFIX', 'BARC0', 35.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'barclays_standard'), 'DOMAIN', 'barclays.in', 10.0, 10),
    ((SELECT id FROM public.bank_parsers WHERE parser_key = 'barclays_standard'), 'ACCOUNT_PATTERN', '(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{10,12})\b', 20.0, 10);

-- ============================================================================
-- 12. SEED DATA: DEFAULT GLOBAL LEDGER MAPPINGS
-- ============================================================================
INSERT INTO public.ledger_mappings (is_global, narration_pattern, match_type, mapped_ledger_name, voucher_type, priority)
VALUES
    (true, 'CASH WITHDRAWAL', 'CONTAINS', 'Cash', 'Contra', 100),
    (true, 'CASH DEPOSIT', 'CONTAINS', 'Cash', 'Contra', 100),
    (true, 'CSH DEP (CDM)', 'CONTAINS', 'Cash', 'Contra', 100),
    (true, 'ATM WDL', 'CONTAINS', 'Cash', 'Contra', 100),
    (true, 'INTEREST PAID', 'CONTAINS', 'Bank Interest Expense', 'Payment', 50),
    (true, 'INTEREST RECEIVED', 'CONTAINS', 'Bank Interest Income', 'Receipt', 50),
    (true, 'CHG:', 'CONTAINS', 'Bank Charges A/C', 'Payment', 50),
    (true, 'GST:', 'CONTAINS', 'GST Input Tax Credit', 'Payment', 50)
ON CONFLICT DO NOTHING;



-- ============================================================================
-- 12. SEED DATA: DEFAULT GLOBAL LEDGER MAPPINGS
-- ============================================================================
INSERT INTO public.ledger_mappings (is_global, narration_pattern, keyword, match_type, mapped_ledger_name, voucher_type, priority)
VALUES
    (true, 'CASH WITHDRAWAL', 'CASH WITHDRAWAL', 'CONTAINS', 'Cash', 'Contra', 100),
    (true, 'CASH DEPOSIT', 'CASH DEPOSIT', 'CONTAINS', 'Cash', 'Contra', 100),
    (true, 'CSH DEP (CDM)', 'CSH DEP', 'CONTAINS', 'Cash', 'Contra', 100),
    (true, 'ATM WDL', 'ATM WDL', 'CONTAINS', 'Cash', 'Contra', 100),
    (true, 'INTEREST PAID', 'INTEREST PAID', 'CONTAINS', 'Bank Interest Expense', 'Payment', 50),
    (true, 'INTEREST RECEIVED', 'INTEREST RECEIVED', 'CONTAINS', 'Bank Interest Income', 'Receipt', 50),
    (true, 'CHG:', 'CHG:', 'CONTAINS', 'Bank Charges A/C', 'Payment', 50),
    (true, 'GST:', 'GST:', 'CONTAINS', 'GST Input Tax Credit', 'Payment', 50)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 13. FIRST ADMIN ACCOUNT SETUP INSTRUCTIONS & COMMANDS
-- ============================================================================
-- STEP 1: Open website (/signup) and register a normal user account with your desired email.
-- STEP 2: In Supabase SQL Editor, execute EITHER of the following options:
--
-- OPTION A (Recommended — By Email):
--     SELECT public.promote_user_to_admin('your-email@example.com');
--
-- OPTION B (Direct SQL Update by Email):
--     UPDATE public.profiles
--     SET role = 'ADMIN', updated_at = now()
--     WHERE LOWER(email) = LOWER('your-email@example.com');
--
--     UPDATE public.user_access
--     SET unlimited = true, access_type = 'UNLIMITED', updated_at = now()
--     WHERE user_id = (SELECT id FROM auth.users WHERE LOWER(email) = LOWER('your-email@example.com'));
--
--     UPDATE auth.users
--     SET raw_user_meta_data = COALESCE(raw_user_meta_data, '{}'::jsonb) || '{"role": "ADMIN", "is_admin": true, "is_unlimited": true}'::jsonb
--     WHERE LOWER(email) = LOWER('your-email@example.com');
--
-- OPTION C (By User UUID):
--     SELECT public.assign_admin_role('00000000-0000-0000-0000-000000000000', 'ADMIN');
--
-- RESULTS OF ADMIN PROMOTION:
--   1. Profile role becomes 'ADMIN'.
--   2. User access entitlement becomes 'UNLIMITED' (permanent quota bypass).
--   3. Auth metadata is updated so JWT tokens reflect admin privileges immediately.
--   4. Action is safely recorded in audit_logs.
--   5. Full server-verified access to /admin, /admin/convert, /admin/users, /admin/parsers, /admin/settings.
-- ============================================================================

-- ============================================================================
-- 14. READ-ONLY DATABASE VERIFICATION QUERIES
-- ============================================================================
-- Run these queries after executing this script to confirm successful setup:

-- Check 1: Verify PostgreSQL Extensions
SELECT extname, extversion FROM pg_extension WHERE extname IN ('uuid-ossp', 'pgcrypto');

-- Check 2: Verify 38 Commercial Banks Seeded (Expected count: 38)
SELECT count(*) AS total_registered_banks FROM public.bank_parsers;

-- Check 3: Verify All Bank Detection Signatures Seeded (Expected count: >= 114)
SELECT count(*) AS total_signatures FROM public.bank_signatures;

-- Check 4: Verify System Settings Seeded (Expected count: 15)
SELECT count(*) AS total_system_settings FROM public.system_settings;

-- Check 5: Verify All 13 Public Tables Have Row Level Security (RLS) Enabled
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY tablename;

-- Check 6: Verify Atomic Quota Stored Procedure Exists
SELECT routine_name, routine_type, security_type
FROM information_schema.routines 
WHERE routine_schema = 'public' AND routine_name = 'check_and_record_usage';

-- Check 7: Verify User Signup Trigger Exists on auth.users
SELECT trigger_name, event_manipulation, event_object_table, action_statement
FROM information_schema.triggers
WHERE trigger_schema = 'public' OR event_object_table = 'users';

-- ============================================================================
-- END OF KANGRA HUB COMPLETE SUPABASE DATABASE SCHEMA
-- ============================================================================
