-- ============================================================================
-- SVARIO — STAGE 6: CLINIC WORKFLOW MODULE SCHEMA, CONCURRENCY & RLS
-- Migration: 20261116000007_stage6_clinic_workflow_and_rls.sql
-- Purpose:
--   1. Create clinic_departments, clinic_doctors, clinic_specialities.
--   2. Create doctor mapping tables: clinic_doctor_departments,
--      clinic_doctor_specialities, clinic_doctor_consultation_types.
--   3. Create clinic_consultation_types (in_person / online, duration, optional fee).
--   4. Create clinic_doctor_working_hours, clinic_doctor_breaks,
--      clinic_doctor_unavailability.
--   5. Create clinic_appointments with idempotency keys, half-open [starts_at, ends_at)
--      GiST exclusion constraint preventing overlapping active doctor bookings,
--      and minimal administrative patient fields only.
--   6. Enable and FORCE Row Level Security (RLS) on all 11 Stage 6 tables.
-- ============================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ----------------------------------------------------------------------------
-- 1. public.clinic_departments
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.clinic_departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_clinic_departments_id_business_org
        UNIQUE (id, business_id, organization_id),
    CONSTRAINT uq_clinic_departments_business_name
        UNIQUE (business_id, name),
    CONSTRAINT fk_clinic_departments_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_clinic_departments_name_len
        CHECK (char_length(btrim(name)) BETWEEN 2 AND 120)
);

CREATE INDEX IF NOT EXISTS idx_clinic_departments_org_business
    ON public.clinic_departments (organization_id, business_id, is_active);

DROP TRIGGER IF EXISTS trg_clinic_departments_set_updated_at ON public.clinic_departments;
CREATE TRIGGER trg_clinic_departments_set_updated_at
    BEFORE UPDATE ON public.clinic_departments
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 2. public.clinic_doctors
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.clinic_doctors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    professional_title TEXT NULL,
    public_bio TEXT NULL,
    languages TEXT[] NOT NULL DEFAULT ARRAY['en']::TEXT[],
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_clinic_doctors_id_business_org
        UNIQUE (id, business_id, organization_id),
    CONSTRAINT fk_clinic_doctors_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_clinic_doctors_name_len
        CHECK (char_length(btrim(display_name)) BETWEEN 2 AND 120)
);

CREATE INDEX IF NOT EXISTS idx_clinic_doctors_org_business
    ON public.clinic_doctors (organization_id, business_id, is_active);

DROP TRIGGER IF EXISTS trg_clinic_doctors_set_updated_at ON public.clinic_doctors;
CREATE TRIGGER trg_clinic_doctors_set_updated_at
    BEFORE UPDATE ON public.clinic_doctors
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 3. public.clinic_specialities
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.clinic_specialities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_clinic_specialities_id_business_org
        UNIQUE (id, business_id, organization_id),
    CONSTRAINT uq_clinic_specialities_business_name
        UNIQUE (business_id, name),
    CONSTRAINT fk_clinic_specialities_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_clinic_specialities_name_len
        CHECK (char_length(btrim(name)) BETWEEN 2 AND 120)
);

CREATE INDEX IF NOT EXISTS idx_clinic_specialities_org_business
    ON public.clinic_specialities (organization_id, business_id, is_active);

