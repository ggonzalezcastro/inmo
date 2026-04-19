"""add_broker_messaging_config_fields

Revision ID: d9f9d197f1bb
Revises: e6f193bab118
Create Date: 2026-01-20 17:59:59.310474

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd9f9d197f1bb'
down_revision: Union[str, None] = 'e6f193bab118'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table: str, column: str) -> bool:
    r = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :t AND column_name = :c
    """), {"t": table, "c": column})
    return r.fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()
    cols = [
        ("benefits_info", postgresql.JSONB(astext_type=sa.Text())),
        ("qualification_requirements", postgresql.JSONB(astext_type=sa.Text())),
        ("follow_up_messages", postgresql.JSONB(astext_type=sa.Text())),
        ("additional_fields", postgresql.JSONB(astext_type=sa.Text())),
        ("meeting_config", postgresql.JSONB(astext_type=sa.Text())),
        ("message_templates", postgresql.JSONB(astext_type=sa.Text())),
    ]
    for col_name, col_type in cols:
        if not _column_exists(conn, "broker_prompt_configs", col_name):
            op.add_column("broker_prompt_configs", sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    for col in ("message_templates", "meeting_config", "additional_fields", "follow_up_messages", "qualification_requirements", "benefits_info"):
        conn = op.get_bind()
        if _column_exists(conn, "broker_prompt_configs", col):
            op.drop_column("broker_prompt_configs", col)

