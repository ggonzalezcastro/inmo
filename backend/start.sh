#!/bin/sh
set -e

# Dispatch based on Railway service name — celery services skip DB init entirely.
case "${RAILWAY_SERVICE_NAME}" in
  "celery worker")
    echo "=== Starting Celery worker ===" >&2
    exec celery -A app.celery_app worker --loglevel=info
    ;;
  "celery-beat")
    echo "=== Starting Celery beat ===" >&2
    exec celery -A app.celery_app beat --loglevel=info
    ;;
esac

python3 -m app.startup

echo "=== Starting server ===" >&2
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
