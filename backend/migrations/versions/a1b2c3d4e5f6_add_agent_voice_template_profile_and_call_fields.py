"""add agent_voice_templates, agent_voice_profiles, and voice_call new columns

Revision ID: a1b2c3d4e5f6
Revises: b3c4d5e6f7g8
Create Date: 2026-04-12

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str]] = 'b3c4d5e6f7g8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── agent_voice_templates ─────────────────────────────────────────────────
    op.create_table(
        'agent_voice_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('broker_id', sa.Integer(), sa.ForeignKey('brokers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('business_prompt', sa.Text(), nullable=True),
        sa.Column('qualification_criteria', JSONB(), nullable=True),
        sa.Column('niche_instructions', sa.Text(), nullable=True),
        sa.Column('language', sa.String(20), server_default='es', nullable=False),
        sa.Column('transcriber_config', JSONB(), nullable=True),
        sa.Column('max_duration_seconds', sa.Integer(), server_default='600', nullable=False),
        sa.Column('max_silence_seconds', sa.Float(), server_default='30.0', nullable=False),
        sa.Column('recording_policy', sa.String(20), server_default='enabled', nullable=False),
        sa.Column('available_voice_ids', JSONB(), server_default='[]', nullable=False),
        sa.Column('available_tones', JSONB(), server_default='[]', nullable=False),
        sa.Column('default_call_mode', sa.String(20), server_default='transcriptor', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_voice_templates_broker_id', 'agent_voice_templates', ['broker_id'])

    # ── agent_voice_profiles ──────────────────────────────────────────────────
    op.create_table(
        'agent_voice_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('agent_voice_templates.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('selected_voice_id', sa.String(255), nullable=True),
        sa.Column('selected_tone', sa.String(50), nullable=True),
        sa.Column('assistant_name', sa.String(100), nullable=True),
        sa.Column('opening_message', sa.Text(), nullable=True),
        sa.Column('preferred_call_mode', sa.String(20), nullable=True),
        sa.Column('vapi_assistant_id', sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )
    op.create_index('ix_agent_voice_profiles_user_id', 'agent_voice_profiles', ['user_id'])
    op.create_index('ix_agent_voice_profiles_template_id', 'agent_voice_profiles', ['template_id'])

    # ── voice_calls new columns ───────────────────────────────────────────────
    op.add_column('voice_calls', sa.Column('agent_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
    op.add_column('voice_calls', sa.Column('call_mode', sa.String(20), nullable=True))
    op.add_column('voice_calls', sa.Column('call_purpose', sa.String(50), nullable=True))
    op.add_column('voice_calls', sa.Column('call_output', JSONB(), nullable=True))
    op.add_column('voice_calls', sa.Column('template_snapshot', JSONB(), nullable=True))
    op.add_column('voice_calls', sa.Column('profile_snapshot', JSONB(), nullable=True))
    op.create_index('ix_voice_calls_agent_user_id', 'voice_calls', ['agent_user_id'])


def downgrade() -> None:
    op.drop_index('ix_voice_calls_agent_user_id', table_name='voice_calls')
    op.drop_column('voice_calls', 'profile_snapshot')
    op.drop_column('voice_calls', 'template_snapshot')
    op.drop_column('voice_calls', 'call_output')
    op.drop_column('voice_calls', 'call_purpose')
    op.drop_column('voice_calls', 'call_mode')
    op.drop_column('voice_calls', 'agent_user_id')

    op.drop_index('ix_agent_voice_profiles_template_id', table_name='agent_voice_profiles')
    op.drop_index('ix_agent_voice_profiles_user_id', table_name='agent_voice_profiles')
    op.drop_table('agent_voice_profiles')

    op.drop_index('ix_agent_voice_templates_broker_id', table_name='agent_voice_templates')
    op.drop_table('agent_voice_templates')
