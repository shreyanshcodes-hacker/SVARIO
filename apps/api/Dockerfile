# ==============================================================================
# SVARIO API — FastAPI Backend Container (Ubuntu 24.04 LTS)
# ==============================================================================

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:${PATH}" \
    API_HOST="0.0.0.0" \
    API_PORT="8000"

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        build-essential \
        libssl-dev \
        libffi-dev \
        python3 \
        python3-dev \
        python3-pip \
        python3-venv \
        postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/apps/api

COPY apps/api/requirements.txt /app/apps/api/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip setuptools wheel \
    && /opt/venv/bin/pip install -r /app/apps/api/requirements.txt

COPY apps/api /app/apps/api
COPY supabase /app/supabase

RUN useradd --create-home --shell /bin/bash svario \
    && chown -R svario:svario /app /opt/venv

USER svario

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health >/dev/null || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
