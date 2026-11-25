-- ============================================================================
-- SVARIO — STAGE 12B: SMS REMINDER ENGINE FOUNDATION (HARDENED & IDEMPOTENT)
-- Migration: 20261125000011_stage12b_appointment_sms_reminders.sql
-- Purpose:
--   Additive, non-destructive, idempotent database foundation for appointment
--   SMS reminders:
--   1. `public.business_notification_settings` — backend-only explicit
--      `owner_sms_phone` configuration (never auto-falls back to public salon
--      reception phone numbers), strict least-privilege grants.
--   2. `public.salon_appointments` composite unique key `(id, business_id,
--      organization_id)` to enforce cross-tenant FK integrity.
--   3. `public.appointment_sms_reminders` — durable reminder queue with
--      composite cross-tenant FK to `salon_appointments`, deduplication per
--      `(appointment_id, recipient_type, appointment_version)`, UTC-safe
--      `TIMESTAMPTZ` defaults (`now()`), retry/lease metadata, and RLS.
--   4. `public.claim_due_appointment_reminders` — `SECURITY DEFINER`,
--      `SET search_path = ''`, `service_role`-ONLY atomic claiming RPC using
--      `pg_catalog.now()`, SQL `LEAST`/`GREATEST`, `FOR UPDATE SKIP LOCKED`,
--      and safe stale-lease recovery.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. Explicit Business Notification Settings (Owner SMS Phone)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.business_notification_settings (
    business_id UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    owner_sms_phone TEXT NULL,
    sms_reminders_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_business_notification_settings_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_business_notification_owner_sms_phone_e164
        CHECK (
            owner_sms_phone IS NULL
            OR (
                char_length(btrim(owner_sms_phone)) BETWEEN 7 AND 20
                AND btrim(owner_sms_phone) ~ '^\+[1-9][0-9]{6,14}$'
            )
        )
);

-- Ensure UTC-safe TIMESTAMPTZ defaults even if table already existed
ALTER TABLE public.business_notification_settings
    ALTER COLUMN created_at SET DEFAULT now(),
    ALTER COLUMN updated_at SET DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_business_notification_settings_org
    ON public.business_notification_settings (organization_id, business_id);

DROP TRIGGER IF EXISTS trg_business_notification_settings_set_updated_at
    ON public.business_notification_settings;
CREATE TRIGGER trg_business_notification_settings_set_updated_at
    BEFORE UPDATE ON public.business_notification_settings
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.business_notification_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.business_notification_settings FORCE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.business_notification_settings FROM PUBLIC;
REVOKE ALL ON TABLE public.business_notification_settings FROM anon;
REVOKE ALL ON TABLE public.business_notification_settings FROM authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.business_notification_settings TO authenticated;
GRANT ALL ON TABLE public.business_notification_settings TO service_role;

DROP POLICY IF EXISTS business_notification_settings_select_owner_or_admin
    ON public.business_notification_settings;
CREATE POLICY business_notification_settings_select_owner_or_admin
    ON public.business_notification_settings FOR SELECT TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS business_notification_settings_insert_owner_or_admin
    ON public.business_notification_settings;
CREATE POLICY business_notification_settings_insert_owner_or_admin
    ON public.business_notification_settings FOR INSERT TO authenticated
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS business_notification_settings_update_owner_or_admin
    ON public.business_notification_settings;
CREATE POLICY business_notification_settings_update_owner_or_admin
    ON public.business_notification_settings FOR UPDATE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS business_notification_settings_delete_owner_or_admin
    ON public.business_notification_settings;
CREATE POLICY business_notification_settings_delete_owner_or_admin
    ON public.business_notification_settings FOR DELETE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- ----------------------------------------------------------------------------
