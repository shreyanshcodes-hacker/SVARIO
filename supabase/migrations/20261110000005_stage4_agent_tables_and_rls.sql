-- ============================================================================
-- SVARIO — STAGE 4: AI AGENT & CONVERSATIONAL INTELLIGENCE SCHEMA & RLS
-- Migration: 20261110000005_stage4_agent_tables_and_rls.sql
-- Purpose:
--   1. Create public.conversation_summaries for privacy-aware, configurable
--      session summary persistence (`save_conversation_summary` tool).
--   2. Create public.escalation_requests for controlled human escalation
--      workflows (`request_human_escalation` tool).
--   3. Enforce composite foreign keys (business_id, organization_id) ->
--      public.businesses(id, organization_id) and enable + force Row Level
--      Security (RLS) on both tables.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. public.conversation_summaries
--    Stores non-sensitive, privacy-aware session summaries.
--    Never stores raw audio or patient clinical medical histories.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.conversation_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    primary_intent TEXT NOT NULL DEFAULT 'unknown',
    detected_language TEXT NOT NULL DEFAULT 'en',
    summary_text TEXT NOT NULL,
    booking_preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    escalated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_conversation_summaries_business_session
        UNIQUE (business_id, session_id),
    CONSTRAINT fk_conversation_summaries_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_conversation_summaries_language
        CHECK (detected_language IN ('en', 'hi', 'hinglish')),
    CONSTRAINT chk_conversation_summaries_text_len
        CHECK (char_length(btrim(summary_text)) BETWEEN 3 AND 2000)
);

CREATE INDEX IF NOT EXISTS idx_conversation_summaries_org_business
    ON public.conversation_summaries (organization_id, business_id);

CREATE INDEX IF NOT EXISTS idx_conversation_summaries_business_org
    ON public.conversation_summaries (business_id, organization_id);

DROP TRIGGER IF EXISTS trg_conversation_summaries_set_updated_at ON public.conversation_summaries;
CREATE TRIGGER trg_conversation_summaries_set_updated_at
    BEFORE UPDATE ON public.conversation_summaries
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 2. public.escalation_requests
--    Stores controlled human escalation requests linked to verified businesses.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.escalation_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    escalation_reference TEXT NOT NULL,
    reason TEXT NOT NULL,
    summary TEXT NOT NULL,
    urgency TEXT NOT NULL DEFAULT 'standard',
    status TEXT NOT NULL DEFAULT 'pending_human_review',
    target_contact_name TEXT NULL,
    target_contact_method TEXT NOT NULL DEFAULT 'phone',
    notification_delivered BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_escalation_requests_reference
        UNIQUE (escalation_reference),
    CONSTRAINT fk_escalation_requests_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_escalation_requests_urgency
        CHECK (urgency IN ('standard', 'priority', 'clinical_staff', 'emergency_redirected')),
    CONSTRAINT chk_escalation_requests_status
        CHECK (status IN ('pending_human_review', 'acknowledged', 'resolved')),
    CONSTRAINT chk_escalation_requests_method
        CHECK (target_contact_method IN ('phone', 'email', 'either'))
);

CREATE INDEX IF NOT EXISTS idx_escalation_requests_org_business
    ON public.escalation_requests (organization_id, business_id);

CREATE INDEX IF NOT EXISTS idx_escalation_requests_business_org
    ON public.escalation_requests (business_id, organization_id);

DROP TRIGGER IF EXISTS trg_escalation_requests_set_updated_at ON public.escalation_requests;
CREATE TRIGGER trg_escalation_requests_set_updated_at
    BEFORE UPDATE ON public.escalation_requests
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 3. Enable and Force Row Level Security (RLS)
-- ----------------------------------------------------------------------------
ALTER TABLE public.conversation_summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversation_summaries FORCE ROW LEVEL SECURITY;

ALTER TABLE public.escalation_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.escalation_requests FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS conversation_summaries_select_member ON public.conversation_summaries;
CREATE POLICY conversation_summaries_select_member
    ON public.conversation_summaries
    FOR SELECT
    TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS conversation_summaries_insert_member ON public.conversation_summaries;
CREATE POLICY conversation_summaries_insert_member
    ON public.conversation_summaries
    FOR INSERT
    TO authenticated
    WITH CHECK (public.is_org_member(organization_id));

DROP POLICY IF EXISTS conversation_summaries_update_owner_or_admin ON public.conversation_summaries;
CREATE POLICY conversation_summaries_update_owner_or_admin
    ON public.conversation_summaries
    FOR UPDATE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS conversation_summaries_delete_owner_only ON public.conversation_summaries;
CREATE POLICY conversation_summaries_delete_owner_only
    ON public.conversation_summaries
    FOR DELETE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner']));

DROP POLICY IF EXISTS escalation_requests_select_member ON public.escalation_requests;
CREATE POLICY escalation_requests_select_member
    ON public.escalation_requests
    FOR SELECT
    TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS escalation_requests_insert_member ON public.escalation_requests;
CREATE POLICY escalation_requests_insert_member
    ON public.escalation_requests
    FOR INSERT
    TO authenticated
    WITH CHECK (public.is_org_member(organization_id));

DROP POLICY IF EXISTS escalation_requests_update_owner_or_admin ON public.escalation_requests;
CREATE POLICY escalation_requests_update_owner_or_admin
    ON public.escalation_requests
    FOR UPDATE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS escalation_requests_delete_owner_only ON public.escalation_requests;
CREATE POLICY escalation_requests_delete_owner_only
    ON public.escalation_requests
    FOR DELETE
    TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner']));

COMMIT;