DROP TRIGGER IF EXISTS trg_clinic_specialities_set_updated_at ON public.clinic_specialities;
CREATE TRIGGER trg_clinic_specialities_set_updated_at
    BEFORE UPDATE ON public.clinic_specialities
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 4. public.clinic_doctor_departments
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.clinic_doctor_departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    doctor_id UUID NOT NULL,
    department_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_clinic_doctor_departments_mapping
        UNIQUE (business_id, doctor_id, department_id),
    CONSTRAINT fk_clinic_doctor_departments_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_clinic_doctor_departments_doctor
        FOREIGN KEY (doctor_id, business_id, organization_id)
        REFERENCES public.clinic_doctors(id, business_id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_clinic_doctor_departments_department
        FOREIGN KEY (department_id, business_id, organization_id)
        REFERENCES public.clinic_departments(id, business_id, organization_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_clinic_doctor_departments_org_business
    ON public.clinic_doctor_departments (organization_id, business_id, doctor_id);

-- ----------------------------------------------------------------------------
-- 5. public.clinic_doctor_specialities
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.clinic_doctor_specialities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    doctor_id UUID NOT NULL,
    speciality_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_clinic_doctor_specialities_mapping
        UNIQUE (business_id, doctor_id, speciality_id),
    CONSTRAINT fk_clinic_doctor_specialities_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_clinic_doctor_specialities_doctor
        FOREIGN KEY (doctor_id, business_id, organization_id)
        REFERENCES public.clinic_doctors(id, business_id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_clinic_doctor_specialities_speciality
        FOREIGN KEY (speciality_id, business_id, organization_id)
        REFERENCES public.clinic_specialities(id, business_id, organization_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_clinic_doctor_specialities_org_business
    ON public.clinic_doctor_specialities (organization_id, business_id, doctor_id);

-- ----------------------------------------------------------------------------
-- 6. public.clinic_consultation_types
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.clinic_consultation_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NULL,
    duration_minutes INTEGER NOT NULL,
    consultation_mode TEXT NOT NULL DEFAULT 'in_person',
    fee_amount NUMERIC(10, 2) NULL,
    currency_code TEXT NULL DEFAULT 'INR',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_clinic_consultation_types_id_business_org
        UNIQUE (id, business_id, organization_id),
    CONSTRAINT fk_clinic_consultation_types_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_clinic_consultation_types_name_len
        CHECK (char_length(btrim(name)) BETWEEN 2 AND 120),
    CONSTRAINT chk_clinic_consultation_types_duration
        CHECK (duration_minutes BETWEEN 5 AND 240),
    CONSTRAINT chk_clinic_consultation_types_mode
        CHECK (consultation_mode IN ('in_person', 'online')),
    CONSTRAINT chk_clinic_consultation_types_fee
        CHECK (fee_amount IS NULL OR (fee_amount >= 0 AND fee_amount <= 1000000)),
    CONSTRAINT chk_clinic_consultation_types_currency
        CHECK (currency_code IS NULL OR char_length(btrim(currency_code)) = 3)
);

CREATE INDEX IF NOT EXISTS idx_clinic_consultation_types_org_business
    ON public.clinic_consultation_types (organization_id, business_id, is_active);

DROP TRIGGER IF EXISTS trg_clinic_consultation_types_set_updated_at ON public.clinic_consultation_types;
CREATE TRIGGER trg_clinic_consultation_types_set_updated_at
    BEFORE UPDATE ON public.clinic_consultation_types
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 7. public.clinic_doctor_consultation_types
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.clinic_doctor_consultation_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    doctor_id UUID NOT NULL,
    consultation_type_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_clinic_doctor_consultation_mapping
        UNIQUE (business_id, doctor_id, consultation_type_id),
    CONSTRAINT fk_clinic_doctor_consultation_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_clinic_doctor_consultation_doctor
        FOREIGN KEY (doctor_id, business_id, organization_id)
        REFERENCES public.clinic_doctors(id, business_id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_clinic_doctor_consultation_type
        FOREIGN KEY (consultation_type_id, business_id, organization_id)
        REFERENCES public.clinic_consultation_types(id, business_id, organization_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_clinic_doctor_consultation_org_business
    ON public.clinic_doctor_consultation_types (organization_id, business_id, doctor_id);

-- ----------------------------------------------------------------------------
-- 8. public.clinic_doctor_working_hours
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.clinic_doctor_working_hours (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    doctor_id UUID NOT NULL,
    day_of_week SMALLINT NOT NULL,
    start_time TIME NULL,
    end_time TIME NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_clinic_doctor_working_hours_doctor_day
        UNIQUE (doctor_id, day_of_week),
    CONSTRAINT fk_clinic_doctor_working_hours_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_clinic_doctor_working_hours_doctor
        FOREIGN KEY (doctor_id, business_id, organization_id)
        REFERENCES public.clinic_doctors(id, business_id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_clinic_doctor_working_hours_day
        CHECK (day_of_week BETWEEN 0 AND 6),
    CONSTRAINT chk_clinic_doctor_working_hours_consistency
        CHECK (
            is_active = FALSE
            OR (start_time IS NOT NULL AND end_time IS NOT NULL AND start_time < end_time)
        )
);

CREATE INDEX IF NOT EXISTS idx_clinic_doctor_working_hours_org_business
    ON public.clinic_doctor_working_hours (organization_id, business_id, doctor_id);

DROP TRIGGER IF EXISTS trg_clinic_doctor_working_hours_set_updated_at ON public.clinic_doctor_working_hours;
CREATE TRIGGER trg_clinic_doctor_working_hours_set_updated_at
    BEFORE UPDATE ON public.clinic_doctor_working_hours
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 9. public.clinic_doctor_breaks
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.clinic_doctor_breaks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    doctor_id UUID NOT NULL,
    day_of_week SMALLINT NULL,
    specific_date DATE NULL,
    break_start TIME NOT NULL,
    break_end TIME NOT NULL,
    reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_clinic_doctor_breaks_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_clinic_doctor_breaks_doctor
        FOREIGN KEY (doctor_id, business_id, organization_id)
        REFERENCES public.clinic_doctors(id, business_id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_clinic_doctor_breaks_day
        CHECK (day_of_week IS NULL OR (day_of_week BETWEEN 0 AND 6)),
    CONSTRAINT chk_clinic_doctor_breaks_target_required
        CHECK (day_of_week IS NOT NULL OR specific_date IS NOT NULL),
    CONSTRAINT chk_clinic_doctor_breaks_time_order
        CHECK (break_start < break_end)
);

CREATE INDEX IF NOT EXISTS idx_clinic_doctor_breaks_org_business_doctor
    ON public.clinic_doctor_breaks (organization_id, business_id, doctor_id);

-- ----------------------------------------------------------------------------
-- 10. public.clinic_doctor_unavailability
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.clinic_doctor_unavailability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    doctor_id UUID NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_clinic_doctor_unavailability_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_clinic_doctor_unavailability_doctor
        FOREIGN KEY (doctor_id, business_id, organization_id)
        REFERENCES public.clinic_doctors(id, business_id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_clinic_doctor_unavailability_order
        CHECK (starts_at < ends_at)
);

CREATE INDEX IF NOT EXISTS idx_clinic_doctor_unavailability_org_business_doctor
    ON public.clinic_doctor_unavailability (organization_id, business_id, doctor_id, starts_at);

-- ----------------------------------------------------------------------------
-- 11. public.clinic_appointments
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.clinic_appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    booking_reference TEXT NOT NULL,
    doctor_id UUID NOT NULL,
    consultation_type_id UUID NOT NULL,
    department_id UUID NULL,
    patient_display_name TEXT NOT NULL,
    patient_contact TEXT NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    status TEXT NOT NULL DEFAULT 'confirmed',
    source TEXT NOT NULL DEFAULT 'dashboard',
    idempotency_key TEXT NULL,
    cancellation_reason TEXT NULL,
    cancelled_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_clinic_appointments_reference
        UNIQUE (booking_reference),
    CONSTRAINT fk_clinic_appointments_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_clinic_appointments_doctor
        FOREIGN KEY (doctor_id, business_id, organization_id)
        REFERENCES public.clinic_doctors(id, business_id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_clinic_appointments_consultation_type
        FOREIGN KEY (consultation_type_id, business_id, organization_id)
        REFERENCES public.clinic_consultation_types(id, business_id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_clinic_appointments_department
        FOREIGN KEY (department_id, business_id, organization_id)
        REFERENCES public.clinic_departments(id, business_id, organization_id)
        ON DELETE SET NULL,
    CONSTRAINT chk_clinic_appointments_patient_name_len
        CHECK (char_length(btrim(patient_display_name)) BETWEEN 2 AND 120),
    CONSTRAINT chk_clinic_appointments_patient_contact_len
        CHECK (char_length(btrim(patient_contact)) BETWEEN 5 AND 80),
    CONSTRAINT chk_clinic_appointments_status
        CHECK (status IN ('confirmed', 'rescheduled', 'cancelled', 'completed', 'no_show')),
    CONSTRAINT chk_clinic_appointments_source
        CHECK (source IN ('dashboard', 'voice_agent', 'api')),
    CONSTRAINT chk_clinic_appointments_time_order
        CHECK (starts_at < ends_at),
    CONSTRAINT excl_clinic_appointments_no_doctor_overlap
        EXCLUDE USING gist (
            doctor_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        )
        WHERE (status IN ('confirmed', 'rescheduled'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_clinic_appointments_business_idempotency
    ON public.clinic_appointments (business_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_clinic_appointments_org_business_starts
    ON public.clinic_appointments (organization_id, business_id, starts_at);

CREATE INDEX IF NOT EXISTS idx_clinic_appointments_doctor_starts
    ON public.clinic_appointments (doctor_id, starts_at)
    WHERE status IN ('confirmed', 'rescheduled');

DROP TRIGGER IF EXISTS trg_clinic_appointments_set_updated_at ON public.clinic_appointments;
CREATE TRIGGER trg_clinic_appointments_set_updated_at
    BEFORE UPDATE ON public.clinic_appointments
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 12. Enable and FORCE Row Level Security (RLS) on all 11 Clinic Tables
-- ----------------------------------------------------------------------------
ALTER TABLE public.clinic_departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinic_departments FORCE ROW LEVEL SECURITY;

ALTER TABLE public.clinic_doctors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinic_doctors FORCE ROW LEVEL SECURITY;

ALTER TABLE public.clinic_specialities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinic_specialities FORCE ROW LEVEL SECURITY;

ALTER TABLE public.clinic_doctor_departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinic_doctor_departments FORCE ROW LEVEL SECURITY;

ALTER TABLE public.clinic_doctor_specialities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinic_doctor_specialities FORCE ROW LEVEL SECURITY;

ALTER TABLE public.clinic_consultation_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinic_consultation_types FORCE ROW LEVEL SECURITY;

ALTER TABLE public.clinic_doctor_consultation_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinic_doctor_consultation_types FORCE ROW LEVEL SECURITY;

ALTER TABLE public.clinic_doctor_working_hours ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinic_doctor_working_hours FORCE ROW LEVEL SECURITY;

ALTER TABLE public.clinic_doctor_breaks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinic_doctor_breaks FORCE ROW LEVEL SECURITY;

ALTER TABLE public.clinic_doctor_unavailability ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinic_doctor_unavailability FORCE ROW LEVEL SECURITY;

ALTER TABLE public.clinic_appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinic_appointments FORCE ROW LEVEL SECURITY;

-- Configuration Tables (Authenticated org members read; owner/admin write)
-- 1. clinic_departments
DROP POLICY IF EXISTS clinic_departments_select_member ON public.clinic_departments;
CREATE POLICY clinic_departments_select_member ON public.clinic_departments
    FOR SELECT TO authenticated USING (public.is_org_member(organization_id));
DROP POLICY IF EXISTS clinic_departments_insert_owner_or_admin ON public.clinic_departments;
CREATE POLICY clinic_departments_insert_owner_or_admin ON public.clinic_departments
    FOR INSERT TO authenticated WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));
DROP POLICY IF EXISTS clinic_departments_update_owner_or_admin ON public.clinic_departments;
CREATE POLICY clinic_departments_update_owner_or_admin ON public.clinic_departments
    FOR UPDATE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));
DROP POLICY IF EXISTS clinic_departments_delete_owner_or_admin ON public.clinic_departments;
CREATE POLICY clinic_departments_delete_owner_or_admin ON public.clinic_departments
    FOR DELETE TO authenticated USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- 2. clinic_doctors
DROP POLICY IF EXISTS clinic_doctors_select_member ON public.clinic_doctors;
CREATE POLICY clinic_doctors_select_member ON public.clinic_doctors
    FOR SELECT TO authenticated USING (public.is_org_member(organization_id));
DROP POLICY IF EXISTS clinic_doctors_insert_owner_or_admin ON public.clinic_doctors;
CREATE POLICY clinic_doctors_insert_owner_or_admin ON public.clinic_doctors
    FOR INSERT TO authenticated WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));
DROP POLICY IF EXISTS clinic_doctors_update_owner_or_admin ON public.clinic_doctors;
CREATE POLICY clinic_doctors_update_owner_or_admin ON public.clinic_doctors
    FOR UPDATE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));
DROP POLICY IF EXISTS clinic_doctors_delete_owner_or_admin ON public.clinic_doctors;
CREATE POLICY clinic_doctors_delete_owner_or_admin ON public.clinic_doctors
    FOR DELETE TO authenticated USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- 3. clinic_specialities
DROP POLICY IF EXISTS clinic_specialities_select_member ON public.clinic_specialities;
CREATE POLICY clinic_specialities_select_member ON public.clinic_specialities
    FOR SELECT TO authenticated USING (public.is_org_member(organization_id));
DROP POLICY IF EXISTS clinic_specialities_insert_owner_or_admin ON public.clinic_specialities;
CREATE POLICY clinic_specialities_insert_owner_or_admin ON public.clinic_specialities
    FOR INSERT TO authenticated WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));
DROP POLICY IF EXISTS clinic_specialities_update_owner_or_admin ON public.clinic_specialities;
CREATE POLICY clinic_specialities_update_owner_or_admin ON public.clinic_specialities
    FOR UPDATE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));
