# SVARIO — Infrastructure, Docker (Ubuntu 24.04) & Deployment Guide

**Milestone:** Stage 2 — Industry Selection & Business Onboarding  
**Container Base Image:** `ubuntu:24.04`  
**Cloud Hosting Targets:** Vercel (`apps/web`) + Render (`apps/api`) + Supabase PostgreSQL

---

## 1. Ubuntu 24.04 Docker Container Setup

Svario includes complete `ubuntu:24.04` Dockerfiles for both **unified single-container deployment** (`Dockerfile`) and **multi-service Docker Compose orchestration** (`docker-compose.yml`).

### What Is Installed Inside the Ubuntu 24.04 Image
- **System Packages:** `ca-certificates`, `curl`, `gnupg`, `git`, `build-essential`, `pkg-config`, `libssl-dev`, `libffi-dev`, `postgresql-client`
- **Python 3 Runtime:** `python3`, `python3-venv`, `python3-pip`, `python3-dev` with an isolated virtual environment at `/opt/venv` containing all FastAPI, Pydantic v2, `httpx`, `PyJWT[crypto]`, and `pytest` dependencies from `apps/api/requirements.txt`
- **Node.js Runtime:** Node.js 22 LTS + `npm` with all Next.js 15, React 19, Tailwind CSS v4, TypeScript, and `@supabase/supabase-js` dependencies built for production
- **Security:** Runs as non-root user `svario` with built-in `/health` HTTP healthcheck

---

### Option A: Run Unified Full-Stack Ubuntu Container (`Dockerfile`)

Builds and runs **both** the FastAPI backend (`:8000`) and the Next.js frontend (`:3000`) inside a single `ubuntu:24.04` container:

```powershell
# 1. Build the unified Ubuntu 24.04 image
docker build -t svario-ubuntu:latest .

# 2. Run the container (exposing Web on 3000 and API on 8000)
docker run --rm -it `
  --name svario-app `
  --env-file apps/api/.env `
  --env-file apps/web/.env.local `
  -p 3000:3000 `
  -p 8000:8000 `
  svario-ubuntu:latest
```

You can also switch runtime modes via `-e SVARIO_RUN_MODE=<mode>`:
- `SVARIO_RUN_MODE=all` (default): Starts both FastAPI (`:8000`) and Next.js production server (`:3000`)
- `SVARIO_RUN_MODE=dev`: Starts FastAPI (`--reload`) and Next.js (`next dev`)
- `SVARIO_RUN_MODE=api`: Starts only FastAPI (`:8000`)
- `SVARIO_RUN_MODE=web`: Starts only Next.js (`:3000`)

---

### Option B: Run with Docker Compose (`docker-compose.yml`)

```powershell
# Start separate Ubuntu 24.04 containers for svario-api (:8000) and svario-web (:3000)
docker compose up --build

# Or start the unified single-container profile via Docker Compose
docker compose --profile unified up --build
```

---

## 2. Cloud Deployment Targets (Vercel & Render)

| Component | Source Directory | Hosting Target | Runtime | Health Check |
| :--- | :--- | :--- | :--- | :--- |
| **Svario Web** | `apps/web` | **Vercel** | Node.js / Next.js App Router | `/` |
| **Svario API** | `apps/api` | **Render** | Python 3 / FastAPI + Uvicorn | `GET /health` |
| **Svario Database & Auth** | `supabase/migrations` | **Supabase** | PostgreSQL 17 + GoTrue JWKS | `/auth/v1/.well-known/jwks.json` |
