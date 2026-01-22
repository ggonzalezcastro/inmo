"""add_data_collection_prompt_to_broker_prompt_configs

Revision ID: 33aa1b0fa1bf
Revises: 0f0500a3ddf7
Create Date: 2026-01-20 15:29:19.632444

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '33aa1b0fa1bf'
down_revision: Union[str, None] = '0f0500a3ddf7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if column already exists
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'broker_prompt_configs' 
            AND column_name = 'data_collection_prompt'
        )
    """))
    column_exists = result.scalar()
    
    # Add column if it doesn't exist
    if not column_exists:
        op.add_column('broker_prompt_configs',
            sa.Column('data_collection_prompt', sa.Text(), nullable=True)
        )


def downgrade() -> None:
    # Remove column if it exists
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'broker_prompt_configs' 
            AND column_name = 'data_collection_prompt'
        )
    """))
    column_exists = result.scalar()
    
    if column_exists:
        op.drop_column('broker_prompt_configs', 'data_collection_prompt')

