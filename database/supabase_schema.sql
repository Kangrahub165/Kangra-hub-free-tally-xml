-- ============================================================================
-- Kangra Hub Free Tally XML - Supabase Database Schema
-- File: database/supabase_schema.sql
-- Description: Complete production schema with RLS, triggers, functions, and seed data.
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Clean up any existing objects if re-running
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP FUNCTION IF EXISTS public.handle_new_user();
DROP FUNCTION IF EXISTS public.is_admin(UUID);
DROP FUNCTION IF EXISTS public.get_user_daily_usage(UUID, DATE);
DROP FUNCTION IF EXISTS public.check_and_record_usage(UUID, INT);

-- ============================================================================
-- 1. SYSTEM SETTINGS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.system_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    setting_key TEXT NOT NULL UNIQUE,
    setting_value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by UUID REFERENCES auth.users(id) ON DELETE SET NULL
);

-- ============================================================================
-- 2. PROFILES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    mobile_number TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'USER' CHECK (role IN ('USER', 'ADMIN', 'SUPER_ADMIN')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON public.profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_profiles_email ON public.profiles(email);
CREATE INDEX IF NOT EXISTS idx_profiles_role ON public.profiles(role);

-- ============================================================================
-- 3. USER ACCESS / ENTITLEMENTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.user_access (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    access_type TEXT NOT NULL DEFAULT 'FREE' CHECK (access_type IN ('FREE', 'PAID', 'UNLIMITED')),
    status TEXT NOT NULL DEFAULT 'APPROVED' CHECK (status IN ('APPROVED', 'PENDING', 'SUSPENDED', 'EXPIRED')),
    daily_page_limit INT NOT NULL DEFAULT 50,
    unlimited BOOLEAN NOT NULL DEFAULT false,
    approved_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_access_user_id ON public.user_access(user_id);
CREATE INDEX IF NOT EXISTS idx_user_access_unlimited ON public.user_access(unlimited);

-- ============================================================================
-- 4. USAGE DAILY TABLE (Asia/Kolkata timezone basis)
-- ============================================================================
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

CREATE INDEX IF NOT EXISTS idx_usage_daily_user_date ON public.usage_daily(user_id, usage_date);

-- ============================================================================
-- 5. CONVERSION JOBS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.conversion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    bank_name TEXT NOT NULL,
    statement_format TEXT NOT NULL DEFAULT 'Standard',
    parser_key TEXT,
    parser_version TEXT DEFAULT '1.0',
    page_count INT NOT NULL DEFAULT 1 CHECK (page_count > 0),
    transaction_count INT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PROCESSING' CHECK (status IN ('PROCESSING', 'COMPLETED', 'FAILED', 'NEEDS_REVIEW')),
    confidence_score NUMERIC(5, 2) DEFAULT 100.00,
    error_code TEXT,
    error_message TEXT,
    output_xml_filename TEXT,
    processing_duration_ms INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_conversion_jobs_user_id ON public.conversion_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_conversion_jobs_status ON public.conversion_jobs(status);
CREATE INDEX IF NOT EXISTS idx_conversion_jobs_created_at ON public.conversion_jobs(created_at DESC);

-- ============================================================================
-- 6. TRANSACTIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES public.conversion_jobs(id) ON DELETE CASCADE,
    row_index INT NOT NULL DEFAULT 0,
    transaction_date DATE NOT NULL,
    value_date DATE,
    narration TEXT NOT NULL,
    reference_number TEXT,
    debit NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    credit NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    balance NUMERIC(15, 2),
    confidence_score NUMERIC(5, 2) DEFAULT 100.00,
    ledger_name TEXT,
    voucher_type TEXT NOT NULL DEFAULT 'Payment' CHECK (voucher_type IN ('Payment', 'Receipt', 'Contra', 'Journal')),
    validation_status TEXT NOT NULL DEFAULT 'VALID' CHECK (validation_status IN ('VALID', 'WARNING', 'ERROR')),
    validation_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_transactions_job_id ON public.transactions(job_id);

-- ============================================================================
-- 7. LEDGER MAPPINGS TABLE (User party-to-ledger preferences)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.ledger_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    source_pattern TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    tally_ledger_name TEXT NOT NULL,
    confidence NUMERIC(5, 2) DEFAULT 100.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT unique_user_source_pattern UNIQUE (user_id, source_pattern)
);

CREATE INDEX IF NOT EXISTS idx_ledger_mappings_user_id ON public.ledger_mappings(user_id);

-- ============================================================================
-- 8. BANK PARSERS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.bank_parsers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bank_name TEXT NOT NULL,
    format_name TEXT NOT NULL DEFAULT 'Standard',
    parser_key TEXT NOT NULL UNIQUE,
    version TEXT NOT NULL DEFAULT '1.0',
    is_active BOOLEAN NOT NULL DEFAULT true,
    confidence_threshold NUMERIC(5, 2) NOT NULL DEFAULT 75.00,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bank_parsers_key ON public.bank_parsers(parser_key);
CREATE INDEX IF NOT EXISTS idx_bank_parsers_active ON public.bank_parsers(is_active);

-- ============================================================================
-- 9. BANK SIGNATURES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.bank_signatures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bank_parser_id UUID NOT NULL REFERENCES public.bank_parsers(id) ON DELETE CASCADE,
    pattern TEXT NOT NULL,
    priority INT NOT NULL DEFAULT 10,
    signature_type TEXT NOT NULL DEFAULT 'TEXT_KEYWORD' CHECK (signature_type IN ('TEXT_KEYWORD', 'REGEX', 'HEADER_LAYOUT')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bank_signatures_parser ON public.bank_signatures(bank_parser_id);

-- ============================================================================
-- 10. AUDIT LOGS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    ip_address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_admin ON public.audit_logs(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON public.audit_logs(created_at DESC);

-- ============================================================================
-- HELPER FUNCTIONS & TRIGGERS
-- ============================================================================

-- Check if a user has ADMIN or SUPER_ADMIN role
CREATE OR REPLACE FUNCTION public.is_admin(p_user_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_role TEXT;
BEGIN
    SELECT role INTO v_role FROM public.profiles WHERE user_id = p_user_id;
    RETURN (v_role IN ('ADMIN', 'SUPER_ADMIN'));
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to automatically create profile and access record on user signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
    v_full_name TEXT;
    v_mobile TEXT;
    v_default_daily_limit INT := 50;
BEGIN
    v_full_name := COALESCE(new.raw_user_meta_data->>'full_name', 'User');
    v_mobile := COALESCE(new.raw_user_meta_data->>'mobile_number', '');

    -- Insert into profiles
    INSERT INTO public.profiles (user_id, full_name, email, mobile_number, role, is_active)
    VALUES (new.id, v_full_name, new.email, v_mobile, 'USER', true)
    ON CONFLICT (user_id) DO UPDATE SET
        full_name = EXCLUDED.full_name,
        email = EXCLUDED.email,
        mobile_number = EXCLUDED.mobile_number,
        updated_at = now();

    -- Insert into user_access
    INSERT INTO public.user_access (user_id, access_type, status, daily_page_limit, unlimited)
    VALUES (new.id, 'FREE', 'APPROVED', v_default_daily_limit, false)
    ON CONFLICT (user_id) DO NOTHING;

    RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Automatic updated_at timestamp trigger function
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_profiles_updated_at BEFORE UPDATE ON public.profiles FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trigger_user_access_updated_at BEFORE UPDATE ON public.user_access FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trigger_usage_daily_updated_at BEFORE UPDATE ON public.usage_daily FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trigger_ledger_mappings_updated_at BEFORE UPDATE ON public.ledger_mappings FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trigger_bank_parsers_updated_at BEFORE UPDATE ON public.bank_parsers FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trigger_system_settings_updated_at BEFORE UPDATE ON public.system_settings FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- Stored procedure to verify & record usage before conversion
CREATE OR REPLACE FUNCTION public.check_and_record_usage(p_user_id UUID, p_pages INT)
RETURNS TABLE (
    allowed BOOLEAN,
    remaining_pages INT,
    daily_limit INT,
    is_unlimited BOOLEAN,
    message TEXT
) AS $$
DECLARE
    v_is_admin BOOLEAN;
    v_is_unlimited BOOLEAN;
    v_limit INT := 50;
    v_used INT := 0;
    v_today DATE := (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::DATE;
BEGIN
    -- Check admin status
    SELECT public.is_admin(p_user_id) INTO v_is_admin;
    IF v_is_admin THEN
        RETURN QUERY SELECT true, 999999, 999999, true, 'Admin unlimited access'::TEXT;
        RETURN;
    END IF;

    -- Check user access record
    SELECT ua.unlimited, ua.daily_page_limit
    INTO v_is_unlimited, v_limit
    FROM public.user_access ua
    WHERE ua.user_id = p_user_id;

    IF v_is_unlimited THEN
        RETURN QUERY SELECT true, 999999, 999999, true, 'Unlimited approved user'::TEXT;
        RETURN;
    END IF;

    IF v_limit IS NULL THEN
        v_limit := 50;
    END IF;

    -- Get today's usage
    SELECT COALESCE(pages_processed, 0)
    INTO v_used
    FROM public.usage_daily
    WHERE user_id = p_user_id AND usage_date = v_today;

    IF (v_used + p_pages) > v_limit THEN
        RETURN QUERY SELECT false, GREATEST(0, v_limit - v_used), v_limit, false,
            FORMAT('You have %s pages remaining today. This PDF contains %s pages.', GREATEST(0, v_limit - v_used), p_pages)::TEXT;
        RETURN;
    END IF;

    -- Record usage
    INSERT INTO public.usage_daily (user_id, usage_date, pages_processed, files_processed)
    VALUES (p_user_id, v_today, p_pages, 1)
    ON CONFLICT (user_id, usage_date)
    DO UPDATE SET
        pages_processed = public.usage_daily.pages_processed + p_pages,
        files_processed = public.usage_daily.files_processed + 1,
        updated_at = now();

    RETURN QUERY SELECT true, (v_limit - (v_used + p_pages)), v_limit, false, 'Usage recorded successfully'::TEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_access ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.usage_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversion_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ledger_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bank_parsers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bank_signatures ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- 1. Profiles RLS
CREATE POLICY "Users can view own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = user_id OR public.is_admin(auth.uid()));

CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = user_id OR public.is_admin(auth.uid()));

-- 2. User Access RLS
CREATE POLICY "Users can view own access" ON public.user_access
    FOR SELECT USING (auth.uid() = user_id OR public.is_admin(auth.uid()));

CREATE POLICY "Admins can update user access" ON public.user_access
    FOR ALL USING (public.is_admin(auth.uid()));

-- 3. Usage Daily RLS
CREATE POLICY "Users can view own usage" ON public.usage_daily
    FOR SELECT USING (auth.uid() = user_id OR public.is_admin(auth.uid()));

-- 4. Conversion Jobs RLS
CREATE POLICY "Users can view own jobs" ON public.conversion_jobs
    FOR SELECT USING (auth.uid() = user_id OR public.is_admin(auth.uid()));

CREATE POLICY "Users can insert own jobs" ON public.conversion_jobs
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own jobs" ON public.conversion_jobs
    FOR UPDATE USING (auth.uid() = user_id OR public.is_admin(auth.uid()));

-- 5. Transactions RLS
CREATE POLICY "Users can view own job transactions" ON public.transactions
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.conversion_jobs j
            WHERE j.id = transactions.job_id AND (j.user_id = auth.uid() OR public.is_admin(auth.uid()))
        )
    );

CREATE POLICY "Users can manage own job transactions" ON public.transactions
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.conversion_jobs j
            WHERE j.id = transactions.job_id AND (j.user_id = auth.uid() OR public.is_admin(auth.uid()))
        )
    );

