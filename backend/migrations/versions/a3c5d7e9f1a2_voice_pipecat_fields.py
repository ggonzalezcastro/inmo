"""add Pipecat voice fields to voice_calls and call_transcripts

Revision ID: a3c5d7e9f1g2
Revises: z2b3c4d5e6f7
Create Date: 2026-05-04

Adds fields required for Pipecat-based voice pipeline:
- voice_calls: pipecat_mode, call_direction, initiated_by_id, agent_phone, lead_phone,
  speaking seconds per speaker, handoff fields, extracted_data, call_metrics
- call_transcripts: emotion_detected, emotion_tag_used, duration_ms
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 'a3c5d7e9f1a2'
down_revision: Union[str, Sequence[str]] = 'z2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── voice_calls new columns ───────────────────────────────────────────────
    op.add_column('voice_calls', sa.Column('pipecat_mode', sa.String(20), nullable=True))
    op.add_column('voice_calls', sa.Column('call_direction', sa.String(10), nullable=True, server_default='outbound'))
    op.add_column('voice_calls', sa.Column('initiated_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
    op.add_column('voice_calls', sa.Column('agent_phone', sa.String(20), nullable=True))
    op.add_column('voice_calls', sa.Column('lead_phone', sa.String(20), nullable=True))
    op.add_column('voice_calls', sa.Column('ai_speaking_seconds', sa.Float(), nullable=True, server_default='0.0'))
    op.add_column('voice_calls', sa.Column('human_speaking_seconds', sa.Float(), nullable=True, server_default='0.0'))
    op.add_column('voice_calls', sa.Column('lead_speaking_seconds', sa.Float(), nullable=True, server_default='0.0'))
    op.add_column('voice_calls', sa.Column('handoff_occurred', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('voice_calls', sa.Column('handoff_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('voice_calls', sa.Column('handoff_reason', sa.Text(), nullable=True))
    op.add_column('voice_calls', sa.Column('handoff_to_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
    op.add_column('voice_calls', sa.Column('extracted_data', JSONB(), nullable=True))
    op.add_column('voice_calls', sa.Column('call_metrics', JSONB(), nullable=True))

    # ── call_transcripts new columns ──────────────────────────────────────────
    op.add_column('call_transcripts', sa.Column('emotion_detected', sa.String(50), nullable=True))
    op.add_column('call_transcripts', sa.Column('emotion_tag_used', sa.String(100), nullable=True))
    op.add_column('call_transcripts', sa.Column('duration_ms', sa.Integer(), nullable=True))

    # ── indexes for FKs that participate in ondelete='SET NULL' ───────────────
    # Without these, deleting a user (handoff_to_user_id, initiated_by_id) does
    # a full scan on voice_calls.
    op.create_index('idx_voice_call_initiated_by', 'voice_calls', ['initiated_by_id'])
    op.create_index('idx_voice_call_handoff_to_user', 'voice_calls', ['handoff_to_user_id'])


def downgrade() -> None:
    # indexes
    op.drop_index('idx_voice_call_handoff_to_user', table_name='voice_calls')
    op.drop_index('idx_voice_call_initiated_by', table_name='voice_calls')

    # call_transcripts
    op.drop_column('call_transcripts', 'duration_ms')
    op.drop_column('call_transcripts', 'emotion_tag_used')
    op.drop_column('call_transcripts', 'emotion_detected')

    # voice_calls
    op.drop_column('voice_calls', 'call_metrics')
    op.drop_column('voice_calls', 'extracted_data')
    op.drop_column('voice_calls', 'handoff_to_user_id')
    op.drop_column('voice_calls', 'handoff_reason')
    op.drop_column('voice_calls', 'handoff_at')
    op.drop_column('voice_calls', 'handoff_occurred')
    op.drop_column('voice_calls', 'lead_speaking_seconds')
    op.drop_column('voice_calls', 'human_speaking_seconds')
    op.drop_column('voice_calls', 'ai_speaking_seconds')
    op.drop_column('voice_calls', 'lead_phone')
    op.drop_column('voice_calls', 'agent_phone')
    op.drop_column('voice_calls', 'initiated_by_id')
    op.drop_column('voice_calls', 'call_direction')
    op.drop_column('voice_calls', 'pipecat_mode')
