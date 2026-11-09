# ==============================================================================
# SVARIO — Unified Full-Stack Container (Ubuntu 24.04 LTS)
# Includes:
#   - Ubuntu 24.04 LTS base OS + PostgreSQL client + system build/crypto libs
#   - Python 3 + isolated virtualenv (/opt/venv) for Svario FastAPI Backend
#   - Node.js 22 LTS + npm for Svario Next.js 15 Frontend
#   - Supabase migrations & project documentation
# ==============================================================================

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    SVARIO_RUN_MODE="all" \
    API_HOST="0.0.0.0" \
    API_PORT="8000" \
    PORT="3000"

# 1. Install core Ubuntu packages, Python 3, PostgreSQL client, and Node.js 22 LTS
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        git \
        build-essential \
        pkg-config \
        libssl-dev \
        libffi-dev \
        python3 \
        python3-dev \
        python3-pip \
        python3-venv \
        postgresql-client \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Setup Python virtual environment and install FastAPI backend dependencies
COPY apps/api/requirements.txt /app/apps/api/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip setuptools wheel \
    && /opt/venv/bin/pip install -r /app/apps/api/requirements.txt

# 3. Install Next.js frontend dependencies
COPY apps/web/package.json apps/web/package-lock.json /app/apps/web/
RUN cd /app/apps/web && npm ci --include=dev

# 4. Copy application source code, migrations, and entrypoint
COPY apps/api /app/apps/api
COPY apps/web /app/apps/web
COPY supabase /app/supabase
COPY docs /app/docs
COPY infra /app/infra
COPY .env.example /app/.env.example

# Build arguments for Next.js public environment variables (can be overridden at build time)
ARG NEXT_PUBLIC_APP_NAME=SVARIO
ARG NEXT_PUBLIC_APP_STAGE=2
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ARG NEXT_PUBLIC_SITE_URL=http://localhost:3000
ARG NEXT_PUBLIC_SUPABASE_URL=https://pxijyektjscrltwpvzua.supabase.co
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB4aWp5ZWt0anNjcmx0d3B2enVhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTM3MjI5MjMsImV4cCI6MjEwOTI5ODkyM30._cSA-iuNLQhQf_Ek66VgNTlfckwEvLrjGc2UCu-6uwI

ENV NEXT_PUBLIC_APP_NAME=${NEXT_PUBLIC_APP_NAME} \
    NEXT_PUBLIC_APP_STAGE=${NEXT_PUBLIC_APP_STAGE} \
    NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL} \
    NEXT_PUBLIC_SITE_URL=${NEXT_PUBLIC_SITE_URL} \
    NEXT_PUBLIC_SUPABASE_URL=${NEXT_PUBLIC_SUPABASE_URL} \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=${NEXT_PUBLIC_SUPABASE_ANON_KEY}

# 5. Build Next.js production bundle & normalize line endings on entrypoint
RUN cd /app/apps/web && npm run build \
    && sed -i 's/\r$//' /app/infra/docker-entrypoint.sh \
    && chmod +x /app/infra/docker-entrypoint.sh

# 6. Create non-root runtime user
RUN useradd --create-home --shell /bin/bash svario \
    && chown -R svario:svario /app /opt/venv

USER svario

EXPOSE 3000 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health >/dev/null || exit 1

ENTRYPOINT ["/app/infra/docker-entrypoint.sh"]
