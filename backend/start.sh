#!/bin/sh
set -e

echo "=== Resetting database ===" >&2
python3 -c "
import os, sys

raw_url = os.environ['DATABASE_URL']
url = raw_url \
    .replace('postgresql+asyncpg://', 'postgresql://') \
    .replace('postgres://', 'postgresql://')

print(f'DB URL prefix: {url[:30]}...', flush=True, file=sys.stderr)

from sqlalchemy import create_engine, text
engine = create_engine(url)

try:
    with engine.connect() as conn:
        conn.execute(text('COMMIT'))  # exit any open transaction
        # Kill other connections so DROP SCHEMA does not hang
        conn.execute(text('''
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = current_database()
              AND pid <> pg_backend_pid()
        '''))
        conn.execute(text('DROP SCHEMA public CASCADE'))
        conn.execute(text('CREATE SCHEMA public'))
        conn.execute(text('COMMIT'))
    print('Schema reset OK', flush=True, file=sys.stderr)
except Exception as e:
    print(f'ERROR resetting schema: {e}', flush=True, file=sys.stderr)
    sys.exit(1)

# Create vector extension outside a transaction (required by PostgreSQL)
try:
    with engine.connect() as conn:
        conn.execute(text('COMMIT'))
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
        conn.execute(text('COMMIT'))
    print('vector extension OK', flush=True, file=sys.stderr)
except Exception as e:
    print(f'WARNING: vector extension skipped: {e}', flush=True, file=sys.stderr)
"

echo "=== Creating tables ===" >&2
python3 -c "
import os, sys
sys.path.insert(0, '/app')

raw_url = os.environ['DATABASE_URL']
url = raw_url \
    .replace('postgresql+asyncpg://', 'postgresql://') \
    .replace('postgres://', 'postgresql://')

from sqlalchemy import create_engine
from app.models import *
from app.models.base import Base

engine = create_engine(url)
Base.metadata.create_all(engine)
print('Tables created OK', flush=True, file=sys.stderr)
"

echo "=== Stamping alembic ===" >&2
alembic stamp heads

echo "=== Seeding data ===" >&2
python3 -c "
import os, sys
sys.path.insert(0, '/app')

raw_url = os.environ['DATABASE_URL']
url = raw_url \
    .replace('postgresql+asyncpg://', 'postgresql://') \
    .replace('postgres://', 'postgresql://')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
engine = create_engine(url)
Session = sessionmaker(bind=engine)
session = Session()

from app.models.broker import Broker
from app.models.user import User
from app.middleware.auth import hash_password

broker = Broker(name='Demo Inmobiliaria')
session.add(broker)
session.flush()

admin = User(
    email='admin@demo.cl',
    hashed_password=hash_password('Admin1234!'),
    name='Admin Demo',
    role='ADMIN',
    broker_id=broker.id,
    is_active=True,
)
session.add(admin)

agent = User(
    email='agente@demo.cl',
    hashed_password=hash_password('Agente1234!'),
    name='Agente Demo',
    role='AGENT',
    broker_id=broker.id,
    is_active=True,
)
session.add(agent)
session.commit()
print(f'Seeded: broker={broker.id}, admin=admin@demo.cl, agent=agente@demo.cl', flush=True, file=sys.stderr)
session.close()
"

echo "=== Starting server ===" >&2
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
