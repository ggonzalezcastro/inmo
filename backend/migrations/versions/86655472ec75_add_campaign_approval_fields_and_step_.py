"""add_campaign_approval_fields_and_step_channels

Revision ID: 86655472ec75
Revises: 8256e6e04a85
Create Date: 2026-03-02 18:24:06.729014

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '86655472ec75'
down_revision: Union[str, None] = '8256e6e04a85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add 'pending_review' to campaignstatus enum
    op.execute("ALTER TYPE campaignstatus ADD VALUE IF NOT EXISTS 'pending_review' AFTER 'draft'")

    # 2. Add approval tracking columns to campaigns
    op.add_column('campaigns', sa.Column('created_by', sa.Integer(), nullable=True))
    op.add_column('campaigns', sa.Column('approved_by', sa.Integer(), nullable=True))
    op.create_index('ix_campaigns_created_by', 'campaigns', ['created_by'], unique=False)
    op.create_foreign_key('fk_campaigns_created_by', 'campaigns', 'users', ['created_by'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_campaigns_approved_by', 'campaigns', 'users', ['approved_by'], ['id'], ondelete='SET NULL')

    # 3. Add per-step message and channel fields to campaign_steps
    op.add_column('campaign_steps', sa.Column('message_text', sa.Text(), nullable=True))
    op.add_column('campaign_steps', sa.Column('use_ai_message', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('campaign_steps', sa.Column('step_channel', sa.Enum('telegram', 'call', 'whatsapp', 'email', name='campaignchannel', create_type=False), nullable=True))


def downgrade() -> None:
    op.drop_column('campaign_steps', 'step_channel')
    op.drop_column('campaign_steps', 'use_ai_message')
    op.drop_column('campaign_steps', 'message_text')
    op.drop_constraint('fk_campaigns_approved_by', 'campaigns', type_='foreignkey')
    op.drop_constraint('fk_campaigns_created_by', 'campaigns', type_='foreignkey')
    op.drop_index('ix_campaigns_created_by', table_name='campaigns')
    op.drop_column('campaigns', 'approved_by')
    op.drop_column('campaigns', 'created_by')
    # Note: cannot remove enum values in PostgreSQL without dropping the type

