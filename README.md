<p align="center">
  <img src="apps/web/public/svario-logo.jpg" alt="SVARIO Logo" width="110" style="border-radius: 16px;" />
</p>

<h1 align="center">SVARIO</h1>

<p align="center">
  <strong>AI that speaks for your business.</strong><br/>
  AI Voice Receptionist &amp; Appointment Booking Platform — Built Salon-First, Ready for Healthcare Expansion.
</p>

---

## 1. Product Overview

**SVARIO** gives salons an always-on AI voice receptionist and a shareable public booking website that answers customer calls, explains real salon services and pricing, checks live stylist availability, and books, reschedules, or cancels appointments automatically.

### Industry Positioning
- **Salons** — **Available Now** (Full AI voice receptionist, live availability, booking engine, owner dashboard, and 8 public booking website templates).
- **Clinics** — **Coming Soon** *(foundation modules preserved for post-hackathon expansion)*.
- **Hospitals** — **Coming Soon** *(foundation modules preserved for post-hackathon expansion)*.

---

## 2. Verified Features

### AI Voice Receptionist (OpenAI Realtime WebRTC)
- Real-time bidirectional browser audio over OpenAI Realtime WebRTC with short-lived server-minted ephemeral credentials.
- Live salon **service & pricing discovery** directly from Supabase (`get_salon_services`).
- Real-time **stylist & slot availability** checks respecting business hours, staff shifts, breaks, holidays, and existing bookings (`check_salon_availability`).
- **Automatic appointment booking** with explicit customer confirmation, PostgreSQL GiST double-booking prevention (`excl_salon_appointments_no_staff_overlap`), and idempotency (`create_salon_appointment`).
- **Appointment rescheduling & cancellation** through natural conversation (`reschedule_salon_appointment`, `cancel_salon_appointment`).
- **Customer information capture** (name, phone, optional email) with strict server-side tenant resolution — never exposing private tenant UUIDs or credentials to the browser.

### Public Salon Booking Websites (`/s/[slug]`)
- Unique shareable salon URLs (`/s/<salon-slug>`) with draft, preview, and publish lifecycle.
- **8 distinct salon website templates**:
  `luxe_studio`, `minimal_elegance`, `blush_beauty`, `noir_salon`, `organic_glow`, `urban_chic`, `editorial_pro`, and `classic_beauty`.
- **Template-aware embedded AI Receptionist** that automatically adapts to the salon's selected template theme.
- Private brand asset storage (`salon-brand-assets`) served securely through backend proxy routes.

### Salon Owner Dashboard (`/dashboard`, `/dashboard/booking-website`, `/onboarding`)
- Multi-tenant organization & business onboarding wizard (profile, operating hours, languages, assistant persona, FAQs, escalation settings).
- Full salon management: services & pricing catalog, stylists & service assignments, working hours, breaks, holidays, live availability preview, and appointment management (book, reschedule, cancel).
- Booking Website Studio: template gallery, live preview, custom branding, URL slug availability checker, and publish/unpublish controls.

### Public Marketing & Brand Experience
- Customer-facing landing page (`/`) with official Svario branding, **Simple, Transparent Pricing** (**Starter — ₹3,999/month** and **Pro — Coming Soon**), and Salon-first industry positioning.
- Dedicated **About Us** page (`/about`) featuring founder profile and attribution.

### Post-Hackathon Foundation (Safely Paused)
- **SMS Reminder Engine & MSG91 Adapter + DLR Webhook**: Database schema (`appointment_sms_reminders`, `appointment_sms_delivery_events`), atomic `FOR UPDATE SKIP LOCKED` claiming, lease fencing, `AMBIGUOUS_TIMEOUT` protection, and recipient-level reconciliation are implemented and verified, and intentionally paused (`SMS_REMINDERS_ENABLED=false`, `SMS_PROVIDER=noop`, `MSG91_LOGS_RECONCILIATION_ENABLED=false`).
- **Email Reminders (Resend + Supabase Cron/Edge Function)**: Architecture planned for post-hackathon rollout.

---

## 3. Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend** | Next.js 15 (App Router), React, TypeScript (Strict), Tailwind CSS v4 |
| **Backend** | Python 3, FastAPI, Pydantic v2, `httpx` |
| **Database & Storage** | Supabase PostgreSQL 17 with Forced Row Level Security (RLS) & Private Storage |
| **Authentication** | Supabase Auth + FastAPI JWKS/JWT Verification |
| **Voice Runtime** | OpenAI Realtime API (WebRTC + `oai-events` Data Channel) |
| **Testing** | Pytest (Backend) + Vitest & React Testing Library (Frontend) |
| **Deployment** | Vercel (Frontend) + Render / Unified Docker Image (Backend) |

---

## 4. Repository Structure

```text
SVARIO/
├── apps/
│   ├── web/                          # Next.js 15 + TypeScript + Tailwind CSS frontend
│   │   ├── public/                   # Official Svario logo (svario-logo.jpg) & founder portrait
│   │   └── src/
│   │       ├── app/                  # /, /about, /login, /signup, /onboarding, /dashboard, /dashboard/booking-website, /s/[slug], /voice-test
│   │       ├── components/           # Branding, Pricing, Auth, Dashboard, Onboarding, Voice, 8 Website Templates & Public AI Receptionist
│   │       ├── context/              # AuthOrganizationContext
│   │       ├── lib/                  # Typed API client, WebRTC voice client & Supabase browser client
│   │       └── __tests__/            # Vitest + React Testing Library test suite (10 files, 65 tests)
│   └── api/                          # Python + FastAPI backend
│       ├── app/
│       │   ├── agents/               # AgentOrchestrator, SalonAgent, tool schemas & salon_tools
│       │   ├── core/                 # Pydantic settings, JWT verifier & internal voice actor security
│       │   ├── modules/              # organizations, onboarding, salons, clinics, voice, websites, notifications
│       │   ├── routes/               # REST API routes (auth, orgs, onboarding, salons, voice, public websites, webhooks)
│       │   ├── workers/              # Standalone SMS reminder worker (paused by default)
│       │   └── main.py
│       └── tests/                    # Pytest test suite (125 passed)
├── supabase/
│   └── migrations/                   # Versioned PostgreSQL schemas, RLS policies & SECURITY DEFINER RPCs
├── brand assets/                     # Official Svario logo & color system assets
├── docs/                             # Architecture, Stage Plan, Development Guide & Security Baseline
└── infra/                            # Docker entrypoint & deployment docs
```

---

## 5. Running Tests & Verification

```powershell
# Backend test suite (125 passed, 1 skipped)
cd apps/api
python -m pytest -q

# Frontend TypeScript check, ESLint, Vitest (10 files, 65 tests), and Next.js build
cd ../web
npx tsc --noEmit
npm run lint
npm test -- --run
npm run build
```

---

## 6. Documentation Index

- [Architecture Specification](docs/architecture.md)
- [Stage Delivery Plan](docs/stage-plan.md)
- [Development Guide](docs/development-guide.md)
- [Security Baseline](docs/security-baseline.md)
- [Infrastructure & Deployment](infra/README.md)

---

## 7. Team & Attribution

- **Shreyansh Jaiswal** — Founder & CEO, Svario
- **Developed with Shreyansh Codes**
