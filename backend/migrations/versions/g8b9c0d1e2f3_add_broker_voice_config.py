"""add_broker_voice_config

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2025-01-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "g8b9c0d1e2f3"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "broker_voice_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("assistant_id_default", sa.String(length=255), nullable=True),
        sa.Column("assistant_id_by_type", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("voice_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("model_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("transcriber_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("timing_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("end_call_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("first_message_template", sa.Text(), nullable=True),
        sa.Column("recording_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("broker_id"),
    )
    op.create_index(
        "idx_broker_voice_config_broker",
        "broker_voice_configs",
        ["broker_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_broker_voice_config_broker", table_name="broker_voice_configs")
    op.drop_table("broker_voice_configs")
