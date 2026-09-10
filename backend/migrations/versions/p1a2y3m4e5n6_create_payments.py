"""create payments and broker_payment_configs tables (Transbank Webpay Plus)

Revision ID: p1a2y3m4e5n6
Revises: c7d8e9f0a1b2
Create Date: 2026-07-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'p1a2y3m4e5n6'
down_revision: Union[str, Sequence[str]] = 'c7d8e9f0a1b2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── payments ───────────────────────────────────────────────────────────────
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        # Tenancy + FKs
        sa.Column('broker_id', sa.Integer(), sa.ForeignKey('brokers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('deal_id', sa.Integer(), sa.ForeignKey('deals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        # Provider
        sa.Column('provider', sa.String(30), nullable=False, server_default='transbank'),
        sa.Column('environment', sa.String(20), nullable=False, server_default='integration'),
        # Webpay identity
        sa.Column('buy_order', sa.String(26), nullable=False),
        sa.Column('session_id', sa.String(61), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(128), nullable=True),
        sa.Column('webpay_url', sa.String(255), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='created'),
        # Commit result
        sa.Column('response_code', sa.Integer(), nullable=True),
        sa.Column('authorization_code', sa.String(20), nullable=True),
        sa.Column('payment_type_code', sa.String(10), nullable=True),
        sa.Column('installments_number', sa.Integer(), nullable=True),
        sa.Column('card_last4', sa.String(4), nullable=True),
        sa.Column('transaction_date', sa.String(40), nullable=True),
        sa.Column('raw_response', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('committed_at', sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_payments_broker_id', 'payments', ['broker_id'])
    op.create_index('ix_payments_deal_id', 'payments', ['deal_id'])
    op.create_index('ix_payments_token', 'payments', ['token'])
    op.create_index('uq_payments_buy_order', 'payments', ['buy_order'], unique=True)

    # ── broker_payment_configs ─────────────────────────────────────────────────
    op.create_table(
        'broker_payment_configs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('broker_id', sa.Integer(), sa.ForeignKey('brokers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False, server_default='transbank'),
        sa.Column('environment', sa.String(20), nullable=False, server_default='integration'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('commerce_code', sa.String(64), nullable=True),
        sa.Column('api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('uq_broker_payment_configs_broker_id', 'broker_payment_configs', ['broker_id'], unique=True)


def downgrade() -> None:
    op.drop_index('uq_broker_payment_configs_broker_id', table_name='broker_payment_configs')
    op.drop_table('broker_payment_configs')

    op.drop_index('uq_payments_buy_order', table_name='payments')
    op.drop_index('ix_payments_token', table_name='payments')
    op.drop_index('ix_payments_deal_id', table_name='payments')
    op.drop_index('ix_payments_broker_id', table_name='payments')
    op.drop_table('payments')
