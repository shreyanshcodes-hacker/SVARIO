# SVARIO — Staged Delivery Plan

**Current Active Milestone:** **STAGE 4 — AI AGENT & CONVERSATIONAL INTELLIGENCE**  
**Status:** Complete (Awaiting Approval to Proceed to Stage 5)

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

### Stage 4 — AI Agent & Conversational Intelligence (Current Milestone — Complete)
- **Objective:** Implement modular multi-industry AI agent intelligence, typed intent classification, grounded business knowledge retrieval, session-scoped context, controlled backend tool execution, human escalation workflows, and multilingual support (`en`, `hi`, `hinglish`).
- **Completed Deliverables:**
  - **Phase 4A & 4B — Modular Agent Architecture & Industry Instructions (`apps/api/app/agents/`):** `BaseIndustryAgent`, `SalonAgent`, `ClinicAgent`, `HospitalAgent`, and `build_stage4_agent_instructions`.
  - **Phase 4C — Typed Intent Recognition (`intent.py` & `schemas.py`):** 14 typed intents (`greeting`, `business_information`, `opening_hours`, `location`, `services_enquiry`, `pricing_enquiry`, `speciality_enquiry`, `department_enquiry`, `booking_intent`, `rescheduling_intent`, `cancellation_intent`, `human_support`, `emergency_intent`, `unknown`) + `SafetyFlag` detection.
  - **Phase 4D, 4E & 4F — Grounded Knowledge Retrieval, Session Context & 5 Structured Tools (`tools/` & `context.py`):** `get_business_profile`, `get_business_hours`, `search_business_knowledge`, `save_conversation_summary`, and `request_human_escalation`, backed by `conversation_summaries` and `escalation_requests` with forced RLS on Supabase.
  - **Phase 4G, 4H & 4I — Controlled Orchestrator, Human Escalation & Realtime Voice Integration (`orchestrator.py`, `routes/voice.py`, `webrtcClient.ts`):** `POST /api/v1/voice/tools/execute`, `POST /api/v1/agent/turns`, `GET /api/v1/voice/sessions/{session_id}/context`, and automatic `response.function_call_arguments.done` -> `conversation.item.create` + `response.create` handling over `oai-events`.
  - **Phase 4J & 4K — Multilingual Support (`en`, `hi`, `hinglish`) & Reproducible Multi-Industry AI Evaluation Suite (`tests/test_stage4_agent.py` & `stage4-agent-voice.test.tsx`).**
- **Explicitly Excluded from Stage 4:**
  - Live appointment booking, rescheduling, or cancellation execution (`Stage 5+`)
