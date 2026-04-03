"""add_outlook_calendar_columns_to_broker_prompt_configs

Revision ID: 18bc8eda7670
Revises: x1y2z3a4b5c6
Create Date: 2026-04-03 12:50:05.087551

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '18bc8eda7670'
down_revision: Union[str, None] = 'x1y2z3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('broker_prompt_configs', sa.Column('outlook_refresh_token', sa.Text(), nullable=True))
    op.add_column('broker_prompt_configs', sa.Column('outlook_calendar_id', sa.String(length=500), nullable=True))
    op.add_column('broker_prompt_configs', sa.Column('outlook_calendar_email', sa.String(length=255), nullable=True))
    op.add_column('broker_prompt_configs', sa.Column('calendar_provider', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('broker_prompt_configs', 'calendar_provider')
    op.drop_column('broker_prompt_configs', 'outlook_calendar_email')
    op.drop_column('broker_prompt_configs', 'outlook_calendar_id')
    op.drop_column('broker_prompt_configs', 'outlook_refresh_token')

