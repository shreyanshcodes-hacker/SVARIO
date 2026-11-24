-- ============================================================================
-- SVARIO — WHITE-LABEL BOOKING WEBSITE ENGINE (STAGE 2: TEMPLATES & PUBLIC RPC)
-- Migration: 20261124000009_stage8_booking_website_templates_and_public_rpc.sql
-- Purpose:
--   1. Add `template_id` column (default 'luxe_studio') with strict CHECK
--      constraint limiting values to the 8 approved salon website templates.
--   2. Add strict regex CHECK constraint `chk_booking_website_configs_asset_paths`
--      ensuring `logo_path` and `cover_image_path` strictly match
--      `<organization_id>/<business_id>/(logo|cover)-<12hex>.(png|jpg|webp)`
--      with zero nested paths or path traversal.
--   3. Add hardened SECURITY DEFINER RPC `public.is_booking_website_slug_taken`
--      (SET search_path = '', authenticated only) verifying caller org membership
--      before honoring `p_exclude_business_id` (prevents cross-tenant oracle probing).
--   4. Add hardened SECURITY DEFINER RPC `public.get_published_booking_website_by_slug`
--      (SET search_path = '') returning ONLY strictly allowlisted public fields
--      (`has_logo`, `has_cover` booleans — NEVER raw storage paths or tenant UUIDs)
--      with safe scalar assistant variables (no unassigned RECORD crash).
--   5. Add service-role-only SECURITY DEFINER RPC `public.get_published_brand_asset_path`
--      (SET search_path = '', GRANT EXECUTE TO service_role ONLY) so FastAPI's
--      private-Storage proxy resolves verified published asset paths server-side
--      with ZERO anonymous policies on `storage.objects`.
-- ============================================================================

BEGIN;

