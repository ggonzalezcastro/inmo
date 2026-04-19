"""add post_processed to voice_calls

Revision ID: o6j7k8l9m0n1
Revises: n5i6j7k8l9m0
Create Date: 2026-03-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o6j7k8l9m0n1"
down_revision: Union[str, None] = "n5i6j7k8l9m0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "voice_calls",
        sa.Column(
            "post_processed",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("voice_calls", "post_processed")
