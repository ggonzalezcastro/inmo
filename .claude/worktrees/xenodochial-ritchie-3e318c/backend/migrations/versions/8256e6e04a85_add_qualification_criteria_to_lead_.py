"""add_qualification_criteria_to_lead_config

Revision ID: 8256e6e04a85
Revises: o6j7k8l9m0n1
Create Date: 2026-03-02 14:47:40.208870

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '8256e6e04a85'
down_revision: Union[str, None] = 'o6j7k8l9m0n1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('broker_lead_configs', sa.Column('qualification_criteria', postgresql.JSONB(), nullable=True))
    op.add_column('broker_lead_configs', sa.Column('max_acceptable_debt', sa.Integer(), nullable=True))
    op.add_column('broker_lead_configs', sa.Column('alert_on_qualified', sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column('broker_lead_configs', 'alert_on_qualified')
    op.drop_column('broker_lead_configs', 'max_acceptable_debt')
    op.drop_column('broker_lead_configs', 'qualification_criteria')
