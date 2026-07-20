"""Fix broker_id FKs: voice_calls, campaigns, message_templates pointed to users.id

Revision ID: b5c6d7e8f9a0
Revises: merge_voice_pipecat
Create Date: 2026-06-10

These three tables declared broker_id with ForeignKey("users.id") since their
original migration (e5f6g7a8h9i0). The column has always been populated with
real broker ids (code passes current_user["broker_id"]), so the constraint was
semantically wrong: deleting a user could cascade-delete another broker's rows,
and integrity was only coincidental while broker ids overlapped user ids.

Pre-check for orphans before running in production:
    SELECT 'voice_calls' AS t, count(*) FROM voice_calls
        WHERE broker_id NOT IN (SELECT id FROM brokers)
    UNION ALL
    SELECT 'campaigns', count(*) FROM campaigns
        WHERE broker_id NOT IN (SELECT id FROM brokers)
    UNION ALL
    SELECT 'message_templates', count(*) FROM message_templates
        WHERE broker_id NOT IN (SELECT id FROM brokers);
If any count > 0, fix those rows first — create_foreign_key will fail otherwise.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b5c6d7e8f9a0'
down_revision: Union[str, Sequence[str], None] = 'merge_voice_pipecat'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("voice_calls", "campaigns", "message_templates")


def upgrade() -> None:
    for table in _TABLES:
        op.drop_constraint(f"{table}_broker_id_fkey", table, type_="foreignkey")
        op.create_foreign_key(
            f"{table}_broker_id_fkey", table, "brokers",
            ["broker_id"], ["id"], ondelete="CASCADE",
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_constraint(f"{table}_broker_id_fkey", table, type_="foreignkey")
        op.create_foreign_key(
            f"{table}_broker_id_fkey", table, "users",
            ["broker_id"], ["id"], ondelete="CASCADE",
        )
