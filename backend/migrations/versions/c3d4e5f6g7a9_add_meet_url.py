"""Add meet_url to appointments

Revision ID: c3d4e5f6g7a9
Revises: b2c4d5e6f7a8
Create Date: 2025-11-26 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7a9'
down_revision: Union[str, None] = 'b2c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add meet_url column to appointments table
    op.add_column('appointments', sa.Column('meet_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('appointments', 'meet_url')




