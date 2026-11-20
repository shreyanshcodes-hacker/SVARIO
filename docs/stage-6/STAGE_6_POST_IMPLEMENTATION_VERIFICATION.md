# SVARIO — STAGE 6 POST-IMPLEMENTATION VERIFICATION REPORT
## Persistence, RLS, Realtime Voice and Deployment Readiness

**Auditor Role:** Independent Senior Software Auditor and Security Engineer  
**Date:** 2026-11-20  
**Stage Audited:** Stage 6 — Clinic Workflow Module  
**Reported Commit:** `403b914`  
**Previous Baseline:** `855b994`  
**Final Verdict:** **NOT VERIFIED — CRITICAL DEFECTS FOUND**

---

## 1. Git Baseline (Check 1)

- **Branch:** `main`
- **HEAD Commit:** `403b914` (`feat(clinic): implement Stage 6 clinic workflow module`)
- **Commit `403b914` Exists:** Verified (`git cat-file -t 403b914` -> `commit`).
- **Previous Baseline `855b994`:** Verified as immediate parent (`855b994 feat(salon): implement Stage 5 salon workflow module, tools, and UI`).
- **Working Tree Status (prior to creating this report):** Clean (`git status --short` returned empty).
- **Stage 6 Migration:** `supabase/migrations/20261116000007_stage6_clinic_workflow_and_rls.sql` exists (`True`).
- **Stage 6 Documentation (`docs/stage-6/`):** All 6 expected files exist (`CLINIC_API_REFERENCE.md`, `CLINIC_DOMAIN_DESIGN.md`, `CLINIC_SAFETY_AND_PRIVACY.md`, `STAGE_6_COMPLETION_REPORT.md`, `STAGE_6_PRE_IMPLEMENTATION_AUDIT.md`, `STAGE_6_TEST_REPORT.md`).

---

## 2. Repository Selection Findings (Check 2 — BLOCKER)

Direct inspection of `apps/api/app/modules/clinics/repository.py`, `apps/api/app/modules/clinics/service.py`, `apps/api/app/routes/clinics.py`, and `apps/api/app/core/config.py`:

| Question | Verified Answer & Exact Reference |
| :--- | :--- |
| 1. Which repository does the clinic API use by default? | `InMemoryClinicRepository` (`apps/api/app/modules/clinics/service.py:71, 1141-1145`). Runtime probe confirmed `DEFAULT_REPO_TYPE: InMemoryClinicRepository`, `IS_IN_MEMORY: True`. |
| 2. Which repository is selected in production? | **`InMemoryClinicRepository` — BLOCKER.** `get_clinic_workflow_service()` (`service.py:1123-1146`) accepts `settings: Settings = Depends(get_settings)` but **never reads `settings.is_live_supabase_configured`, `settings.svario_env`, or `settings.database_url`**. |
| 3. Is a real Supabase/PostgreSQL implementation complete? | **No.** `apps/api/app/modules/clinics/repository.py` only defines `ClinicRepositoryProtocol` and `InMemoryClinicRepository`. There is no `SupabaseRestClinicRepository` or `PostgresClinicRepository`. |
| 4. Does the repository execute real SQL/database operations? | **No.** All reads/writes operate on Python dictionaries (`self._departments`, `self._doctors`, `self._appointments`, etc.) guarded only by an in-process `asyncio.Lock`. |
| 5. Are clinic writes persisted across application restarts? | **No.** Restarting the process or creating a fresh `ClinicWorkflowService()` instance starts with empty in-memory dicts; all clinic appointments and configurations are lost. |
| 6. Is the repository selected through a secure configuration mechanism? | **No.** Unlike `get_organization_repository()` (`apps/api/app/modules/organizations/service.py:31-37`), which selects `SupabaseRestOrganizationRepository` when `settings.is_live_supabase_configured` is `True`, `get_clinic_workflow_service()` hardcodes `InMemoryClinicRepository()`. |
| 7. Can production accidentally fall back to an in-memory repository? | **Yes — it always uses in-memory.** Furthermore, even in `organizations/service.py`, there is no fail-closed guard refusing `InMemory*Repository` when `SVARIO_ENV=production` and Supabase config is missing. |
| 8. Are missing database configuration values handled safely? | **No.** Missing `DATABASE_URL` or Supabase credentials do not raise a startup error in production; the API silently serves ephemeral in-memory state. |

*(Note: No `render.yaml` exists in the repository; deployment is currently defined only via `Dockerfile`, `apps/api/Dockerfile`, and `docker-compose.yml`.)*

