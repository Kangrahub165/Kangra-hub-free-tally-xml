-- ============================================================================
-- Kangra Hub Free Tally XML - Safe Additive Migration: Appeals & Suspension
-- File: database/safe_additive_appeals_and_suspension.sql
-- Description:
--   1. Fully additive: NO DROP TABLE, NO TRUNCATE, NO DATA LOSS.
--   2. Ensures public.profiles has all suspension tracking columns.
--   3. Ensures public.admin_user_settings has suspension tracking columns.
--   4. Creates public.account_appeals table for user appeals and admin reviews.
--   5. Configures secure RLS policies allowing users to view/create their appeals
--      and administrators/service_role to manage all appeals.
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 1. ADDITIVE SUSPENSION COLUMNS TO public.profiles
-- ============================================================================
DO $$
BEGIN
    -- suspended_at
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'suspended_at'
    ) THEN
        ALTER TABLE public.profiles ADD COLUMN suspended_at TIMESTAMPTZ;
    END IF;

    -- suspension_reason
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'suspension_reason'
    ) THEN
        ALTER TABLE public.profiles ADD COLUMN suspension_reason TEXT;
    END IF;

    -- suspension_delete_at (suspended_at + 3 months)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'suspension_delete_at'
    ) THEN
        ALTER TABLE public.profiles ADD COLUMN suspension_delete_at TIMESTAMPTZ;
    END IF;

    -- suspension_reviewed_at
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'suspension_reviewed_at'
    ) THEN
        ALTER TABLE public.profiles ADD COLUMN suspension_reviewed_at TIMESTAMPTZ;
    END IF;

    -- suspension_reviewed_by
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'suspension_reviewed_by'
    ) THEN
        ALTER TABLE public.profiles ADD COLUMN suspension_reviewed_by TEXT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_profiles_suspended_at ON public.profiles(suspended_at);
CREATE INDEX IF NOT EXISTS idx_profiles_suspension_delete_at ON public.profiles(suspension_delete_at);

-- ============================================================================
-- 2. ADDITIVE SUSPENSION COLUMNS TO public.admin_user_settings
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.admin_user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE,
    quota_mode TEXT NOT NULL DEFAULT 'GLOBAL' CHECK (quota_mode IN ('GLOBAL', 'CUSTOM', 'UNLIMITED')),
    custom_daily_limit INTEGER DEFAULT NULL,
    account_status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (account_status IN ('ACTIVE', 'SUSPENDED', 'BLOCKED', 'DEACTIVATED')),
    admin_notes TEXT,
    updated_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'admin_user_settings' AND column_name = 'suspended_at'
    ) THEN
        ALTER TABLE public.admin_user_settings ADD COLUMN suspended_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'admin_user_settings' AND column_name = 'suspension_reason'
    ) THEN
        ALTER TABLE public.admin_user_settings ADD COLUMN suspension_reason TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'admin_user_settings' AND column_name = 'suspension_delete_at'
    ) THEN
        ALTER TABLE public.admin_user_settings ADD COLUMN suspension_delete_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'admin_user_settings' AND column_name = 'suspension_reviewed_at'
    ) THEN
        ALTER TABLE public.admin_user_settings ADD COLUMN suspension_reviewed_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'admin_user_settings' AND column_name = 'suspension_reviewed_by'
    ) THEN
        ALTER TABLE public.admin_user_settings ADD COLUMN suspension_reviewed_by TEXT;
    END IF;
END $$;

-- ============================================================================
-- 3. CREATE public.account_appeals TABLE (PRD Section 9)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.account_appeals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    user_email TEXT NOT NULL,
    user_name TEXT,
    subject TEXT NOT NULL DEFAULT 'Request to review my suspended account',
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'under_review', 'approved', 'rejected')),
    admin_response TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT
);

-- Essential indexes for high-speed lookup and filtering
CREATE INDEX IF NOT EXISTS idx_account_appeals_user_id ON public.account_appeals(user_id);
CREATE INDEX IF NOT EXISTS idx_account_appeals_email ON public.account_appeals(user_email);
CREATE INDEX IF NOT EXISTS idx_account_appeals_status ON public.account_appeals(status);
CREATE INDEX IF NOT EXISTS idx_account_appeals_created_at ON public.account_appeals(created_at DESC);

-- ============================================================================
-- 4. ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================
ALTER TABLE public.account_appeals ENABLE ROW LEVEL SECURITY;

-- Drop existing policies safely to prevent conflict
DROP POLICY IF EXISTS "Users can insert their own appeals" ON public.account_appeals;
DROP POLICY IF EXISTS "Users can view their own appeals" ON public.account_appeals;
DROP POLICY IF EXISTS "Admins can view all appeals" ON public.account_appeals;
DROP POLICY IF EXISTS "Admins can update appeals" ON public.account_appeals;
DROP POLICY IF EXISTS "Service role full access on appeals" ON public.account_appeals;

-- Service role has unrestricted access
CREATE POLICY "Service role full access on appeals"
    ON public.account_appeals
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Authenticated users can insert their own appeal
CREATE POLICY "Users can insert their own appeals"
    ON public.account_appeals
    FOR INSERT
    TO authenticated, anon
    WITH CHECK (true);

-- Users can view their own appeals
CREATE POLICY "Users can view their own appeals"
    ON public.account_appeals
    FOR SELECT
    TO authenticated
    USING (
        user_id = auth.uid()::text 
        OR user_email = auth.jwt()->>'email'
        OR EXISTS (
            SELECT 1 FROM public.profiles 
            WHERE profiles.user_id = auth.uid() 
            AND profiles.role IN ('ADMIN', 'SUPER_ADMIN')
        )
    );

-- Admin update policy
CREATE POLICY "Admins can update appeals"
    ON public.account_appeals
    FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.profiles 
            WHERE profiles.user_id = auth.uid() 
            AND profiles.role IN ('ADMIN', 'SUPER_ADMIN')
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.profiles 
            WHERE profiles.user_id = auth.uid() 
            AND profiles.role IN ('ADMIN', 'SUPER_ADMIN')
        )
    );

-- Table permissions
GRANT ALL ON public.account_appeals TO postgres;
GRANT ALL ON public.account_appeals TO service_role;
GRANT SELECT, INSERT ON public.account_appeals TO authenticated;
GRANT SELECT, INSERT ON public.account_appeals TO anon;
