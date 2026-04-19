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
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'broker_prompt_configs' AND column_name = 'data_collection_prompt'
    """))
    if result.fetchone() is None:
        op.add_column('broker_prompt_configs',
            sa.Column('data_collection_prompt', sa.Text(), nullable=True)
        )


def downgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'broker_prompt_configs' AND column_name = 'data_collection_prompt'
    """))
    if result.fetchone() is not None:
        op.drop_column('broker_prompt_configs', 'data_collection_prompt')

