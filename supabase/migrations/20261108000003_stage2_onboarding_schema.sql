-- ============================================================================
-- SVARIO — STAGE 2: INDUSTRY SELECTION & BUSINESS ONBOARDING SCHEMA
-- Migration: 20261108000003_stage2_onboarding_schema.sql
-- Purpose:
--   1. Safely extend public.business_hours with `is_overnight` support.
--   2. Create public.business_profiles, public.business_languages,
--      public.business_faqs, public.assistant_settings,
--      public.escalation_settings, and public.onboarding_progress.
--   3. Enforce composite foreign keys (business_id, organization_id) ->
--      public.businesses(id, organization_id) to guarantee strict tenant
--      ownership across all child onboarding records.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 0. Extend public.business_hours to support explicit overnight schedules safely
-- ----------------------------------------------------------------------------
ALTER TABLE public.business_hours
    ADD COLUMN IF NOT EXISTS is_overnight BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.business_hours
    DROP CONSTRAINT IF EXISTS chk_business_hours_open_close_consistency;

ALTER TABLE public.business_hours
    ADD CONSTRAINT chk_business_hours_open_close_consistency
    CHECK (
        is_closed = TRUE
        OR (
            opens_at IS NOT NULL
            AND closes_at IS NOT NULL
            AND (
                (is_overnight = FALSE AND opens_at < closes_at)
                OR (is_overnight = TRUE AND opens_at > closes_at)
            )
        )
    );

-- ----------------------------------------------------------------------------
-- 1. public.business_profiles
--    1:1 rich business profile for a business unit (no duplicate profiles).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.business_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    description TEXT NULL,
    phone TEXT NULL,
    email TEXT NULL,
    website TEXT NULL,
    address TEXT NULL,
    city TEXT NULL,
    state TEXT NULL,
    country TEXT NULL,
    postal_code TEXT NULL,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_business_profiles_business_id
        UNIQUE (business_id),
    CONSTRAINT fk_business_profiles_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_business_profiles_display_name_len
        CHECK (char_length(btrim(display_name)) BETWEEN 2 AND 120),
    CONSTRAINT chk_business_profiles_timezone_nonempty
        CHECK (char_length(btrim(timezone)) >= 2)
);

CREATE INDEX IF NOT EXISTS idx_business_profiles_org_business
    ON public.business_profiles (organization_id, business_id);

DROP TRIGGER IF EXISTS trg_business_profiles_set_updated_at ON public.business_profiles;
CREATE TRIGGER trg_business_profiles_set_updated_at
    BEFORE UPDATE ON public.business_profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 2. public.business_languages
--    Per-business language preferences (English 'en', Hindi 'hi', Hinglish 'hinglish').
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.business_languages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    language_code TEXT NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_business_languages_business_code
        UNIQUE (business_id, language_code),
    CONSTRAINT fk_business_languages_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_business_languages_code
        CHECK (language_code IN ('en', 'hi', 'hinglish'))
);

CREATE INDEX IF NOT EXISTS idx_business_languages_org_business
    ON public.business_languages (organization_id, business_id);

-- Ensure at most one primary language per business
CREATE UNIQUE INDEX IF NOT EXISTS idx_business_languages_one_primary
    ON public.business_languages (business_id)
    WHERE is_primary = TRUE;

-- ----------------------------------------------------------------------------
-- 3. public.business_faqs
--    Editable FAQ items scoped to organization + business.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.business_faqs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_business_faqs_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_business_faqs_question_len
        CHECK (char_length(btrim(question)) BETWEEN 3 AND 500),
    CONSTRAINT chk_business_faqs_answer_len
        CHECK (char_length(btrim(answer)) BETWEEN 2 AND 2000),
    CONSTRAINT chk_business_faqs_category_len
        CHECK (char_length(btrim(category)) BETWEEN 2 AND 80),
    CONSTRAINT chk_business_faqs_sort_order_nonneg
        CHECK (sort_order >= 0)
);

CREATE INDEX IF NOT EXISTS idx_business_faqs_org_business_sort
    ON public.business_faqs (organization_id, business_id, sort_order ASC);

