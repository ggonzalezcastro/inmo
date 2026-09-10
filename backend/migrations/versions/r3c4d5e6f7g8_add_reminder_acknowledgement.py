"""add persistent reminder acknowledgement

Revision ID: r3c4d5e6f7g8
Revises: q2b3c4d5e6f7
Create Date: 2026-08-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "r3c4d5e6f7g8"
down_revision: Union[str, Sequence[str]] = "q2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lead_tasks",
        sa.Column("reminder_acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_lead_tasks_reminder_acknowledged_at",
        "lead_tasks",
        ["reminder_acknowledged_at"],
    )
    op.drop_index("ix_lead_tasks_pending_reminders", table_name="lead_tasks")
    op.create_index(
        "ix_lead_tasks_pending_reminders",
        "lead_tasks",
        ["status", "reminder_acknowledged_at", "reminder_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_lead_tasks_pending_reminders", table_name="lead_tasks")
    op.create_index(
        "ix_lead_tasks_pending_reminders",
        "lead_tasks",
        ["status", "reminder_sent_at", "reminder_at"],
    )
    op.drop_index("ix_lead_tasks_reminder_acknowledged_at", table_name="lead_tasks")
    op.drop_column("lead_tasks", "reminder_acknowledged_at")