-- 6. Ledger Mappings RLS
CREATE POLICY "Users manage own ledger mappings" ON public.ledger_mappings
    FOR ALL USING (auth.uid() = user_id);

-- 7. Bank Parsers & Signatures (Public read, admin write)
CREATE POLICY "Anyone can read active parsers" ON public.bank_parsers
    FOR SELECT USING (is_active = true OR public.is_admin(auth.uid()));

CREATE POLICY "Admins can manage parsers" ON public.bank_parsers
    FOR ALL USING (public.is_admin(auth.uid()));

CREATE POLICY "Anyone can read signatures" ON public.bank_signatures
    FOR SELECT USING (true);

CREATE POLICY "Admins can manage signatures" ON public.bank_signatures
    FOR ALL USING (public.is_admin(auth.uid()));

-- 8. System Settings (Public read for public config, admin write)
CREATE POLICY "Anyone can read public settings" ON public.system_settings
    FOR SELECT USING (true);

CREATE POLICY "Admins can manage settings" ON public.system_settings
    FOR ALL USING (public.is_admin(auth.uid()));

-- 9. Audit Logs (Admin only)
CREATE POLICY "Admins can view audit logs" ON public.audit_logs
    FOR SELECT USING (public.is_admin(auth.uid()));

CREATE POLICY "Admins can insert audit logs" ON public.audit_logs
    FOR INSERT WITH CHECK (public.is_admin(auth.uid()));

