# SVARIO — STAGE 6 REMEDIATION REPORT
## P0–P2 Defect Resolution and Verification

**Project:** Svario  
**Team:** AgentX  
**Date:** 2026-11-20  
**Branch:** `main`  
**Original Stage 6 Checkpoint Preserved:** `403b914` (parent `855b994`)  
**Verdict:** **REMEDIATION PARTIALLY VERIFIED** *(All P0–P2 code, persistence, PostgreSQL constraint, timezone/DST, tool filtering, and prompt defects are resolved and verified; live multi-role JWT RLS probing and live OpenAI Realtime audio call execution remain unexecuted in this local environment).*

---

## 1. Original Defects Remediated
From `docs/stage-6/STAGE_6_POST_IMPLEMENTATION_VERIFICATION.md`:
1. **[P0 — BLOCKER]** `get_clinic_workflow_service()` unconditionally instantiated `InMemoryClinicRepository`; no real Supabase/PostgreSQL clinic repository existed, and production did not fail closed when DB config was missing.
2. **[P1 — HIGH]** `tzdata` was missing from `apps/api/requirements.txt`, `Dockerfile`, and `apps/api/Dockerfile`, causing `ZoneInfoNotFoundError` and falling back to non-DST fixed offsets / UTC.
3. **[P2 — MEDIUM]** `VoiceSessionService` passed unfiltered `build_realtime_tool_definitions()` (all 21 Salon + Clinic tools) to OpenAI Realtime sessions.
4. **[P2 — MEDIUM]** `common_base` in `apps/api/app/agents/instructions.py` still included the Stage 4 no-booking boundary, contradicting Stage 5 Salon and Stage 6 Clinic booking directives.

---

## 2. Root Causes
- **P0:** Stage 6 mirrored Stage 5's `InMemory*Repository` DI pattern instead of Stage 1/2's `SupabaseRest*Repository` + `settings.is_live_supabase_configured` pattern, and lacked a `SVARIO_ENV=production` fail-closed guard.
- **P1:** Windows Python and minimal `ubuntu:24.04` Docker images do not ship IANA zoneinfo data unless `tzdata` is explicitly installed.
- **P2 (Tools):** `build_realtime_tool_definitions()` lacked an `allowed_tools` filter parameter.
- **P2 (Prompt):** `common_base` hardcoded Stage 4's global no-booking rule regardless of `bundle.organization.industry`.

---

## 3. Files Changed

### Created
- `apps/api/app/modules/clinics/supabase_repository.py` — Production `SupabaseRestClinicRepository` implementing all 28 `ClinicRepositoryProtocol` operations via Supabase PostgREST.
- `apps/api/tests/test_stage6_remediation.py` — Automated tests for P0 repository selection/fail-closed guard/persistence, P1 IANA timezone & DST transitions, P2 Realtime tool filtering, and P2 prompt consistency.
- `docs/stage-6/STAGE_6_REMEDIATION_REPORT.md` — This remediation report.

### Modified
- `apps/api/app/modules/clinics/service.py` — Added `get_clinic_repository()` (selects `SupabaseRestClinicRepository` when live Supabase is configured, fails closed in `production`, allows `InMemoryClinicRepository` only in non-production without Supabase), bound per-request actor context (`set_current_clinic_actor`), removed hardcoded fixed-offset timezone fallbacks.
- `apps/api/app/main.py` — Added fail-closed production startup validation in `create_app()`.
- `apps/api/requirements.txt` — Added `tzdata>=2024.2`.
- `Dockerfile` & `apps/api/Dockerfile` — Added `tzdata` to `apt-get install`.
- `apps/api/app/agents/instructions.py` — Added `allowed_tools` filtering to `build_realtime_tool_definitions()` and replaced the contradictory Stage 4 no-booking rule in `common_base` with an industry-aware `Backend-Confirmed Scheduling Boundary`.
- `apps/api/app/modules/voice/service.py` — Passed `allowed_tools=get_industry_agent(bundle.organization.industry).allowed_tools` to `build_realtime_tool_definitions()`.
- `docs/stage-6/STAGE_6_POST_IMPLEMENTATION_VERIFICATION.md` — Preserved historical findings and appended remediation status addendum.

