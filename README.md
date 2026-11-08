# SVARIO

> **AI that speaks for your business.**  
> Multi-Industry AI Voice Agent Platform for **Salons**, **Clinics**, and **Hospitals**.

**Current Milestone:** `STAGE 2 — INDUSTRY SELECTION & BUSINESS ONBOARDING` (Version 2.0)

---

## 1. Product Overview

**SVARIO** is a premium, multi-industry AI Voice Agent Platform built to handle inbound reception, domain-aware caller triage, and scheduling coordination across three target industries:

1. **Salons** — Service duration guidance, stylist tier preference matching, and peak-hour front-desk call overflow.
2. **Clinics** — Structured outpatient intake, practitioner specialty routing, pre-visit instructions, and non-diagnostic clinical guardrails.
3. **Hospitals** — 24/7 departmental switchboard navigation, OPD directory routing, visiting-hour FAQs, and zero-delay emergency human escalation.

---

## 2. Approved Technology Stack

| Layer | Technology | Status in Stage 2 |
| :--- | :--- | :--- |
| **Frontend** | Next.js 15 (App Router) + TypeScript (Strict) | Active (`apps/web`) |
| **Styling** | Tailwind CSS v4 + Official Svario Tokens | Active (`apps/web`) |
| **Backend** | Python + FastAPI | Active (`apps/api`) |
| **Validation & Config** | Pydantic v2 + `pydantic-settings` | Active (`apps/api`) |
| **Database** | Supabase PostgreSQL (Stage 1 + Stage 2 RLS Migrations) | Active (`supabase/migrations/`) |
| **Authentication** | Supabase Auth + FastAPI JWKS/JWT Verification | Active (`apps/web`, `apps/api`) |
| **Voice Runtime** | OpenAI Realtime API | Planned (Stage 3+) |
| **Realtime Events** | Supabase Realtime | Planned (Stage 4+) |
| **Deployments** | Vercel (Frontend) + Render (Backend) | Documented (`infra/README.md`) |

---

## 3. Repository Structure

```text
Voice agent-PS-03/
├── apps/
│   ├── web/                  # Next.js 15 + TypeScript + Tailwind CSS frontend
│   │   ├── src/
│   │   │   ├── app/          # /, /login, /signup, /forgot-password, /reset-password, /onboarding, /dashboard
│   │   │   ├── components/   # Auth, Organizations, OnboardingWizard & Foundation UI
│   │   │   ├── context/      # AuthOrganizationContext
│   │   │   ├── lib/          # Typed FastAPI client & browser Supabase client
│   │   │   └── __tests__/    # Vitest + React Testing Library tests (Stage 1 & Stage 2)
│   │   └── package.json
│   └── api/                  # Python + FastAPI backend
│       ├── app/
│       │   ├── core/         # Pydantic settings, JWT verifier & error handlers
│       │   ├── routes/       # /, /health, /architecture, /api/v1/auth, /api/v1/organizations, /onboarding
│       │   ├── modules/      # organizations, onboarding, shared, salons, clinics, hospitals
│       │   └── main.py
│       ├── tests/            # Pytest test suite (Auth, Orgs, Onboarding, RLS Audit, Live RLS)
│       └── requirements.txt
├── supabase/
│   └── migrations/           # Stage 1 & Stage 2 SQL schemas and forced RLS policies
├── brand assets/             # Preserved official color system & brand asset files
├── docs/                     # Architecture, Stage Plan, Development Guide, Security Baseline
└── infra/                    # Deployment configuration
```

---

## 4. Running Tests & Verification

```powershell
# Backend tests (30 passed, 1 skipped live-DB test when credentials are absent)
cd apps/api
python -m pytest -v

# Frontend unit tests, lint, typecheck, and production build
cd ../web
npm test
npm run lint
npm run typecheck
npm run build
```

---

## 5. Documentation Index

- [Architecture Specification](docs/architecture.md)
- [Stage Delivery Plan](docs/stage-plan.md)
- [Development Guide](docs/development-guide.md)
- [Security Baseline](docs/security-baseline.md)
- [Infrastructure & Deployment](infra/README.md)
