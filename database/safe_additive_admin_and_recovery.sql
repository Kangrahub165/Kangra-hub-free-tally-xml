-- ============================================================================
-- Kangra Hub Free Tally XML - Safe Additive Migration
-- File: database/safe_additive_admin_and_recovery.sql
-- Description:
--   1. Fully additive: NO DROP TABLE, NO TRUNCATE, NO DATA LOSS.
--   2. Ensures public.profiles has all status and verification columns.
--   3. Creates public.admin_user_settings for per-user quota overrides.
--   4. Enhances public.account_recovery_requests for 2-Step Account Recovery.
--   5. Ensures public.admin_audit_log exists for complete admin audit trail.
--   6. Configures secure RLS policies allowing Admin and Service Role access.
--   7. Configures handle_new_user() trigger on auth.users (INSERT & UPDATE).
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 1. ADDITIVE ENHANCEMENT TO public.profiles
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL DEFAULT 'User',
    email TEXT NOT NULL,
    mobile_number TEXT,
    role TEXT NOT NULL DEFAULT 'USER' CHECK (role IN ('USER', 'ADMIN', 'SUPER_ADMIN')),
    account_status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (account_status IN ('ACTIVE', 'SUSPENDED', 'BLOCKED', 'DEACTIVATED')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    email_verified BOOLEAN NOT NULL DEFAULT false,
    mobile_verified BOOLEAN NOT NULL DEFAULT false,
    mfa_enabled BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Safely add any missing columns to public.profiles
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'account_status') THEN
        ALTER TABLE public.profiles ADD COLUMN account_status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (account_status IN ('ACTIVE', 'SUSPENDED', 'BLOCKED', 'DEACTIVATED'));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'is_active') THEN
        ALTER TABLE public.profiles ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT true;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'email_verified') THEN
        ALTER TABLE public.profiles ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT false;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'mobile_verified') THEN
        ALTER TABLE public.profiles ADD COLUMN mobile_verified BOOLEAN NOT NULL DEFAULT false;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'mfa_enabled') THEN
        ALTER TABLE public.profiles ADD COLUMN mfa_enabled BOOLEAN NOT NULL DEFAULT false;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'last_login_at') THEN
        ALTER TABLE public.profiles ADD COLUMN last_login_at TIMESTAMPTZ;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON public.profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_profiles_email ON public.profiles(email);
CREATE INDEX IF NOT EXISTS idx_profiles_role ON public.profiles(role);
CREATE INDEX IF NOT EXISTS idx_profiles_status ON public.profiles(account_status);

-- ============================================================================
-- 2. CREATE public.admin_user_settings (PRD Section 45)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.admin_user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    quota_mode TEXT NOT NULL DEFAULT 'GLOBAL' CHECK (quota_mode IN ('GLOBAL', 'CUSTOM', 'UNLIMITED')),
    custom_daily_limit INTEGER DEFAULT NULL,
    account_status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (account_status IN ('ACTIVE', 'SUSPENDED', 'BLOCKED', 'DEACTIVATED')),
    admin_notes TEXT,
    updated_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_user_settings_user_id ON public.admin_user_settings(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_user_settings_quota_mode ON public.admin_user_settings(quota_mode);
CREATE INDEX IF NOT EXISTS idx_admin_user_settings_status ON public.admin_user_settings(account_status);

-- ============================================================================
-- 3. CREATE & ENHANCE public.account_recovery_requests (PRD Sections 24-30, 45)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.account_recovery_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_reference TEXT NOT NULL UNIQUE,
    account_identifier TEXT NOT NULL,
    known_email TEXT,
    known_mobile TEXT,
    requested_new_email TEXT,
    requested_new_mobile TEXT,
    reason TEXT NOT NULL,
    identity_verification_info TEXT,
    status TEXT NOT NULL DEFAULT 'Pending',
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    decision_reason TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Safely add 2-Step Recovery columns
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'account_recovery_requests' AND column_name = 'user_id') THEN
        ALTER TABLE public.account_recovery_requests ADD COLUMN user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'account_recovery_requests' AND column_name = 'step1_status') THEN
        ALTER TABLE public.account_recovery_requests ADD COLUMN step1_status TEXT NOT NULL DEFAULT 'PENDING';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'account_recovery_requests' AND column_name = 'step1_notes') THEN
        ALTER TABLE public.account_recovery_requests ADD COLUMN step1_notes TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'account_recovery_requests' AND column_name = 'step1_verified_by') THEN
        ALTER TABLE public.account_recovery_requests ADD COLUMN step1_verified_by TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'account_recovery_requests' AND column_name = 'step1_verified_at') THEN
        ALTER TABLE public.account_recovery_requests ADD COLUMN step1_verified_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'account_recovery_requests' AND column_name = 'proposed_new_email') THEN
        ALTER TABLE public.account_recovery_requests ADD COLUMN proposed_new_email TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'account_recovery_requests' AND column_name = 'step2_status') THEN
        ALTER TABLE public.account_recovery_requests ADD COLUMN step2_status TEXT NOT NULL DEFAULT 'PENDING';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'account_recovery_requests' AND column_name = 'step2_otp_hash') THEN
        ALTER TABLE public.account_recovery_requests ADD COLUMN step2_otp_hash TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'account_recovery_requests' AND column_name = 'step2_otp_expires_at') THEN
        ALTER TABLE public.account_recovery_requests ADD COLUMN step2_otp_expires_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'account_recovery_requests' AND column_name = 'step2_verified_at') THEN
        ALTER TABLE public.account_recovery_requests ADD COLUMN step2_verified_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'account_recovery_requests' AND column_name = 'completed_at') THEN
        ALTER TABLE public.account_recovery_requests ADD COLUMN completed_at TIMESTAMPTZ;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_recovery_requests_ref ON public.account_recovery_requests(request_reference);
