# SVARIO — Local Development & Supabase Setup Guide

**Milestone:** Stage 2 — Industry Selection & Business Onboarding  
**Stack:** Next.js 15 + TypeScript + Tailwind CSS v4 + `@supabase/supabase-js` | FastAPI + Pydantic v2 + `PyJWT[crypto]`

---

## 1. Prerequisites

- **Node.js:** v20+ (v24 recommended) and `npm`
- **Python:** Python 3.11+ and `pip`
- **Supabase Project:** A Supabase cloud project or local Supabase CLI stack (`supabase start`) for live authentication and database persistence.

---

## 2. Supabase Project & Dashboard Configuration

1. **Create or Open a Supabase Project** in the Supabase Dashboard.
2. **Inspect JWT Signing Settings:**
   - Navigate to **Project Settings → API → JWT Settings**.
   - Locate the **JWKS URL**: `https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json`.
   - Svario uses asymmetric JWT verification (`ES256`/`RS256`/`EdDSA`) via JWKS by default. If your project uses legacy symmetric `HS256`, either enable asymmetric signing keys in Supabase Auth or set `SUPABASE_JWT_ALGORITHMS=HS256` and `SUPABASE_JWT_SECRET=<your-jwt-secret>` in `apps/api/.env`.
3. **Configure Authentication Redirect URLs:**
   - Navigate to **Authentication → URL Configuration**:
     - **Site URL:** `http://localhost:3000` (or your production Vercel URL)
     - **Redirect URLs (Allowlist):**
       - `http://localhost:3000/dashboard`
       - `http://localhost:3000/onboarding`
       - `http://localhost:3000/reset-password`
       - `http://localhost:3000/login`
4. **Email Auth Provider:**
   - Navigate to **Authentication → Providers → Email** and ensure **Enable Email provider** is turned on.

---

## 3. Applying Database Migrations (`supabase/migrations/`)

Svario's Stage 1 & Stage 2 database schemas and Row Level Security policies are stored in:
1. `supabase/migrations/20261103000001_stage1_core_schema.sql`
2. `supabase/migrations/20261103000002_stage1_rls_policies.sql`
3. `supabase/migrations/20261108000003_stage2_onboarding_schema.sql`
4. `supabase/migrations/20261108000004_stage2_onboarding_rls.sql`

### Option A: Using Supabase CLI
```powershell
supabase link --project-ref <your-project-ref>
supabase db push
```

### Option B: Using `psql` or Supabase SQL Editor
Run the migration files in chronological order:
1. Execute `supabase/migrations/20261103000001_stage1_core_schema.sql`
2. Execute `supabase/migrations/20261103000002_stage1_rls_policies.sql`
3. Execute `supabase/migrations/20261108000003_stage2_onboarding_schema.sql`
4. Execute `supabase/migrations/20261108000004_stage2_onboarding_rls.sql`

---

## 4. Stage 2 Onboarding API Endpoints

All Stage 2 onboarding endpoints require `Authorization: Bearer <supabase-jwt>` and verify organization membership (`SELECT` allowed for `owner | admin | staff`; mutations restricted to `owner | admin`):

- `GET /api/v1/organizations/{organization_id}/onboarding` — Returns complete onboarding bundle (`organization`, `profile`, `hours`, `languages`, `assistant`, `faqs`, `faq_templates`, `escalation`, `healthcare_safeguards`, `progress`).
- `PUT /api/v1/organizations/{organization_id}/onboarding/industry` — Updates organization industry (`salon | clinic | hospital`).
- `GET/PUT /api/v1/organizations/{organization_id}/onboarding/profile` — Reads or updates 1:1 `business_profiles` record.
- `GET/PUT /api/v1/organizations/{organization_id}/onboarding/hours` — Reads or replaces 7-day `business_hours` schedule.
- `GET/PUT /api/v1/organizations/{organization_id}/onboarding/languages` — Reads or updates primary & supported `business_languages` (`en | hi | hinglish`).
- `GET/PUT /api/v1/organizations/{organization_id}/onboarding/assistant` — Reads or updates `assistant_settings`.
- `GET/POST /api/v1/organizations/{organization_id}/onboarding/faqs` — Lists or creates `business_faqs`.
- `PUT/DELETE /api/v1/organizations/{organization_id}/onboarding/faqs/{faq_id}` — Updates or deletes an organization-owned FAQ.
- `GET/PUT /api/v1/organizations/{organization_id}/onboarding/escalation` — Reads or updates `escalation_settings`.
- `GET/PUT /api/v1/organizations/{organization_id}/onboarding/progress` — Reads or updates `onboarding_progress` (`current_step`, `completed_steps`, `is_completed`).

---

## 5. Running the Applications

### Start Backend (`apps/api` — Port 8000)
```powershell
cd apps/api
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Start Frontend (`apps/web` — Port 3000)
```powershell
cd apps/web
npm install
npm run dev
```

---

## 6. Running Automated Tests

### Backend Tests (Auth, Organizations, Onboarding, Static RLS Audit & Live RLS Harness)
```powershell
cd apps/api
python -m pytest -v
```

### Frontend Unit Tests, Lint, Typecheck & Production Build
```powershell
cd apps/web
npm test
npm run lint
npm run typecheck
npm run build
```
