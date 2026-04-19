"""promote human_mode, human_assigned_to, human_taken_at to typed columns

Moves these three fields from the leads.metadata JSONB blob to proper typed
columns with a foreign key, a NOT NULL boolean, and a partial index for
efficient queries.

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-03

"""
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the three new columns (idempotent via IF NOT EXISTS)
    op.execute("""
        ALTER TABLE leads
        ADD COLUMN IF NOT EXISTS human_mode BOOLEAN NOT NULL DEFAULT false
    """)
    op.execute("""
        ALTER TABLE leads
        ADD COLUMN IF NOT EXISTS human_assigned_to INTEGER
            REFERENCES users(id) ON DELETE SET NULL
    """)
    op.execute("""
        ALTER TABLE leads
        ADD COLUMN IF NOT EXISTS human_taken_at TIMESTAMPTZ
    """)

    # Copy existing values from JSONB to the new typed columns.
    # human_assigned_to is stored as a string in JSON, cast to integer.
    # human_taken_at is stored as an ISO-8601 string, cast to timestamptz.
    op.execute("""
        UPDATE leads
        SET
            human_mode = COALESCE((metadata->>'human_mode')::boolean, false),
            human_assigned_to = NULLIF(metadata->>'human_assigned_to', '')::integer,
            human_taken_at = NULLIF(metadata->>'human_taken_at', '')::timestamptz
        WHERE metadata IS NOT NULL
          AND (
              metadata ? 'human_mode'
              OR metadata ? 'human_assigned_to'
              OR metadata ? 'human_taken_at'
          )
    """)

    # Partial index — only indexes rows where human_mode=true (typically a
    # tiny fraction of leads), so it stays small and fast.
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_leads_human_mode_true
        ON leads (human_mode)
        WHERE human_mode = true
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_leads_human_mode_true")

    # Copy values back into JSONB before dropping the columns
    op.execute("""
        UPDATE leads
        SET metadata = metadata
            || jsonb_build_object(
                'human_mode', human_mode,
                'human_assigned_to', human_assigned_to,
                'human_taken_at', to_char(human_taken_at, 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
               )
        WHERE human_mode = true OR human_assigned_to IS NOT NULL OR human_taken_at IS NOT NULL
    """)

    op.drop_column('leads', 'human_taken_at')
    op.drop_column('leads', 'human_assigned_to')
    op.drop_column('leads', 'human_mode')
