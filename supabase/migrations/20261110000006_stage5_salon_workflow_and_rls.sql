-- ============================================================================
-- SVARIO — STAGE 5: SALON WORKFLOW MODULE SCHEMA, CONCURRENCY & RLS
-- Migration: 20261110000006_stage5_salon_workflow_and_rls.sql
-- Purpose:
--   1. Create public.salon_services for salon service catalog CRUD.
--   2. Create public.salon_staff and public.salon_staff_services for staff
--      profiles and staff-service assignments.
--   3. Create public.salon_staff_working_hours, public.salon_staff_breaks, and
--      public.salon_holidays for weekly staff schedules, breaks, and closures.
--   4. Create public.salon_appointments with idempotency keys and a GiST
--      exclusion constraint to prevent double-booking under concurrent load.
--   5. Enforce composite foreign keys (business_id, organization_id) ->
--      public.businesses(id, organization_id) and enable + force Row Level
--      Security (RLS) across all 7 Stage 5 salon tables.
-- ============================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ----------------------------------------------------------------------------
-- 1. public.salon_services
--    Salon treatment & service catalog scoped to (organization_id, business_id).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.salon_services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    price NUMERIC(10, 2) NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    duration_minutes INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_salon_services_id_business_org
        UNIQUE (id, business_id, organization_id),
    CONSTRAINT fk_salon_services_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_salon_services_name_len
        CHECK (char_length(btrim(name)) BETWEEN 2 AND 120),
    CONSTRAINT chk_salon_services_category_len
        CHECK (char_length(btrim(category)) BETWEEN 2 AND 80),
    CONSTRAINT chk_salon_services_price_range
        CHECK (price >= 0 AND price <= 1000000),
    CONSTRAINT chk_salon_services_currency_len
        CHECK (char_length(btrim(currency)) = 3),
    CONSTRAINT chk_salon_services_duration_range
        CHECK (duration_minutes BETWEEN 5 AND 480)
);

CREATE INDEX IF NOT EXISTS idx_salon_services_org_business
    ON public.salon_services (organization_id, business_id);

CREATE INDEX IF NOT EXISTS idx_salon_services_business_org_active
    ON public.salon_services (business_id, organization_id, is_active);

DROP TRIGGER IF EXISTS trg_salon_services_set_updated_at ON public.salon_services;
CREATE TRIGGER trg_salon_services_set_updated_at
    BEFORE UPDATE ON public.salon_services
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 2. public.salon_staff
--    Stylists and specialists scoped to (organization_id, business_id).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.salon_staff (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    role_designation TEXT NOT NULL DEFAULT 'Stylist',
    email TEXT NULL,
    phone TEXT NULL,
    bio TEXT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_salon_staff_id_business_org
        UNIQUE (id, business_id, organization_id),
    CONSTRAINT fk_salon_staff_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_salon_staff_full_name_len
        CHECK (char_length(btrim(full_name)) BETWEEN 2 AND 120),
    CONSTRAINT chk_salon_staff_role_len
        CHECK (char_length(btrim(role_designation)) BETWEEN 2 AND 80)
);

CREATE INDEX IF NOT EXISTS idx_salon_staff_org_business
    ON public.salon_staff (organization_id, business_id);

CREATE INDEX IF NOT EXISTS idx_salon_staff_business_org_active
    ON public.salon_staff (business_id, organization_id, is_active);

