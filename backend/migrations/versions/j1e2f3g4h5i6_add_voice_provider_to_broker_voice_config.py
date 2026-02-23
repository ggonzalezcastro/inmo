"""add voice provider and provider_credentials to broker_voice_config

Revision ID: j1e2f3g4h5i6
Revises: i0d1e2f3g4h5
Create Date: 2025-02-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "j1e2f3g4h5i6"
down_revision: Union[str, None] = "i0d1e2f3g4h5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "broker_voice_configs",
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="vapi"),
    )
    op.add_column(
        "broker_voice_configs",
        sa.Column("provider_credentials", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("broker_voice_configs", "provider_credentials")
    op.drop_column("broker_voice_configs", "provider")
