"""add agent_model_configs table

Revision ID: z2b3c4d5e6f7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-10

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'z2b3c4d5e6f7'
down_revision: Union[str, Sequence[str]] = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'agent_model_configs',
        sa.Column('id', sa.Integer(), primary_key=True, index=True, autoincrement=True),
        sa.Column('broker_id', sa.Integer(), sa.ForeignKey('brokers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agent_type', sa.String(20), nullable=False),
        sa.Column('llm_provider', sa.String(20), nullable=False),
        sa.Column('llm_model', sa.String(80), nullable=False),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('max_tokens', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
    )
    op.create_index('ix_agent_model_configs_broker_id', 'agent_model_configs', ['broker_id'])
    op.create_unique_constraint(
        'uq_agent_model_config_broker_agent',
        'agent_model_configs',
        ['broker_id', 'agent_type'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_agent_model_config_broker_agent', 'agent_model_configs', type_='unique')
    op.drop_index('ix_agent_model_configs_broker_id', table_name='agent_model_configs')
    op.drop_table('agent_model_configs')
