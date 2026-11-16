# SVARIO — Multi-Industry Architecture Specification

**Milestone:** Stage 5 — Salon Workflow Module  
**Roadmap Version:** 2.0  
**Tagline:** *AI that speaks for your business.*

---

## 1. Architectural Vision

**SVARIO** is a multi-industry AI Voice Agent Platform engineered for three high-call-volume service verticals:

1. **Salons** (`salon` / `app.modules.salons` / `app.agents.industries.salon`) — Beauty, hair, nail, and wellness studios with multi-stylist appointment orchestration.
2. **Clinics** (`clinic` / `app.agents.industries.clinic`) — Outpatient, dental, dermatology, physiotherapy, and specialty clinics.
3. **Hospitals** (`hospital` / `app.agents.industries.hospital`) — Multi-specialty hospitals and institutional OPD switchboards.

### Core Separation of Concerns
- **AI interprets and communicates.**
- **FastAPI validates and executes.**
- **Supabase is the source of truth.**

Svario separates **multi-tenant identity & organization governance** (`Stage 1`), **organization-scoped business onboarding** (`Stage 2`), **shared browser WebRTC voice infrastructure** (`Stage 3`), **modular AI agent & conversational intelligence** (`Stage 4`), and **salon workflow domain module** (`Stage 5`) from future healthcare clinic/hospital workflows (`Stage 6+`).

---

## 2. Monorepo Topology (Stage 5)

```text
Voice agent-PS-03/
├── apps/
│   ├── web/                               # Next.js 15 (App Router) + TypeScript + Tailwind CSS v4
│   │   ├── src/
│   │   │   ├── app/
│   │   │   │   ├── page.tsx               # Platform Foundation page
│   │   │   │   ├── login/page.tsx         # Supabase email/password sign-in
│   │   │   │   ├── signup/page.tsx        # Operator registration + email verification
│   │   │   │   ├── forgot-password/page.tsx # Password recovery request
│   │   │   │   ├── reset-password/page.tsx  # Password reset completion
│   │   │   │   ├── onboarding/page.tsx    # Protected 8-step Stage 2 business onboarding wizard
│   │   │   │   ├── dashboard/page.tsx     # Protected workspace, org switcher, onboarding & Salon Hub
│   │   │   │   └── voice-test/page.tsx    # Stage 3–5 Browser WebRTC Voice & Agent Test Lab
│   │   │   ├── components/
│   │   │   │   ├── auth/                  # Reusable AuthShell, Login, Signup, Recovery forms
│   │   │   │   ├── organizations/         # OrganizationOnboardingForm & OrganizationSwitcher
│   │   │   │   ├── onboarding/            # OnboardingWizard (8-step wizard + healthcare notices)
│   │   │   │   ├── dashboard/             # SalonDashboardView (Services, Staff, Appointments, Availability)
│   │   │   │   └── voice/                 # VoiceOrbWaveform, VoiceSessionPanel & VoiceTestView
│   │   │   ├── context/
│   │   │   │   └── AuthOrganizationContext.tsx # Session restoration + active org context
│   │   │   ├── lib/
│   │   │   │   ├── api.ts                 # Typed FastAPI client (Stages 1–5 endpoints)
│   │   │   │   ├── supabase/client.ts     # Browser @supabase/supabase-js client
│   │   │   │   └── voice/                 # WebRTC client, 10-state machine, tool execution & events
│   │   │   ├── types/
│   │   │   │   ├── platform.ts            # Core platform types
│   │   │   │   └── salon.ts               # Stage 5 Salon domain contracts
│   │   │   └── __tests__/                 # Vitest + React Testing Library suite (Stages 1–5)
│   │   ├── package.json
│   │   └── vitest.config.ts
│   └── api/                               # Python + FastAPI + Pydantic v2 + PyJWT[crypto]
│       ├── app/
│       │   ├── agents/                    # Stage 4–5 Modular AI Agent Architecture
│       │   │   ├── base.py                # BaseIndustryAgent contract
│       │   │   ├── schemas.py             # Intents, SafetyFlags, 11 Tool I/O & Session Context schemas
│       │   │   ├── instructions.py        # Server-composed system prompts & Realtime tool definitions
│       │   │   ├── intent.py              # Typed IntentClassifier & multilingual detector (en/hi/hinglish)
│       │   │   ├── context.py             # Tenant-isolated ConversationContextManager & PII redaction
│       │   │   ├── orchestrator.py        # Controlled AgentOrchestrator & tool execution engine
│       │   │   ├── industries/            # SalonAgent (6 salon tools), ClinicAgent & HospitalAgent
│       │   │   └── tools/                 # Salon & baseline backend-validated tools
│       │   ├── modules/
│       │   │   ├── salons/                # Stage 5 Salon Domain Module (Schemas, Repository, Service)
│       │   │   ├── organizations/         # Multi-tenant schemas, repository & RBAC service
│       │   │   ├── onboarding/            # Stage 2 schemas, repository & RBAC service
│       │   │   ├── voice/                 # Stage 3–5 session & tool execution service
│       │   │   └── shared/                # Voice, AI, Scheduling, Notifications contracts
│       │   ├── routes/
│       │   │   ├── salons.py              # REST CRUD for services, staff, shifts, breaks, holidays, appointments
│       │   │   ├── voice.py               # WebRTC sessions, tool dispatch, agent turns
│       │   │   ├── onboarding.py          # Onboarding routes
│       │   │   └── organizations.py       # Organization & member routes
│       │   └── main.py
│       ├── tests/                         # Pytest suite (Auth, Orgs, Onboarding, Voice, Salon Stage 5)
│       └── requirements.txt
├── supabase/
│   └── migrations/                        # PostgreSQL migrations (including 20261110000006 Stage 5 Salon)
└── docs/
```

