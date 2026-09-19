-- ============================================================================
-- Kangra Hub Free Tally XML — Admin Role Promotion Script
-- File: database/promote_admin.sql
-- Description: Run this script in the Supabase SQL Editor to promote a user to ADMIN.
-- ============================================================================

-- 1. Helper Function: promote_user_to_admin(p_email TEXT)
-- This function updates both public.profiles and auth.users metadata atomically.
CREATE OR REPLACE FUNCTION public.promote_user_to_admin(p_email TEXT)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_user_id UUID;
BEGIN
    -- Locate the user by email (case-insensitive)
    SELECT id INTO v_user_id 
    FROM auth.users 
    WHERE LOWER(email) = LOWER(TRIM(p_email));

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'No user found with email address: %', p_email;
    END IF;

    -- 1. Confirm email in auth.users if not confirmed, and sync metadata
    UPDATE auth.users
    SET email_confirmed_at = COALESCE(email_confirmed_at, now()),
        raw_user_meta_data = COALESCE(raw_user_meta_data, '{}'::jsonb) || jsonb_build_object(
            'role', 'ADMIN',
            'is_admin', true,
            'is_unlimited', true,
            'full_name', 'System Administrator'
        ),
        raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb) || jsonb_build_object(
            'role', 'ADMIN',
            'is_admin', true,
            'is_unlimited', true,
            'provider', 'email'
        ),
        updated_at = now()
    WHERE id = v_user_id;

    -- 2. Upsert public.profiles role to ADMIN
    INSERT INTO public.profiles (
        user_id,
        email,
        full_name,
        role,
        account_status,
        is_active,
        terms_accepted,
        updated_at
    )
    VALUES (
        v_user_id,
        LOWER(TRIM(p_email)),
        'System Administrator',
        'ADMIN'::public.user_role,
        'ACTIVE'::public.account_status,
        true,
        true,
        now()
    )
    ON CONFLICT (user_id) DO UPDATE SET
        email = LOWER(TRIM(p_email)),
        role = 'ADMIN'::public.user_role,
        account_status = 'ACTIVE'::public.account_status,
        is_active = true,
        terms_accepted = true,
        updated_at = now();

    -- 3. Upsert public.user_access to UNLIMITED
    INSERT INTO public.user_access (
        user_id,
        access_type,
        daily_page_limit,
        unlimited,
        notes,
        updated_at
    )
    VALUES (
        v_user_id,
        'UNLIMITED'::public.access_tier,
        999999,
        true,
        'Authoritative System Administrator Entitlement',
        now()
    )
    ON CONFLICT (user_id) DO UPDATE SET
        access_type = 'UNLIMITED'::public.access_tier,
        unlimited = true,
        notes = 'Authoritative System Administrator Entitlement',
        updated_at = now();

    -- 4. Audit Log entry
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'audit_logs') THEN
        INSERT INTO public.audit_logs (admin_user_id, admin_email, action, target, target_id, metadata)
        VALUES (
            v_user_id,
            LOWER(TRIM(p_email)),
            'ADMIN_ROLE_PROMOTED',
            LOWER(TRIM(p_email)),
            v_user_id::TEXT,
            jsonb_build_object('role', 'ADMIN', 'unlimited', true, 'timestamp', now())
        );
    END IF;

    RETURN FORMAT('Success: User %s (%s) has been promoted to ADMIN with UNLIMITED access.', p_email, v_user_id);
END;
$$;

-- ============================================================================
-- 2. PROMOTION EXECUTION EXAMPLE
-- Run this function in Supabase SQL Editor to promote admin@tallyxml.in
-- ============================================================================
SELECT public.promote_user_to_admin('admin@tallyxml.in');

-- ============================================================================
-- 3. VERIFICATION QUERY
-- Run this query to inspect all users with ADMIN or SUPER_ADMIN privileges.
-- ============================================================================
SELECT 
    p.user_id,
    p.full_name,
    p.email,
    p.role,
    ua.unlimited,
    ua.access_type,
    p.created_at
FROM public.profiles p
LEFT JOIN public.user_access ua ON ua.user_id = p.user_id
WHERE p.role IN ('ADMIN', 'SUPER_ADMIN')
ORDER BY p.created_at DESC;
