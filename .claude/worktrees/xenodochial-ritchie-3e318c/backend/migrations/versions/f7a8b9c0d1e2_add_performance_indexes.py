"""Add performance indexes for frequent queries

Revision ID: f7a8b9c0d1e2
Revises: d9f9d197f1bb
Create Date: 2025-01-29

Indexes added:
- idx_leads_broker_stage: leads filtered by broker_id and pipeline_stage (pipeline/board)
- idx_leads_assigned_status: leads filtered by assigned_to and status (assignment views)
- idx_messages_lead_created: telegram_messages by lead_id and created_at DESC (message history)
"""
from typing import Sequence, Union

from alembic import op


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "d9f9d197f1bb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_leads_broker_stage",
        "leads",
        ["broker_id", "pipeline_stage"],
        unique=False,
    )
    op.create_index(
        "idx_leads_assigned_status",
        "leads",
        ["assigned_to", "status"],
        unique=False,
    )
    op.create_index(
        "idx_messages_lead_created",
        "telegram_messages",
        ["lead_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_messages_lead_created", table_name="telegram_messages")
    op.drop_index("idx_leads_assigned_status", table_name="leads")
    op.drop_index("idx_leads_broker_stage", table_name="leads")
