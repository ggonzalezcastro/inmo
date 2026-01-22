"""Add google_event_id to appointments

Revision ID: d4e5f6g7a8h9
Revises: c3d4e5f6g7a9
Create Date: 2025-01-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6g7a8h9'
down_revision: Union[str, None] = 'c3d4e5f6g7a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add google_event_id column to appointments table
    op.add_column('appointments', sa.Column('google_event_id', sa.String(length=255), nullable=True))
    # Add index for faster lookups
    op.create_index('idx_appointment_google_event', 'appointments', ['google_event_id'])


def downgrade() -> None:
    op.drop_index('idx_appointment_google_event', table_name='appointments')
    op.drop_column('appointments', 'google_event_id')



