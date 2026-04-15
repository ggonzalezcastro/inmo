#!/bin/sh
set -e

# Dispatch based on Railway service name so all services can share this Dockerfile.
# celery worker and celery-beat must NOT reset the database.
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

echo "=== DB init (advisory-locked) ===" >&2
python3 -c "
import os, sys
sys.path.insert(0, '/app')

raw_url = os.environ['DATABASE_URL']
url = raw_url \
    .replace('postgresql+asyncpg://', 'postgresql://') \
    .replace('postgres://', 'postgresql://')

print(f'DB URL prefix: {url[:30]}...', flush=True, file=sys.stderr)

from sqlalchemy import create_engine, text
engine = create_engine(url)

# Advisory lock (id=987654321) serializes concurrent Railway instances.
# One instance does the full init; the other waits, then skips (tables already exist).
LOCK_ID = 987654321

with engine.connect() as lock_conn:
    lock_conn.execute(text('COMMIT'))  # must be outside transaction for session-level lock
    print('Acquiring advisory lock...', flush=True, file=sys.stderr)
    lock_conn.execute(text(f'SELECT pg_advisory_lock({LOCK_ID})'))
    print('Lock acquired.', flush=True, file=sys.stderr)

    try:
        # Check if DB is already initialized (tables exist)
        with engine.connect() as chk:
            result = chk.execute(text(
                \"SELECT count(*) FROM information_schema.tables \"
                \"WHERE table_schema='public' AND table_name='users'\"
            ))
            already_init = result.scalar() > 0

        if already_init:
            print('Tables already exist — skipping init.', flush=True, file=sys.stderr)
        else:
            # --- Reset schema ---
            with engine.connect() as conn:
                conn.execute(text('COMMIT'))
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

            # --- Vector extension ---
            try:
                with engine.connect() as conn:
                    conn.execute(text('COMMIT'))
                    conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
                    conn.execute(text('COMMIT'))
                print('vector extension OK', flush=True, file=sys.stderr)
            except Exception as e:
                print(f'WARNING: vector extension skipped: {e}', flush=True, file=sys.stderr)

            # --- Create tables ---
            from app.models import *
            from app.models.base import Base
            Base.metadata.create_all(engine)
            print('Tables created OK', flush=True, file=sys.stderr)

            # --- Seed ---
            from sqlalchemy.orm import sessionmaker
            from app.models.broker import Broker
            from app.models.user import User
            from app.middleware.auth import hash_password

            Session = sessionmaker(bind=engine)
            session = Session()
            broker = Broker(name='Demo Inmobiliaria')
            session.add(broker)
            session.flush()
            session.add(User(
                email='admin@demo.cl',
                hashed_password=hash_password('Admin1234!'),
                name='Admin Demo',
                role='ADMIN',
                broker_id=broker.id,
                is_active=True,
            ))
            session.add(User(
                email='agente@demo.cl',
                hashed_password=hash_password('Agente1234!'),
                name='Agente Demo',
                role='AGENT',
                broker_id=broker.id,
                is_active=True,
            ))
            session.commit()
            print(f'Seeded: broker={broker.id}, admin=admin@demo.cl, agent=agente@demo.cl', flush=True, file=sys.stderr)
            session.close()

    finally:
        lock_conn.execute(text(f'SELECT pg_advisory_unlock({LOCK_ID})'))
        print('Advisory lock released.', flush=True, file=sys.stderr)
"

echo "=== Stamping alembic ===" >&2
alembic stamp heads

echo "=== Starting server ===" >&2
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
