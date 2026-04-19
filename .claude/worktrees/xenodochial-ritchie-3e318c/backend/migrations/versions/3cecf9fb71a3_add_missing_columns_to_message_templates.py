"""add_missing_columns_to_message_templates

Revision ID: 3cecf9fb71a3
Revises: e5f6g7a8h9i0
Create Date: 2025-12-01 14:07:46.215378

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3cecf9fb71a3'
down_revision: Union[str, None] = 'e5f6g7a8h9i0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add channel column if it doesn't exist
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'message_templates' AND column_name = 'channel'
            ) THEN
                ALTER TABLE message_templates 
                ADD COLUMN channel templatechannel NOT NULL DEFAULT 'telegram';
            END IF;
        END $$;
    """)
    
    # Add agent_type column if it doesn't exist
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'message_templates' AND column_name = 'agent_type'
            ) THEN
                ALTER TABLE message_templates 
                ADD COLUMN agent_type agenttype;
            END IF;
        END $$;
    """)
    
    # Create indexes if they don't exist
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_message_templates_channel 
        ON message_templates(channel);
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_message_templates_agent_type 
        ON message_templates(agent_type);
    """)


def downgrade() -> None:
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS ix_message_templates_channel;")
    op.execute("DROP INDEX IF EXISTS ix_message_templates_agent_type;")
    
    # Drop columns
    op.execute("ALTER TABLE message_templates DROP COLUMN IF EXISTS channel;")
    op.execute("ALTER TABLE message_templates DROP COLUMN IF EXISTS agent_type;")