DROP POLICY IF EXISTS clinic_specialities_delete_owner_or_admin ON public.clinic_specialities;
CREATE POLICY clinic_specialities_delete_owner_or_admin ON public.clinic_specialities
    FOR DELETE TO authenticated USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- 4. clinic_doctor_departments
DROP POLICY IF EXISTS clinic_doctor_departments_select_member ON public.clinic_doctor_departments;
CREATE POLICY clinic_doctor_departments_select_member ON public.clinic_doctor_departments
    FOR SELECT TO authenticated USING (public.is_org_member(organization_id));
DROP POLICY IF EXISTS clinic_doctor_departments_insert_owner_or_admin ON public.clinic_doctor_departments;
CREATE POLICY clinic_doctor_departments_insert_owner_or_admin ON public.clinic_doctor_departments
    FOR INSERT TO authenticated WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));
DROP POLICY IF EXISTS clinic_doctor_departments_delete_owner_or_admin ON public.clinic_doctor_departments;
CREATE POLICY clinic_doctor_departments_delete_owner_or_admin ON public.clinic_doctor_departments
    FOR DELETE TO authenticated USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- 5. clinic_doctor_specialities
DROP POLICY IF EXISTS clinic_doctor_specialities_select_member ON public.clinic_doctor_specialities;
CREATE POLICY clinic_doctor_specialities_select_member ON public.clinic_doctor_specialities
    FOR SELECT TO authenticated USING (public.is_org_member(organization_id));
