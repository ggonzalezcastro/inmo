"""add priority assignment fields to users and brokers

Revision ID: y1a2b3c4d5e6
Revises: x1y2z3a4b5c6
Create Date: 2026-04-09

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'y1a2b3c4d5e6'
down_revision: Union[str, Sequence[str]] = 'x1y2z3a4b5c6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add assignment_priority to users (nullable, lower = higher priority)
    op.add_column(
        'users',
        sa.Column('assignment_priority', sa.Integer(), nullable=True),
    )
    # Add priority_assignment_enabled to brokers (default OFF = round-robin)
    op.add_column(
        'brokers',
        sa.Column('priority_assignment_enabled', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_column('brokers', 'priority_assignment_enabled')
    op.drop_column('users', 'assignment_priority')
