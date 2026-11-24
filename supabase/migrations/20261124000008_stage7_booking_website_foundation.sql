-- ============================================================================
-- SVARIO — WHITE-LABEL BOOKING WEBSITE ENGINE (STAGE 1 FOUNDATION)
-- Migration: 20261124000008_stage7_booking_website_foundation.sql
-- Purpose:
--   1. Create public.booking_website_configs (1:1 per salon business) storing
--      slug, publishing status, branding studio settings, and approved public
--      website appearance options (reusing business_profiles, business_hours,
--      business_languages, and assistant_settings without duplicating them).
--   2. Enforce strict tenant isolation via composite FK (business_id, organization_id)
--      -> public.businesses(id, organization_id) and FORCE ROW LEVEL SECURITY.
--   3. Create Supabase Storage bucket `salon-brand-assets` (2 MB max; PNG/JPEG/WEBP)
--      with tenant-scoped owner/admin upload policies.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.booking_website_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    slug TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    published_at TIMESTAMPTZ NULL,
    headline TEXT NULL,
    tagline TEXT NULL,
    logo_path TEXT NULL,
    cover_image_path TEXT NULL,
    primary_color TEXT NOT NULL DEFAULT '#7657F6',
    secondary_color TEXT NOT NULL DEFAULT '#36C6D3',
    accent_color TEXT NOT NULL DEFAULT '#F59E0B',
    background_color TEXT NOT NULL DEFAULT '#0B1020',
    text_color TEXT NOT NULL DEFAULT '#F5F7FC',
    theme TEXT NOT NULL DEFAULT 'dark',
    font_family TEXT NOT NULL DEFAULT 'inter',
    button_style TEXT NOT NULL DEFAULT 'rounded',
    social_instagram TEXT NULL,
    social_facebook TEXT NULL,
    social_whatsapp TEXT NULL,
    show_services BOOLEAN NOT NULL DEFAULT TRUE,
    show_hours BOOLEAN NOT NULL DEFAULT TRUE,
    show_ai_receptionist BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_booking_website_configs_business
        UNIQUE (business_id),
    CONSTRAINT uq_booking_website_configs_slug
        UNIQUE (slug),
    CONSTRAINT fk_booking_website_configs_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_booking_website_configs_slug_format
        CHECK (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$' AND char_length(slug) BETWEEN 3 AND 64),
    CONSTRAINT chk_booking_website_configs_status
        CHECK (status IN ('draft', 'published', 'disabled')),
    CONSTRAINT chk_booking_website_configs_theme
        CHECK (theme IN ('light', 'dark')),
    CONSTRAINT chk_booking_website_configs_font
        CHECK (font_family IN ('inter', 'plus_jakarta_sans', 'dm_sans', 'playfair_display', 'poppins')),
    CONSTRAINT chk_booking_website_configs_button_style
        CHECK (button_style IN ('rounded', 'pill', 'square')),
    CONSTRAINT chk_booking_website_configs_colors
        CHECK (
            primary_color ~ '^#[0-9A-Fa-f]{6}$'
            AND secondary_color ~ '^#[0-9A-Fa-f]{6}$'
            AND accent_color ~ '^#[0-9A-Fa-f]{6}$'
            AND background_color ~ '^#[0-9A-Fa-f]{6}$'
            AND text_color ~ '^#[0-9A-Fa-f]{6}$'
        )
);

CREATE INDEX IF NOT EXISTS idx_booking_website_configs_org_business
    ON public.booking_website_configs (organization_id, business_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_booking_website_configs_slug_lower
    ON public.booking_website_configs (lower(slug));

DROP TRIGGER IF EXISTS trg_booking_website_configs_set_updated_at ON public.booking_website_configs;
CREATE TRIGGER trg_booking_website_configs_set_updated_at
    BEFORE UPDATE ON public.booking_website_configs
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- Enable & Force Row Level Security
ALTER TABLE public.booking_website_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.booking_website_configs FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS booking_website_configs_select_member ON public.booking_website_configs;
CREATE POLICY booking_website_configs_select_member
    ON public.booking_website_configs FOR SELECT TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS booking_website_configs_insert_owner_or_admin ON public.booking_website_configs;
CREATE POLICY booking_website_configs_insert_owner_or_admin
    ON public.booking_website_configs FOR INSERT TO authenticated
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS booking_website_configs_update_owner_or_admin ON public.booking_website_configs;
CREATE POLICY booking_website_configs_update_owner_or_admin
    ON public.booking_website_configs FOR UPDATE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS booking_website_configs_delete_owner_or_admin ON public.booking_website_configs;
CREATE POLICY booking_website_configs_delete_owner_or_admin
    ON public.booking_website_configs FOR DELETE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- Create private tenant-scoped Storage bucket for approved salon brand assets (logos/covers)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'salon-brand-assets',
    'salon-brand-assets',
    FALSE,
    2097152,
    ARRAY['image/png', 'image/jpeg', 'image/webp']
)
ON CONFLICT (id) DO UPDATE
SET
    public = EXCLUDED.public,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;