-- ============================================================================
-- SEED DATA
-- ============================================================================

-- System Settings default seed
INSERT INTO public.system_settings (setting_key, setting_value, description)
VALUES 
    ('site_name', '"Kangra Hub Free Tally XML"'::jsonb, 'Public site name'),
    ('site_mode', '"FREE"'::jsonb, 'Access mode: FREE or PAID'),
    ('free_daily_page_limit', '50'::jsonb, 'Default daily page quota for free users'),
    ('max_upload_size_mb', '25'::jsonb, 'Maximum upload file size in Megabytes'),
    ('max_pages_per_file', '200'::jsonb, 'Maximum allowed pages per bank statement PDF'),
    ('maintenance_mode', 'false'::jsonb, 'Whether maintenance mode is active'),
    ('allow_new_signups', 'true'::jsonb, 'Whether public signups are permitted'),
    ('file_retention_minutes', '60'::jsonb, 'Temporary storage retention before cleanup'),
    ('buy_coffee_enabled', 'true'::jsonb, 'Show Buy Me a Coffee widget in Admin Panel'),
    ('buy_coffee_upi_id', '""'::jsonb, 'Owner UPI ID for Buy Me a Coffee support'),
    ('buy_coffee_payment_url', '""'::jsonb, 'Direct UPI payment URI (e.g. upi://pay?...)'),
    ('buy_coffee_button_text', '"Buy Me a Coffee ☕"'::jsonb, 'Support button text'),
    ('buy_coffee_message', '"Enjoying Kangra Hub Free Tally XML? Support the project with a cup of coffee."'::jsonb, 'Admin support card message'),
    ('buy_coffee_qr_path', '"/buy-a-coffee/googlepay_qr.png"'::jsonb, 'Path to official owner QR code asset')
