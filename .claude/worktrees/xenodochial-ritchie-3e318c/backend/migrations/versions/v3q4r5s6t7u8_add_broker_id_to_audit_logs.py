"""add broker_id to audit_logs

Revision ID: v3q4r5s6t7u8
Revises: u2p3q4r5s6t7
Create Date: 2026-04-02 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'v3q4r5s6t7u8'
down_revision = 'u2p3q4r5s6t7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'audit_logs',
        sa.Column('broker_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_audit_logs_broker_id',
        'audit_logs', 'brokers',
        ['broker_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('idx_audit_broker_id', 'audit_logs', ['broker_id'])


def downgrade() -> None:
    op.drop_index('idx_audit_broker_id', table_name='audit_logs')
    op.drop_constraint('fk_audit_logs_broker_id', 'audit_logs', type_='foreignkey')
    op.drop_column('audit_logs', 'broker_id')