DROP POLICY IF EXISTS clinic_doctor_specialities_insert_owner_or_admin ON public.clinic_doctor_specialities;
CREATE POLICY clinic_doctor_specialities_insert_owner_or_admin ON public.clinic_doctor_specialities
    FOR INSERT TO authenticated WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));
DROP POLICY IF EXISTS clinic_doctor_specialities_delete_owner_or_admin ON public.clinic_doctor_specialities;
CREATE POLICY clinic_doctor_specialities_delete_owner_or_admin ON public.clinic_doctor_specialities
    FOR DELETE TO authenticated USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- 6. clinic_consultation_types
DROP POLICY IF EXISTS clinic_consultation_types_select_member ON public.clinic_consultation_types;
CREATE POLICY clinic_consultation_types_select_member ON public.clinic_consultation_types
    FOR SELECT TO authenticated USING (public.is_org_member(organization_id));
DROP POLICY IF EXISTS clinic_consultation_types_insert_owner_or_admin ON public.clinic_consultation_types;
CREATE POLICY clinic_consultation_types_insert_owner_or_admin ON public.clinic_consultation_types
    FOR INSERT TO authenticated WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));
DROP POLICY IF EXISTS clinic_consultation_types_update_owner_or_admin ON public.clinic_consultation_types;
CREATE POLICY clinic_consultation_types_update_owner_or_admin ON public.clinic_consultation_types
    FOR UPDATE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));