CREATE INDEX IF NOT EXISTS idx_recovery_requests_status ON public.account_recovery_requests(status);
CREATE INDEX IF NOT EXISTS idx_recovery_requests_ident ON public.account_recovery_requests(account_identifier);
CREATE INDEX IF NOT EXISTS idx_recovery_requests_created_at ON public.account_recovery_requests(created_at DESC);

-- ============================================================================
-- 4. CREATE public.admin_audit_log (PRD Section 31, 45)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.admin_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    target_user_id TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    ip_address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_audit_log_action ON public.admin_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_target ON public.admin_audit_log(target_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_created_at ON public.admin_audit_log(created_at DESC);

-- Also ensure public.audit_logs has compatibility
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id TEXT,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    ip_address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================================
-- 5. GRANTS & ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.admin_user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.account_recovery_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.admin_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- Permissions
GRANT ALL ON TABLE public.profiles TO postgres, service_role;
GRANT SELECT, INSERT, UPDATE ON TABLE public.profiles TO anon, authenticated;

GRANT ALL ON TABLE public.admin_user_settings TO postgres, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.admin_user_settings TO anon, authenticated;

GRANT ALL ON TABLE public.account_recovery_requests TO postgres, service_role;
GRANT SELECT, INSERT, UPDATE ON TABLE public.account_recovery_requests TO anon, authenticated;

GRANT ALL ON TABLE public.admin_audit_log TO postgres, service_role;
GRANT SELECT, INSERT ON TABLE public.admin_audit_log TO anon, authenticated;

GRANT ALL ON TABLE public.audit_logs TO postgres, service_role;
GRANT SELECT, INSERT ON TABLE public.audit_logs TO anon, authenticated;

-- Service role bypasses RLS
DROP POLICY IF EXISTS "Service role full access on profiles" ON public.profiles;
CREATE POLICY "Service role full access on profiles"
    ON public.profiles FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role');

DROP POLICY IF EXISTS "Service role full access on admin_user_settings" ON public.admin_user_settings;
CREATE POLICY "Service role full access on admin_user_settings"
    ON public.admin_user_settings FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role');

DROP POLICY IF EXISTS "Service role full access on recovery" ON public.account_recovery_requests;
CREATE POLICY "Service role full access on recovery"
    ON public.account_recovery_requests FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role');

DROP POLICY IF EXISTS "Service role full access on admin_audit_log" ON public.admin_audit_log;
CREATE POLICY "Service role full access on admin_audit_log"
    ON public.admin_audit_log FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role');

-- Users can view their own profile
DROP POLICY IF EXISTS "Users can view own profile" ON public.profiles;
CREATE POLICY "Users can view own profile"
    ON public.profiles FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own profile" ON public.profiles;
CREATE POLICY "Users can update own profile"
    ON public.profiles FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Admins can view and update all profiles
DROP POLICY IF EXISTS "Admins can view all profiles" ON public.profiles;
CREATE POLICY "Admins can view all profiles"
    ON public.profiles FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.profiles admin_p
            WHERE admin_p.user_id = auth.uid()
            AND admin_p.role IN ('ADMIN', 'SUPER_ADMIN')
        )
    );