---

## 3. Stage 5 Salon Workflow Database Architecture & Concurrency Protection

Stage 5 introduces 7 dedicated tables in `public` with forced RLS and a database-level GiST exclusion constraint preventing double-booking:

1. `public.salon_services`: Services catalog (name, category, price > 0, duration 5..480 min, active flag).
2. `public.salon_staff`: Stylist profiles (name, role, active flag, contact details).
3. `public.salon_staff_services`: M:N junction assigning services to qualified stylists.
4. `public.salon_staff_working_hours`: Weekly recurring shift windows (0=Sunday..6=Saturday).
5. `public.salon_staff_breaks`: Recurring or date-specific break intervals (e.g., lunch breaks).
6. `public.salon_holidays`: Whole-salon closures and staff leaves (full-day or partial).
7. `public.salon_appointments`: Transactional booking records with:
   - **GiST Exclusion Constraint (`btree_gist`):** `excl_salon_appointments_no_staff_overlap` enforces `EXCLUDE USING gist (staff_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&) WHERE (status IN ('confirmed', 'rescheduled'))`. This guarantees zero double-booking even under concurrent race conditions.
   - **Idempotency Key:** Protects against duplicate network submissions.
   - **Strict RLS:** All 7 tables enforce multi-tenant isolation via `organization_id IN (SELECT organization_id FROM public.organization_members WHERE user_id = (SELECT auth.uid()))`.
