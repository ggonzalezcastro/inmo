"""add verified lead advisory records

Revision ID: s4d5e6f7g8h9
Revises: r3c4d5e6f7g8
Create Date: 2026-08-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "s4d5e6f7g8h9"
down_revision: Union[str, Sequence[str]] = "r3c4d5e6f7g8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lead_advisories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "broker_id",
            sa.Integer(),
            sa.ForeignKey("brokers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            sa.Integer(),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "advisor_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "recorded_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "channel IN ('whatsapp', 'phone', 'video_call', "
            "'property_visit', 'in_person', 'other')",
            name="ck_lead_advisories_channel",
        ),
    )
    for column in (
        "id",
        "broker_id",
        "lead_id",
        "advisor_id",
        "recorded_by",
        "channel",
        "occurred_at",
    ):
        op.create_index(
            f"ix_lead_advisories_{column}",
            "lead_advisories",
            [column],
        )
    op.create_index(
        "ix_lead_advisories_broker_advisor_occurred",
        "lead_advisories",
        ["broker_id", "advisor_id", "occurred_at"],
    )
    op.create_index(
        "ix_lead_advisories_broker_lead_occurred",
        "lead_advisories",
        ["broker_id", "lead_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lead_advisories_broker_lead_occurred",
        table_name="lead_advisories",
    )
    op.drop_index(
        "ix_lead_advisories_broker_advisor_occurred",
        table_name="lead_advisories",
    )
    for column in reversed((
        "id",
        "broker_id",
        "lead_id",
        "advisor_id",
        "recorded_by",
        "channel",
        "occurred_at",
    )):
        op.drop_index(
            f"ix_lead_advisories_{column}",
            table_name="lead_advisories",
        )
    op.drop_table("lead_advisories")
