-- ============================================================================
-- SVARIO — STAGE 1: CORE DATA, MULTI-TENANT AUTH & ORGANIZATION FOUNDATION
-- Migration: 20261103000001_stage1_core_schema.sql
-- Purpose: Establish profiles, organizations, organization_members,
--          businesses, business_settings, business_hours, and audit_logs.
-- Security Note:
--   - Passwords are NEVER stored in application tables (managed by Supabase Auth).
--   - Patient medical histories / clinical records are NEVER stored here.
--   - Raw voice audio recordings are NEVER stored here.
-- ============================================================================

BEGIN;

-- Ensure pgcrypto is available for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ----------------------------------------------------------------------------
-- Shared Trigger Function: Automatically maintain updated_at timestamps
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
    NEW.updated_at = timezone('utc', now());
    RETURN NEW;
END;
$$;

-- ----------------------------------------------------------------------------
-- 1. profiles
--    1:1 profile linked to auth.users(id).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL DEFAULT '',
    avatar_url TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

DROP TRIGGER IF EXISTS trg_profiles_set_updated_at ON public.profiles;
CREATE TRIGGER trg_profiles_set_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- Automatically provision a profile row whenever a new user signs up in auth.users.
-- SECURITY DEFINER is required because auth.users triggers execute in the auth context
-- and need controlled permission to insert into public.profiles.
CREATE OR REPLACE FUNCTION public.handle_new_auth_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    INSERT INTO public.profiles (id, full_name, avatar_url)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data ->> 'full_name', ''),
        NEW.raw_user_meta_data ->> 'avatar_url'
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION public.handle_new_auth_user() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS trg_on_auth_user_created ON auth.users;
CREATE TRIGGER trg_on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_auth_user();

-- ----------------------------------------------------------------------------
-- 2. organizations
--    Multi-tenant root entity. A user may belong to multiple organizations.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    industry TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT chk_organizations_name_len
        CHECK (char_length(btrim(name)) BETWEEN 2 AND 120),
    CONSTRAINT chk_organizations_slug_format
        CHECK (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$' AND char_length(slug) BETWEEN 2 AND 80),
    CONSTRAINT chk_organizations_industry
        CHECK (industry IN ('salon', 'clinic', 'hospital'))
);

CREATE INDEX IF NOT EXISTS idx_organizations_industry
    ON public.organizations (industry);

DROP TRIGGER IF EXISTS trg_organizations_set_updated_at ON public.organizations;
CREATE TRIGGER trg_organizations_set_updated_at
    BEFORE UPDATE ON public.organizations
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 3. organization_members
--    Many-to-many join between organizations and profiles with role RBAC.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.organization_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_organization_members_org_user
        UNIQUE (organization_id, user_id),
    CONSTRAINT chk_organization_members_role
        CHECK (role IN ('owner', 'admin', 'staff'))
);

CREATE INDEX IF NOT EXISTS idx_organization_members_user_id
    ON public.organization_members (user_id);

CREATE INDEX IF NOT EXISTS idx_organization_members_org_role
    ON public.organization_members (organization_id, role);

-- ----------------------------------------------------------------------------
-- 4. businesses
--    Operational business unit belonging to an organization.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.businesses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NULL,
    phone TEXT NULL,
    email TEXT NULL,
    address TEXT NULL,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT chk_businesses_name_len
        CHECK (char_length(btrim(name)) BETWEEN 2 AND 120),
    CONSTRAINT chk_businesses_timezone_nonempty
        CHECK (char_length(btrim(timezone)) >= 2),
    -- Composite unique key enables child tables to enforce same-organization integrity
    CONSTRAINT uq_businesses_id_organization_id
        UNIQUE (id, organization_id)
);

CREATE INDEX IF NOT EXISTS idx_businesses_organization_id
    ON public.businesses (organization_id);

DROP TRIGGER IF EXISTS trg_businesses_set_updated_at ON public.businesses;
CREATE TRIGGER trg_businesses_set_updated_at
    BEFORE UPDATE ON public.businesses
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 5. business_settings
--    Per-business language and AI assistant toggle configuration.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.business_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    default_language TEXT NOT NULL DEFAULT 'en',
    supported_languages TEXT[] NOT NULL DEFAULT ARRAY['en']::TEXT[],
    assistant_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_business_settings_business_id
        UNIQUE (business_id),
    CONSTRAINT fk_business_settings_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_business_settings_default_language
        CHECK (char_length(btrim(default_language)) BETWEEN 2 AND 16),
    CONSTRAINT chk_business_settings_supported_languages
        CHECK (cardinality(supported_languages) >= 1)
);

CREATE INDEX IF NOT EXISTS idx_business_settings_org_business
    ON public.business_settings (organization_id, business_id);

DROP TRIGGER IF EXISTS trg_business_settings_set_updated_at ON public.business_settings;
CREATE TRIGGER trg_business_settings_set_updated_at
    BEFORE UPDATE ON public.business_settings
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 6. business_hours
--    Weekly operating hours (0 = Sunday .. 6 = Saturday) for a business.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.business_hours (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    weekday SMALLINT NOT NULL,
    opens_at TIME NULL,
    closes_at TIME NULL,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT chk_business_hours_weekday
        CHECK (weekday BETWEEN 0 AND 6),
    CONSTRAINT uq_business_hours_business_weekday
        UNIQUE (business_id, weekday),
    CONSTRAINT fk_business_hours_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_business_hours_open_close_consistency
        CHECK (
            is_closed = TRUE
            OR (opens_at IS NOT NULL AND closes_at IS NOT NULL AND opens_at < closes_at)
        )
);

CREATE INDEX IF NOT EXISTS idx_business_hours_org_business
    ON public.business_hours (organization_id, business_id);

DROP TRIGGER IF EXISTS trg_business_hours_set_updated_at ON public.business_hours;
CREATE TRIGGER trg_business_hours_set_updated_at
    BEFORE UPDATE ON public.business_hours
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 7. audit_logs
--    Immutable security and administrative event log.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NULL REFERENCES public.organizations(id) ON DELETE SET NULL,
    actor_user_id UUID NULL REFERENCES public.profiles(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id UUID NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT chk_audit_logs_action_nonempty
        CHECK (char_length(btrim(action)) >= 2),
    CONSTRAINT chk_audit_logs_resource_type_nonempty
        CHECK (char_length(btrim(resource_type)) >= 2)
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_org_created_at
    ON public.audit_logs (organization_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_created_at
    ON public.audit_logs (actor_user_id, created_at DESC);

COMMIT;
