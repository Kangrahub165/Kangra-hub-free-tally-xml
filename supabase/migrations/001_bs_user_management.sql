-- ==============================================================================
-- Kangra Hub Bank Statement to Tally XML - User Management & Storage Migration
-- Prefix: bs_ (Zero overlap or clash with Sales / Purchase project)
-- ==============================================================================

-- 1. Roles Enum (Idempotent creation)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'bs_role') THEN
        CREATE TYPE bs_role AS ENUM ('super_admin', 'admin', 'user');
    END IF;
END $$;

-- 2. User Profiles (Linked to Supabase auth.users)
CREATE TABLE IF NOT EXISTS bs_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    phone TEXT,
    company TEXT,
    role bs_role NOT NULL DEFAULT 'user',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('pending', 'active', 'suspended', 'deleted')),
    plan TEXT NOT NULL DEFAULT 'free',
    daily_limit INT NOT NULL DEFAULT 50,
    monthly_limit INT NOT NULL DEFAULT 1500,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS bs_profiles_email_idx ON bs_profiles (email);
CREATE INDEX IF NOT EXISTS bs_profiles_role_idx ON bs_profiles (role);
CREATE INDEX IF NOT EXISTS bs_profiles_status_idx ON bs_profiles (status);

-- 3. Conversion History (one row per statement upload)
CREATE TABLE IF NOT EXISTS bs_conversions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES bs_profiles(id) ON DELETE SET NULL,
    file_name TEXT,
    file_type TEXT CHECK (file_type IN ('pdf', 'jpg', 'jpeg')),
    pages INT DEFAULT 1,
    rows_extracted INT DEFAULT 0,
    engine TEXT DEFAULT 'gemini',
    status TEXT NOT NULL DEFAULT 'processing' CHECK (status IN ('processing', 'success', 'failed')),
    error_message TEXT,
    tokens_used INT DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS bs_conversions_user_idx ON bs_conversions (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS bs_conversions_status_idx ON bs_conversions (status);

-- 4. Audit Log (Read-only security & admin action tracking)
CREATE TABLE IF NOT EXISTS bs_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID REFERENCES bs_profiles(id) ON DELETE SET NULL,
    target_user_id UUID REFERENCES bs_profiles(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    details JSONB,
    ip_address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS bs_audit_logs_actor_idx ON bs_audit_logs (actor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS bs_audit_logs_action_idx ON bs_audit_logs (action);

-- 5. Login History (Audit sessions & security tracking)
CREATE TABLE IF NOT EXISTS bs_login_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES bs_profiles(id) ON DELETE CASCADE,
    ip_address TEXT,
    user_agent TEXT,
    success BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS bs_login_history_user_idx ON bs_login_history (user_id, created_at DESC);

-- 6. Application Settings (Configured by Administrator)
CREATE TABLE IF NOT EXISTS bs_settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_by UUID REFERENCES bs_profiles(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO bs_settings (key, value) VALUES
    ('max_file_mb', '25'::JSONB),
    ('max_image_mb', '10'::JSONB),
    ('allowed_types', '["pdf","jpg","jpeg"]'::JSONB),
    ('signup_open', 'true'::JSONB),
    ('maintenance_mode', 'false'::JSONB),
    ('gemini_enabled', 'true'::JSONB)
ON CONFLICT (key) DO UPDATE
    SET updated_at = NOW();

-- 7. Security Definer Helper: Is current authenticated user an admin?
CREATE OR REPLACE FUNCTION bs_is_admin()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1 FROM bs_profiles
        WHERE id = auth.uid()
          AND role IN ('admin', 'super_admin')
          AND status = 'active'
    );
$$;

-- 8. Auto-create profile trigger on new Supabase Auth signup
CREATE OR REPLACE FUNCTION bs_handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO bs_profiles (id, email, full_name)
    VALUES (
        new.id,
        new.email,
        COALESCE(new.raw_user_meta_data->>'full_name', split_part(new.email, '@', 1))
    )
    ON CONFLICT (id) DO UPDATE
    SET email = EXCLUDED.email,
        full_name = COALESCE(EXCLUDED.full_name, bs_profiles.full_name);
    RETURN new;
END;
$$;

DROP TRIGGER IF EXISTS bs_on_auth_user_created ON auth.users;
CREATE TRIGGER bs_on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION bs_handle_new_user();

-- 9. Auto-touch updated_at trigger
CREATE OR REPLACE FUNCTION bs_touch_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    new.updated_at = NOW();
    RETURN new;
END;
$$;

DROP TRIGGER IF EXISTS bs_profiles_touch ON bs_profiles;
CREATE TRIGGER bs_profiles_touch
    BEFORE UPDATE ON bs_profiles
    FOR EACH ROW
    EXECUTE FUNCTION bs_touch_updated_at();

-- 10. Enable Row Level Security (RLS) on all Bank Statement tables
ALTER TABLE bs_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE bs_conversions ENABLE ROW LEVEL SECURITY;
ALTER TABLE bs_audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE bs_login_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE bs_settings ENABLE ROW LEVEL SECURITY;

-- 11. Row Level Security Policies
-- bs_profiles: Users read their own profile; admins read all
DROP POLICY IF EXISTS bs_profiles_self_read ON bs_profiles;
CREATE POLICY bs_profiles_self_read ON bs_profiles
    FOR SELECT USING (id = auth.uid() OR bs_is_admin());

-- bs_profiles: Users update basic fields only
DROP POLICY IF EXISTS bs_profiles_self_update ON bs_profiles;
CREATE POLICY bs_profiles_self_update ON bs_profiles
    FOR UPDATE USING (id = auth.uid())
    WITH CHECK (id = auth.uid());

-- bs_conversions: Users see their own conversions; admins see all
DROP POLICY IF EXISTS bs_conv_own_read ON bs_conversions;
CREATE POLICY bs_conv_own_read ON bs_conversions
    FOR SELECT USING (user_id = auth.uid() OR bs_is_admin());

-- bs_audit_logs: Only admins can view audit logs
DROP POLICY IF EXISTS bs_audit_admin_read ON bs_audit_logs;
CREATE POLICY bs_audit_admin_read ON bs_audit_logs
    FOR SELECT USING (bs_is_admin());

-- bs_login_history: Users view their own logins; admins view all
DROP POLICY IF EXISTS bs_login_own_read ON bs_login_history;
CREATE POLICY bs_login_own_read ON bs_login_history
    FOR SELECT USING (user_id = auth.uid() OR bs_is_admin());

-- bs_settings: Anyone can read app settings
DROP POLICY IF EXISTS bs_settings_read ON bs_settings;
CREATE POLICY bs_settings_read ON bs_settings
    FOR SELECT USING (TRUE);

-- Revoke dangerous direct updates from browser; only allow safe columns
REVOKE UPDATE ON bs_profiles FROM authenticated;
GRANT UPDATE (full_name, phone, company) ON bs_profiles TO authenticated;

-- Service role bypasses RLS and maintains full administrative rights on Render backend