ON CONFLICT (setting_key) DO NOTHING;

-- Seed 38 Supported Banks
INSERT INTO public.bank_parsers (bank_name, format_name, parser_key, version, is_active, confidence_threshold, description)
VALUES
    ('Punjab National Bank (PNB)', 'Savings & Current Standard', 'pnb_standard', '1.0', true, 80.00, 'PNB statement format with transaction date, particulars, debit, credit, balance'),
    ('State Bank of India (SBI)', 'Standard e-Statement', 'sbi_standard', '1.0', true, 80.00, 'SBI standard internet banking and branch statement'),
    ('HDFC Bank', 'Standard e-Statement', 'hdfc_standard', '1.0', true, 80.00, 'HDFC Bank standard account statement layout'),
    ('ICICI Bank', 'Standard e-Statement', 'icici_standard', '1.0', true, 80.00, 'ICICI Bank digital statement format'),
    ('Axis Bank', 'Standard e-Statement', 'axis_standard', '1.0', true, 80.00, 'Axis Bank statement format'),
    ('Kotak Mahindra Bank', 'Standard e-Statement', 'kotak_standard', '1.0', true, 80.00, 'Kotak Mahindra Bank statement format'),
    ('Bank of Baroda (BOB)', 'Standard e-Statement', 'bob_standard', '1.0', true, 80.00, 'Bank of Baroda statement format'),
    ('IDFC FIRST Bank', 'Standard e-Statement', 'idfc_standard', '1.0', true, 80.00, 'IDFC FIRST Bank statement format'),
    ('YES Bank', 'Standard e-Statement', 'yes_standard', '1.0', true, 80.00, 'YES Bank statement format'),
    ('RBL Bank', 'Standard e-Statement', 'rbl_standard', '1.0', true, 80.00, 'RBL Bank statement format'),
    ('DCB Bank', 'Standard e-Statement', 'dcb_standard', '1.0', true, 80.00, 'DCB Bank statement format'),
    ('Union Bank of India', 'Standard e-Statement', 'union_standard', '1.0', true, 80.00, 'Union Bank of India statement format'),
    ('Canara Bank', 'Standard e-Statement', 'canara_standard', '1.0', true, 80.00, 'Canara Bank statement format'),
    ('Indian Bank', 'Standard e-Statement', 'indian_standard', '1.0', true, 80.00, 'Indian Bank statement format'),
    ('Indian Overseas Bank (IOB)', 'Standard e-Statement', 'iob_standard', '1.0', true, 80.00, 'Indian Overseas Bank statement format'),
    ('Bank of India (BOI)', 'Standard e-Statement', 'boi_standard', '1.0', true, 80.00, 'Bank of India statement format'),
    ('Bank of Maharashtra', 'Standard e-Statement', 'maharashtra_standard', '1.0', true, 80.00, 'Bank of Maharashtra statement format'),
    ('Central Bank of India', 'Standard e-Statement', 'cbi_standard', '1.0', true, 80.00, 'Central Bank of India statement format'),
    ('UCO Bank', 'Standard e-Statement', 'uco_standard', '1.0', true, 80.00, 'UCO Bank statement format'),
    ('Punjab & Sind Bank', 'Standard e-Statement', 'psb_standard', '1.0', true, 80.00, 'Punjab & Sind Bank statement format'),
    ('IndusInd Bank', 'Standard e-Statement', 'indusind_standard', '1.0', true, 80.00, 'IndusInd Bank statement format'),
    ('IDBI Bank', 'Standard e-Statement', 'idbi_standard', '1.0', true, 80.00, 'IDBI Bank statement format'),
    ('Federal Bank', 'Standard e-Statement', 'federal_standard', '1.0', true, 80.00, 'Federal Bank statement format'),
    ('Bandhan Bank', 'Standard e-Statement', 'bandhan_standard', '1.0', true, 80.00, 'Bandhan Bank statement format'),
    ('AU Small Finance Bank', 'Standard e-Statement', 'au_standard', '1.0', true, 80.00, 'AU Small Finance Bank statement format'),
    ('City Union Bank', 'Standard e-Statement', 'cub_standard', '1.0', true, 80.00, 'City Union Bank statement format'),
    ('Karnataka Bank', 'Standard e-Statement', 'karnataka_standard', '1.0', true, 80.00, 'Karnataka Bank statement format'),
    ('South Indian Bank', 'Standard e-Statement', 'sib_standard', '1.0', true, 80.00, 'South Indian Bank statement format'),
    ('Tamilnad Mercantile Bank', 'Standard e-Statement', 'tmb_standard', '1.0', true, 80.00, 'Tamilnad Mercantile Bank statement format'),
    ('Jammu & Kashmir Bank', 'Standard e-Statement', 'jkb_standard', '1.0', true, 80.00, 'Jammu & Kashmir Bank statement format'),
    ('CSB Bank', 'Standard e-Statement', 'csb_standard', '1.0', true, 80.00, 'CSB Bank statement format'),
    ('Dhanlaxmi Bank', 'Standard e-Statement', 'dhanlaxmi_standard', '1.0', true, 80.00, 'Dhanlaxmi Bank statement format'),
    ('Nainital Bank', 'Standard e-Statement', 'nainital_standard', '1.0', true, 80.00, 'Nainital Bank statement format'),
    ('Equitas Small Finance Bank', 'Standard e-Statement', 'equitas_standard', '1.0', true, 80.00, 'Equitas Small Finance Bank statement format'),
    ('HSBC', 'Standard e-Statement', 'hsbc_standard', '1.0', true, 80.00, 'HSBC India statement format'),
    ('DBS Bank', 'Standard e-Statement', 'dbs_standard', '1.0', true, 80.00, 'DBS Bank India statement format'),
    ('Deutsche Bank', 'Standard e-Statement', 'deutsche_standard', '1.0', true, 80.00, 'Deutsche Bank India statement format'),
    ('Barclays', 'Standard e-Statement', 'barclays_standard', '1.0', true, 80.00, 'Barclays Bank India statement format')
