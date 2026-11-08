-- ============================================================================
-- SVARIO — STAGE 2: ROW LEVEL SECURITY (RLS) FOR ONBOARDING TABLES
-- Migration: 20261108000004_stage2_onboarding_rls.sql
-- Purpose:
--   Enable and force Row Level Security on all 6 Stage 2 onboarding tables:
--   business_profiles, business_languages, business_faqs,
--   assistant_settings, escalation_settings, and onboarding_progress.
--
-- Security Model:
--   - Reuses hardened Stage 1 non-recursive helpers `public.is_org_member`
--     and `public.has_org_role`.
--   - Organization members (`owner`, `admin`, `staff`) can SELECT records
--     belonging to their organization.
--   - Only `owner` or `admin` can INSERT or UPDATE onboarding & business
--     configuration records (both USING and WITH CHECK enforced).
--   - Only `owner` (or `owner`/`admin` for FAQs & language entries) can DELETE.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- Enable and Force RLS on all 6 Stage 2 tables
-- ----------------------------------------------------------------------------
ALTER TABLE public.business_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.business_profiles FORCE ROW LEVEL SECURITY;

ALTER TABLE public.business_languages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.business_languages FORCE ROW LEVEL SECURITY;

ALTER TABLE public.business_faqs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.business_faqs FORCE ROW LEVEL SECURITY;

ALTER TABLE public.assistant_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assistant_settings FORCE ROW LEVEL SECURITY;

ALTER TABLE public.escalation_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.escalation_settings FORCE ROW LEVEL SECURITY;

ALTER TABLE public.onboarding_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.onboarding_progress FORCE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- 1. Policies for public.business_profiles
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS business_profiles_select_member ON public.business_profiles;
CREATE POLICY business_profiles_select_member
    ON public.business_profiles
    FOR SELECT
    TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS business_profiles_insert_owner_or_admin ON public.business_profiles;
CREATE POLICY business_profiles_insert_owner_or_admin
    ON public.business_profiles
    FOR INSERT
    TO authenticated
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS business_profiles_update_owner_or_admin ON public.business_profiles;
CREATE POLICY business_profiles_update_owner_or_admin
    ON public.business_profiles
    FOR UPDATE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS business_profiles_delete_owner_only ON public.business_profiles;
CREATE POLICY business_profiles_delete_owner_only
    ON public.business_profiles
    FOR DELETE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner']));

-- ----------------------------------------------------------------------------
-- 2. Policies for public.business_languages
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS business_languages_select_member ON public.business_languages;
CREATE POLICY business_languages_select_member
    ON public.business_languages
    FOR SELECT
    TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS business_languages_insert_owner_or_admin ON public.business_languages;
CREATE POLICY business_languages_insert_owner_or_admin
    ON public.business_languages
    FOR INSERT
    TO authenticated
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS business_languages_update_owner_or_admin ON public.business_languages;
CREATE POLICY business_languages_update_owner_or_admin
    ON public.business_languages
    FOR UPDATE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS business_languages_delete_owner_or_admin ON public.business_languages;
CREATE POLICY business_languages_delete_owner_or_admin
    ON public.business_languages
    FOR DELETE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- ----------------------------------------------------------------------------
-- 3. Policies for public.business_faqs
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS business_faqs_select_member ON public.business_faqs;
CREATE POLICY business_faqs_select_member
    ON public.business_faqs
    FOR SELECT
    TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS business_faqs_insert_owner_or_admin ON public.business_faqs;
CREATE POLICY business_faqs_insert_owner_or_admin
    ON public.business_faqs
    FOR INSERT
    TO authenticated
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS business_faqs_update_owner_or_admin ON public.business_faqs;
CREATE POLICY business_faqs_update_owner_or_admin
    ON public.business_faqs
    FOR UPDATE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS business_faqs_delete_owner_or_admin ON public.business_faqs;
CREATE POLICY business_faqs_delete_owner_or_admin
    ON public.business_faqs
    FOR DELETE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- ----------------------------------------------------------------------------
-- 4. Policies for public.assistant_settings
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS assistant_settings_select_member ON public.assistant_settings;
CREATE POLICY assistant_settings_select_member
    ON public.assistant_settings
    FOR SELECT
    TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS assistant_settings_insert_owner_or_admin ON public.assistant_settings;
CREATE POLICY assistant_settings_insert_owner_or_admin
    ON public.assistant_settings
    FOR INSERT
    TO authenticated
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS assistant_settings_update_owner_or_admin ON public.assistant_settings;
CREATE POLICY assistant_settings_update_owner_or_admin
    ON public.assistant_settings
    FOR UPDATE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS assistant_settings_delete_owner_only ON public.assistant_settings;
CREATE POLICY assistant_settings_delete_owner_only
    ON public.assistant_settings
    FOR DELETE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner']));

-- ----------------------------------------------------------------------------
-- 5. Policies for public.escalation_settings
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS escalation_settings_select_member ON public.escalation_settings;
CREATE POLICY escalation_settings_select_member
    ON public.escalation_settings
    FOR SELECT
    TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS escalation_settings_insert_owner_or_admin ON public.escalation_settings;
CREATE POLICY escalation_settings_insert_owner_or_admin
    ON public.escalation_settings
    FOR INSERT
    TO authenticated
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS escalation_settings_update_owner_or_admin ON public.escalation_settings;
CREATE POLICY escalation_settings_update_owner_or_admin
    ON public.escalation_settings
    FOR UPDATE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS escalation_settings_delete_owner_only ON public.escalation_settings;
CREATE POLICY escalation_settings_delete_owner_only
    ON public.escalation_settings
    FOR DELETE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner']));

-- ----------------------------------------------------------------------------
-- 6. Policies for public.onboarding_progress
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS onboarding_progress_select_member ON public.onboarding_progress;
CREATE POLICY onboarding_progress_select_member
    ON public.onboarding_progress
    FOR SELECT
    TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS onboarding_progress_insert_owner_or_admin ON public.onboarding_progress;
CREATE POLICY onboarding_progress_insert_owner_or_admin
    ON public.onboarding_progress
    FOR INSERT
    TO authenticated
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS onboarding_progress_update_owner_or_admin ON public.onboarding_progress;
CREATE POLICY onboarding_progress_update_owner_or_admin
    ON public.onboarding_progress
    FOR UPDATE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS onboarding_progress_delete_owner_only ON public.onboarding_progress;
CREATE POLICY onboarding_progress_delete_owner_only
    ON public.onboarding_progress
    FOR DELETE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner']));

COMMIT;
