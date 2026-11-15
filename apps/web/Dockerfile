# ==============================================================================
# SVARIO WEB — Next.js 15 Frontend Container (Ubuntu 24.04 LTS)
# ==============================================================================

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/apps/web

COPY apps/web/package.json apps/web/package-lock.json /app/apps/web/
RUN npm ci --include=dev

COPY apps/web /app/apps/web

ARG NEXT_PUBLIC_APP_NAME=SVARIO
ARG NEXT_PUBLIC_APP_STAGE=4
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

RUN npm run build \
    && useradd --create-home --shell /bin/bash svario \
    && chown -R svario:svario /app

USER svario

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:3000 >/dev/null || exit 1

CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
