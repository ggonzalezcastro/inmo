#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade heads

echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
