"""add_phone_number_id_to_broker_voice_config

Revision ID: h9c0d1e2f3g4
Revises: g8b9c0d1e2f3
Create Date: 2025-01-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "h9c0d1e2f3g4"
down_revision: Union[str, None] = "g8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "broker_voice_configs",
        sa.Column("phone_number_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("broker_voice_configs", "phone_number_id")
