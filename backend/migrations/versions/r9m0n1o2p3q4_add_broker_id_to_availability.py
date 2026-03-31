"""add broker_id to availability_slots and appointment_blocks

Revision ID: r9m0n1o2p3q4
Revises: q8l9m0n1o2p3
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = 'r9m0n1o2p3q4'
down_revision = 'q8l9m0n1o2p3'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Add broker_id to availability_slots
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='availability_slots' AND column_name='broker_id'"
    ))
    if not result.fetchone():
        op.add_column('availability_slots', sa.Column(
            'broker_id', sa.Integer(),
            sa.ForeignKey('brokers.id', ondelete='CASCADE'),
            nullable=True, index=True
        ))

    # Add broker_id to appointment_blocks
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='appointment_blocks' AND column_name='broker_id'"
    ))
    if not result.fetchone():
        op.add_column('appointment_blocks', sa.Column(
            'broker_id', sa.Integer(),
            sa.ForeignKey('brokers.id', ondelete='CASCADE'),
            nullable=True, index=True
        ))


def downgrade():
    conn = op.get_bind()

    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='availability_slots' AND column_name='broker_id'"
    ))
    if result.fetchone():
        op.drop_column('availability_slots', 'broker_id')

    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='appointment_blocks' AND column_name='broker_id'"
    ))
    if result.fetchone():
        op.drop_column('appointment_blocks', 'broker_id')