---

## 4. Repository Implementation Details
`SupabaseRestClinicRepository` (`apps/api/app/modules/clinics/supabase_repository.py`):
- Implements every method in `ClinicRepositoryProtocol` (`clinic_departments`, `clinic_specialities`, `clinic_consultation_types`, `clinic_doctors`, `clinic_doctor_departments`, `clinic_doctor_specialities`, `clinic_doctor_consultation_types`, `clinic_doctor_working_hours`, `clinic_doctor_breaks`, `clinic_doctor_unavailability`, `clinic_appointments`).
- Uses `contextvars.ContextVar` (`_current_clinic_actor`) bound by `ClinicWorkflowService._verify_org_access()` to forward the authenticated user's real Supabase JWT (`Authorization: Bearer {actor.raw_token}`) to PostgREST so PostgreSQL RLS is enforced per request.
- For verified internal voice sessions (`https://svario.internal/auth/v1`), uses `SUPABASE_SERVICE_ROLE_KEY` strictly scoped by backend-resolved `organization_id` and `business_id` filters, failing closed (`503`) if unconfigured.
- Maps PostgreSQL `23P01` (`excl_clinic_appointments_no_doctor_overlap`) to `ClinicConflictError` (HTTP `409`), replays existing appointments on `23505` idempotency conflicts, and stores all appointment/unavailability timestamps in UTC.

---

## 5. Production Repository Selection
- Runtime check with configured `.env`: `RESOLVED_REPO_TYPE: SupabaseRestClinicRepository`.
- Verified in `test_production_selects_supabase_repository_and_fails_closed_without_config`:
  - `SVARIO_ENV=production` + live Supabase -> `SupabaseRestClinicRepository`.
  - `SVARIO_ENV=production` + missing Supabase -> `RuntimeError` in both `get_clinic_repository()` and `create_app()` (no silent fallback to memory).
  - `SVARIO_ENV=development` + missing Supabase -> `InMemoryClinicRepository`.

---

## 6. Database Persistence & Live PostgreSQL Evidence
1. **Live Supabase PostgreSQL (`pxijyektjscrltwpvzua`) PL/pgSQL Verification:** Executed directly against live Supabase (`public.clinic_appointments` and related tables) with temporary synthetic records cleaned up at the end:
   - Appointment creation (`confirmed`), overlap rejection (`23P01` `exclusion_violation` on `excl_clinic_appointments_no_doctor_overlap`), adjacent half-open `[09:00, 09:30)` + `[09:30, 10:00)` acceptance, duplicate idempotency rejection (`23505` `unique_violation`), reschedule overlap rejection (`23P01`), cancellation releasing `[09:00, 09:30)` for rebooking, and subtransaction rollback (`0` rows persisted after error) — **all verified passed on live PostgreSQL**.
2. **Repository Adapter Persistence Verification (`test_supabase_rest_clinic_repository_persistence_and_constraints`):** Verified via `httpx.MockTransport` simulating PostgREST persistence across 3 fresh `SupabaseRestClinicRepository` instances (`repo1` insert -> `repo2` read/idempotency replay/`23P01` overlap/cancel -> `repo3` read cancelled status) and verified user JWT forwarding (`Authorization: Bearer test.user.jwt`).

---

## 7. Concurrency Test Results
- Simultaneous booking race (`asyncio.gather` in `test_stage6_clinic.py`): 1 succeeds, 1 receives `409 Conflict`.
- Simultaneous reschedule race onto the same slot (`asyncio.gather` in `test_stage6_remediation.py`): 1 succeeds, 1 receives `409 Conflict`.
- Live PostgreSQL `excl_clinic_appointments_no_doctor_overlap` (`23P01`) verified for both `INSERT` and `UPDATE` (reschedule) on Supabase `pxijyektjscrltwpvzua`.

