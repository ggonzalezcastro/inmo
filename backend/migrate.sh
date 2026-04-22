#!/bin/sh
set -e

echo "=== Ensuring pgvector extension ==="
python3 -c "
import os
from sqlalchemy import create_engine, text
raw_url = os.environ['DATABASE_URL']
url = raw_url.replace('postgresql+asyncpg://', 'postgresql://').replace('postgres://', 'postgresql://')
engine = create_engine(url)
with engine.begin() as conn:
    conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
print('Extension OK')
"

echo "=== Running migrations ==="
alembic upgrade heads

echo "=== Done ==="