DROP TRIGGER IF EXISTS trg_business_faqs_set_updated_at ON public.business_faqs;
CREATE TRIGGER trg_business_faqs_set_updated_at
    BEFORE UPDATE ON public.business_faqs
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 4. public.assistant_settings
--    1:1 AI Voice Assistant configuration for a business (Stage 2 config only).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.assistant_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    assistant_name TEXT NOT NULL DEFAULT 'Svario Receptionist',
    greeting TEXT NOT NULL DEFAULT 'Hello! Thank you for calling. How may I assist you today?',
    personality TEXT NOT NULL DEFAULT 'professional',
    response_style TEXT NOT NULL DEFAULT 'balanced',
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_assistant_settings_business_id
        UNIQUE (business_id),
    CONSTRAINT fk_assistant_settings_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_assistant_settings_name_len
        CHECK (char_length(btrim(assistant_name)) BETWEEN 2 AND 80),
    CONSTRAINT chk_assistant_settings_greeting_len
        CHECK (char_length(btrim(greeting)) BETWEEN 5 AND 500),
    CONSTRAINT chk_assistant_settings_personality
        CHECK (personality IN ('professional', 'friendly', 'warm')),
    CONSTRAINT chk_assistant_settings_response_style
        CHECK (response_style IN ('concise', 'balanced', 'detailed'))
);

CREATE INDEX IF NOT EXISTS idx_assistant_settings_org_business
    ON public.assistant_settings (organization_id, business_id);

DROP TRIGGER IF EXISTS trg_assistant_settings_set_updated_at ON public.assistant_settings;
CREATE TRIGGER trg_assistant_settings_set_updated_at
    BEFORE UPDATE ON public.assistant_settings
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 5. public.escalation_settings
--    1:1 Human escalation & administrative handoff configuration.
--    Healthcare Note: Administrative reception only — never stores medical data.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.escalation_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    contact_name TEXT NULL,
    contact_email TEXT NULL,
    contact_phone TEXT NULL,
    escalation_instructions TEXT NULL,
    preferred_method TEXT NOT NULL DEFAULT 'phone',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_escalation_settings_business_id
        UNIQUE (business_id),
    CONSTRAINT fk_escalation_settings_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_escalation_settings_preferred_method
        CHECK (preferred_method IN ('phone', 'email', 'either')),
    CONSTRAINT chk_escalation_settings_active_contact_required
        CHECK (
            enabled = FALSE
            OR (
                (contact_name IS NOT NULL AND char_length(btrim(contact_name)) >= 2)
                AND (
                    (contact_phone IS NOT NULL AND char_length(btrim(contact_phone)) >= 6)
                    OR (contact_email IS NOT NULL AND char_length(btrim(contact_email)) >= 5)
                )
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_escalation_settings_org_business
    ON public.escalation_settings (organization_id, business_id);

DROP TRIGGER IF EXISTS trg_escalation_settings_set_updated_at ON public.escalation_settings;
CREATE TRIGGER trg_escalation_settings_set_updated_at
    BEFORE UPDATE ON public.escalation_settings
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 6. public.onboarding_progress
--    1:1 Multi-step onboarding progress tracker per business.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.onboarding_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    current_step TEXT NOT NULL DEFAULT 'industry',
    completed_steps TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    completed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_onboarding_progress_business_id
        UNIQUE (business_id),
    CONSTRAINT fk_onboarding_progress_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_onboarding_progress_current_step
        CHECK (
            current_step IN (
                'industry',
                'profile',
                'hours',
                'languages',
                'assistant',
                'faqs',
                'escalation',
                'review'
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_onboarding_progress_org_business
    ON public.onboarding_progress (organization_id, business_id);

-- Covering indexes matching composite foreign key column order (business_id, organization_id)
CREATE INDEX IF NOT EXISTS idx_business_settings_business_org
    ON public.business_settings (business_id, organization_id);
CREATE INDEX IF NOT EXISTS idx_business_hours_business_org
    ON public.business_hours (business_id, organization_id);
CREATE INDEX IF NOT EXISTS idx_business_profiles_business_org
    ON public.business_profiles (business_id, organization_id);
CREATE INDEX IF NOT EXISTS idx_business_languages_business_org
    ON public.business_languages (business_id, organization_id);
CREATE INDEX IF NOT EXISTS idx_business_faqs_business_org
    ON public.business_faqs (business_id, organization_id);
CREATE INDEX IF NOT EXISTS idx_assistant_settings_business_org
    ON public.assistant_settings (business_id, organization_id);
CREATE INDEX IF NOT EXISTS idx_escalation_settings_business_org
    ON public.escalation_settings (business_id, organization_id);
CREATE INDEX IF NOT EXISTS idx_onboarding_progress_business_org
    ON public.onboarding_progress (business_id, organization_id);

DROP TRIGGER IF EXISTS trg_onboarding_progress_set_updated_at ON public.onboarding_progress;
CREATE TRIGGER trg_onboarding_progress_set_updated_at
    BEFORE UPDATE ON public.onboarding_progress
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

COMMIT;
