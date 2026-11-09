# SVARIO — Staged Delivery Plan

**Current Active Milestone:** **STAGE 3 — SHARED BROWSER VOICE INFRASTRUCTURE**  
**Status:** Complete (Awaiting Approval to Proceed to Stage 4)

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

### Stage 3 — Shared Browser Voice Infrastructure (Current Milestone — Complete)
- **Objective:** Implement shared browser WebRTC voice infrastructure powered by the OpenAI Realtime API across Salons, Clinics, and Hospitals.
- **Completed Deliverables:**
  - **Phase 3A — OpenAI Realtime Configuration (`apps/api/app/core/config.py`):** Configurable `OPENAI_API_KEY` (backend-only), `OPENAI_REALTIME_MODEL`, `OPENAI_REALTIME_VOICE`, `OPENAI_REALTIME_SESSION_TTL_SECONDS`, `OPENAI_REALTIME_MODALITIES`, and `VOICE_SESSION_RATE_LIMIT_PER_MINUTE`.
  - **Phase 3B — Secure Session Creation (`POST /api/v1/voice/sessions`):** Strict access validation (`organization_member` JWT RBAC or deliberate signed `public_visitor` token), server-authoritative instruction assembly, sliding-window rate limiting, and short-lived ephemeral credential minting.
  - **Phase 3C & 3D — WebRTC Client & 10-State Machine (`apps/web/src/lib/voice/`):** `SvarioWebRtcVoiceClient` managing `getUserMedia`, `RTCPeerConnection`, remote `<audio>` playback, `oai-events` data channel, barge-in interruption, mute/unmute, session expiration, reconnection without leaks, and tab cleanup across all 10 states (`idle`, `requesting_permission`, `connecting`, `connected`, `listening`, `processing`, `speaking`, `reconnecting`, `error`, `ended`).
  - **Phase 3E — Voice UI & Dedicated Voice-Test Page (`/voice-test`):** `VoiceOrbWaveform`, `VoiceSessionPanel`, and `/voice-test` page using the official Svario palette (`#0B1020`, `#171D33`, `#7657F6`, `#36C6D3`, `#F5F7FC`, `#A7B0C4`).
  - **Phase 3F & 3G — Typed Event Layer & Industry Compatibility:** Typed `oai-events` handling with zero raw audio or transcript storage by default, supporting `salon`, `clinic`, and `hospital` organizations with mandatory administrative-only healthcare guardrails.
- **Explicitly Excluded from Stage 3:**
  - Appointment booking, cancellation, or rescheduling (`Stage 4+`)
  - Industry-specific database catalogs or workflows (salon service menus, clinic doctor schedules, hospital department directories) (`Stage 4+`)
  - Persistent call transcripts or raw audio recording (`Stage 4+`)
