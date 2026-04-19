"""Ensure users has name (from broker_name) and broker_id.

Fixes schema drift: initial migration created users.broker_name; the model
expects users.name. Also ensures broker_id exists (FK to brokers).
Idempotent: safe to run on DBs already fixed manually or by a7e6cad13f8d.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "n5i6j7k8l9m0"
down_revision = "m4h5i6j7k8l9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1) Rename broker_name -> name if needed (model expects 'name')
    r = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'broker_name'
    """))
    has_broker_name = r.fetchone() is not None
    r = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'name'
    """))
    has_name = r.fetchone() is not None
    if has_broker_name and not has_name:
        op.execute(sa.text("ALTER TABLE users RENAME COLUMN broker_name TO name"))

    # 2) Add broker_id if missing (FK to brokers, nullable)
    r = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'broker_id'
    """))
    if r.fetchone() is None:
        op.execute(sa.text("""
            ALTER TABLE users
            ADD COLUMN broker_id INTEGER REFERENCES brokers(id) ON DELETE CASCADE
        """))
        op.execute(sa.text("CREATE INDEX ix_users_broker_id ON users (broker_id)"))


def downgrade() -> None:
    conn = op.get_bind()

    # Remove broker_id if we added it (optional: only if no FKs depend on it from users side)
    r = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'broker_id'
    """))
    if r.fetchone() is not None:
        op.execute(sa.text("DROP INDEX IF EXISTS ix_users_broker_id"))
        op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS broker_id"))

    # Rename name -> broker_name (revert only if we have name and no broker_name)
    r = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'name'
    """))
    has_name = r.fetchone() is not None
    r = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'broker_name'
    """))
    has_broker_name = r.fetchone() is not None
    if has_name and not has_broker_name:
        op.execute(sa.text("ALTER TABLE users RENAME COLUMN name TO broker_name"))
