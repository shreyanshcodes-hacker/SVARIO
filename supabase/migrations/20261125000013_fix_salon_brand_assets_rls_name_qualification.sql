-- ============================================================================
-- SVARIO — FIX STORAGE RLS NAME SHADOWING ON `salon-brand-assets`
-- Migration: 20261125000013_fix_salon_brand_assets_rls_name_qualification.sql
-- Root Cause:
--   In 20261124000008, the EXISTS subquery `FROM public.businesses b` used
--   unqualified `storage.foldername(name)`, which PostgreSQL resolved to
--   `b.name` (the business display name) instead of `storage.objects.name`
--   (the object path `<organization_id>/<business_id>/<filename>`).
--   This caused all authenticated uploads to fail RLS with HTTP 400.
-- Fix:
--   Explicitly qualify `objects.name` in all four `salon-brand-assets`
--   storage.objects policies while keeping all security checks intact.
-- ============================================================================

BEGIN;

DROP POLICY IF EXISTS salon_brand_assets_select_member ON storage.objects;
CREATE POLICY salon_brand_assets_select_member
    ON storage.objects FOR SELECT TO authenticated
    USING (
        bucket_id = 'salon-brand-assets'
        AND (storage.foldername(objects.name))[1] ~ '^[0-9a-fA-F-]{36}$'
        AND (storage.foldername(objects.name))[2] ~ '^[0-9a-fA-F-]{36}$'
        AND public.is_org_member(((storage.foldername(objects.name))[1])::uuid)
        AND EXISTS (
            SELECT 1 FROM public.businesses b
            WHERE b.id = ((storage.foldername(objects.name))[2])::uuid
              AND b.organization_id = ((storage.foldername(objects.name))[1])::uuid
        )
    );

DROP POLICY IF EXISTS salon_brand_assets_insert_owner_or_admin ON storage.objects;
CREATE POLICY salon_brand_assets_insert_owner_or_admin
    ON storage.objects FOR INSERT TO authenticated
    WITH CHECK (
        bucket_id = 'salon-brand-assets'
        AND (storage.foldername(objects.name))[1] ~ '^[0-9a-fA-F-]{36}$'
        AND (storage.foldername(objects.name))[2] ~ '^[0-9a-fA-F-]{36}$'
        AND public.has_org_role(((storage.foldername(objects.name))[1])::uuid, ARRAY['owner', 'admin'])
        AND EXISTS (
            SELECT 1 FROM public.businesses b
            WHERE b.id = ((storage.foldername(objects.name))[2])::uuid
              AND b.organization_id = ((storage.foldername(objects.name))[1])::uuid
        )
    );

DROP POLICY IF EXISTS salon_brand_assets_update_owner_or_admin ON storage.objects;
CREATE POLICY salon_brand_assets_update_owner_or_admin
    ON storage.objects FOR UPDATE TO authenticated
    USING (
        bucket_id = 'salon-brand-assets'
        AND (storage.foldername(objects.name))[1] ~ '^[0-9a-fA-F-]{36}$'
        AND (storage.foldername(objects.name))[2] ~ '^[0-9a-fA-F-]{36}$'
        AND public.has_org_role(((storage.foldername(objects.name))[1])::uuid, ARRAY['owner', 'admin'])
        AND EXISTS (
            SELECT 1 FROM public.businesses b
            WHERE b.id = ((storage.foldername(objects.name))[2])::uuid
              AND b.organization_id = ((storage.foldername(objects.name))[1])::uuid
        )
    )
    WITH CHECK (
        bucket_id = 'salon-brand-assets'
        AND (storage.foldername(objects.name))[1] ~ '^[0-9a-fA-F-]{36}$'
        AND (storage.foldername(objects.name))[2] ~ '^[0-9a-fA-F-]{36}$'
        AND public.has_org_role(((storage.foldername(objects.name))[1])::uuid, ARRAY['owner', 'admin'])
        AND EXISTS (
            SELECT 1 FROM public.businesses b
            WHERE b.id = ((storage.foldername(objects.name))[2])::uuid
              AND b.organization_id = ((storage.foldername(objects.name))[1])::uuid
        )
    );

DROP POLICY IF EXISTS salon_brand_assets_delete_owner_or_admin ON storage.objects;
CREATE POLICY salon_brand_assets_delete_owner_or_admin
    ON storage.objects FOR DELETE TO authenticated
    USING (
        bucket_id = 'salon-brand-assets'
        AND (storage.foldername(objects.name))[1] ~ '^[0-9a-fA-F-]{36}$'
        AND (storage.foldername(objects.name))[2] ~ '^[0-9a-fA-F-]{36}$'
        AND public.has_org_role(((storage.foldername(objects.name))[1])::uuid, ARRAY['owner', 'admin'])
        AND EXISTS (
            SELECT 1 FROM public.businesses b
            WHERE b.id = ((storage.foldername(objects.name))[2])::uuid
              AND b.organization_id = ((storage.foldername(objects.name))[1])::uuid
        )
    );

COMMIT;