---

## 3. Real Database Persistence Findings (Check 2)

- **Status:** **FAILED — BLOCKER.**
- Because no PostgreSQL/Supabase repository implementation exists for clinics, creating an appointment via `ClinicWorkflowService` does **not** write to `public.clinic_appointments` in Supabase (`pxijyektjscrltwpvzua`), cannot be read from a separate database connection, and does **not** survive an application restart or a fresh service instance.
- Per audit instructions, no adapter was silently implemented before reporting this blocker.

---

## 4. Live Supabase RLS Findings (Check 3)

### Live PostgreSQL Catalog Verification (`pxijyektjscrltwpvzua`)
Executed read-only catalog queries via `supabase_mcp:execute_sql`:
- **ENABLE & FORCE RLS (`pg_class`):** Verified `rls_enabled = true` AND `rls_forced = true` on all **11** `clinic_*` tables:
  `clinic_appointments`, `clinic_consultation_types`, `clinic_departments`, `clinic_doctor_breaks`, `clinic_doctor_consultation_types`, `clinic_doctor_departments`, `clinic_doctor_specialities`, `clinic_doctor_unavailability`, `clinic_doctor_working_hours`, `clinic_doctors`, `clinic_specialities`.
- **Policies (`pg_policies`):** Verified **39** RLS policies across all 11 tables:
  - Every policy targets `{authenticated}` only — **0** `anon` policies exist.
  - All 10 configuration/mapping tables enforce `SELECT` via `is_org_member(organization_id)` and `INSERT`/`UPDATE`/`DELETE` via `has_org_role(organization_id, ARRAY['owner', 'admin'])`.
  - `clinic_appointments` enforces `SELECT`/`INSERT`/`UPDATE` via `is_org_member(organization_id)` and `DELETE` via `has_org_role(organization_id, ARRAY['owner', 'admin'])`.
- **Helper Functions (`pg_proc`):** Verified `public.is_org_member` and `public.has_org_role` are `STABLE SECURITY DEFINER SET search_path TO 'public', 'pg_temp'` using `(select auth.uid())` against `public.organization_members`.
- **Cross-Tenant FKs & Constraints (`pg_constraint` on `public.clinic_appointments`):**
  - Composite FKs verified: `fk_clinic_appointments_org_business`, `fk_clinic_appointments_doctor`, `fk_clinic_appointments_consultation_type`, `fk_clinic_appointments_department`.
  - GiST exclusion constraint verified: `excl_clinic_appointments_no_doctor_overlap` (`EXCLUDE USING gist (doctor_id WITH =, tstzrange(starts_at, ends_at, '[)'::text) WITH &&) WHERE ((status = ANY (ARRAY['confirmed'::text, 'rescheduled'::text])))`).

### Live Multi-Role JWT Testing
- **Anonymous User (`anon` key via PostgREST `GET /rest/v1/clinic_appointments?select=id`):** Executed live -> `HTTP 200`, `ROWS: []` (no patient appointments exposed to anonymous callers).
- **Roles A–D (Clinic owner, Clinic manager/admin, Different org member, Unrelated authenticated user):** **NOT VERIFIED** — no live Supabase Auth test user JWTs are provisioned in this audit environment.

---

## 5. Appointment Concurrency Results (Check 4)

- **Real Database Concurrency Test:** **NOT VERIFIED — BLOCKED BY CHECK 2.**
- While the PostgreSQL constraint `excl_clinic_appointments_no_doctor_overlap` and partial unique index `uq_clinic_appointments_business_idempotency` are verified present in live Supabase, and in-memory concurrency tests pass (`test_stage6_clinic.py`), end-to-end transactional concurrency, double-booking rejection, reschedule overlap rejection, cancellation persistence, and rollback behavior **through a real PostgreSQL clinic repository** have not been executed because no real repository adapter exists yet.

---

## 6. Realtime Voice Verification (Check 5)

### Code Inspection Findings
- **Verified Working:**
  - All 10 clinic tools are defined in `AgentToolName` (`apps/api/app/agents/schemas.py`), registered in `ClinicAgent.allowed_tools` (`apps/api/app/agents/industries/clinic.py`), defined in `build_realtime_tool_definitions()` (`apps/api/app/agents/instructions.py`), and dispatched in `AgentOrchestrator._dispatch_tool_sync()` (`apps/api/app/agents/orchestrator.py`).
  - `AgentOrchestrator.execute_realtime_tool()` enforces `tool_name not in industry_agent.allowed_tools` (`orchestrator.py:355-368`), rejects model-supplied `organization_id`/`business_id`/`tenant_id` (`orchestrator.py:130-134`), enforces per-turn tool limits and rate limits, and sets `escalation_triggered` for `REQUEST_CLINIC_HUMAN_ESCALATION`.
  - `ClinicAgent` directives and `IntentClassifier` enforce non-diagnostic safeguards and immediate emergency redirection.