ON CONFLICT (parser_key) DO NOTHING;

-- Seed signatures for the primary banks
INSERT INTO public.bank_signatures (bank_parser_id, pattern, priority, signature_type)
SELECT id, 'PUNJAB NATIONAL BANK', 10, 'TEXT_KEYWORD' FROM public.bank_parsers WHERE parser_key = 'pnb_standard'
UNION ALL
SELECT id, 'STATE BANK OF INDIA', 10, 'TEXT_KEYWORD' FROM public.bank_parsers WHERE parser_key = 'sbi_standard'
UNION ALL
SELECT id, 'HDFC BANK', 10, 'TEXT_KEYWORD' FROM public.bank_parsers WHERE parser_key = 'hdfc_standard'
UNION ALL
SELECT id, 'ICICI BANK', 10, 'TEXT_KEYWORD' FROM public.bank_parsers WHERE parser_key = 'icici_standard'
UNION ALL
SELECT id, 'AXIS BANK', 10, 'TEXT_KEYWORD' FROM public.bank_parsers WHERE parser_key = 'axis_standard'
UNION ALL
SELECT id, 'KOTAK MAHINDRA BANK', 10, 'TEXT_KEYWORD' FROM public.bank_parsers WHERE parser_key = 'kotak_standard'
UNION ALL
SELECT id, 'BANK OF BARODA', 10, 'TEXT_KEYWORD' FROM public.bank_parsers WHERE parser_key = 'bob_standard'
UNION ALL
SELECT id, 'IDFC FIRST BANK', 10, 'TEXT_KEYWORD' FROM public.bank_parsers WHERE parser_key = 'idfc_standard'
UNION ALL
SELECT id, 'YES BANK', 10, 'TEXT_KEYWORD' FROM public.bank_parsers WHERE parser_key = 'yes_standard';