-- 2. Composite Unique Key on public.salon_appointments for Cross-Tenant FK
-- ----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_constraint
        WHERE conrelid = 'public.salon_appointments'::regclass
          AND conname = 'uq_salon_appointments_id_business_org'
    ) THEN
        ALTER TABLE public.salon_appointments
            ADD CONSTRAINT uq_salon_appointments_id_business_org
            UNIQUE (id, business_id, organization_id);
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 3. Appointment SMS Reminders Queue Table
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.appointment_sms_reminders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL,
    appointment_id UUID NOT NULL,
    appointment_version INTEGER NOT NULL DEFAULT 1,
    appointment_start_at TIMESTAMPTZ NOT NULL,
    staff_id UUID NULL,
    recipient_type TEXT NOT NULL,
    recipient_phone TEXT NULL,
    recipient_name TEXT NULL,
    scheduled_for TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    skip_reason TEXT NULL,
    template_key TEXT NOT NULL,
    provider_name TEXT NULL,
    provider_message_id TEXT NULL,
    provider_status TEXT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    next_retry_at TIMESTAMPTZ NULL,
    locked_at TIMESTAMPTZ NULL,
    locked_by TEXT NULL,
    sent_at TIMESTAMPTZ NULL,
    delivered_at TIMESTAMPTZ NULL,
    last_error TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_appointment_sms_reminders_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_appointment_sms_reminders_appointment_tenant
        FOREIGN KEY (appointment_id, business_id, organization_id)
        REFERENCES public.salon_appointments(id, business_id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT uq_appointment_sms_reminders_dedup
        UNIQUE (appointment_id, recipient_type, appointment_version),
    CONSTRAINT chk_appointment_sms_reminders_version
        CHECK (appointment_version >= 1),
    CONSTRAINT chk_appointment_sms_reminders_recipient_type
        CHECK (recipient_type IN ('customer', 'owner', 'staff')),
    CONSTRAINT chk_appointment_sms_reminders_status
        CHECK (
            status IN (
                'pending',
                'processing',
                'sent',
                'delivered',
                'failed',
                'cancelled',
                'skipped'
            )
        ),
    CONSTRAINT chk_appointment_sms_reminders_phone_consistency
        CHECK (
            (status = 'skipped' AND recipient_phone IS NULL)
            OR (
                recipient_phone IS NOT NULL
                AND char_length(btrim(recipient_phone)) BETWEEN 7 AND 20
                AND btrim(recipient_phone) ~ '^\+[1-9][0-9]{6,14}$'
            )
        ),
    CONSTRAINT chk_appointment_sms_reminders_retry_bounds
        CHECK (retry_count >= 0 AND max_retries >= 0 AND retry_count <= max_retries + 1)
);

-- Ensure UTC-safe defaults & composite cross-tenant FK even if table already existed
ALTER TABLE public.appointment_sms_reminders
    ALTER COLUMN created_at SET DEFAULT now(),
    ALTER COLUMN updated_at SET DEFAULT now();

ALTER TABLE public.appointment_sms_reminders
    DROP CONSTRAINT IF EXISTS appointment_sms_reminders_appointment_id_fkey;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_constraint
        WHERE conrelid = 'public.appointment_sms_reminders'::regclass
          AND conname = 'fk_appointment_sms_reminders_appointment_tenant'
    ) THEN
        ALTER TABLE public.appointment_sms_reminders
            ADD CONSTRAINT fk_appointment_sms_reminders_appointment_tenant
            FOREIGN KEY (appointment_id, business_id, organization_id)
            REFERENCES public.salon_appointments(id, business_id, organization_id)
            ON DELETE CASCADE;
    END IF;
END $$;

-- Hot worker polling index (only pending rows)
CREATE INDEX IF NOT EXISTS idx_appt_sms_reminders_due
    ON public.appointment_sms_reminders (scheduled_for, next_retry_at)
    WHERE status = 'pending';

-- Stale lease recovery index (only actively locked rows)
CREATE INDEX IF NOT EXISTS idx_appt_sms_reminders_processing_lease
    ON public.appointment_sms_reminders (locked_at)
    WHERE status = 'processing';

-- Provider delivery webhook lookup (unique per provider + provider_message_id)
CREATE UNIQUE INDEX IF NOT EXISTS uq_appt_sms_reminders_provider_msg
    ON public.appointment_sms_reminders (provider_name, provider_message_id)
    WHERE provider_name IS NOT NULL AND provider_message_id IS NOT NULL;

-- Multi-tenant appointment lookup index
CREATE INDEX IF NOT EXISTS idx_appt_sms_reminders_tenant_appt
    ON public.appointment_sms_reminders (organization_id, business_id, appointment_id, appointment_version DESC);

DROP TRIGGER IF EXISTS trg_appointment_sms_reminders_set_updated_at
    ON public.appointment_sms_reminders;
