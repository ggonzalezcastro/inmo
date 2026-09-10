"""allow Meta leads whose professional channel does not expose a phone

Revision ID: x9i0j1k2l3m4
Revises: w8h9i0j1k2l3
Create Date: 2026-09-01
"""

from alembic import op
import sqlalchemy as sa


revision = "x9i0j1k2l3m4"
down_revision = "w8h9i0j1k2l3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "leads",
        "phone",
        existing_type=sa.String(length=20),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        "UPDATE leads SET phone = 'meta_rollback_' || id::text WHERE phone IS NULL"
    )
    op.alter_column(
        "leads",
        "phone",
        existing_type=sa.String(length=20),
        nullable=False,
    )
