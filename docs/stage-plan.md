# SVARIO — Staged Delivery Plan

**Current Active Milestone:** **STAGE 5 — SALON WORKFLOW MODULE**  
**Status:** Complete (Awaiting Approval to Proceed to Stage 6)

---

## Overview of Stages

### Stage 0 — Product Foundation (Completed & Approved)
- Established monorepo (`apps/web`, `apps/api`, `docs`, `infra`), official Svario brand design tokens, FastAPI `/health` and `/architecture` endpoints, and multi-industry architectural boundaries for Salons, Clinics, and Hospitals.

---

### Stage 1 — Core Data, Multi-Tenant Authentication & Organization Foundation (Completed & Approved)
- Implemented Supabase PostgreSQL core schema (`profiles`, `organizations`, `organization_members`, `businesses`, `business_settings`, `business_hours`, `audit_logs`), forced RLS policies, Supabase Auth flows, FastAPI cryptographic JWT verification, and organization RBAC endpoints.

---

### Stage 2 — Industry Selection & Business Onboarding (Completed & Approved)
- Implemented Stage 2 onboarding tables (`business_profiles`, `business_languages`, `business_faqs`, `assistant_settings`, `escalation_settings`, `onboarding_progress`), forced RLS policies, `/api/v1/organizations/{organization_id}/onboarding/*` APIs, and the 8-step `/onboarding` wizard.

---

### Stage 3 — Shared Browser Voice Infrastructure (Completed & Approved)
- Implemented shared browser WebRTC voice infrastructure powered by OpenAI Realtime API (`POST /v1/realtime/client_secrets` with `gpt-realtime`), `POST /api/v1/voice/sessions`, `SvarioWebRtcVoiceClient` with a 10-state machine, and `/voice-test`.

---

### Stage 4 — AI Agent & Conversational Intelligence (Completed & Approved)
- Implemented modular multi-industry AI agent intelligence, typed intent classification, grounded business knowledge retrieval, session-scoped context, controlled backend tool execution, human escalation workflows, and multilingual support (`en`, `hi`, `hinglish`).

---

### Stage 5 — Salon Workflow Module (Current Milestone — Complete)
- **Objective:** Implement complete end-to-end salon appointment scheduling, service catalog CRUD, staff rosters and service assignments, weekly working schedules, breaks, whole-salon holidays and closures, dynamic non-conflicting slot availability calculation, transactional appointment booking with GiST double-booking protection and idempotency, AI voice agent salon tools, and interactive frontend operations dashboard.
- **Completed Deliverables:**
  - **A. Salon Services (`public.salon_services`):** Name, category, price (> 0), duration (5-480 min), active/inactive flag. Owner/Admin only modification.
  - **B. Staff Management (`public.salon_staff`, `public.salon_staff_services`):** Stylist profiles, active flag, many-to-many service assignments.
  - **C. Working Schedules & Breaks (`public.salon_staff_working_hours`, `public.salon_staff_breaks`, `public.salon_holidays`):** Weekly stylist shifts, recurring/date-specific breaks, whole-day/partial salon closures and staff leaves.
  - **D. Dynamic Availability Calculation Engine:** Real-time computation respecting salon hours, stylist shifts, break intervals, whole/partial closures, and existing appointments.
  - **E. Appointment Management (`public.salon_appointments`):** Double-booking prevention via PostgreSQL `btree_gist` exclusion constraint `excl_salon_appointments_no_staff_overlap`, idempotency key replay, lifecycle transitions (`confirmed`, `rescheduled`, `cancelled`, `completed`, `no_show`).
  - **F. AI Voice Agent Salon Tools:** 6 structured tools (`get_salon_services`, `get_salon_staff`, `check_salon_availability`, `create_salon_appointment`, `reschedule_salon_appointment`, `cancel_salon_appointment`), strict server-side context resolution, no trusted model tenant IDs.
  - **G. Frontend Salon Dashboard View (`SalonDashboardView.tsx`):** Services catalog, stylist roster, calendar/booking manager, and live slot availability calculator.
  - **H. Security & RLS:** 7 Supabase tables with `ENABLE ROW LEVEL SECURITY` and forced RLS, strict organization isolation.
  - **I. Verification & Testing:** 55 backend tests (`pytest apps/api/tests -q`), 23 frontend tests (`vitest run`), Next.js 15 production build.
- **Explicitly Excluded from Stage 5:**
  - Clinic doctor consultation booking or hospital OPD department workflows (`Stage 6+`).