-- 1. Additive `template_id` column + strict template & asset-path CHECK constraints
ALTER TABLE public.booking_website_configs
    ADD COLUMN IF NOT EXISTS template_id TEXT NOT NULL DEFAULT 'luxe_studio';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_constraint
        WHERE conname = 'chk_booking_website_configs_template_id'
          AND conrelid = 'public.booking_website_configs'::regclass
    ) THEN
        ALTER TABLE public.booking_website_configs
            ADD CONSTRAINT chk_booking_website_configs_template_id
            CHECK (
                template_id IN (
                    'luxe_studio',
                    'minimal_elegance',
                    'blush_beauty',
                    'noir_salon',
                    'organic_glow',
                    'urban_chic',
                    'editorial_pro',
                    'classic_beauty'
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_constraint
        WHERE conname = 'chk_booking_website_configs_asset_paths'
          AND conrelid = 'public.booking_website_configs'::regclass
    ) THEN
        ALTER TABLE public.booking_website_configs
            ADD CONSTRAINT chk_booking_website_configs_asset_paths
            CHECK (
                (
                    logo_path IS NULL
                    OR logo_path ~ ('^' || organization_id::text || '/' || business_id::text || '/logo-[0-9a-f]{12}\.(png|jpg|webp)$')
                )
                AND (
                    cover_image_path IS NULL
                    OR cover_image_path ~ ('^' || organization_id::text || '/' || business_id::text || '/cover-[0-9a-f]{12}\.(png|jpg|webp)$')
                )
            );
    END IF;
END $$;

-- 2. Guarantee ZERO anonymous SELECT policies exist on private `salon-brand-assets` bucket
DROP POLICY IF EXISTS salon_brand_assets_select_published_anon ON storage.objects;
DROP FUNCTION IF EXISTS public.is_published_brand_asset(TEXT);

-- 3. Hardened cross-tenant boolean slug check (authenticated members only; no oracle probing)
CREATE OR REPLACE FUNCTION public.is_booking_website_slug_taken(
    p_slug TEXT,
    p_exclude_business_id UUID DEFAULT NULL
)
RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_clean_slug TEXT;
    v_verified_exclude_business_id UUID := NULL;
BEGIN
    v_clean_slug := pg_catalog.lower(pg_catalog.btrim(coalesce(p_slug, '')));
    IF v_clean_slug = ''
       OR pg_catalog.char_length(v_clean_slug) < 3
       OR pg_catalog.char_length(v_clean_slug) > 64
       OR v_clean_slug !~ '^[a-z0-9]+(?:-[a-z0-9]+)*$' THEN
        RETURN TRUE;
    END IF;

    -- Only honor p_exclude_business_id if the authenticated caller is a verified member of its org
    IF p_exclude_business_id IS NOT NULL THEN
        SELECT b.id
        INTO v_verified_exclude_business_id
        FROM public.businesses b
        WHERE b.id = p_exclude_business_id
          AND public.is_org_member(b.organization_id)
        LIMIT 1;
    END IF;

    RETURN EXISTS (
        SELECT 1
        FROM public.booking_website_configs w
        WHERE pg_catalog.lower(w.slug) = v_clean_slug
          AND (
              v_verified_exclude_business_id IS NULL
              OR w.business_id <> v_verified_exclude_business_id
          )
    );
END;
$$;

REVOKE ALL ON FUNCTION public.is_booking_website_slug_taken(TEXT, UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.is_booking_website_slug_taken(TEXT, UUID) FROM anon;
GRANT EXECUTE ON FUNCTION public.is_booking_website_slug_taken(TEXT, UUID) TO authenticated, service_role;

-- 4. Strictly allowlisted public slug resolver RPC (ZERO raw storage paths or tenant UUIDs)
CREATE OR REPLACE FUNCTION public.get_published_booking_website_by_slug(p_slug TEXT)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_clean_slug TEXT;
    v_config RECORD;
    v_profile RECORD;
    v_assistant_enabled BOOLEAN := FALSE;
    v_assistant_name TEXT := NULL;
    v_assistant_greeting TEXT := NULL;
    v_hours JSONB := '[]'::jsonb;
    v_services JSONB := '[]'::jsonb;
BEGIN
    v_clean_slug := pg_catalog.lower(pg_catalog.btrim(coalesce(p_slug, '')));
    IF v_clean_slug = ''
       OR pg_catalog.char_length(v_clean_slug) < 3
       OR pg_catalog.char_length(v_clean_slug) > 64
       OR v_clean_slug !~ '^[a-z0-9]+(?:-[a-z0-9]+)*$' THEN
        RETURN NULL;
    END IF;

    SELECT
        w.slug,
        w.template_id,
        w.published_at,
        w.headline,
        w.tagline,
        (w.logo_path IS NOT NULL) AS has_logo,
        (w.cover_image_path IS NOT NULL) AS has_cover,
        w.primary_color,
        w.secondary_color,
        w.accent_color,
        w.background_color,
        w.text_color,
        w.theme,
        w.font_family,
        w.button_style,
        w.social_instagram,
        w.social_facebook,
        w.social_whatsapp,
        w.show_services,
        w.show_hours,
        w.show_ai_receptionist,
        w.organization_id,
        w.business_id
    INTO v_config
    FROM public.booking_website_configs w
    JOIN public.businesses b
      ON b.id = w.business_id
     AND b.organization_id = w.organization_id
    JOIN public.organizations o
      ON o.id = w.organization_id
    WHERE pg_catalog.lower(w.slug) = v_clean_slug
      AND w.status = 'published'
      AND o.industry = 'salon'
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    SELECT
        bp.display_name,
        bp.description,
        bp.phone,
        bp.email,
        bp.address,
        bp.city,
        bp.state,
        bp.country,
        bp.timezone
    INTO v_profile
    FROM public.business_profiles bp
    WHERE bp.business_id = v_config.business_id
      AND bp.organization_id = v_config.organization_id
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    IF v_config.show_hours THEN
        SELECT coalesce(
            pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_object(
                    'weekday', bh.weekday,
                    'is_closed', bh.is_closed,
                    'opens_at', CASE WHEN bh.opens_at IS NOT NULL THEN pg_catalog.to_char(bh.opens_at, 'HH24:MI') ELSE NULL END,
                    'closes_at', CASE WHEN bh.closes_at IS NOT NULL THEN pg_catalog.to_char(bh.closes_at, 'HH24:MI') ELSE NULL END,
                    'is_overnight', bh.is_overnight
                )
                ORDER BY bh.weekday ASC
            ),
            '[]'::jsonb
        )
        INTO v_hours
        FROM public.business_hours bh
        WHERE bh.business_id = v_config.business_id
          AND bh.organization_id = v_config.organization_id;
    END IF;

    IF v_config.show_services THEN
        SELECT coalesce(
            pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_object(
                    'id', s.id,
                    'name', s.name,
                    'category', s.category,
                    'description', s.description,
                    'duration_minutes', s.duration_minutes,
                    'price', s.price,
                    'currency', s.currency
                )
                ORDER BY coalesce(s.category, ''), s.name ASC
            ),
            '[]'::jsonb
        )
        INTO v_services
        FROM public.salon_services s
        WHERE s.business_id = v_config.business_id
          AND s.organization_id = v_config.organization_id
          AND s.is_active = TRUE;
    END IF;

    SELECT
        coalesce(a.enabled, FALSE),
        a.assistant_name,
        a.greeting
    INTO v_assistant_enabled, v_assistant_name, v_assistant_greeting
    FROM public.assistant_settings a
    WHERE a.business_id = v_config.business_id
      AND a.organization_id = v_config.organization_id
    LIMIT 1;

    IF NOT FOUND THEN
        v_assistant_enabled := FALSE;
        v_assistant_name := NULL;
        v_assistant_greeting := NULL;
    END IF;

    RETURN pg_catalog.jsonb_build_object(
        'slug', v_config.slug,
        'template_id', v_config.template_id,
        'published_at', v_config.published_at,
        'headline', v_config.headline,
        'tagline', v_config.tagline,
        'has_logo', v_config.has_logo,
        'has_cover', v_config.has_cover,
        'primary_color', v_config.primary_color,
        'secondary_color', v_config.secondary_color,
        'accent_color', v_config.accent_color,
        'background_color', v_config.background_color,
        'text_color', v_config.text_color,
        'theme', v_config.theme,
        'font_family', v_config.font_family,
        'button_style', v_config.button_style,
        'social_instagram', v_config.social_instagram,
        'social_facebook', v_config.social_facebook,
        'social_whatsapp', v_config.social_whatsapp,
        'show_services', v_config.show_services,
        'show_hours', v_config.show_hours,
        'show_ai_receptionist', v_config.show_ai_receptionist,
        'business', pg_catalog.jsonb_build_object(
            'display_name', v_profile.display_name,
            'description', v_profile.description,
            'phone', v_profile.phone,
            'email', v_profile.email,
            'address', v_profile.address,
            'city', v_profile.city,
            'state', v_profile.state,
            'country', v_profile.country,
            'timezone', v_profile.timezone
        ),
        'hours', v_hours,
        'services', v_services,
        'receptionist', pg_catalog.jsonb_build_object(
            'enabled', (v_config.show_ai_receptionist AND v_assistant_enabled),
            'assistant_name', CASE
                WHEN v_config.show_ai_receptionist AND v_assistant_enabled
                THEN v_assistant_name
                ELSE NULL
            END,
            'greeting', CASE
                WHEN v_config.show_ai_receptionist AND v_assistant_enabled
                THEN v_assistant_greeting
                ELSE NULL
            END
        )
    );
