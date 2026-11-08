-- ============================================================================
-- SVARIO — STAGE 1: ROW LEVEL SECURITY (RLS) & TENANT ISOLATION POLICIES
-- Migration: 20261103000002_stage1_rls_policies.sql
-- Purpose:
--   Enable and enforce strict Row Level Security on all 7 Stage 1 tables:
--   profiles, organizations, organization_members, businesses,
--   business_settings, business_hours, and audit_logs.
--
-- Security Architecture Notes:
--   1. Helper functions `public.is_org_member` and `public.has_org_role` use
--      SECURITY DEFINER specifically to break potential RLS recursion when
--      evaluating membership on `public.organization_members` and related
--      tables.
--   2. Both functions set a strict `search_path = public, pg_temp`, bind
--      exclusively to `auth.uid()` (never accepting an arbitrary user_id
--      parameter), and have execution revoked from `PUBLIC` and `anon`.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- Enable and Force RLS on all Stage 1 tables
-- ----------------------------------------------------------------------------
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles FORCE ROW LEVEL SECURITY;

ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organizations FORCE ROW LEVEL SECURITY;

ALTER TABLE public.organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization_members FORCE ROW LEVEL SECURITY;

ALTER TABLE public.businesses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.businesses FORCE ROW LEVEL SECURITY;

ALTER TABLE public.business_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.business_settings FORCE ROW LEVEL SECURITY;

ALTER TABLE public.business_hours ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.business_hours FORCE ROW LEVEL SECURITY;

ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs FORCE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- Non-recursive SECURITY DEFINER Membership Helper Functions
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.is_org_member(target_org_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.organization_members AS om
        WHERE om.organization_id = target_org_id
          AND om.user_id = auth.uid()
    );
$$;

REVOKE ALL ON FUNCTION public.is_org_member(UUID) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.is_org_member(UUID) TO authenticated;

CREATE OR REPLACE FUNCTION public.has_org_role(target_org_id UUID, allowed_roles TEXT[])
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.organization_members AS om
        WHERE om.organization_id = target_org_id
          AND om.user_id = auth.uid()
          AND om.role = ANY(allowed_roles)
    );
$$;

