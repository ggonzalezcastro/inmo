#!/bin/sh
set -e

echo "Stamping all migration heads (tables already exist from init_db)..."
alembic stamp z2b3c4d5e6f7 18bc8eda7670 9d8a10e4b28e p1a2b3c4d5e6 2>/dev/null || true

echo "Adding any missing columns..."
python3 -c "
import os
from sqlalchemy import create_engine, text
url = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql+psycopg2://')
engine = create_engine(url)
cols = [
    'ALTER TABLE users ADD COLUMN IF NOT EXISTS assignment_priority INTEGER',
    'ALTER TABLE users ADD COLUMN IF NOT EXISTS outlook_refresh_token TEXT',
    'ALTER TABLE users ADD COLUMN IF NOT EXISTS outlook_calendar_id VARCHAR(255)',
    'ALTER TABLE users ADD COLUMN IF NOT EXISTS outlook_calendar_email VARCHAR(255)',
    'ALTER TABLE users ADD COLUMN IF NOT EXISTS outlook_calendar_connected BOOLEAN DEFAULT FALSE',
]
with engine.begin() as conn:
    for col in cols:
        try:
            conn.execute(text(col))
            print(f'OK: {col[:60]}')
        except Exception as e:
            print(f'Skip: {e}')
"

echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