END;
$$;

REVOKE ALL ON FUNCTION public.get_published_booking_website_by_slug(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_published_booking_website_by_slug(TEXT) TO anon, authenticated, service_role;

-- 5. Service-role-ONLY helper to resolve a published salon's verified private Storage asset path
CREATE OR REPLACE FUNCTION public.get_published_brand_asset_path(
    p_slug TEXT,
    p_asset_type TEXT
)
RETURNS TEXT
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_clean_slug TEXT;
    v_clean_type TEXT;
    v_org_id UUID;
    v_biz_id UUID;
    v_path TEXT;
BEGIN
    v_clean_slug := pg_catalog.lower(pg_catalog.btrim(coalesce(p_slug, '')));
    v_clean_type := pg_catalog.lower(pg_catalog.btrim(coalesce(p_asset_type, '')));

    IF v_clean_type NOT IN ('logo', 'cover') THEN
        RETURN NULL;
    END IF;

    IF v_clean_slug = ''
       OR pg_catalog.char_length(v_clean_slug) < 3
       OR pg_catalog.char_length(v_clean_slug) > 64
       OR v_clean_slug !~ '^[a-z0-9]+(?:-[a-z0-9]+)*$' THEN
        RETURN NULL;
    END IF;

    SELECT
        w.organization_id,
        w.business_id,
        CASE WHEN v_clean_type = 'logo' THEN w.logo_path ELSE w.cover_image_path END
    INTO v_org_id, v_biz_id, v_path
    FROM public.booking_website_configs w
    JOIN public.businesses b
      ON b.id = w.business_id
     AND b.organization_id = w.organization_id
    JOIN public.organizations o
      ON o.id = w.organization_id
    WHERE pg_catalog.lower(w.slug) = v_clean_slug
      AND w.status = 'published'
      AND o.industry = 'salon'
    LIMIT 1;

    IF NOT FOUND OR v_path IS NULL THEN
        RETURN NULL;
    END IF;

    -- Defense-in-depth: strictly verify path matches <org_id>/<biz_id>/(logo|cover)-<12hex>.(png|jpg|webp)
    IF v_path !~ ('^' || v_org_id::text || '/' || v_biz_id::text || '/' || v_clean_type || '-[0-9a-f]{12}\.(png|jpg|webp)$') THEN
        RETURN NULL;
    END IF;

    RETURN v_path;
END;
$$;

REVOKE ALL ON FUNCTION public.get_published_brand_asset_path(TEXT, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.get_published_brand_asset_path(TEXT, TEXT) FROM anon;
REVOKE ALL ON FUNCTION public.get_published_brand_asset_path(TEXT, TEXT) FROM authenticated;
GRANT EXECUTE ON FUNCTION public.get_published_brand_asset_path(TEXT, TEXT) TO service_role;

COMMIT;