DROP TRIGGER IF EXISTS trg_salon_staff_set_updated_at ON public.salon_staff;
CREATE TRIGGER trg_salon_staff_set_updated_at
    BEFORE UPDATE ON public.salon_staff
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 3. public.salon_staff_services
--    Many-to-many join assigning salon services to qualified staff members.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.salon_staff_services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    staff_id UUID NOT NULL,
    service_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_salon_staff_services_assignment
        UNIQUE (business_id, staff_id, service_id),
    CONSTRAINT fk_salon_staff_services_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_salon_staff_services_staff
        FOREIGN KEY (staff_id, business_id, organization_id)
        REFERENCES public.salon_staff(id, business_id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_salon_staff_services_service
        FOREIGN KEY (service_id, business_id, organization_id)
        REFERENCES public.salon_services(id, business_id, organization_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_salon_staff_services_org_business
    ON public.salon_staff_services (organization_id, business_id);

CREATE INDEX IF NOT EXISTS idx_salon_staff_services_service_staff
    ON public.salon_staff_services (business_id, service_id, staff_id);

-- ----------------------------------------------------------------------------
-- 4. public.salon_staff_working_hours
--    Weekly working schedule per staff member (0=Sunday .. 6=Saturday).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.salon_staff_working_hours (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    staff_id UUID NOT NULL,
    weekday SMALLINT NOT NULL,
    is_off BOOLEAN NOT NULL DEFAULT FALSE,
    start_time TIME NULL,
    end_time TIME NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_salon_staff_working_hours_staff_weekday
        UNIQUE (staff_id, weekday),
    CONSTRAINT fk_salon_staff_working_hours_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_salon_staff_working_hours_staff
        FOREIGN KEY (staff_id, business_id, organization_id)
        REFERENCES public.salon_staff(id, business_id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_salon_staff_working_hours_weekday
        CHECK (weekday BETWEEN 0 AND 6),
    CONSTRAINT chk_salon_staff_working_hours_consistency
        CHECK (
            is_off = TRUE
            OR (start_time IS NOT NULL AND end_time IS NOT NULL AND start_time < end_time)
        )
);

CREATE INDEX IF NOT EXISTS idx_salon_staff_working_hours_org_business
    ON public.salon_staff_working_hours (organization_id, business_id, staff_id);

DROP TRIGGER IF EXISTS trg_salon_staff_working_hours_set_updated_at ON public.salon_staff_working_hours;
CREATE TRIGGER trg_salon_staff_working_hours_set_updated_at
    BEFORE UPDATE ON public.salon_staff_working_hours
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 5. public.salon_staff_breaks
--    Recurring weekly or date-specific break windows per staff member.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.salon_staff_breaks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    staff_id UUID NOT NULL,
    weekday SMALLINT NULL,
    specific_date DATE NULL,
    label TEXT NOT NULL DEFAULT 'Break',
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_salon_staff_breaks_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_salon_staff_breaks_staff
        FOREIGN KEY (staff_id, business_id, organization_id)
        REFERENCES public.salon_staff(id, business_id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_salon_staff_breaks_weekday
        CHECK (weekday IS NULL OR (weekday BETWEEN 0 AND 6)),
    CONSTRAINT chk_salon_staff_breaks_target_required
        CHECK (weekday IS NOT NULL OR specific_date IS NOT NULL),
    CONSTRAINT chk_salon_staff_breaks_time_order
        CHECK (start_time < end_time)
);

CREATE INDEX IF NOT EXISTS idx_salon_staff_breaks_org_business_staff
    ON public.salon_staff_breaks (organization_id, business_id, staff_id);

-- ----------------------------------------------------------------------------
-- 6. public.salon_holidays
--    Whole-salon holidays/special closures (staff_id IS NULL) or staff leave.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.salon_holidays (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    staff_id UUID NULL,
    holiday_date DATE NOT NULL,
    title TEXT NOT NULL,
    is_closed_all_day BOOLEAN NOT NULL DEFAULT TRUE,
    start_time TIME NULL,
    end_time TIME NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_salon_holidays_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_salon_holidays_staff
        FOREIGN KEY (staff_id, business_id, organization_id)
        REFERENCES public.salon_staff(id, business_id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT chk_salon_holidays_title_len
        CHECK (char_length(btrim(title)) BETWEEN 2 AND 120),
    CONSTRAINT chk_salon_holidays_time_consistency
        CHECK (
            is_closed_all_day = TRUE
            OR (start_time IS NOT NULL AND end_time IS NOT NULL AND start_time < end_time)
        )
);

CREATE INDEX IF NOT EXISTS idx_salon_holidays_org_business_date
    ON public.salon_holidays (organization_id, business_id, holiday_date);

-- ----------------------------------------------------------------------------
-- 7. public.salon_appointments
--    Salon bookings with idempotency and GiST exclusion double-booking guard.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.salon_appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
    booking_reference TEXT NOT NULL,
    idempotency_key TEXT NULL,
    service_id UUID NOT NULL,
    staff_id UUID NOT NULL,
    customer_name TEXT NOT NULL,
    customer_phone TEXT NOT NULL,
    customer_email TEXT NULL,
    notes TEXT NULL,
    appointment_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    status TEXT NOT NULL DEFAULT 'confirmed',
    source TEXT NOT NULL DEFAULT 'dashboard',
    cancelled_at TIMESTAMPTZ NULL,
    cancellation_reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_salon_appointments_reference
        UNIQUE (booking_reference),
    CONSTRAINT fk_salon_appointments_org_business
        FOREIGN KEY (business_id, organization_id)
        REFERENCES public.businesses(id, organization_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_salon_appointments_service
        FOREIGN KEY (service_id, business_id, organization_id)
        REFERENCES public.salon_services(id, business_id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_salon_appointments_staff
        FOREIGN KEY (staff_id, business_id, organization_id)
        REFERENCES public.salon_staff(id, business_id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT chk_salon_appointments_customer_name_len
        CHECK (char_length(btrim(customer_name)) BETWEEN 2 AND 120),
    CONSTRAINT chk_salon_appointments_customer_phone_len
        CHECK (char_length(btrim(customer_phone)) BETWEEN 6 AND 32),
    CONSTRAINT chk_salon_appointments_status
        CHECK (status IN ('confirmed', 'rescheduled', 'cancelled', 'completed', 'no_show')),
    CONSTRAINT chk_salon_appointments_source
        CHECK (source IN ('dashboard', 'voice_agent', 'api')),
    CONSTRAINT chk_salon_appointments_time_order
        CHECK (start_time < end_time AND start_at < end_at),
    CONSTRAINT excl_salon_appointments_no_staff_overlap
        EXCLUDE USING gist (
            staff_id WITH =,
            tstzrange(start_at, end_at, '[)') WITH &&
        )
        WHERE (status IN ('confirmed', 'rescheduled'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_salon_appointments_business_idempotency
    ON public.salon_appointments (business_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_salon_appointments_org_business_date
    ON public.salon_appointments (organization_id, business_id, appointment_date, start_time);

CREATE INDEX IF NOT EXISTS idx_salon_appointments_staff_date
    ON public.salon_appointments (staff_id, appointment_date)
    WHERE status IN ('confirmed', 'rescheduled');

DROP TRIGGER IF EXISTS trg_salon_appointments_set_updated_at ON public.salon_appointments;
CREATE TRIGGER trg_salon_appointments_set_updated_at
    BEFORE UPDATE ON public.salon_appointments
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- ----------------------------------------------------------------------------
-- 8. Enable and Force Row Level Security (RLS) on all 7 Stage 5 Salon Tables
-- ----------------------------------------------------------------------------
ALTER TABLE public.salon_services ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.salon_services FORCE ROW LEVEL SECURITY;

ALTER TABLE public.salon_staff ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.salon_staff FORCE ROW LEVEL SECURITY;

ALTER TABLE public.salon_staff_services ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.salon_staff_services FORCE ROW LEVEL SECURITY;

ALTER TABLE public.salon_staff_working_hours ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.salon_staff_working_hours FORCE ROW LEVEL SECURITY;

ALTER TABLE public.salon_staff_breaks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.salon_staff_breaks FORCE ROW LEVEL SECURITY;

ALTER TABLE public.salon_holidays ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.salon_holidays FORCE ROW LEVEL SECURITY;

ALTER TABLE public.salon_appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.salon_appointments FORCE ROW LEVEL SECURITY;

-- Policies for public.salon_services (All org members can read; owner/admin can write)
DROP POLICY IF EXISTS salon_services_select_member ON public.salon_services;
CREATE POLICY salon_services_select_member
    ON public.salon_services FOR SELECT TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS salon_services_insert_owner_or_admin ON public.salon_services;
CREATE POLICY salon_services_insert_owner_or_admin
    ON public.salon_services FOR INSERT TO authenticated
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS salon_services_update_owner_or_admin ON public.salon_services;
CREATE POLICY salon_services_update_owner_or_admin
    ON public.salon_services FOR UPDATE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS salon_services_delete_owner_or_admin ON public.salon_services;
CREATE POLICY salon_services_delete_owner_or_admin
    ON public.salon_services FOR DELETE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- Policies for public.salon_staff
DROP POLICY IF EXISTS salon_staff_select_member ON public.salon_staff;
CREATE POLICY salon_staff_select_member
    ON public.salon_staff FOR SELECT TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS salon_staff_insert_owner_or_admin ON public.salon_staff;
CREATE POLICY salon_staff_insert_owner_or_admin
    ON public.salon_staff FOR INSERT TO authenticated
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS salon_staff_update_owner_or_admin ON public.salon_staff;
CREATE POLICY salon_staff_update_owner_or_admin
    ON public.salon_staff FOR UPDATE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS salon_staff_delete_owner_or_admin ON public.salon_staff;
CREATE POLICY salon_staff_delete_owner_or_admin
    ON public.salon_staff FOR DELETE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- Policies for public.salon_staff_services
DROP POLICY IF EXISTS salon_staff_services_select_member ON public.salon_staff_services;
CREATE POLICY salon_staff_services_select_member
    ON public.salon_staff_services FOR SELECT TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS salon_staff_services_insert_owner_or_admin ON public.salon_staff_services;
CREATE POLICY salon_staff_services_insert_owner_or_admin
    ON public.salon_staff_services FOR INSERT TO authenticated
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS salon_staff_services_update_owner_or_admin ON public.salon_staff_services;
CREATE POLICY salon_staff_services_update_owner_or_admin
    ON public.salon_staff_services FOR UPDATE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS salon_staff_services_delete_owner_or_admin ON public.salon_staff_services;
CREATE POLICY salon_staff_services_delete_owner_or_admin
    ON public.salon_staff_services FOR DELETE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- Policies for public.salon_staff_working_hours
DROP POLICY IF EXISTS salon_staff_working_hours_select_member ON public.salon_staff_working_hours;
CREATE POLICY salon_staff_working_hours_select_member
    ON public.salon_staff_working_hours FOR SELECT TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS salon_staff_working_hours_insert_owner_or_admin ON public.salon_staff_working_hours;
CREATE POLICY salon_staff_working_hours_insert_owner_or_admin
    ON public.salon_staff_working_hours FOR INSERT TO authenticated
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS salon_staff_working_hours_update_owner_or_admin ON public.salon_staff_working_hours;
CREATE POLICY salon_staff_working_hours_update_owner_or_admin
    ON public.salon_staff_working_hours FOR UPDATE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS salon_staff_working_hours_delete_owner_or_admin ON public.salon_staff_working_hours;
CREATE POLICY salon_staff_working_hours_delete_owner_or_admin
    ON public.salon_staff_working_hours FOR DELETE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- Policies for public.salon_staff_breaks
DROP POLICY IF EXISTS salon_staff_breaks_select_member ON public.salon_staff_breaks;
CREATE POLICY salon_staff_breaks_select_member
    ON public.salon_staff_breaks FOR SELECT TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS salon_staff_breaks_insert_owner_or_admin ON public.salon_staff_breaks;
CREATE POLICY salon_staff_breaks_insert_owner_or_admin
    ON public.salon_staff_breaks FOR INSERT TO authenticated
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS salon_staff_breaks_update_owner_or_admin ON public.salon_staff_breaks;
CREATE POLICY salon_staff_breaks_update_owner_or_admin
    ON public.salon_staff_breaks FOR UPDATE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS salon_staff_breaks_delete_owner_or_admin ON public.salon_staff_breaks;
CREATE POLICY salon_staff_breaks_delete_owner_or_admin
    ON public.salon_staff_breaks FOR DELETE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- Policies for public.salon_holidays
DROP POLICY IF EXISTS salon_holidays_select_member ON public.salon_holidays;
CREATE POLICY salon_holidays_select_member
    ON public.salon_holidays FOR SELECT TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS salon_holidays_insert_owner_or_admin ON public.salon_holidays;
CREATE POLICY salon_holidays_insert_owner_or_admin
    ON public.salon_holidays FOR INSERT TO authenticated
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS salon_holidays_update_owner_or_admin ON public.salon_holidays;
CREATE POLICY salon_holidays_update_owner_or_admin
    ON public.salon_holidays FOR UPDATE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']))
    WITH CHECK (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

DROP POLICY IF EXISTS salon_holidays_delete_owner_or_admin ON public.salon_holidays;
CREATE POLICY salon_holidays_delete_owner_or_admin
    ON public.salon_holidays FOR DELETE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

-- Policies for public.salon_appointments (Members can view/create/update appointments; owner/admin can delete)
DROP POLICY IF EXISTS salon_appointments_select_member ON public.salon_appointments;
CREATE POLICY salon_appointments_select_member
    ON public.salon_appointments FOR SELECT TO authenticated
    USING (public.is_org_member(organization_id));

DROP POLICY IF EXISTS salon_appointments_insert_member ON public.salon_appointments;
CREATE POLICY salon_appointments_insert_member
    ON public.salon_appointments FOR INSERT TO authenticated
    WITH CHECK (public.is_org_member(organization_id));

DROP POLICY IF EXISTS salon_appointments_update_member ON public.salon_appointments;
CREATE POLICY salon_appointments_update_member
    ON public.salon_appointments FOR UPDATE TO authenticated
    USING (public.is_org_member(organization_id))
    WITH CHECK (public.is_org_member(organization_id));

DROP POLICY IF EXISTS salon_appointments_delete_owner_or_admin ON public.salon_appointments;
CREATE POLICY salon_appointments_delete_owner_or_admin
    ON public.salon_appointments FOR DELETE TO authenticated
    USING (public.has_org_role(organization_id, ARRAY['owner', 'admin']));

COMMIT;