│       │   │   ├── base.py                # BaseIndustryAgent contract
│       │   │   ├── schemas.py             # 14 Intents, SafetyFlags, Tool I/O & Session Context schemas
│       │   │   ├── instructions.py        # Server-composed Stage 4 system prompts & 5 Realtime tools
│       │   │   ├── intent.py              # Typed IntentClassifier & multilingual detector (en/hi/hinglish)
│       │   │   ├── context.py             # Tenant-isolated ConversationContextManager & PII redaction
│       │   │   ├── orchestrator.py        # Controlled 9-step AgentOrchestrator & tool execution engine
│       │   │   ├── industries/            # SalonAgent, ClinicAgent & HospitalAgent
│       │   │   └── tools/                 # 5 backend-validated tools (profile, hours, FAQ, summary, escalation)
│       │   ├── core/
│       │   │   ├── config.py              # Pydantic settings (Supabase, JWKS, OpenAI Realtime, Rate Limit)
│       │   │   ├── auth.py                # SupabaseJWTVerifier + get_current_user dependency
│       │   │   └── errors.py              # Standardized JSON error handlers
│       │   ├── routes/
│       │   │   ├── root.py                # GET /
│       │   │   ├── health.py              # GET /health
│       │   │   ├── industries.py          # GET /architecture
│       │   │   ├── auth.py                # GET /api/v1/auth/me
│       │   │   ├── organizations.py       # POST/GET /api/v1/organizations & /members
│       │   │   ├── onboarding.py          # GET/PUT/POST/DELETE /api/v1/organizations/{id}/onboarding/*
│       │   │   └── voice.py               # POST /voice/sessions, /voice/tools/execute, /agent/turns & GET /context
│       │   ├── modules/
│       │   │   ├── organizations/         # Multi-tenant schemas, repository & RBAC service
│       │   │   ├── onboarding/            # Stage 2 schemas, repository & RBAC service
│       │   │   ├── voice/                 # Stage 3–4 session & tool execution service
│       │   │   ├── shared/                # Voice, AI, Scheduling, Notifications contracts
│       │   │   ├── salons/
│       │   │   ├── clinics/
│       │   │   └── hospitals/
│       │   └── main.py
│       ├── tests/                         # Pytest suite (Auth, Orgs, Onboarding, Voice, Stage 4 Agent & Eval)
│       └── requirements.txt
├── supabase/
│   └── migrations/                        # Stage 1, Stage 2 & Stage 4 PostgreSQL schemas & forced RLS policies
├── brand assets/                          # Preserved official color system & brand references
├── docs/
└── infra/
```

---

## 3. Stage 4 Realtime Voice & Controlled Agent Tool-Calling Flow

```mermaid
sequenceDiagram
    participant Browser as Next.js Browser (SvarioWebRtcVoiceClient)
    participant FastAPI as Svario FastAPI (VoiceSessionService & AgentOrchestrator)
    participant Supabase as Supabase PostgreSQL (Forced RLS)
    participant OpenAI as OpenAI Realtime API (gpt-realtime)

    Browser->>FastAPI: POST /api/v1/voice/sessions
    FastAPI->>Supabase: Load verified Business Profile, Hours, Languages, FAQs & Escalation
    FastAPI->>FastAPI: Compose Stage 4 Industry Instructions + Register 5 Tool Schemas
    FastAPI->>OpenAI: POST /v1/realtime/client_secrets (session.instructions + session.tools)
    OpenAI-->>FastAPI: Ephemeral Secret (ek_...) + Session ID
    FastAPI-->>Browser: Short-Lived WebRTC Session Details
    Browser->>OpenAI: WebRTC SDP Offer/Answer (/v1/realtime/calls) + oai-events Data Channel
    OpenAI-->>Browser: event: response.function_call_arguments.done (tool_name, call_id, args)
    Browser->>FastAPI: POST /api/v1/voice/tools/execute (Bearer JWT or Signed Public Token)
    FastAPI->>FastAPI: Verify Tenant/Session Isolation + Validate Tool Schema + Per-Turn Limit
    FastAPI->>Supabase: Execute Approved Read/Summary/Escalation Operation + Audit Log
    FastAPI-->>Browser: Validated Tool Output (JSON)
    Browser->>OpenAI: oai-events: conversation.item.create (function_call_output) + response.create
    OpenAI-->>Browser: Grounded Spoken Response (en / hi / hinglish)
```

### Voice Session State Machine (10 Explicit States)
- `idle`: Initial standby state prior to session initiation.
- `requesting_permission`: Prompting browser `navigator.mediaDevices.getUserMedia`.
- `connecting`: Minting short-lived backend credential and negotiating WebRTC SDP offer/answer.
- `connected`: `RTCPeerConnection` established; awaiting data channel readiness.
- `listening`: Active microphone stream and `oai-events` channel ready for caller speech.
- `processing`: Caller turn committed (`input_audio_buffer.speech_stopped`); synthesizing AI response.
- `speaking`: AI voice output streaming over remote `<audio>` track (supports instant barge-in interruption).
- `reconnecting`: Tearing down prior `RTCPeerConnection`/tracks and establishing a fresh session without leaks.
- `error`: Recoverable or non-recoverable failure (`MICROPHONE_PERMISSION_DENIED`, `MICROPHONE_NOT_FOUND`, `SESSION_EXPIRED`, `SDP_NEGOTIATION_FAILED`, etc.).
- `ended`: Cleanly disconnected with all microphone tracks stopped and peer connection closed.