DROP POLICY IF EXISTS clinic_consultation_types_delete_owner_or_admin ON public.clinic_consultation_types;
CREATE POLICY clinic_consultation_types_delete_owner_or_admin ON public.clinic_consultation_types
    FOR DELETE TO authenticated USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- 7. clinic_doctor_consultation_types
DROP POLICY IF EXISTS clinic_doctor_consultation_select_member ON public.clinic_doctor_consultation_types;
CREATE POLICY clinic_doctor_consultation_select_member ON public.clinic_doctor_consultation_types
    FOR SELECT TO authenticated USING (public.is_org_member(organization_id));
DROP POLICY IF EXISTS clinic_doctor_consultation_insert_owner_or_admin ON public.clinic_doctor_consultation_types;
CREATE POLICY clinic_doctor_consultation_insert_owner_or_admin ON public.clinic_doctor_consultation_types
    FOR INSERT TO authenticated WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));
DROP POLICY IF EXISTS clinic_doctor_consultation_delete_owner_or_admin ON public.clinic_doctor_consultation_types;
CREATE POLICY clinic_doctor_consultation_delete_owner_or_admin ON public.clinic_doctor_consultation_types
    FOR DELETE TO authenticated USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- 8. clinic_doctor_working_hours
DROP POLICY IF EXISTS clinic_doctor_working_hours_select_member ON public.clinic_doctor_working_hours;
CREATE POLICY clinic_doctor_working_hours_select_member ON public.clinic_doctor_working_hours
    FOR SELECT TO authenticated USING (public.is_org_member(organization_id));