DROP POLICY IF EXISTS "Admins can update all profiles" ON public.profiles;
CREATE POLICY "Admins can update all profiles"
    ON public.profiles FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM public.profiles admin_p
            WHERE admin_p.user_id = auth.uid()
            AND admin_p.role IN ('ADMIN', 'SUPER_ADMIN')
        )
    );

-- Allow public recovery submission
DROP POLICY IF EXISTS "Allow public recovery submission" ON public.account_recovery_requests;
CREATE POLICY "Allow public recovery submission"
    ON public.account_recovery_requests FOR INSERT
    WITH CHECK (true);

DROP POLICY IF EXISTS "Users can view own recovery request" ON public.account_recovery_requests;
CREATE POLICY "Users can view own recovery request"
    ON public.account_recovery_requests FOR SELECT
    USING (auth.uid() = user_id OR auth.jwt() ->> 'role' = 'service_role');

-- ============================================================================
-- 6. TRIGGER FUNCTION: AUTO-CREATE & SYNC PROFILE ON AUTH EVENT
-- ============================================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
    user_full_name TEXT;
    user_mobile TEXT;
    is_verified BOOLEAN;
BEGIN
    user_full_name := COALESCE(NEW.raw_user_meta_data->>'full_name', 'User');
    user_mobile := COALESCE(NEW.raw_user_meta_data->>'mobile_number', NEW.raw_user_meta_data->>'phone', '');
    is_verified := (NEW.email_confirmed_at IS NOT NULL) OR COALESCE((NEW.raw_user_meta_data->>'email_verified')::BOOLEAN, false);

    INSERT INTO public.profiles (
        user_id,
        full_name,
        email,
        mobile_number,
        role,
        account_status,
        is_active,
        email_verified,
        mobile_verified
    )
    VALUES (
        NEW.id,
        user_full_name,
        COALESCE(NEW.email, ''),
        user_mobile,
        COALESCE(NEW.raw_user_meta_data->>'role', 'USER'),
        'ACTIVE',
        true,
        is_verified,
        COALESCE((NEW.raw_user_meta_data->>'mobile_verified')::BOOLEAN, false)
    )
    ON CONFLICT (user_id) DO UPDATE
    SET
        full_name = CASE WHEN EXCLUDED.full_name <> 'User' THEN EXCLUDED.full_name ELSE public.profiles.full_name END,
        email = CASE WHEN EXCLUDED.email <> '' THEN EXCLUDED.email ELSE public.profiles.email END,
        mobile_number = CASE WHEN EXCLUDED.mobile_number <> '' THEN EXCLUDED.mobile_number ELSE public.profiles.mobile_number END,
        email_verified = CASE WHEN is_verified = true THEN true ELSE public.profiles.email_verified END,
        updated_at = now();

    -- Also initialize default admin_user_settings row if not present
    INSERT INTO public.admin_user_settings (
        user_id,
        quota_mode,
        custom_daily_limit,
        account_status
    )
    VALUES (
        NEW.id,
        'GLOBAL',
        NULL,
        'ACTIVE'
    )
    ON CONFLICT (user_id) DO NOTHING;

    RETURN NEW;
EXCEPTION WHEN OTHERS THEN
    -- Never break Supabase Auth flow with unhandled exceptions
    RAISE WARNING 'handle_new_user exception for user %: %', NEW.id, SQLERRM;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Bind trigger for BOTH INSERT and UPDATE on auth.users
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

DROP TRIGGER IF EXISTS on_auth_user_updated ON auth.users;
CREATE TRIGGER on_auth_user_updated
    AFTER UPDATE OF email, email_confirmed_at, raw_user_meta_data ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================================================
-- VERIFICATION SELECT
-- ============================================================================
SELECT 'Safe additive migration for Kangra Hub completed successfully.' AS status;
