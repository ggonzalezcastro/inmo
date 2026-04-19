"""add_broker_id_to_leads

Revision ID: 0f0500a3ddf7
Revises: a7e6cad13f8d
Create Date: 2025-12-01 19:28:26.678422

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f0500a3ddf7'
down_revision: Union[str, None] = 'a7e6cad13f8d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add broker_id column to leads table
    op.add_column('leads', sa.Column('broker_id', sa.Integer(), nullable=True))
    
    # Create foreign key constraint
    op.create_foreign_key(
        'leads_broker_id_fkey',
        'leads', 'brokers',
        ['broker_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # Create index
    op.create_index('ix_leads_broker_id', 'leads', ['broker_id'], unique=False)
    
    # Migrate existing leads: assign them to the first broker (if exists)
    op.execute("""
        UPDATE leads
        SET broker_id = (SELECT id FROM brokers LIMIT 1)
        WHERE broker_id IS NULL AND EXISTS (SELECT 1 FROM brokers);
    """)


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_leads_broker_id', table_name='leads')
    
    # Drop foreign key constraint
    op.drop_constraint('leads_broker_id_fkey', 'leads', type_='foreignkey')
    
    # Drop column
    op.drop_column('leads', 'broker_id')
