-- ============================================================================
-- SVARIO — STAGE 12C.2: SMS DELIVERY RECEIPT (DLR) EVENTS & DEDUPLICATION
-- Migration: 20261125000012_stage12c2_sms_delivery_events.sql
-- Purpose:
--   Additive, idempotent migration providing persistent, race-safe delivery
--   receipt deduplication and minimal non-PII audit tracking:
--   1. Composite unique key `(id, business_id, organization_id)` on
--      `public.appointment_sms_reminders` for tenant-safe FK enforcement.
--   2. `public.appointment_sms_delivery_events` — stores deterministic
--      non-PII event fingerprints (`UNIQUE (provider_name, event_fingerprint)`),
--      normalized DLR outcomes, and validated provider timestamps.
--   3. Strict RLS: zero `anon` access, `authenticated` owner/admin SELECT-only,
--      `service_role` full write access.
--
-- DO NOT MODIFY HISTORICAL MIGRATIONS. REVIEW BEFORE MANUAL APPLICATION.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. Composite Unique Key on appointment_sms_reminders for Tenant-Safe FK
-- ----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_constraint
        WHERE conrelid = 'public.appointment_sms_reminders'::regclass
          AND conname = 'uq_appointment_sms_reminders_id_business_org'
    ) THEN
        ALTER TABLE public.appointment_sms_reminders
            ADD CONSTRAINT uq_appointment_sms_reminders_id_business_org
            UNIQUE (id, business_id, organization_id);
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 2. Delivery Receipt Audit & Deduplication Table (Zero Raw PII)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.appointment_sms_delivery_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL,
    reminder_id UUID NOT NULL,
    provider_name TEXT NOT NULL,
    provider_message_id TEXT NOT NULL,
    event_fingerprint TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'webhook',
    normalized_outcome TEXT NOT NULL,
    raw_status_code TEXT NULL,
    provider_event_at TIMESTAMPTZ NULL,
    applied BOOLEAN NOT NULL DEFAULT FALSE,
    ignored_reason TEXT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_sms_delivery_events_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_sms_delivery_events_reminder_tenant
        FOREIGN KEY (reminder_id, business_id, organization_id)
        REFERENCES public.appointment_sms_reminders(id, business_id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT uq_sms_delivery_events_provider_fingerprint
        UNIQUE (provider_name, event_fingerprint),
    CONSTRAINT chk_sms_delivery_events_source
        CHECK (source IN ('webhook', 'logs_reconciliation')),
    CONSTRAINT chk_sms_delivery_events_outcome
        CHECK (normalized_outcome IN ('delivered', 'failed', 'rejected', 'unknown')),
    CONSTRAINT chk_sms_delivery_events_fingerprint_len
        CHECK (char_length(event_fingerprint) = 64)
);

CREATE INDEX IF NOT EXISTS idx_sms_delivery_events_reminder_received
    ON public.appointment_sms_delivery_events (reminder_id, received_at DESC);

CREATE INDEX IF NOT EXISTS idx_sms_delivery_events_tenant_msg
    ON public.appointment_sms_delivery_events (organization_id, business_id, provider_name, provider_message_id);

ALTER TABLE public.appointment_sms_delivery_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.appointment_sms_delivery_events FORCE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.appointment_sms_delivery_events FROM PUBLIC;
REVOKE ALL ON TABLE public.appointment_sms_delivery_events FROM anon;
REVOKE ALL ON TABLE public.appointment_sms_delivery_events FROM authenticated;
GRANT SELECT ON TABLE public.appointment_sms_delivery_events TO authenticated;
GRANT ALL ON TABLE public.appointment_sms_delivery_events TO service_role;

DROP POLICY IF EXISTS sms_delivery_events_select_owner_or_admin
    ON public.appointment_sms_delivery_events;
CREATE POLICY sms_delivery_events_select_owner_or_admin
    ON public.appointment_sms_delivery_events FOR SELECT TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

COMMIT;
