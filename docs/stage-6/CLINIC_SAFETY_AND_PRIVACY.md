# SVARIO — STAGE 6: CLINIC HEALTHCARE SAFETY & PRIVACY

**Status:** Mandatory Administrative Guardrails (Stage 6 MVP)  
**Scope:** Outpatient & Specialty Clinics (`OrganizationIndustry.CLINIC`)

---

## 1. Scope Boundaries

Svario operates strictly as an **administrative clinic receptionist** for scheduling, clinic information, department/doctor discovery, and human escalation. Svario is **not** a clinical decision support tool, Electronic Health Record (EHR) system, or medical assistant.

---

## 2. Prohibited Clinical Behavior

The Clinic AI Agent (`ClinicAgent` + `IntentClassifier` + `AgentOrchestrator`) strictly prohibits:
1. Diagnosing diseases or medical conditions.
2. Interpreting patient symptoms or medical test/lab results.
3. Recommending medical treatments, surgeries, or therapies.
4. Prescribing medications, suggesting dosages, or advising callers to start/stop medication.
5. Performing clinical triage or making claims about treatment outcomes.
6. Replacing a qualified healthcare professional.

---

## 3. Emergency Handling

When `IntentClassifier` detects `AgentIntent.EMERGENCY_INTENT` (raising `SafetyFlag.MEDICAL_EMERGENCY_DETECTED`):
- Normal appointment booking is **immediately halted** (`booking_created = False`).
- The agent immediately instructs the caller (in `en`, `hi`, or `hinglish`) to contact local emergency services (`112 / 108 / 911`) or proceed to the nearest hospital emergency department without asking delaying questions.
- The agent never attempts to diagnose the emergency, never invents local emergency numbers, and never claims emergency dispatch occurred unless verified.

---

## 4. Data Minimization & Privacy

- **Appointment Fields:** `clinic_appointments` collects ONLY `patient_display_name` and `patient_contact` (phone or email). Extra clinical keys (e.g., `symptoms`, `diagnosis`, `medical_history`) are rejected (`ConfigDict(extra="forbid")` -> HTTP `422`).
- **Voice & Transcripts:** Raw voice recordings are not persisted (`raw_audio_storage_enabled = False`). Conversation summaries pass through `redact_sensitive_summary_text(..., is_healthcare=True)` to strip sensitive contact/clinical details.
- **Dashboard Masking:** `ClinicDashboardView` masks patient contact details (`••••XXXX`) in list views to prevent shoulder-surfing exposure.
- **Voice Reschedule/Cancel Verification:** Callers must provide both `booking_reference` and `patient_contact_verification`; failed verification never reveals whether an appointment exists.

---

## 5. Authorization, Access Controls & Retention Assumptions

- **Database RLS:** All 11 `clinic_*` tables have `ENABLE` and `FORCE ROW LEVEL SECURITY`. No `anon` policy is granted on `clinic_appointments`.
- **Backend Ownership:** FastAPI independently verifies organization membership, `industry == "clinic"`, and `owner`/`admin` roles for all configuration mutations.
- **Retention:** MVP uses in-memory/ephemeral session context and PostgreSQL relational records; retention/purging policies must be configured per clinic jurisdiction prior to production.

---

## 6. Regulatory & Compliance Disclaimer (MVP Limitation)

> [!WARNING]
> Implementing technical safeguards (data minimization, RLS, non-diagnostic prompts, and emergency redirection) does **not** by itself certify compliance with HIPAA, GDPR, DISHA, ABDM, or local healthcare privacy/medical-device regulations. Formal legal, privacy, and regulatory review (including BAAs with infrastructure/LLM providers) is **mandatory** before deploying Svario with real-world patient data.
