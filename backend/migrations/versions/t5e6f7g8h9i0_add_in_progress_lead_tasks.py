"""add in-progress state to lead tasks

Revision ID: t5e6f7g8h9i0
Revises: s4d5e6f7g8h9
Create Date: 2026-08-25
"""
from typing import Sequence, Union

from alembic import op


revision: str = "t5e6f7g8h9i0"
down_revision: Union[str, Sequence[str]] = "s4d5e6f7g8h9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_lead_tasks_status", "lead_tasks", type_="check")
    op.create_check_constraint(
        "ck_lead_tasks_status",
        "lead_tasks",
        "status IN ('open', 'in_progress', 'completed')",
    )


def downgrade() -> None:
    op.execute("UPDATE lead_tasks SET status = 'open' WHERE status = 'in_progress'")
    op.drop_constraint("ck_lead_tasks_status", "lead_tasks", type_="check")
    op.create_check_constraint(
        "ck_lead_tasks_status",
        "lead_tasks",
        "status IN ('open', 'completed')",
    )
