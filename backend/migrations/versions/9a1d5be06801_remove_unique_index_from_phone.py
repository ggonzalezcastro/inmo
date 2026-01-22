"""remove_unique_index_from_phone

Revision ID: 9a1d5be06801
Revises: 79639f974b80
Create Date: 2025-12-01 16:39:32.011393

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a1d5be06801'
down_revision: Union[str, None] = '79639f974b80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the unique index on phone to allow duplicate phones
    op.execute("DROP INDEX IF EXISTS ix_leads_phone;")


def downgrade() -> None:
    # Re-create unique index (optional - only if you want to revert)
    # Note: This might fail if there are duplicate phones
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_leads_phone 
        ON leads(phone);
    """)

