#!/usr/bin/env bash
set -euo pipefail

MODE="${SVARIO_RUN_MODE:-all}"
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${PORT:-3000}"

echo "============================================================"
echo " SVARIO — Ubuntu 24.04 Container Runtime"
echo " Mode: ${MODE} | API Port: ${API_PORT} | Web Port: ${WEB_PORT}"
echo "============================================================"

case "${MODE}" in
  api)
    cd /app/apps/api
    exec /opt/venv/bin/uvicorn app.main:app --host "${API_HOST}" --port "${API_PORT}"
    ;;
  web)
    cd /app/apps/web
    exec npm run start -- --hostname 0.0.0.0 --port "${WEB_PORT}"
    ;;
  dev)
    cd /app/apps/api
    /opt/venv/bin/uvicorn app.main:app --reload --host "${API_HOST}" --port "${API_PORT}" &
    API_PID=$!

    cd /app/apps/web
    npm run dev -- --hostname 0.0.0.0 --port "${WEB_PORT}" &
    WEB_PID=$!

    trap 'kill -TERM ${API_PID} ${WEB_PID} 2>/dev/null || true' SIGINT SIGTERM
    wait -n "${API_PID}" "${WEB_PID}"
    ;;
  all|*)
    cd /app/apps/api
    /opt/venv/bin/uvicorn app.main:app --host "${API_HOST}" --port "${API_PORT}" &
    API_PID=$!

    cd /app/apps/web
    npm run start -- --hostname 0.0.0.0 --port "${WEB_PORT}" &
    WEB_PID=$!

    trap 'kill -TERM ${API_PID} ${WEB_PID} 2>/dev/null || true' SIGINT SIGTERM
    wait -n "${API_PID}" "${WEB_PID}"
    ;;
esac
