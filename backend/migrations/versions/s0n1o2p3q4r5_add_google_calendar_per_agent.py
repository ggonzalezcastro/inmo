"""add google calendar per agent

Revision ID: s0n1o2p3q4r5
Revises: r9m0n1o2p3q4
Create Date: 2026-04-01 13:55:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 's0n1o2p3q4r5'
down_revision = 'r9m0n1o2p3q4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('google_calendar_id', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('google_calendar_connected', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('users', 'google_calendar_connected')
    op.drop_column('users', 'google_calendar_id')