DROP POLICY IF EXISTS clinic_doctor_working_hours_insert_owner_or_admin ON public.clinic_doctor_working_hours;
CREATE POLICY clinic_doctor_working_hours_insert_owner_or_admin ON public.clinic_doctor_working_hours
    FOR INSERT TO authenticated WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));
DROP POLICY IF EXISTS clinic_doctor_working_hours_update_owner_or_admin ON public.clinic_doctor_working_hours;
CREATE POLICY clinic_doctor_working_hours_update_owner_or_admin ON public.clinic_doctor_working_hours
    FOR UPDATE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));
DROP POLICY IF EXISTS clinic_doctor_working_hours_delete_owner_or_admin ON public.clinic_doctor_working_hours;
CREATE POLICY clinic_doctor_working_hours_delete_owner_or_admin ON public.clinic_doctor_working_hours
    FOR DELETE TO authenticated USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- 9. clinic_doctor_breaks
DROP POLICY IF EXISTS clinic_doctor_breaks_select_member ON public.clinic_doctor_breaks;
CREATE POLICY clinic_doctor_breaks_select_member ON public.clinic_doctor_breaks
    FOR SELECT TO authenticated USING (public.is_org_member(organization_id));
DROP POLICY IF EXISTS clinic_doctor_breaks_insert_owner_or_admin ON public.clinic_doctor_breaks;
CREATE POLICY clinic_doctor_breaks_insert_owner_or_admin ON public.clinic_doctor_breaks
    FOR INSERT TO authenticated WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));
DROP POLICY IF EXISTS clinic_doctor_breaks_delete_owner_or_admin ON public.clinic_doctor_breaks;
CREATE POLICY clinic_doctor_breaks_delete_owner_or_admin ON public.clinic_doctor_breaks
    FOR DELETE TO authenticated USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- 10. clinic_doctor_unavailability
DROP POLICY IF EXISTS clinic_doctor_unavailability_select_member ON public.clinic_doctor_unavailability;
CREATE POLICY clinic_doctor_unavailability_select_member ON public.clinic_doctor_unavailability
    FOR SELECT TO authenticated USING (public.is_org_member(organization_id));
DROP POLICY IF EXISTS clinic_doctor_unavailability_insert_owner_or_admin ON public.clinic_doctor_unavailability;
CREATE POLICY clinic_doctor_unavailability_insert_owner_or_admin ON public.clinic_doctor_unavailability
    FOR INSERT TO authenticated WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));
DROP POLICY IF EXISTS clinic_doctor_unavailability_delete_owner_or_admin ON public.clinic_doctor_unavailability;
CREATE POLICY clinic_doctor_unavailability_delete_owner_or_admin ON public.clinic_doctor_unavailability
    FOR DELETE TO authenticated USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- 11. clinic_appointments (Authenticated org members only — NEVER anonymous access to patient contacts)
DROP POLICY IF EXISTS clinic_appointments_select_member ON public.clinic_appointments;
CREATE POLICY clinic_appointments_select_member ON public.clinic_appointments
    FOR SELECT TO authenticated USING (public.is_org_member(organization_id));
DROP POLICY IF EXISTS clinic_appointments_insert_member ON public.clinic_appointments;
CREATE POLICY clinic_appointments_insert_member ON public.clinic_appointments
    FOR INSERT TO authenticated WITH CHECK (public.is_org_member(organization_id));
DROP POLICY IF EXISTS clinic_appointments_update_member ON public.clinic_appointments;
CREATE POLICY clinic_appointments_update_member ON public.clinic_appointments
    FOR UPDATE TO authenticated
    USING (public.is_org_member(organization_id))
    WITH CHECK (public.is_org_member(organization_id));
DROP POLICY IF EXISTS clinic_appointments_delete_owner_or_admin ON public.clinic_appointments;
CREATE POLICY clinic_appointments_delete_owner_or_admin ON public.clinic_appointments
    FOR DELETE TO authenticated USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

COMMIT;
