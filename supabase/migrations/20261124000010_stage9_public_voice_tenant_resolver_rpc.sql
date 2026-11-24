-- ============================================================================
-- SVARIO — STAGE 3 PUBLIC AI RECEPTIONIST: SERVICE-ROLE TENANT RESOLVER RPC
-- Migration: 20261124000010_stage9_public_voice_tenant_resolver_rpc.sql
-- Purpose:
--   Add a service-role-ONLY SECURITY DEFINER RPC
--   `public.get_published_website_tenant_ids(p_slug TEXT)` so the FastAPI
--   backend can resolve the real `(organization_id, business_id)` of a
--   published salon website strictly server-side for live availability checks
--   and appointment persistence — without EVER exposing tenant UUIDs to `anon`,
--   `authenticated`, or browser clients.
-- ============================================================================

BEGIN;

CREATE OR REPLACE FUNCTION public.get_published_website_tenant_ids(p_slug TEXT)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_clean_slug TEXT;
    v_org_id UUID;
    v_biz_id UUID;
BEGIN
    v_clean_slug := pg_catalog.lower(pg_catalog.btrim(coalesce(p_slug, '')));
    IF v_clean_slug = ''
       OR pg_catalog.char_length(v_clean_slug) < 3
       OR pg_catalog.char_length(v_clean_slug) > 64
       OR v_clean_slug !~ '^[a-z0-9]+(?:-[a-z0-9]+)*$' THEN
        RETURN NULL;
    END IF;

    SELECT w.organization_id, w.business_id
    INTO v_org_id, v_biz_id
    FROM public.booking_website_configs w
    JOIN public.businesses b
      ON b.id = w.business_id
     AND b.organization_id = w.organization_id
    JOIN public.organizations o
      ON o.id = w.organization_id
    WHERE pg_catalog.lower(w.slug) = v_clean_slug
      AND w.status = 'published'
      AND w.show_ai_receptionist = TRUE
      AND o.industry = 'salon'
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    RETURN pg_catalog.jsonb_build_object(
        'organization_id', v_org_id,
        'business_id', v_biz_id
    );
END;
$$;

REVOKE ALL ON FUNCTION public.get_published_website_tenant_ids(TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.get_published_website_tenant_ids(TEXT) FROM anon;
REVOKE ALL ON FUNCTION public.get_published_website_tenant_ids(TEXT) FROM authenticated;
GRANT EXECUTE ON FUNCTION public.get_published_website_tenant_ids(TEXT) TO service_role;

COMMIT;
