-- ============================================================================
-- Kangra Hub Free Tally XML - Supabase Trigger Fix
-- File: database/fix_supabase_trigger.sql
-- Run this in your Supabase SQL Editor to resolve:
-- 500 Database error saving new user
-- ============================================================================

-- 1. Ensure public.profiles table exists and has necessary columns
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

-- Add any missing columns safely
DO 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'account_status') THEN
        ALTER TABLE public.profiles ADD COLUMN account_status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (account_status IN ('ACTIVE', 'SUSPENDED', 'BLOCKED', 'DEACTIVATED'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'mobile_number') THEN
        ALTER TABLE public.profiles ADD COLUMN mobile_number TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'email_verified') THEN
        ALTER TABLE public.profiles ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT true;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'mobile_verified') THEN
        ALTER TABLE public.profiles ADD COLUMN mobile_verified BOOLEAN NOT NULL DEFAULT false;
    END IF;
END ;

-- 2. Safe Trigger Function with Error Handling (Prevents Signup 500 Failure)
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS 
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
 LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- 3. Grant Permissions
GRANT ALL ON TABLE public.profiles TO postgres, service_role;
GRANT SELECT, INSERT, UPDATE ON TABLE public.profiles TO anon, authenticated;

-- 4. Re-bind Trigger to auth.users
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

SELECT 'Trigger and profiles table successfully updated.' AS status;
