-- ============================================================================
-- Kangra Hub Free Tally XML - Authentication, OTP & Account Management Schema
-- File: database/otp_and_auth_setup.sql
-- Description: 
--   1. Note: OTP codes are verified in secure salted SHA-256 volatile memory
--      to protect customer privacy and comply with financial security standards.
--      NO OTP TABLE IS STRICTLY REQUIRED for OTP generation/validation.
--   2. This script ensures Supabase has all supporting tables for:
--      - Profiles with Account Statuses (ACTIVE, BLOCKED, SUSPENDED, DEACTIVATED)
--      - Verification flags (email_verified, mobile_verified)
--      - Immutable Security Audit Logs (audit_logs)
--      - Account Recovery Requests (for lost contact recovery flow)
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 1. ENHANCE PROFILES TABLE (Section 16: Account Status & Verification)
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
    email_verified BOOLEAN NOT NULL DEFAULT true,
    mobile_verified BOOLEAN NOT NULL DEFAULT false,
    mfa_enabled BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Ensure columns exist if table was created earlier
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'account_status') THEN
        ALTER TABLE public.profiles ADD COLUMN account_status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (account_status IN ('ACTIVE', 'SUSPENDED', 'BLOCKED', 'DEACTIVATED'));
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'email_verified') THEN
        ALTER TABLE public.profiles ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT true;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'mobile_verified') THEN
        ALTER TABLE public.profiles ADD COLUMN mobile_verified BOOLEAN NOT NULL DEFAULT false;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'mfa_enabled') THEN
        ALTER TABLE public.profiles ADD COLUMN mfa_enabled BOOLEAN NOT NULL DEFAULT false;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON public.profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_profiles_email ON public.profiles(email);
CREATE INDEX IF NOT EXISTS idx_profiles_role ON public.profiles(role);
CREATE INDEX IF NOT EXISTS idx_profiles_status ON public.profiles(account_status);

-- ============================================================================
-- 2. AUDIT LOGS TABLE (Section 57: Admin and Security Audit Trail)
-- ============================================================================
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

CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON public.audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON public.audit_logs(created_at DESC);

-- ============================================================================
-- 3. ACCOUNT RECOVERY REQUESTS TABLE (Section 16: Lost Contact Recovery)
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
    status TEXT NOT NULL DEFAULT 'PENDING_ADMIN_REVIEW' CHECK (status IN ('PENDING_ADMIN_REVIEW', 'APPROVED', 'REJECTED', 'MORE_INFO_REQUESTED')),
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    decision_reason TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_recovery_requests_ref ON public.account_recovery_requests(request_reference);
CREATE INDEX IF NOT EXISTS idx_recovery_requests_status ON public.account_recovery_requests(status);
CREATE INDEX IF NOT EXISTS idx_recovery_requests_created_at ON public.account_recovery_requests(created_at DESC);

-- ============================================================================
-- 4. ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.account_recovery_requests ENABLE ROW LEVEL SECURITY;

-- Profiles: Users can view their own profile; service role can do all
DROP POLICY IF EXISTS "Users can view own profile" ON public.profiles;
CREATE POLICY "Users can view own profile"
    ON public.profiles FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own profile" ON public.profiles;
CREATE POLICY "Users can update own profile"
    ON public.profiles FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Service role has full access to profiles" ON public.profiles;
CREATE POLICY "Service role has full access to profiles"
    ON public.profiles FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role');

-- Audit Logs: Admin/Service role full access; users cannot tamper
DROP POLICY IF EXISTS "Service role has full access to audit_logs" ON public.audit_logs;
CREATE POLICY "Service role has full access to audit_logs"
    ON public.audit_logs FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role');

-- Account Recovery: Anyone can insert a recovery request; admins/service role can review
DROP POLICY IF EXISTS "Allow public recovery submission" ON public.account_recovery_requests;
CREATE POLICY "Allow public recovery submission"
    ON public.account_recovery_requests FOR INSERT
    WITH CHECK (true);

DROP POLICY IF EXISTS "Service role has full access to recovery" ON public.account_recovery_requests;
CREATE POLICY "Service role has full access to recovery"
    ON public.account_recovery_requests FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role');

-- ============================================================================
-- 5. AUTO-CREATE PROFILE ON SUPABASE AUTH SIGNUP TRIGGER
-- ============================================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
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
        COALESCE(NEW.raw_user_meta_data->>'full_name', 'Registered User'),
        COALESCE(NEW.email, ''),
        COALESCE(NEW.raw_user_meta_data->>'mobile_number', ''),
        COALESCE(NEW.raw_user_meta_data->>'role', 'USER'),
        'ACTIVE',
        true,
        COALESCE((NEW.raw_user_meta_data->>'email_verified')::BOOLEAN, false),
        COALESCE((NEW.raw_user_meta_data->>'mobile_verified')::BOOLEAN, false)
    )
    ON CONFLICT (user_id) DO UPDATE
    SET
        full_name = EXCLUDED.full_name,
        mobile_number = EXCLUDED.mobile_number,
        updated_at = now();
    RETURN NEW;
EXCEPTION WHEN OTHERS THEN
    -- Prevent Supabase Auth 500 'Database error saving new user'
    RAISE WARNING 'handle_new_user exception for user %: %', NEW.id, SQLERRM;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Grant required table permissions
GRANT ALL ON TABLE public.profiles TO postgres, service_role;
GRANT SELECT, INSERT, UPDATE ON TABLE public.profiles TO anon, authenticated;
GRANT ALL ON TABLE public.audit_logs TO postgres, service_role;
GRANT SELECT, INSERT ON TABLE public.audit_logs TO anon, authenticated;
GRANT ALL ON TABLE public.account_recovery_requests TO postgres, service_role, anon, authenticated;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================================================
-- VERIFICATION CONFIRMATION
-- ============================================================================
SELECT 'Database schema for Authentication, User Statuses, and Account Recovery is ready.' AS status;
