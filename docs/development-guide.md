# SVARIO — Local Development, Supabase & Voice Infrastructure Guide

**Milestone:** Stage 3 — Shared Browser Voice Infrastructure  
**Stack:** Next.js 15 + TypeScript + Tailwind CSS v4 + WebRTC | FastAPI + Pydantic v2 + `PyJWT[crypto]` + OpenAI Realtime API

---

## 1. Prerequisites

- **Node.js:** v20+ (v24 recommended) and `npm`
- **Python:** Python 3.11+ and `pip`
- **Supabase Project:** A Supabase cloud project or local Supabase CLI stack (`supabase start`).
- **OpenAI API Key:** A backend-only OpenAI API key with access to the OpenAI Realtime API (`OPENAI_API_KEY` in `apps/api/.env`).

---

## 2. Backend Environment Configuration (`apps/api/.env`)

Copy `apps/api/.env.example` to `apps/api/.env` and configure:

```env
# Supabase JWT Verification
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_JWKS_URL=https://your-project-ref.supabase.co/auth/v1/.well-known/jwks.json
SUPABASE_JWT_ISSUER=https://your-project-ref.supabase.co/auth/v1
SUPABASE_JWT_AUDIENCE=authenticated
SUPABASE_JWT_ALGORITHMS=ES256,RS256,EdDSA

# Stage 3 — OpenAI Realtime Voice Infrastructure (Backend-Only)
OPENAI_API_KEY=sk-proj-...
OPENAI_REALTIME_MODEL=gpt-4o-realtime-preview
OPENAI_REALTIME_VOICE=alloy
OPENAI_REALTIME_API_BASE_URL=https://api.openai.com/v1
OPENAI_REALTIME_SESSION_TTL_SECONDS=120
OPENAI_REALTIME_MODALITIES=audio,text
VOICE_SESSION_RATE_LIMIT_PER_MINUTE=10
VOICE_PUBLIC_TOKEN_SECRET=your-random-hmac-secret
VOICE_PUBLIC_TOKEN_TTL_SECONDS=3600
```

> **Security Rule:** `OPENAI_API_KEY` must remain in `apps/api/.env` only. Never place it in `apps/web/.env.local` or any `NEXT_PUBLIC_*` variable.

---

## 3. Stage 3 Voice API Endpoints

1. `POST /api/v1/voice/sessions`
   - Validates the caller's authorization (`organization_member` via verified Supabase Bearer JWT, or `public_visitor` via HMAC-signed `public_access_token`).
   - Enforces per-caller sliding-window rate limiting (`429 Too Many Requests`).
   - Composes server-authoritative system instructions from the business's Stage 2 onboarding bundle (including mandatory administrative-only healthcare guardrails for `clinic` and `hospital`).
   - Mints a short-lived ephemeral OpenAI Realtime session credential (`ek_...`) and returns only the required WebRTC connection metadata.
2. `POST /api/v1/organizations/{organization_id}/voice/public-token`
   - Restricted to organization `owner` or `admin` members when `assistant.enabled == True`.
   - Mints a short-lived HMAC-SHA256 signed `public_access_token` bound to `(organization_id, business_id)` for deliberate public visitor voice access.

---

## 4. Testing Browser Voice Locally (`/voice-test`)

1. Start the backend (`apps/api` on port `8000`) and frontend (`apps/web` on port `3000`).
2. Sign in at `http://localhost:3000/login`, complete or review your business configuration in `/onboarding`, and click **Voice Test Lab** on `/dashboard` (or navigate directly to `http://localhost:3000/voice-test`).
3. Select your organization and preferred Realtime voice preset, then click **Start Conversation**.
4. Grant browser microphone permission when prompted to establish the WebRTC session.

---

## 5. Running Automated Tests

### Backend Tests (`apps/api`)
```powershell
cd apps/api
python -m pytest -v
```

### Frontend Unit Tests, Lint, Typecheck & Production Build (`apps/web`)
```powershell
cd apps/web
npm test -- --run
npm run lint
npm run typecheck
npm run build
```
