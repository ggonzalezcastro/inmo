"""add referral campaign flag

Revision ID: u6f7g8h9i0j1
Revises: t5e6f7g8h9i0
Create Date: 2026-08-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "u6f7g8h9i0j1"
down_revision: Union[str, Sequence[str]] = "t5e6f7g8h9i0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column(
            "is_referral_campaign",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_campaigns_is_referral_campaign",
        "campaigns",
        ["is_referral_campaign"],
    )
    op.create_index(
        "idx_campaign_broker_referral_status",
        "campaigns",
        ["broker_id", "is_referral_campaign", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_campaign_broker_referral_status", table_name="campaigns")
    op.drop_index("ix_campaigns_is_referral_campaign", table_name="campaigns")
    op.drop_column("campaigns", "is_referral_campaign")
