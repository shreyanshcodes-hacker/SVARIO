# SVARIO — Multi-Industry Architecture Specification

**Milestone:** Stage 3 — Shared Browser Voice Infrastructure  
**Roadmap Version:** 2.0  
**Tagline:** *AI that speaks for your business.*

---

## 1. Architectural Vision

**SVARIO** is a multi-industry AI Voice Agent Platform engineered for three high-call-volume service verticals:

1. **Salons** (`salon` / `app.modules.salons`) — Beauty, hair, and wellness studios.
2. **Clinics** (`clinic` / `app.modules.clinics`) — Outpatient, dental, dermatology, physiotherapy, and specialty clinics.
3. **Hospitals** (`hospital` / `app.modules.hospitals`) — Multi-specialty hospitals and institutional OPD switchboards.

Svario separates **multi-tenant identity & organization governance** (`Stage 1`), **organization-scoped business onboarding** (`Stage 2`), and **shared browser WebRTC voice infrastructure** (`Stage 3`) from **industry-specific transactional workflows** (`Stage 4+`).

---

## 2. Monorepo Topology (Stage 3)

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
│   │   │   │   ├── dashboard/page.tsx     # Protected workspace, org switcher & Voice Test Lab link
│   │   │   │   └── voice-test/page.tsx    # Stage 3 Browser WebRTC Voice Test Lab
│   │   │   ├── components/
│   │   │   │   ├── auth/                  # Reusable AuthShell, Login, Signup, Recovery forms
│   │   │   │   ├── organizations/         # OrganizationOnboardingForm & OrganizationSwitcher
│   │   │   │   ├── onboarding/            # OnboardingWizard (8-step wizard + healthcare notices)
│   │   │   │   └── voice/                 # VoiceOrbWaveform & VoiceSessionPanel (Stage 3)
│   │   │   ├── context/
│   │   │   │   └── AuthOrganizationContext.tsx # Session restoration + active org context
│   │   │   ├── lib/
│   │   │   │   ├── api.ts                 # Typed FastAPI client (Stage 1–3 endpoints)
│   │   │   │   ├── supabase/client.ts     # Browser @supabase/supabase-js client
│   │   │   │   └── voice/                 # Stage 3 WebRTC client, 10-state machine & event types
│   │   │   ├── config/brand.ts
│   │   │   ├── types/platform.ts
│   │   │   └── __tests__/                 # Vitest + React Testing Library suite (Stages 1, 2 & 3)
│   │   ├── package.json
│   │   └── vitest.config.ts
│   └── api/                               # Python + FastAPI + Pydantic v2 + PyJWT[crypto]
│       ├── app/
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
│       │   │   └── voice.py               # POST /api/v1/voice/sessions & /voice/public-token
│       │   ├── modules/
│       │   │   ├── organizations/         # Multi-tenant schemas, repository & RBAC service
│       │   │   ├── onboarding/            # Stage 2 schemas, repository & RBAC service
│       │   │   ├── voice/                 # Stage 3 schemas, prompts, rate limiter, public tokens & service
│       │   │   ├── shared/                # Voice, AI, Scheduling, Notifications contracts
│       │   │   ├── salons/
│       │   │   ├── clinics/
│       │   │   └── hospitals/
│       │   └── main.py
│       ├── tests/                         # Pytest suite (Auth, Orgs, Onboarding, Voice, RLS Audit, Live RLS)
│       └── requirements.txt
├── supabase/
│   └── migrations/                        # Stage 1 & Stage 2 PostgreSQL schemas & forced RLS policies
├── brand assets/                          # Preserved official color system & brand references
├── docs/
└── infra/
```

---

## 3. Stage 3 Shared Browser WebRTC Voice Architecture

```mermaid
sequenceDiagram
    participant Browser as Next.js Browser (SvarioWebRtcVoiceClient)
    participant FastAPI as Svario FastAPI (POST /api/v1/voice/sessions)
    participant Onboarding as Stage 2 Onboarding Store (Supabase / RLS)
    participant OpenAI as OpenAI Realtime API (/v1/realtime)

    Browser->>Browser: getUserMedia({ audio: true }) -> Request mic permission
    Browser->>FastAPI: POST /api/v1/voice/sessions (Bearer JWT or Signed Public Token)
    FastAPI->>FastAPI: Verify Member RBAC or Signed Public Token + Rate Limit
    FastAPI->>Onboarding: Load verified Business Profile, Languages, Hours, FAQs & Assistant Settings
    FastAPI->>FastAPI: Build server-side instructions + Healthcare Administrative Guardrails
    FastAPI->>OpenAI: POST /v1/realtime/sessions (Backend-only OPENAI_API_KEY)
    OpenAI-->>FastAPI: Ephemeral Client Credential (ek_..., short TTL)
    FastAPI-->>Browser: Sanitized Session + Ephemeral Credential (Never exposes permanent key)
    Browser->>Browser: Create RTCPeerConnection + Audio Track + oai-events Data Channel
    Browser->>OpenAI: POST /v1/realtime?model=... (SDP Offer + Bearer ek_...)
    OpenAI-->>Browser: SDP Answer -> Bidirectional Audio + oai-events Stream
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
