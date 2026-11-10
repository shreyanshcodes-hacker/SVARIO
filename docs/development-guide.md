# SVARIO — Local Development, Supabase, Voice & Agent Intelligence Guide

**Milestone:** Stage 4 — AI Agent & Conversational Intelligence  
**Stack:** Next.js 15 + TypeScript + Tailwind CSS v4 + WebRTC | FastAPI + Pydantic v2 + `PyJWT[crypto]` + OpenAI Realtime API (`gpt-realtime`)

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

# Stage 3 & Stage 4 — OpenAI Realtime Voice & Agent Infrastructure (Backend-Only)
OPENAI_API_KEY=sk-proj-...
OPENAI_REALTIME_MODEL=gpt-realtime
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

## 3. Stage 3 & Stage 4 Voice & Agent API Endpoints

1. `POST /api/v1/voice/sessions`
   - Validates caller authorization (`organization_member` via verified Supabase Bearer JWT, or `public_visitor` via HMAC-signed `public_access_token`).
   - Composes Stage 4 industry-specific system instructions (`salon`, `clinic`, `hospital`) and registers the 5 approved agent tools (`get_business_profile`, `get_business_hours`, `search_business_knowledge`, `save_conversation_summary`, `request_human_escalation`).
   - Mints a short-lived ephemeral OpenAI Realtime session credential (`POST /v1/realtime/client_secrets`) and initializes session-scoped conversation context.
2. `POST /api/v1/voice/tools/execute`
   - Validates and executes one of the 5 structured Stage 4 tools on behalf of an active voice session (`response.function_call_arguments.done` over `oai-events`).
   - Enforces tenant isolation, per-turn tool-call limits (`max_tool_calls_per_turn=3`), argument schema validation (`extra="forbid"`), and execution timeouts.
3. `POST /api/v1/agent/turns`
   - Runs a complete 9-step controlled conversational turn (intent classification across 14 intents, safety checks, tool execution, and grounded multilingual response in `en`, `hi`, or `hinglish`).
4. `GET /api/v1/voice/sessions/{session_id}/context`
   - Returns the session-scoped conversation context for an authorized organization member.
5. `POST /api/v1/organizations/{organization_id}/voice/public-token`
   - Restricted to organization `owner` or `admin` members when `assistant.enabled == True`.

---

## 4. Testing Browser Voice & Agent Tools Locally (`/voice-test`)

1. Start the backend (`apps/api` on port `8000`) and frontend (`apps/web` on port `3000`).
2. Sign in at `http://localhost:3000/login`, complete or review your business configuration in `/onboarding`, and navigate to `http://localhost:3000/voice-test`.
3. Select your organization, preferred Realtime voice preset, and conversation language (`English (EN)`, `Hindi (HI)`, or `Hinglish`), then click **Start Conversation**.
4. Ask about business hours, FAQs, services/specialities/departments, or request human support to observe live backend tool execution and human escalation status banners.

---

## 5. Running Automated Tests

### Backend Tests & Multi-Industry AI Evaluation Suite (`apps/api`)
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