- **Defects Discovered in Voice Integration:**
  1. **Unfiltered Realtime Tool List (`apps/api/app/modules/voice/service.py:351`):** `tools = build_realtime_tool_definitions()` sends all 21 tools (including 6 Salon tools) to Clinic Realtime sessions (and 10 Clinic tools to Salon sessions) instead of filtering to `industry_agent.allowed_tools`. Although `execute_realtime_tool` rejects disallowed calls server-side, exposing cross-industry tools confuses the Realtime model.
  2. **Contradictory Stage 4 Booking Boundary Prompt (`apps/api/app/agents/instructions.py:104-105`):** `common_base` still tells the LLM: *"Stage 4 Booking Boundary: Recognising booking, rescheduling, or cancellation intent does NOT create or modify appointments in Stage 4."* This directly contradicts `ClinicAgent.build_industry_directives()` (and `SalonAgent`), which instruct the model to create/reschedule/cancel appointments.
- **Live End-to-End OpenAI Realtime Audio Call:** **NOT EXECUTED** (no live WebRTC microphone/browser audio session was run in this headless audit; only orchestrator/unit tests were executed).

---

## 7. Timezone Verification (Check 6)

- **Finding — MEDIUM/HIGH DEFECT:**
  - `apps/api/requirements.txt` does **not** include `tzdata`.
  - `Dockerfile` (`ubuntu:24.04`) and `apps/api/Dockerfile` (`ubuntu:24.04`) install system packages with `--no-install-recommends` and do **not** install the `tzdata` apt package. Minimal Ubuntu 24.04 images do not ship `/usr/share/zoneinfo`.
  - Consequently, `ZoneInfo(tz_name)` in `ClinicWorkflowService._get_zoneinfo()` (`apps/api/app/modules/clinics/service.py:138-150`) fails with `ZoneInfoNotFoundError` in both Windows local dev and Docker containers, falling back to hardcoded fixed offsets (`America/New_York` -> `-05:00`, `America/Los_Angeles` -> `-08:00`, which are **not DST-aware**) and silently falling back to `UTC` for any IANA timezone not in the 5-entry map.
- **UTC Storage:** `starts_at` / `ends_at` are timezone-aware `TIMESTAMPTZ` in SQL and normalized to aware `datetime` in Python, which is sound once real IANA `tzdata` is installed.

---

## 8. Regression Results (Check 7)

All automated checks were executed fresh on commit `403b914`:

| Check | Command | Actual Result |
| :--- | :--- | :--- |
| Backend Tests (Stages 1–6) | `$env:PYTHONPATH="apps/api"; pytest apps/api/tests -q` | **59 passed, 1 skipped** (5.74s) — Stage 4, Stage 5, Stage 6 all passed; 1 pre-existing live Supabase test skipped |
| Frontend Tests (Stages 1–6) | `npm --prefix apps/web test -- --run` | **6/6 test files passed, 26/26 tests passed** (18.95s) |
| ESLint | `npm --prefix apps/web run lint` | **Passed** (0 errors, 0 warnings) |
| TypeScript Type Check | `.\apps\web\node_modules\.bin\tsc.cmd -p apps/web/tsconfig.json --noEmit` | **Passed** (exit code 0, 0 errors) |
| Next.js Production Build | `npm --prefix apps/web run build` | **Passed** (compiled in 22.0s, 11/11 static pages generated) |

---

## 9. Defects Discovered

