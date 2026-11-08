# SVARIO — Infrastructure & Deployment Guide

**Milestone:** Stage 0 — Product Foundation  
**Frontend Target:** Vercel (`apps/web`)  
**Backend Target:** Render (`apps/api`)

---

## 1. Deployment Architecture Overview

| Component | Source Directory | Hosting Target | Runtime | Health Check |
| :--- | :--- | :--- | :--- | :--- |
| **Svario Web** | `apps/web` | **Vercel** | Node.js / Next.js App Router | `/` |
| **Svario API** | `apps/api` | **Render** | Python 3 / FastAPI + Uvicorn | `GET /health` |

---

## 2. Frontend Deployment (Vercel)

- **Root Directory:** `apps/web`
- **Framework Preset:** Next.js
- **Install Command:** `npm install`
- **Build Command:** `npm run build`
- **Environment Variables (Vercel Project Settings):**
  - `NEXT_PUBLIC_APP_NAME` = `SVARIO`
  - `NEXT_PUBLIC_APP_STAGE` = `0`
  - `NEXT_PUBLIC_API_BASE_URL` = `https://<your-render-api-service>.onrender.com`

---

## 3. Backend Deployment (Render)

- **Root Directory:** `apps/api`
- **Runtime:** Python 3
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health Check Path:** `/health`
- **Environment Variables (Render Service Settings):**
  - `SVARIO_ENV` = `production`
  - `SVARIO_STAGE` = `0`
  - `API_SERVICE_NAME` = `Svario API`
  - `API_VERSION` = `0.1.0`
  - `CORS_ORIGINS` = `https://<your-vercel-domain>.vercel.app`

---

## 4. Planned Managed Services (Stage 1+)

Do **not** provision or wire these into application code during Stage 0:
- **Database:** Supabase PostgreSQL
- **Authentication:** Supabase Auth
- **Realtime Bus:** Supabase Realtime
- **Voice AI Runtime:** OpenAI Realtime API