REVOKE ALL ON FUNCTION public.has_org_role(UUID, TEXT[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.has_org_role(UUID, TEXT[]) TO authenticated;

-- Helper to check whether an organization currently has any members (used only
-- during initial creator->owner bootstrap so no user can claim ownership of an
-- already-populated organization).
CREATE OR REPLACE FUNCTION public.organization_has_members(target_org_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.organization_members AS om
        WHERE om.organization_id = target_org_id
    );
$$;

REVOKE ALL ON FUNCTION public.organization_has_members(UUID) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.organization_has_members(UUID) TO authenticated;

-- ----------------------------------------------------------------------------
-- 1. Policies for public.profiles
--    - Users can read, insert, and update only their own profile (id = auth.uid()).
--    - Anonymous users have no access.
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS profiles_select_own ON public.profiles;
CREATE POLICY profiles_select_own
    ON public.profiles
    FOR SELECT
    TO authenticated
    USING (id = auth.uid());

DROP POLICY IF EXISTS profiles_insert_own ON public.profiles;
CREATE POLICY profiles_insert_own
    ON public.profiles
    FOR INSERT
    TO authenticated
    WITH CHECK (id = auth.uid());

DROP POLICY IF EXISTS profiles_update_own ON public.profiles;
CREATE POLICY profiles_update_own
    ON public.profiles
    FOR UPDATE
    TO authenticated
    USING (id = auth.uid())
    WITH CHECK (id = auth.uid());

-- ----------------------------------------------------------------------------
-- 2. Policies for public.organizations
--    - Members can read organizations they belong to.
--    - Authenticated users can create a new organization.
--    - Only owners or admins can update organization metadata.
--    - Only owners can delete an organization.
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS organizations_select_member ON public.organizations;
CREATE POLICY organizations_select_member
    ON public.organizations
    FOR SELECT
    TO authenticated
    USING (public.is_org_member(id));

DROP POLICY IF EXISTS organizations_insert_authenticated ON public.organizations;
CREATE POLICY organizations_insert_authenticated
    ON public.organizations
    FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() IS NOT NULL);

DROP POLICY IF EXISTS organizations_update_owner_or_admin ON public.organizations;
CREATE POLICY organizations_update_owner_or_admin
    ON public.organizations
    FOR UPDATE
    TO authenticated
    USING (public.has_org_role(id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS organizations_delete_owner_only ON public.organizations;
CREATE POLICY organizations_delete_owner_only
    ON public.organizations
    FOR DELETE
    TO authenticated
    USING (public.has_org_role(id, ARRAY['owner']));

-- ----------------------------------------------------------------------------
-- 3. Policies for public.organization_members
--    - Users can read their own memberships OR memberships in organizations
--      where they are a verified member.
--    - INSERT allowed when:
--        (a) Creator bootstrapping the very first 'owner' membership for a
--            newly created organization (user_id = auth.uid() AND role = 'owner'
--            AND NOT public.organization_has_members(organization_id)), OR
--        (b) Existing 'owner' adding a member of any valid role, OR
--        (c) Existing 'admin' adding a 'staff' member only (cannot add owners/admins).
--    - UPDATE and DELETE restricted strictly to organization 'owner' role
--      (staff and admins cannot promote themselves to owner).
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS organization_members_select_self_or_org ON public.organization_members;
CREATE POLICY organization_members_select_self_or_org
    ON public.organization_members
    FOR SELECT
    TO authenticated
    USING (
        user_id = auth.uid()
        OR public.is_org_member(organization_id)
    );

DROP POLICY IF EXISTS organization_members_insert_authorized ON public.organization_members;
CREATE POLICY organization_members_insert_authorized
    ON public.organization_members
    FOR INSERT
    TO authenticated
    WITH CHECK (
        (
            user_id = auth.uid()
            AND role = 'owner'
            AND NOT public.organization_has_members(organization_id)
        )
        OR public.has_org_role(organization_id, ARRAY['owner'])
        OR (
            public.has_org_role(organization_id, ARRAY['admin'])
            AND role = 'staff'
        )
    );

DROP POLICY IF EXISTS organization_members_update_owner_only ON public.organization_members;
CREATE POLICY organization_members_update_owner_only
    ON public.organization_members
    FOR UPDATE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner']));

DROP POLICY IF EXISTS organization_members_delete_owner_only ON public.organization_members;
CREATE POLICY organization_members_delete_owner_only
    ON public.organization_members
    FOR DELETE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner']));

-- ----------------------------------------------------------------------------
-- 4. Policies for public.businesses
--    - Any organization member can read businesses in their organization.
--    - Only owner/admin can create or update businesses.
--    - Only owner can delete businesses.
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS businesses_select_member ON public.businesses;
CREATE POLICY businesses_select_member
    ON public.businesses
    FOR SELECT
    TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS businesses_insert_owner_or_admin ON public.businesses;
CREATE POLICY businesses_insert_owner_or_admin
    ON public.businesses
    FOR INSERT
    TO authenticated
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS businesses_update_owner_or_admin ON public.businesses;
CREATE POLICY businesses_update_owner_or_admin
    ON public.businesses
    FOR UPDATE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS businesses_delete_owner_only ON public.businesses;
CREATE POLICY businesses_delete_owner_only
    ON public.businesses
    FOR DELETE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner']));

-- ----------------------------------------------------------------------------
-- 5. Policies for public.business_settings
--    - Any organization member can read business_settings in their organization.
--    - Only owner/admin can create or update business_settings.
--    - Only owner can delete business_settings.
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS business_settings_select_member ON public.business_settings;
CREATE POLICY business_settings_select_member
    ON public.business_settings
    FOR SELECT
    TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS business_settings_insert_owner_or_admin ON public.business_settings;
CREATE POLICY business_settings_insert_owner_or_admin
    ON public.business_settings
    FOR INSERT
    TO authenticated
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS business_settings_update_owner_or_admin ON public.business_settings;
CREATE POLICY business_settings_update_owner_or_admin
    ON public.business_settings
    FOR UPDATE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS business_settings_delete_owner_only ON public.business_settings;
CREATE POLICY business_settings_delete_owner_only
    ON public.business_settings
    FOR DELETE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner']));

-- ----------------------------------------------------------------------------
-- 6. Policies for public.business_hours
--    - Any organization member can read business_hours in their organization.
--    - Only owner/admin can create or update business_hours.
--    - Only owner can delete business_hours.
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS business_hours_select_member ON public.business_hours;
CREATE POLICY business_hours_select_member
    ON public.business_hours
    FOR SELECT
    TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS business_hours_insert_owner_or_admin ON public.business_hours;
CREATE POLICY business_hours_insert_owner_or_admin
    ON public.business_hours
    FOR INSERT
    TO authenticated
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS business_hours_update_owner_or_admin ON public.business_hours;
CREATE POLICY business_hours_update_owner_or_admin
    ON public.business_hours
    FOR UPDATE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS business_hours_delete_owner_only ON public.business_hours;
CREATE POLICY business_hours_delete_owner_only
    ON public.business_hours
    FOR DELETE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner']));

-- ----------------------------------------------------------------------------
-- 7. Policies for public.audit_logs
--    - Only owner/admin of the organization can read organization audit logs.
--    - Authenticated users can insert audit log entries only where they are
--      the actor (actor_user_id = auth.uid()) and belong to the organization.
--    - Audit logs are append-only (no UPDATE or DELETE policies).
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS audit_logs_select_owner_or_admin ON public.audit_logs;
CREATE POLICY audit_logs_select_owner_or_admin
    ON public.audit_logs
    FOR SELECT
    TO authenticated
    USING (
        organization_id IS NOT NULL
        AND public.has_org_role(organization_id, ARRAY['owner', 'admin'])
    );

DROP POLICY IF EXISTS audit_logs_insert_authenticated_actor ON public.audit_logs;
CREATE POLICY audit_logs_insert_authenticated_actor
    ON public.audit_logs
    FOR INSERT
    TO authenticated
    WITH CHECK (
        actor_user_id = auth.uid()
        AND (
            organization_id IS NULL
            OR public.is_org_member(organization_id)
        )
    );

COMMIT;