1. **[P0 — BLOCKER] No Real Supabase/PostgreSQL Clinic Repository Adapter (`apps/api/app/modules/clinics/repository.py`, `service.py:1141-1145`):** Production unconditionally uses `InMemoryClinicRepository`; all clinic data is ephemeral and never persisted to Supabase PostgreSQL.
2. **[P1 — HIGH] Missing `tzdata` Dependency in Python & Docker (`apps/api/requirements.txt`, `Dockerfile`, `apps/api/Dockerfile`):** Causes `ZoneInfoNotFoundError` and drops into non-DST fixed-offset / UTC fallbacks in `service.py:138-150`.
3. **[P2 — MEDIUM] Unfiltered Realtime Tool Definitions (`apps/api/app/modules/voice/service.py:351`):** Clinic voice sessions send Salon tools to OpenAI Realtime (and vice versa) instead of filtering by `industry_agent.allowed_tools`.
4. **[P2 — MEDIUM] Contradictory Stage 4 Booking Boundary Prompt (`apps/api/app/agents/instructions.py:104-105`):** Base prompt still tells the model not to create/modify appointments in Stage 4, conflicting with Stage 5 Salon and Stage 6 Clinic booking directives.
5. **[P2 — MEDIUM] No Fail-Closed Production Guard for Ephemeral Repositories:** When `SVARIO_ENV=production` and Supabase env vars are missing, services can fall back to in-memory repositories instead of failing startup.

---

## 10. Fixes Applied
- **None.** Per audit rules (*"Do not silently implement an adapter without reporting the finding first"*), no source code was modified during this verification. Only this verification report (`docs/stage-6/STAGE_6_POST_IMPLEMENTATION_VERIFICATION.md`) was created.

---

## 11. Remaining Limitations
1. Real PostgreSQL persistence and database-level concurrency tests (Check 2 & Check 4) cannot pass until `SupabaseClinicRepository` / `PostgresClinicRepository` is implemented and wired into `get_clinic_workflow_service()`.
2. Live multi-user JWT RLS testing (owner, admin, different-org member, unrelated authenticated user) remains **NOT VERIFIED** pending live Supabase test user credentials.
3. Live OpenAI Realtime WebRTC audio call testing (Check 5) remains **NOT EXECUTED**.
4. Render deployment configuration (`render.yaml`) is not present in the repository.

---

## 12. Final Deployment Readiness

**Verdict: NOT VERIFIED — CRITICAL DEFECTS FOUND**

Stage 6 must **not** proceed to Stage 7 or production deployment until:
1. A real PostgreSQL/Supabase clinic repository implementing `ClinicRepositoryProtocol` is built, wired securely via `settings.is_live_supabase_configured` (failing closed in `SVARIO_ENV=production`), and verified with real persistence + concurrent double-booking tests against Supabase.
2. `tzdata` is added to `apps/api/requirements.txt`, `Dockerfile`, and `apps/api/Dockerfile` so DST-aware IANA `ZoneInfo` works everywhere.
3. `VoiceSessionService` filters Realtime tools by `industry_agent.allowed_tools` and removes the stale Stage 4 no-booking rule for booking-enabled industries (Salon & Clinic).
4. Live multi-user JWT RLS verification is executed against Supabase.

---

## Addendum — Remediation Status (2026-11-20)

Following authorized Stage 6 remediation (see `docs/stage-6/STAGE_6_REMEDIATION_REPORT.md`):
- **[P0 — RESOLVED]** Implemented `SupabaseRestClinicRepository` (`apps/api/app/modules/clinics/supabase_repository.py`), updated `get_clinic_repository()` / `get_clinic_workflow_service()` to select it whenever live Supabase is configured, and added fail-closed `SVARIO_ENV=production` guards in both `service.py` and `main.py`. Verified live PostgreSQL GiST overlap (`23P01`), adjacent half-open ranges, idempotency (`23505`), reschedule overlap, cancellation release, and rollback on Supabase `pxijyektjscrltwpvzua`.
- **[P1 — RESOLVED]** Added `tzdata>=2024.2` to `apps/api/requirements.txt` and `tzdata` to `Dockerfile` and `apps/api/Dockerfile`; removed hardcoded fixed-offset timezone fallbacks; verified DST transitions (`America/New_York` EST `-05:00` vs EDT `-04:00`).
- **[P2 — RESOLVED]** Filtered `build_realtime_tool_definitions(allowed_tools=industry_agent.allowed_tools)` in `VoiceSessionService` and updated `common_base` in `instructions.py` to remove the contradictory Stage 4 no-booking rule for Salon and Clinic.
- **Remaining Unverified Items:** Live multi-role Supabase JWT RLS probing (Roles A–D) and live end-to-end OpenAI Realtime WebRTC audio calls remain **NOT VERIFIED** pending live test-user credentials and a live audio session.
- **Updated Status:** **REMEDIATION PARTIALLY VERIFIED** (all P0–P2 code defects fixed; 63 backend tests passed, 1 skipped; 26 frontend tests passed; lint, tsc, and Next.js build passed).
