"""add twilio_phone_number to broker_voice_configs + 'voice' to chatprovider enum

Revision ID: c7d8e9f0a1b2
Revises: b5c6d7e8f9a0
Create Date: 2026-07-07

- broker_voice_configs.twilio_phone_number: E.164 number for inbound Pipecat
  call routing (phone_number_id is a VAPI id and cannot be matched against
  Twilio's "To" field).
- chatprovider enum gains 'voice' so voice-call turns are logged with their own
  provider instead of falling back to 'webchat' and polluting the chat inbox.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, Sequence[str], None] = 'b5c6d7e8f9a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'broker_voice_configs',
        sa.Column('twilio_phone_number', sa.String(20), nullable=True),
    )
    op.create_index(
        'idx_broker_voice_config_twilio_number',
        'broker_voice_configs',
        ['twilio_phone_number'],
    )

    # ALTER TYPE ... ADD VALUE cannot run inside the migration transaction.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE chatprovider ADD VALUE IF NOT EXISTS 'voice'")


def downgrade() -> None:
    op.drop_index('idx_broker_voice_config_twilio_number', table_name='broker_voice_configs')
    op.drop_column('broker_voice_configs', 'twilio_phone_number')
    # Postgres cannot drop a single enum value; leaving 'voice' in place is safe.