CREATE TRIGGER trg_appointment_sms_reminders_set_updated_at
    BEFORE UPDATE ON public.appointment_sms_reminders
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- Strict RLS: zero anon access; authenticated owners/admins SELECT-only; service_role full
ALTER TABLE public.appointment_sms_reminders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.appointment_sms_reminders FORCE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.appointment_sms_reminders FROM PUBLIC;
REVOKE ALL ON TABLE public.appointment_sms_reminders FROM anon;
REVOKE ALL ON TABLE public.appointment_sms_reminders FROM authenticated;
GRANT SELECT ON TABLE public.appointment_sms_reminders TO authenticated;
GRANT ALL ON TABLE public.appointment_sms_reminders TO service_role;

DROP POLICY IF EXISTS appointment_sms_reminders_select_owner_or_admin
    ON public.appointment_sms_reminders;
CREATE POLICY appointment_sms_reminders_select_owner_or_admin
    ON public.appointment_sms_reminders FOR SELECT TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- ----------------------------------------------------------------------------
-- 4. Atomic Queue Claiming & Stale-Lease Recovery RPC (service_role ONLY)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.claim_due_appointment_reminders(
    p_batch_size INTEGER DEFAULT 25,
    p_worker_id TEXT DEFAULT 'sms-worker',
    p_lease_timeout_seconds INTEGER DEFAULT 300
)
RETURNS SETOF public.appointment_sms_reminders
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_now TIMESTAMPTZ := pg_catalog.now();
    v_batch INTEGER := LEAST(GREATEST(COALESCE(p_batch_size, 25), 1), 100);
    v_lease_secs INTEGER := LEAST(GREATEST(COALESCE(p_lease_timeout_seconds, 300), 30), 3600);
    v_worker TEXT := pg_catalog.left(pg_catalog.btrim(COALESCE(p_worker_id, 'sms-worker')), 120);
    v_stale_cutoff TIMESTAMPTZ;
BEGIN
    IF v_worker = '' THEN
        v_worker := 'sms-worker';
    END IF;

    v_stale_cutoff := v_now - pg_catalog.make_interval(secs => v_lease_secs);

    -- Step 1: Recover stale `processing` leases from crashed workers.
    -- Rows whose appointment has already started are failed permanently;
    -- remaining rows with retry budget return to `pending` with incremented retry_count.
    UPDATE public.appointment_sms_reminders r
    SET
        status = CASE
            WHEN r.appointment_start_at <= v_now THEN 'failed'
            WHEN r.retry_count < r.max_retries THEN 'pending'
            ELSE 'failed'
        END,
        retry_count = CASE
            WHEN r.appointment_start_at <= v_now THEN r.retry_count
            WHEN r.retry_count < r.max_retries THEN r.retry_count + 1
            ELSE r.retry_count
        END,
        next_retry_at = CASE
            WHEN r.appointment_start_at > v_now AND r.retry_count < r.max_retries THEN v_now
            ELSE NULL
        END,
        locked_at = NULL,
        locked_by = NULL,
        last_error = CASE
            WHEN r.appointment_start_at <= v_now THEN 'stale_lease_after_appointment_start'
            WHEN r.retry_count < r.max_retries THEN 'stale_lease_recovered'
            ELSE 'max_retries_exceeded_after_stale_lease'
        END,
        updated_at = v_now
    WHERE r.status = 'processing'
      AND r.locked_at IS NOT NULL
      AND r.locked_at < v_stale_cutoff;

    -- Step 2: Atomically claim due `pending` reminders using FOR UPDATE SKIP LOCKED.
    RETURN QUERY
    WITH due AS (
        SELECT r.id
        FROM public.appointment_sms_reminders r
        WHERE r.status = 'pending'
          AND COALESCE(r.next_retry_at, r.scheduled_for) <= v_now
        ORDER BY COALESCE(r.next_retry_at, r.scheduled_for) ASC, r.created_at ASC
        LIMIT v_batch
        FOR UPDATE SKIP LOCKED
    )
    UPDATE public.appointment_sms_reminders target
    SET
        status = 'processing',
        locked_at = v_now,
        locked_by = v_worker,
        updated_at = v_now
    FROM due
    WHERE target.id = due.id
    RETURNING target.*;
END;
$$;

REVOKE ALL ON FUNCTION public.claim_due_appointment_reminders(INTEGER, TEXT, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.claim_due_appointment_reminders(INTEGER, TEXT, INTEGER) FROM anon;
REVOKE ALL ON FUNCTION public.claim_due_appointment_reminders(INTEGER, TEXT, INTEGER) FROM authenticated;
GRANT EXECUTE ON FUNCTION public.claim_due_appointment_reminders(INTEGER, TEXT, INTEGER) TO service_role;

COMMIT;
