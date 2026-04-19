"""
Startup script for Railway (and any multi-replica deployment).

Runs under an advisory lock so concurrent instances don't race:
  - Instance A: gets lock → upgrades DB → seeds → releases → starts server
  - Instance B: waits for lock → lock released → upgrades (no-op) → seed (no-op) → starts server

Usage:
    python -m app.startup
"""
import os
import sys
import logging

logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                    format="%(asctime)s [startup] %(message)s")
log = logging.getLogger(__name__)

ADVISORY_LOCK_ID = 987_654_321


def _sync_url() -> str:
    raw = os.environ["DATABASE_URL"]
    return (raw
            .replace("postgresql+asyncpg://", "postgresql://")
            .replace("postgres://", "postgresql://"))


def run() -> None:
    from sqlalchemy import create_engine, text

    url = _sync_url()
    log.info("DB URL prefix: %s...", url[:30])
    engine = create_engine(url)

    # --- Advisory lock: serialise concurrent deploys ---
    with engine.connect() as lock_conn:
        lock_conn.execute(text("COMMIT"))          # must be outside transaction
        log.info("Acquiring advisory lock %s …", ADVISORY_LOCK_ID)
        lock_conn.execute(text(f"SELECT pg_advisory_lock({ADVISORY_LOCK_ID})"))
        log.info("Lock acquired.")

        try:
            _ensure_extensions(engine)
            _run_migrations()
            _seed(engine)
        finally:
            lock_conn.execute(text(f"SELECT pg_advisory_unlock({ADVISORY_LOCK_ID})"))
            log.info("Advisory lock released.")


def _ensure_extensions(engine) -> None:
    from sqlalchemy import create_engine, text
    try:
        with engine.connect() as conn:
            conn.execute(text("COMMIT"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("COMMIT"))
        log.info("vector extension OK")
    except Exception as exc:
        log.warning("vector extension skipped: %s", exc)


def _run_migrations() -> None:
    """Run alembic upgrade head via Python API (idempotent)."""
    import subprocess, sys
    log.info("Running alembic upgrade head …")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=False,
    )
    if result.returncode != 0:
        log.error("alembic upgrade head failed (exit %s)", result.returncode)
        sys.exit(result.returncode)
    log.info("alembic upgrade head OK")


def _seed(engine) -> None:
    """Idempotent seed: only inserts Demo broker + users if they don't exist."""
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text

    with engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM brokers WHERE name = 'Demo Inmobiliaria' LIMIT 1")
        ).fetchone()

    if exists:
        log.info("Seed data already present — skipping.")
        return

    sys.path.insert(0, "/app")
    from app.models.broker import Broker
    from app.models.user import User
    from app.middleware.auth import hash_password

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        broker = Broker(name="Demo Inmobiliaria")
        session.add(broker)
        session.flush()

        session.add(User(
            email="admin@demo.cl",
            hashed_password=hash_password("Admin1234!"),
            name="Admin Demo",
            role="ADMIN",
            broker_id=broker.id,
            is_active=True,
        ))
        session.add(User(
            email="agente@demo.cl",
            hashed_password=hash_password("Agente1234!"),
            name="Agente Demo",
            role="AGENT",
            broker_id=broker.id,
            is_active=True,
        ))
        session.commit()
        log.info("Seeded: broker=%s  admin=admin@demo.cl  agent=agente@demo.cl", broker.id)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run()
