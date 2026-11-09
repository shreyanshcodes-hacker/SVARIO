# SVARIO — Security Baseline & Row Level Security Reference

**Milestone:** Stage 3 — Shared Browser Voice Infrastructure  
**Roadmap Version:** 2.0

---

## 1. Defense-in-Depth Security Model

Svario enforces security across **four independent layers**:

1. **Cryptographic JWT Verification in FastAPI (`apps/api/app/core/auth.py`):**
   - Extracts `Authorization: Bearer <token>` via `get_current_user`.
   - Prefers asymmetric signature verification (`ES256`, `RS256`, `EdDSA`) using public keys fetched from `SUPABASE_JWKS_URL`.
   - Validates `exp`, `nbf`, `iat`, `iss`, `aud`, and canonical `UUID` format on `sub`.
2. **Application-Layer RBAC & Membership Verification (`OrganizationService` & `OnboardingService`):**
   - Explicitly verifies caller membership and role (`owner`, `admin`, `staff`) before any organization or onboarding operation.
3. **Database-Layer Row Level Security (`supabase/migrations/`):**
   - Every Stage 1 and Stage 2 table has both `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`.
   - Composite foreign keys `(business_id, organization_id)` prevent cross-tenant record linking.
4. **Stage 3 Voice Session & Credential Security (`apps/api/app/modules/voice/`):**
   - **Backend-Only Master Key:** The permanent `OPENAI_API_KEY` is never exposed to browser clients, error payloads, or logs.
   - **Short-Lived Ephemeral Credentials:** Browser WebRTC sessions authenticate using short-lived ephemeral tokens (`client_secret.value`) minted via OpenAI's official session endpoint.
   - **Prompt Injection Prevention:** `VoiceSessionCreateRequest` enforces `ConfigDict(extra="forbid")` and rejects any browser-supplied `instructions` (`422 Unprocessable Entity`). System instructions are composed exclusively on the backend from verified database records.
   - **Deliberate Public Visitor Access Policy:** A raw `business_id` or `organization_id` UUID is never accepted as proof of authorization. Public visitor sessions require a cryptographically verified HMAC-SHA256 `public_access_token` minted by an organization `owner`/`admin` AND require `assistant.enabled == True`.
   - **Sliding-Window Rate Limiting:** `POST /api/v1/voice/sessions` enforces per-actor/per-IP rate limits (`VOICE_SESSION_RATE_LIMIT_PER_MINUTE`, returning `429 Too Many Requests` with `Retry-After`).
   - **Privacy by Default:** Raw audio is never stored and `input_audio_transcription` is disabled (`None`) by default.

---

## 2. Healthcare Administrative Safeguards (Stage 2 & Stage 3)

For `clinic` and `hospital` organizations, Svario enforces strict administrative-only boundaries both in onboarding UI and in server-composed Realtime system instructions:
- **No medical diagnosis**
- **No prescription or medication dosing advice**
- **No treatment recommendations**
- **No clinical decision-making**
- **Data Minimization:** Never ask for or store unnecessary patient medical history or raw audio/transcripts by default.
- **Emergency Directive:** Callers describing medical emergencies are immediately instructed to contact local emergency services or proceed to the nearest hospital emergency department.
