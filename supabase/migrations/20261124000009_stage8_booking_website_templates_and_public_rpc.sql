-- ============================================================================
-- SVARIO — WHITE-LABEL BOOKING WEBSITE ENGINE (STAGE 2: TEMPLATES & PUBLIC RPC)
-- Migration: 20261124000009_stage8_booking_website_templates_and_public_rpc.sql
-- Purpose:
--   1. Add `template_id` column (default 'luxe_studio') with strict CHECK
--      constraint limiting values to the 8 approved salon website templates.
--   2. Add SECURITY DEFINER RPC `public.get_published_booking_website_by_slug`
--      so unauthenticated visitors can resolve ONLY published salon websites
--      with strictly allowlisted public fields (zero leakage of members,
--      customers, appointments, staff, or internal AI prompts).
--   3. Add SECURITY DEFINER helper `public.is_published_brand_asset` and narrow
--      `anon` SELECT policy on `storage.objects` ONLY for published logo/cover
--      paths while keeping `salon-brand-assets` bucket PRIVATE (public = FALSE).
--   4. Add SECURITY DEFINER helper `public.is_booking_website_slug_taken` for
--      accurate cross-tenant slug availability checks without leaking rows.
-- ============================================================================

BEGIN;

-- 1. Additive `template_id` column on public.booking_website_configs
ALTER TABLE public.booking_website_configs
    ADD COLUMN IF NOT EXISTS template_id TEXT NOT NULL DEFAULT 'luxe_studio';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
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
END $$;

-- 2. Cross-tenant boolean slug availability check (authenticated members only)
CREATE OR REPLACE FUNCTION public.is_booking_website_slug_taken(
    p_slug TEXT,
    p_exclude_business_id UUID DEFAULT NULL
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.booking_website_configs w
        WHERE lower(w.slug) = lower(trim(p_slug))
          AND (p_exclude_business_id IS NULL OR w.business_id <> p_exclude_business_id)
    );
$$;

REVOKE ALL ON FUNCTION public.is_booking_website_slug_taken(TEXT, UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_booking_website_slug_taken(TEXT, UUID) TO authenticated;

-- 3. Narrow helper to check if a storage path belongs to a PUBLISHED website's logo or cover
CREATE OR REPLACE FUNCTION public.is_published_brand_asset(p_storage_path TEXT)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.booking_website_configs w
        JOIN public.organizations o ON o.id = w.organization_id
        WHERE w.status = 'published'
          AND o.industry = 'salon'
          AND p_storage_path IS NOT NULL
          AND (w.logo_path = p_storage_path OR w.cover_image_path = p_storage_path)
    );
$$;

REVOKE ALL ON FUNCTION public.is_published_brand_asset(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_published_brand_asset(TEXT) TO anon, authenticated;

-- Narrow anon SELECT policy on storage.objects ONLY for published logo/cover paths
-- Bucket `salon-brand-assets` remains PRIVATE (public = FALSE).
DROP POLICY IF EXISTS salon_brand_assets_select_published_anon ON storage.objects;
CREATE POLICY salon_brand_assets_select_published_anon
    ON storage.objects FOR SELECT TO anon
    USING (
        bucket_id = 'salon-brand-assets'
        AND public.is_published_brand_asset(name)
    );

-- 4. Strictly allowlisted public slug resolver RPC (returns NULL if unknown/unpublished/non-salon)
CREATE OR REPLACE FUNCTION public.get_published_booking_website_by_slug(p_slug TEXT)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_clean_slug TEXT;
    v_config RECORD;
    v_profile RECORD;
    v_assistant RECORD;
    v_hours JSONB := '[]'::jsonb;
    v_services JSONB := '[]'::jsonb;
BEGIN
    v_clean_slug := lower(trim(coalesce(p_slug, '')));
    IF v_clean_slug = '' OR char_length(v_clean_slug) < 3 OR char_length(v_clean_slug) > 64 THEN
        RETURN NULL;
    END IF;

    SELECT
        w.slug,
        w.template_id,
        w.published_at,
        w.headline,
        w.tagline,
        w.logo_path,
        w.cover_image_path,
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
    WHERE lower(w.slug) = v_clean_slug
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
            jsonb_agg(
                jsonb_build_object(
                    'weekday', bh.weekday,
                    'is_closed', bh.is_closed,
                    'opens_at', CASE WHEN bh.opens_at IS NOT NULL THEN to_char(bh.opens_at, 'HH24:MI') ELSE NULL END,
                    'closes_at', CASE WHEN bh.closes_at IS NOT NULL THEN to_char(bh.closes_at, 'HH24:MI') ELSE NULL END,
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
            jsonb_agg(
                jsonb_build_object(
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
        a.enabled,
        a.assistant_name,
        a.greeting
    INTO v_assistant
    FROM public.assistant_settings a
    WHERE a.business_id = v_config.business_id
      AND a.organization_id = v_config.organization_id
    LIMIT 1;

    RETURN jsonb_build_object(
        'slug', v_config.slug,
        'template_id', v_config.template_id,
        'published_at', v_config.published_at,
        'headline', v_config.headline,
        'tagline', v_config.tagline,
        'logo_path', v_config.logo_path,
        'cover_image_path', v_config.cover_image_path,
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
        'business', jsonb_build_object(
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
        'receptionist', jsonb_build_object(
            'enabled', (v_config.show_ai_receptionist AND coalesce(v_assistant.enabled, FALSE)),
            'assistant_name', CASE
                WHEN v_config.show_ai_receptionist AND coalesce(v_assistant.enabled, FALSE)
                THEN v_assistant.assistant_name
                ELSE NULL
            END,
            'greeting', CASE
                WHEN v_config.show_ai_receptionist AND coalesce(v_assistant.enabled, FALSE)
                THEN v_assistant.greeting
                ELSE NULL
            END
        )
    );
END;
$$;

REVOKE ALL ON FUNCTION public.get_published_booking_website_by_slug(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_published_booking_website_by_slug(TEXT) TO anon, authenticated;

COMMIT;
