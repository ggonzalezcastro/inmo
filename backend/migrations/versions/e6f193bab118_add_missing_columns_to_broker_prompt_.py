"""add_missing_columns_to_broker_prompt_configs

Revision ID: e6f193bab118
Revises: 33aa1b0fa1bf
Create Date: 2026-01-20 17:36:43.138374

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6f193bab118'
down_revision: Union[str, None] = '33aa1b0fa1bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy.dialects import postgresql
    
    # Check which columns exist and add missing ones
    conn = op.get_bind()
    
    columns_to_add = [
        ('identity_prompt', sa.Text(), None),
        ('behavior_rules', sa.Text(), None),
        ('restrictions', sa.Text(), None),
        ('situation_handlers', postgresql.JSONB(astext_type=sa.Text()), None),
        ('output_format', sa.Text(), None),
        ('full_custom_prompt', sa.Text(), None),
        ('tools_instructions', sa.Text(), None),
    ]
    
    for column_name, column_type, default in columns_to_add:
        result = conn.execute(sa.text(f"""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'broker_prompt_configs' 
                AND column_name = '{column_name}'
            )
        """))
        column_exists = result.scalar()
        
        if not column_exists:
            op.add_column('broker_prompt_configs',
                sa.Column(column_name, column_type, nullable=True)
            )


def downgrade() -> None:
    # Remove columns if they exist
    columns_to_remove = [
        'identity_prompt',
        'behavior_rules',
        'restrictions',
        'situation_handlers',
        'output_format',
        'full_custom_prompt',
        'tools_instructions',
    ]
    
    for column_name in columns_to_remove:
        try:
            op.drop_column('broker_prompt_configs', column_name)
        except Exception:
            # Column might not exist, ignore
            pass

