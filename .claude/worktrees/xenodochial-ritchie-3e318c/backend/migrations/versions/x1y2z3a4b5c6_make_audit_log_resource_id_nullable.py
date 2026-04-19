"""make audit_log resource_id nullable

Revision ID: x1y2z3a4b5c6
Revises: c53002c2955b, w4r5s6t7u8v9
Create Date: 2026-04-02

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'x1y2z3a4b5c6'
down_revision: Union[str, Sequence[str]] = ('c53002c2955b', 'w4r5s6t7u8v9')
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'audit_logs',
        'resource_id',
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    # Set any NULL resource_id to 0 before restoring NOT NULL constraint
    op.execute("UPDATE audit_logs SET resource_id = 0 WHERE resource_id IS NULL")
    op.alter_column(
        'audit_logs',
        'resource_id',
        existing_type=sa.Integer(),
        nullable=False,
    )
