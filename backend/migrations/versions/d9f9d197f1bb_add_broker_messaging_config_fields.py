"""add_broker_messaging_config_fields

Revision ID: d9f9d197f1bb
Revises: e6f193bab118
Create Date: 2026-01-20 17:59:59.310474

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd9f9d197f1bb'
down_revision: Union[str, None] = 'e6f193bab118'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new fields to broker_prompt_configs for enhanced messaging
    op.add_column('broker_prompt_configs', sa.Column('benefits_info', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('broker_prompt_configs', sa.Column('qualification_requirements', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('broker_prompt_configs', sa.Column('follow_up_messages', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('broker_prompt_configs', sa.Column('additional_fields', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('broker_prompt_configs', sa.Column('meeting_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('broker_prompt_configs', sa.Column('message_templates', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    # Remove added columns
    op.drop_column('broker_prompt_configs', 'message_templates')
    op.drop_column('broker_prompt_configs', 'meeting_config')
    op.drop_column('broker_prompt_configs', 'additional_fields')
    op.drop_column('broker_prompt_configs', 'follow_up_messages')
    op.drop_column('broker_prompt_configs', 'qualification_requirements')
    op.drop_column('broker_prompt_configs', 'benefits_info')

