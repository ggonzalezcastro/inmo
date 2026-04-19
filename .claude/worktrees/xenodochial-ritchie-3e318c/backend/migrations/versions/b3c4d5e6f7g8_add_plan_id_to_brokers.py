"""add plan_id to brokers

Revision ID: b3c4d5e6f7g8
Revises: y1a2b3c4d5e6
Create Date: 2026-04-03

"""
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b3c4d5e6f7g8'
down_revision: Union[str, None] = 'y1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use IF NOT EXISTS via raw SQL to be idempotent (column may already exist
    # if it was added manually before this migration was created)
    op.execute("""
        ALTER TABLE brokers
        ADD COLUMN IF NOT EXISTS plan_id INTEGER REFERENCES broker_plans(id) ON DELETE SET NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_brokers_plan_id ON brokers (plan_id)
    """)


def downgrade() -> None:
    op.drop_index('ix_brokers_plan_id', table_name='brokers')
    op.drop_column('brokers', 'plan_id')
