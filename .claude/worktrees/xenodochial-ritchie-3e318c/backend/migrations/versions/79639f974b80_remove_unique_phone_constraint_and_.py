"""remove_unique_phone_constraint_and_update_placeholders

Revision ID: 79639f974b80
Revises: 3cecf9fb71a3
Create Date: 2025-12-01 14:10:57.394004

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79639f974b80'
down_revision: Union[str, None] = '3cecf9fb71a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop unique constraint on phone to allow duplicate phones
    op.execute("ALTER TABLE leads DROP CONSTRAINT IF EXISTS uq_phone;")
    
    # Note: The unique=True was also removed from the Column definition in the model
    # This migration handles the database constraint removal


def downgrade() -> None:
    # Re-add unique constraint (optional - only if you want to revert)
    # Note: This might fail if there are duplicate phones
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'uq_phone'
            ) THEN
                ALTER TABLE leads ADD CONSTRAINT uq_phone UNIQUE (phone);
            END IF;
        END $$;
    """)