---

## 8. Timezone Changes
- Installed `tzdata-2026.6` locally and added `tzdata>=2024.2` to `apps/api/requirements.txt`.
- Added `tzdata` apt package to `Dockerfile` and `apps/api/Dockerfile`.
- Removed fixed-offset dictionary fallback from `ClinicWorkflowService._get_zoneinfo()`.
- Verified DST transitions in `America/New_York` (`2026-01-15` -> `-05:00` EST; `2026-07-15` -> `-04:00` EDT) and `Asia/Kolkata` (`+05:30`) via `test_iana_timezone_and_dst_transitions`.

---

## 9. Realtime Tool Filtering Changes
- `build_realtime_tool_definitions(allowed_tools=...)` filters tool definitions strictly to the active industry's `allowed_tools`.
- `VoiceSessionService` now passes `allowed_tools=industry_agent.allowed_tools`.
- Verified Salon sessions expose zero `clinic_*` tools, Clinic sessions expose zero `salon_*` tools, and `AgentOrchestrator.execute_realtime_tool()` rejects cross-industry tool calls (`tool_not_permitted`).

---

## 10. Agent Prompt Corrections
- Replaced hardcoded Stage 4 no-booking rule in `common_base` with an industry-aware rule:
  - Salon & Clinic: `Backend-Confirmed Scheduling Boundary` (booking allowed only via approved tools; never claim success without committed backend result).
  - Hospital: `Pre-Booking Industry Boundary` (no automated booking yet).
- Preserved `ClinicAgent` non-diagnostic (`NEVER provide medical diagnosis`) and emergency redirection safeguards.

---

## 11. Security Verification
- All 11 `clinic_*` tables retain `ENABLE` + `FORCE ROW LEVEL SECURITY` with 39 `{authenticated}`-only policies (0 `anon` policies).
- Live anonymous PostgREST read on `clinic_appointments` returns `[]` (`HTTP 200`).
- `SupabaseRestClinicRepository` forwards real user JWTs for RLS enforcement; service-role key is strictly gated to internal verified voice sessions and never exposed.

---

## 12. Regression Results
| Check | Command | Actual Result |
| :--- | :--- | :--- |
| Backend Tests (Stages 1–6 + Remediation) | `$env:PYTHONPATH="apps/api"; pytest apps/api/tests -q` | **63 passed, 1 skipped** (4.80s) |
| Frontend Tests (Stages 1–6) | `npm --prefix apps/web test -- --run` | **6/6 files passed, 26/26 tests passed** (12.95s) |
| ESLint | `npm --prefix apps/web run lint` | **Passed** (0 errors, 0 warnings) |
| TypeScript Type Check | `.\apps\web\node_modules\.bin\tsc.cmd -p apps/web/tsconfig.json --noEmit` | **Passed** (exit code 0, 0 errors) |
| Next.js Production Build | `npm --prefix apps/web run build` | **Passed** (compiled in 4.0s, 11/11 static pages) |

---

## 13. Live Verification Limitations
1. **Multi-Role Live Supabase JWT RLS Testing (Owner, Admin, Different Org Member, Unrelated User):** **NOT VERIFIED** — no live Supabase Auth test user JWTs are provisioned in this local environment.
2. **Live OpenAI Realtime WebRTC Audio Call:** **NOT EXECUTED** — verified via tool filtering, orchestrator, and prompt unit/integration tests only.
3. **End-to-End `SupabaseRestClinicRepository` HTTP calls against live PostgREST with a real user JWT:** Verified via `httpx.MockTransport` + direct live PostgreSQL SQL verification on `pxijyektjscrltwpvzua`; full HTTP round-trip with a live Supabase user JWT awaits test-user credentials.

---

## 14. Git Status and Commit Information
- Original Stage 6 checkpoint `403b914` preserved intact (no rebase, reset, or force-push).
- Remediation commit recorded separately on `main` (`fix(clinic): resolve Stage 6 persistence and integration defects`).
