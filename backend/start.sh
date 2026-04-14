#!/bin/sh
set -e

echo "Running database migrations..."
# Stamp initial migration if alembic_version is empty (tables created by init_db, not alembic)
alembic stamp a6f3f625b64a 2>/dev/null || true
# Now apply all subsequent migrations
alembic upgrade heads

echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
