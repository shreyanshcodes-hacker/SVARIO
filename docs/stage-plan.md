# SVARIO — Staged Delivery Plan

**Current Active Milestone:** **STAGE 2 — INDUSTRY SELECTION & BUSINESS ONBOARDING**  
**Status:** Complete (Awaiting Approval to Proceed to Stage 3)

---

## Overview of Stages

### Stage 0 — Product Foundation (Completed & Approved)
- Established monorepo (`apps/web`, `apps/api`, `docs`, `infra`), official Svario brand design tokens, FastAPI `/health` and `/architecture` endpoints, and multi-industry architectural boundaries for Salons, Clinics, and Hospitals.

---

### Stage 1 — Core Data, Multi-Tenant Authentication & Organization Foundation (Completed & Approved)
- Implemented Supabase PostgreSQL core schema (`profiles`, `organizations`, `organization_members`, `businesses`, `business_settings`, `business_hours`, `audit_logs`), forced RLS policies, Supabase Auth flows, FastAPI cryptographic JWT verification, and organization RBAC endpoints.

---

### Stage 2 — Industry Selection & Business Onboarding (Current Milestone — Complete)
- **Objective:** Implement organization-scoped industry selection and multi-step business onboarding for Salons, Clinics, and Hospitals.
- **Completed Deliverables:**
  - **Supabase Migrations (`supabase/migrations/`):**
    - `20261108000003_stage2_onboarding_schema.sql`: Extends `business_hours` (`is_overnight`) and creates `business_profiles`, `business_languages`, `business_faqs`, `assistant_settings`, `escalation_settings`, and `onboarding_progress` with UUID PKs, composite foreign keys `(business_id, organization_id)`, unique constraints, and `updated_at` triggers.
    - `20261108000004_stage2_onboarding_rls.sql`: Enables and forces RLS on all 6 new Stage 2 tables with strict `is_org_member` and `has_org_role` policies.
  - **Backend Onboarding APIs (`apps/api`):**
    - Organization-scoped endpoints under `/api/v1/organizations/{organization_id}/onboarding/*` for industry selection, business profile, weekly hours, languages (`en | hi | hinglish`), assistant settings, FAQ CRUD + starter templates, human escalation + healthcare safeguards, and onboarding progress persistence.
  - **Frontend Onboarding Wizard & Dashboard Integration (`apps/web`):**
    - Protected `/onboarding` 8-step wizard with progress bar, step navigation, save & continue later, validation, and completion redirect.
    - Updated `/dashboard` displaying organization name, industry, business profile summary, operating hours, supported languages, assistant configuration status, onboarding completion status, and edit/continue onboarding actions.
- **Explicitly Excluded from Stage 2:**
  - Live OpenAI Realtime voice agent calls (`Stage 3+`)
  - Appointment booking, salon service menus, clinic doctor schedules, or hospital department directories (`Stage 3+`)
  - Analytics dashboards or WhatsApp/external messaging adapters (`Stage 4+`)

---

### Stage 3 — Domain Catalog, Scheduling & Voice Runtime Integration (Planned Next)
- **Objective:** Build industry-specific service/practitioner/department scheduling and connect the voice agent runtime.
