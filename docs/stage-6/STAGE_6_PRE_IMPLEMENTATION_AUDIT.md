# SVARIO — STAGE 6 PRE-IMPLEMENTATION AUDIT

**Milestone:** Stage 6 — Clinic Workflow Module  
**Date:** 2026-11-16  
**Auditor:** AgentX Engineering  
**Base Commit Verified:** `855b994` (`feat(salon): implement Stage 5 salon workflow module, tools, and UI`)

---

## 1. Repository & Git State Verification

- **Current Branch:** `main`
- **Current HEAD:** `855b994` (ahead of `origin/main` by 3 commits)
- **Stage 5 Commit Status:** Verified present in git history (`855b994`).
- **Working Tree Status:** Clean (`nothing to commit, working tree clean`). No unexpected uncommitted changes or conflicting untracked files.
- **Migration Sequence:**
  1. `20261103000001_stage1_core_schema.sql`
  2. `20261103000002_stage1_rls_policies.sql`
  3. `20261108000003_stage2_onboarding_schema.sql`
  4. `20261108000004_stage2_onboarding_rls.sql`
  5. `20261110000005_stage4_agent_tables_and_rls.sql`
  6. `20261110000006_stage5_salon_workflow_and_rls.sql`
  - **Next Sequential Migration:** `20261116000007_stage6_clinic_workflow_and_rls.sql`

---

## 2. Existing Architecture & Reusable Components

### Stage 1 & 2 (Core Auth, Multi-Tenancy, Onboarding)
- **Auth & JWT:** `apps/api/app/core/auth.py` validates Supabase JWTs (`ES256`/`RS256`/`EdDSA`/`HS256`) and provides `AuthenticatedUser`.
- **Tenant Isolation:** Composite foreign keys `(business_id, organization_id)` referencing `public.businesses(id, organization_id)` prevent cross-tenant linking at the DB level.
- **RLS Helper Functions:** `public.is_org_member(organization_id)` and `public.has_org_role(organization_id, ARRAY['owner', 'admin'])` are deployed in Supabase and can be directly reused for all clinic tables.
- **Trigger Helper:** `public.set_updated_at()` is deployed and reusable for `updated_at` maintenance.

### Stage 4 (AI Agent & Conversational Intelligence)
- **Industry Agent:** `apps/api/app/agents/industries/clinic.py` (`ClinicAgent`) already exists with `is_healthcare_vertical = True`, strict non-diagnostic guardrails, and multilingual emergency responses (`en`, `hi`, `hinglish`).
- **Orchestrator:** `apps/api/app/agents/orchestrator.py` (`AgentOrchestrator`) handles intent classification, safety flags (`CLINICAL_DIAGNOSIS_REQUEST`, `PRESCRIPTION_OR_MEDICATION_REQUEST`, `TREATMENT_RECOMMENDATION_REQUEST`, `MEDICAL_EMERGENCY_DETECTED`), per-turn tool limits, and tool dispatch.
- **Tool Definitions & Schemas:** `apps/api/app/agents/schemas.py` and `apps/api/app/agents/instructions.py` enforce `ConfigDict(extra="forbid")` and strip/reject model-supplied `organization_id`/`business_id`.
- **Summary Redaction:** `redact_sensitive_summary_text(..., is_healthcare=True)` in `apps/api/app/agents/context.py` redacts sensitive clinical or contact details.

### Stage 5 (Salon Workflow Patterns)
- **Concurrency & Scheduling Pattern:** PostgreSQL `btree_gist` extension is already enabled in Supabase. Half-open range `tstzrange(starts_at, ends_at, '[)')` with `EXCLUDE USING gist` prevents double-booking at the database layer.
- **Service/Repository Pattern:** `Protocol`-based repository with `InMemoryClinicRepository` (for fast unit/integration tests and local fallback) + strict tenant verification in `ClinicWorkflowService`.
- **Voice Session Actor Pattern:** Internal trusted voice agent sessions (`https://svario.internal/auth/v1`) are allowed to read discovery endpoints and execute customer-facing bookings/reschedules/cancellations while being blocked from administrative mutations (`POST`/`PATCH` departments, doctors, specialities, etc.).

---

## 3. Security Gaps & Mitigations for Stage 6

| Potential Risk | Mitigation in Stage 6 Design |
| :--- | :--- |
| **Anonymous/Public exposure of Patient Contact Info** | Never allow `anon` SELECT on `clinic_appointments`. All RLS policies on clinic tables restrict reads/writes to `authenticated` org members (`is_org_member`), and mutations to `owner`/`admin` where appropriate. |
| **Unverified Reschedule / Cancellation via Voice** | Require both `booking_reference` AND caller verification (`patient_contact` suffix or full contact match) before rescheduling or cancelling via AI tool, and never disclose appointment existence if verification fails. |
| **Medical Advice / Diagnosis Creep** | Enforce strict `ClinicAgent` directives + `IntentClassifier` safety flags. Emergency intent immediately bypasses booking and outputs emergency services redirection. |
| **Cross-Tenant Foreign Key Spoofing** | Every join/mapping table uses composite FKs `(target_id, business_id, organization_id)` referencing parent tables' `UNIQUE (id, business_id, organization_id)`. |
| **Overlapping Doctor Appointments** | Enforce `EXCLUDE USING gist (doctor_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&) WHERE (status IN ('confirmed', 'rescheduled'))` in Postgres and recheck in repository transaction. |

---

## 4. Proposed Clinic-Specific Design & Files Expected to Change

### New Files
- `supabase/migrations/20261116000007_stage6_clinic_workflow_and_rls.sql`
- `apps/api/app/modules/clinics/schemas.py`
- `apps/api/app/modules/clinics/repository.py`
- `apps/api/app/modules/clinics/service.py`
- `apps/api/app/routes/clinics.py`
- `apps/api/app/agents/tools/clinic_tools.py`
- `apps/api/tests/test_stage6_clinic.py`
- `apps/web/src/types/clinic.ts`
- `apps/web/src/components/dashboard/ClinicDashboardView.tsx`
- `apps/web/src/__tests__/stage6-clinic.test.tsx`
- `docs/stage-6/*` (6 required Stage 6 documents)

### Modified Files
- `apps/api/app/routes/__init__.py` (register `clinics_router`)
- `apps/api/app/agents/schemas.py` (add 10 clinic tools + clinic intents/inputs/outputs)
- `apps/api/app/agents/intent.py` (support clinic administrative intents while preserving salon/general intents)
- `apps/api/app/agents/industries/clinic.py` (enable Stage 6 administrative booking directives & allowed tools)
- `apps/api/app/agents/instructions.py` (register clinic Realtime tool definitions)
- `apps/api/app/agents/tools/__init__.py` (export 10 clinic tool handlers)
- `apps/api/app/agents/orchestrator.py` (wire `clinic_service` and dispatch 10 clinic tools)
- `apps/web/src/lib/api.ts` (add typed clinic API client methods)
- `apps/web/src/app/dashboard/page.tsx` (render `ClinicDashboardView` when `industry === "clinic"`)
- `docs/stage-plan.md` (update Stage 6 status after verification)

---

## 5. Stop Gate A Assessment

- Stage 1–5 foundations, JWT auth, tenant isolation, RLS, and agent pipeline are **healthy and verified** (`55` backend tests, `23` frontend tests passing on base commit `855b994`).
- **Decision:** **PROCEED** to Phase B & C.
