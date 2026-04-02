"""add close reason fields to leads

Revision ID: u2p3q4r5s6t7
Revises: t1o2p3q4r5s6
Create Date: 2026-04-01 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'u2p3q4r5s6t7'
down_revision = 't1o2p3q4r5s6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('leads', sa.Column('close_reason', sa.String(100), nullable=True))
    op.add_column('leads', sa.Column('close_reason_detail', sa.Text(), nullable=True))
    op.add_column('leads', sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('leads', sa.Column('closed_from_stage', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('leads', 'close_reason')
    op.drop_column('leads', 'close_reason_detail')
    op.drop_column('leads', 'closed_at')
    op.drop_column('leads', 'closed_from_stage')