-- Storage RLS policies: strict path convention `<organization_id>/<business_id>/<filename>`
DROP POLICY IF EXISTS salon_brand_assets_public_read ON storage.objects;
DROP POLICY IF EXISTS salon_brand_assets_select_member ON storage.objects;
CREATE POLICY salon_brand_assets_select_member
    ON storage.objects FOR SELECT TO authenticated
    USING (
        bucket_id = 'salon-brand-assets'
        AND (storage.foldername(name))[1] ~ '^[0-9a-fA-F-]{36}$'
        AND (storage.foldername(name))[2] ~ '^[0-9a-fA-F-]{36}$'
        AND public.is_org_member(((storage.foldername(name))[1])::uuid)
        AND EXISTS (
            SELECT 1 FROM public.businesses b
            WHERE b.id = ((storage.foldername(name))[2])::uuid
              AND b.organization_id = ((storage.foldername(name))[1])::uuid
        )
    );

DROP POLICY IF EXISTS salon_brand_assets_insert_owner_or_admin ON storage.objects;
CREATE POLICY salon_brand_assets_insert_owner_or_admin
    ON storage.objects FOR INSERT TO authenticated
    WITH CHECK (
        bucket_id = 'salon-brand-assets'
        AND (storage.foldername(name))[1] ~ '^[0-9a-fA-F-]{36}$'
        AND (storage.foldername(name))[2] ~ '^[0-9a-fA-F-]{36}$'
        AND public.has_org_role(((storage.foldername(name))[1])::uuid, ARRAY['owner', 'admin'])
        AND EXISTS (
            SELECT 1 FROM public.businesses b
            WHERE b.id = ((storage.foldername(name))[2])::uuid
              AND b.organization_id = ((storage.foldername(name))[1])::uuid
        )
    );

DROP POLICY IF EXISTS salon_brand_assets_update_owner_or_admin ON storage.objects;
CREATE POLICY salon_brand_assets_update_owner_or_admin
    ON storage.objects FOR UPDATE TO authenticated
    USING (
        bucket_id = 'salon-brand-assets'
        AND (storage.foldername(name))[1] ~ '^[0-9a-fA-F-]{36}$'
        AND (storage.foldername(name))[2] ~ '^[0-9a-fA-F-]{36}$'
        AND public.has_org_role(((storage.foldername(name))[1])::uuid, ARRAY['owner', 'admin'])
        AND EXISTS (
            SELECT 1 FROM public.businesses b
            WHERE b.id = ((storage.foldername(name))[2])::uuid
              AND b.organization_id = ((storage.foldername(name))[1])::uuid
        )
    )
    WITH CHECK (
        bucket_id = 'salon-brand-assets'
        AND (storage.foldername(name))[1] ~ '^[0-9a-fA-F-]{36}$'
        AND (storage.foldername(name))[2] ~ '^[0-9a-fA-F-]{36}$'
        AND public.has_org_role(((storage.foldername(name))[1])::uuid, ARRAY['owner', 'admin'])
        AND EXISTS (
            SELECT 1 FROM public.businesses b
            WHERE b.id = ((storage.foldername(name))[2])::uuid
              AND b.organization_id = ((storage.foldername(name))[1])::uuid
        )
    );

DROP POLICY IF EXISTS salon_brand_assets_delete_owner_or_admin ON storage.objects;
CREATE POLICY salon_brand_assets_delete_owner_or_admin
    ON storage.objects FOR DELETE TO authenticated
    USING (
        bucket_id = 'salon-brand-assets'
        AND (storage.foldername(name))[1] ~ '^[0-9a-fA-F-]{36}$'
        AND (storage.foldername(name))[2] ~ '^[0-9a-fA-F-]{36}$'
        AND public.has_org_role(((storage.foldername(name))[1])::uuid, ARRAY['owner', 'admin'])
        AND EXISTS (
            SELECT 1 FROM public.businesses b
            WHERE b.id = ((storage.foldername(name))[2])::uuid
              AND b.organization_id = ((storage.foldername(name))[1])::uuid
        )
    );

COMMIT;
