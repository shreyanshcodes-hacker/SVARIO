# SVARIO — Security Baseline & Row Level Security Reference

**Milestone:** Stage 2 — Industry Selection & Business Onboarding  
**Roadmap Version:** 2.0

---

## 1. Defense-in-Depth Security Model

Svario enforces security at **three independent layers**:

1. **Cryptographic JWT Verification in FastAPI (`apps/api/app/core/auth.py`):**
   - Extracts `Authorization: Bearer <token>` via `get_current_user`.
   - Rejects missing, malformed, or `alg="none"` tokens immediately.
   - Prefers asymmetric signature verification (`ES256`, `RS256`, `EdDSA`) using public keys fetched from `SUPABASE_JWKS_URL`.
   - Validates `exp`, `nbf`, `iat`, `iss`, `aud`, and canonical `UUID` format on `sub`.
   - Never trusts unverified JWT payloads or client-supplied `user_id` fields in request bodies.
2. **Application-Layer RBAC & Membership Verification (`apps/api/app/modules/organizations/service.py` & `apps/api/app/modules/onboarding/service.py`):**
   - Before every organization or onboarding read/write, `OrganizationService` and `OnboardingService` explicitly verify the caller's membership and role (`owner`, `admin`, `staff`) in that organization.
   - `staff` members have read-only access (`GET`), while `owner` and `admin` members can update industry, business profile, hours, languages, assistant settings, FAQs, escalation settings, and onboarding progress.
3. **Database-Layer Row Level Security (`20261103000002_stage1_rls_policies.sql` & `20261108000004_stage2_onboarding_rls.sql`):**
   - Every Stage 1 and Stage 2 table has both `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`.
   - Composite foreign keys `(business_id, organization_id) REFERENCES public.businesses(id, organization_id)` prevent cross-tenant business record linking.

---

## 2. Row Level Security (RLS) Policy Matrix (Stage 1 & Stage 2)

| Table | `SELECT` Policy | `INSERT` Policy | `UPDATE` Policy | `DELETE` Policy |
| :--- | :--- | :--- | :--- | :--- |
| `profiles` | Own profile only (`id = auth.uid()`) | Own profile only (`id = auth.uid()`) | Own profile only (`id = auth.uid()`) | Cascaded from `auth.users` only |
| `organizations` | Verified org member (`is_org_member(id)`) | Authenticated user (`auth.uid() IS NOT NULL`) | Org `owner` or `admin` (`has_org_role`) | Org `owner` only (`has_org_role`) |
| `organization_members` | Own row (`user_id = auth.uid()`) OR fellow org member (`is_org_member(organization_id)`) | Bootstrap `owner` on empty org, OR `owner` adding any role, OR `admin` adding `staff` only | Org `owner` only | Org `owner` only |
| `businesses` | Verified org member (`is_org_member(organization_id)`) | Org `owner` or `admin` | Org `owner` or `admin` (both `USING` and `WITH CHECK`) | Org `owner` only |
| `business_settings` | Verified org member (`is_org_member(organization_id)`) | Org `owner` or `admin` | Org `owner` or `admin` (both `USING` and `WITH CHECK`) | Org `owner` only |
| `business_hours` | Verified org member (`is_org_member(organization_id)`) | Org `owner` or `admin` | Org `owner` or `admin` (both `USING` and `WITH CHECK`) | Org `owner` or `admin` |
| `business_profiles` | Verified org member (`is_org_member(organization_id)`) | Org `owner` or `admin` | Org `owner` or `admin` (both `USING` and `WITH CHECK`) | Org `owner` only |
| `business_languages` | Verified org member (`is_org_member(organization_id)`) | Org `owner` or `admin` | Org `owner` or `admin` (both `USING` and `WITH CHECK`) | Org `owner` or `admin` |
| `business_faqs` | Verified org member (`is_org_member(organization_id)`) | Org `owner` or `admin` | Org `owner` or `admin` (both `USING` and `WITH CHECK`) | Org `owner` or `admin` |
| `assistant_settings` | Verified org member (`is_org_member(organization_id)`) | Org `owner` or `admin` | Org `owner` or `admin` (both `USING` and `WITH CHECK`) | Org `owner` only |
| `escalation_settings` | Verified org member (`is_org_member(organization_id)`) | Org `owner` or `admin` | Org `owner` or `admin` (both `USING` and `WITH CHECK`) | Org `owner` only |
| `onboarding_progress` | Verified org member (`is_org_member(organization_id)`) | Org `owner` or `admin` | Org `owner` or `admin` (both `USING` and `WITH CHECK`) | Org `owner` only |
| `audit_logs` | Org `owner` or `admin` (`organization_id IS NOT NULL AND has_org_role(...)`) | Authenticated actor (`actor_user_id = auth.uid()` and member of org) | **Denied** (Immutable) | **Denied** (Immutable) |

---

## 3. Healthcare Administrative Safeguards (Stage 2)

For `clinic` and `hospital` organizations, Svario enforces strict administrative-only boundaries:
- **No medical diagnosis**
- **No prescription advice**
- **No treatment recommendations**
- **No clinical decision-making**
- **Emergency Directive:** Medical emergencies must immediately be directed to emergency services or hospital emergency contacts.
- **Data Minimization:** Onboarding does not collect sensitive patient health records or unnecessary medical data.

---

## 4. Security Limitations & Outstanding Verification Checks

1. **Live Supabase RLS Verification Status (`BLOCKED` in Local Environment):**
   - Static SQL policy verification (`apps/api/tests/test_rls_migration_audit.py`) and application-layer RBAC & cross-tenant isolation tests (`apps/api/tests/test_organizations.py`, `apps/api/tests/test_onboarding.py`) were executed and passed.
   - Live execution against a running Supabase PostgreSQL instance (`apps/api/tests/test_rls_live.py`) remains **BLOCKED** in this local environment because no live Supabase credentials (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, test user tokens) are configured locally.
