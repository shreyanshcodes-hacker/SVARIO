# SVARIO — Security Baseline & Row Level Security Reference

**Milestone:** Stage 4 — AI Agent & Conversational Intelligence  
**Roadmap Version:** 2.0

---

## 1. Defense-in-Depth Security Model

Svario enforces security across **five independent layers**:

1. **Cryptographic JWT Verification in FastAPI (`apps/api/app/core/auth.py`):**
   - Extracts `Authorization: Bearer <token>` via `get_current_user`.
   - Prefers asymmetric signature verification (`ES256`, `RS256`, `EdDSA`) using public keys fetched from `SUPABASE_JWKS_URL`.
   - Validates `exp`, `nbf`, `iat`, `iss`, `aud`, and canonical `UUID` format on `sub`.
2. **Application-Layer RBAC & Membership Verification (`OrganizationService` & `OnboardingService`):**
   - Explicitly verifies caller membership and role (`owner`, `admin`, `staff`) before any organization or onboarding operation.
3. **Database-Layer Row Level Security (`supabase/migrations/`):**
   - Every Stage 1, Stage 2, and Stage 4 table (`conversation_summaries`, `escalation_requests`) has both `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`.
   - Composite foreign keys `(business_id, organization_id)` prevent cross-tenant record linking.
4. **Stage 3 Voice Session & Credential Security (`apps/api/app/modules/voice/`):**
   - **Backend-Only Master Key:** The permanent `OPENAI_API_KEY` is never exposed to browser clients, error payloads, or logs.
   - **Short-Lived Ephemeral Credentials:** Browser WebRTC sessions authenticate using short-lived ephemeral tokens (`client_secret.value`) minted via OpenAI's official `POST /v1/realtime/client_secrets` endpoint.
   - **Prompt Injection Prevention:** `VoiceSessionCreateRequest` enforces `ConfigDict(extra="forbid")` and rejects any browser-supplied `instructions` (`422 Unprocessable Entity`). System instructions are composed exclusively on the backend from verified database records.
   - **Deliberate Public Visitor Access Policy:** A raw `business_id` or `organization_id` UUID is never accepted as proof of authorization. Public visitor sessions require a cryptographically verified HMAC-SHA256 `public_access_token` minted by an organization `owner`/`admin` AND require `assistant.enabled == True`.
   - **Sliding-Window Rate Limiting:** `POST /api/v1/voice/sessions` and `POST /api/v1/voice/tools/execute` enforce per-actor/per-IP rate limits (`429 Too Many Requests` with `Retry-After`).
5. **Stage 4 Controlled AI Agent & Tool Execution Security (`apps/api/app/agents/`):**
   - **AI Interprets; FastAPI Validates & Executes:** The model never receives database credentials, never executes SQL, and never alters organization ownership.
   - **Tenant-Bound Tool Execution:** Tool arguments cannot supply or override `organization_id`, `business_id`, or `tenant_id` (`ValueError` -> `status="rejected"`). All tool inputs use `ConfigDict(extra="forbid")`.
   - **Session Context Isolation:** `ConversationContextManager` binds every `session_id` to `(organization_id, business_id)` and raises `403 Forbidden` on any cross-tenant or cross-business session access attempt.
   - **Per-Turn Tool Call Limits & Timeouts:** `AgentOrchestrator` enforces `max_tool_calls_per_turn=3` and `tool_timeout_seconds=5.0` to prevent runaway tool loops.
   - **Truthful Action & Escalation Reporting:** The agent never claims an appointment was booked (`booking_created=False`) and never claims a human staff member was contacted live unless a delivery integration confirms it (`notification_delivered=False`).

---

## 2. Healthcare Administrative Safeguards (Stage 2, Stage 3 & Stage 4)

For `clinic` and `hospital` organizations, Svario enforces strict administrative-only boundaries across onboarding, system instructions, intent classification, and tool execution:
- **No medical diagnosis** (`SafetyFlag.CLINICAL_DIAGNOSIS_REQUEST` triggers immediate refusal + `request_human_escalation` with `urgency='clinical_staff'`)
- **No prescription or medication dosing advice** (`SafetyFlag.PRESCRIPTION_OR_MEDICATION_REQUEST` triggers immediate refusal + clinical staff escalation)
- **No treatment recommendations** (`SafetyFlag.TREATMENT_RECOMMENDATION_REQUEST` triggers immediate refusal + clinical staff escalation)
- **Immediate Emergency Protocol:** Any emergency-intent utterance (`chest pain`, `stroke`, `breathing difficulty`, `unconscious`, `severe bleeding`) short-circuits normal conversation and immediately directs the caller to local emergency services (`112 / 108 / 911`) or the hospital emergency department without asking delaying clarification questions.
- **Data Minimization & Redaction:** Conversation summaries automatically redact phone numbers, emails, national IDs, and clinical symptom descriptions (`redact_sensitive_summary_text`).
