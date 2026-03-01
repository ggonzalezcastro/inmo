"""Add campaigns, pipeline, and voice call models

Revision ID: e5f6g7a8h9i0
Revises: d4e5f6g7a8h9
Create Date: 2025-01-27 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e5f6g7a8h9i0'
down_revision: Union[str, None] = 'd4e5f6g7a8h9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    
    # Create enums for campaigns
    # CampaignChannel enum
    def ensure_enum(name, values):
        r = conn.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = :n"), {"n": name})
        if r.fetchone() is None:
            vals = ", ".join(f"'{v}'" for v in values)
            conn.execute(sa.text(f"CREATE TYPE {name} AS ENUM ({vals})"))

    ensure_enum("campaignchannel", ("telegram", "call", "whatsapp", "email"))
    ensure_enum("campaignstatus", ("draft", "active", "paused", "completed"))
    ensure_enum("campaigntrigger", ("manual", "lead_score", "stage_change", "inactivity"))
    ensure_enum("campaignstepaction", ("send_message", "make_call", "schedule_meeting", "update_stage"))
    ensure_enum("campaignlogstatus", ("pending", "sent", "failed", "skipped"))
    
    # TemplateChannel enum - create only if not exists
    r = conn.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'templatechannel'"))
    if r.fetchone() is None:
        conn.execute(sa.text("CREATE TYPE templatechannel AS ENUM ('telegram', 'call', 'email', 'whatsapp')"))
    
    ensure_enum("agenttype", ("perfilador", "calificador_financiero", "agendador", "seguimiento"))
    ensure_enum("callstatus", ("initiated", "ringing", "answered", "completed", "failed", "no_answer", "busy", "cancelled"))
    ensure_enum("speakertype", ("bot", "customer"))
    ensure_enum("treatmenttype", ("automated_telegram", "automated_call", "manual_follow_up", "hold"))

    templatechannel_enum = postgresql.ENUM("telegram", "call", "email", "whatsapp", name="templatechannel", create_type=False)
    agenttype_enum = postgresql.ENUM("perfilador", "calificador_financiero", "agendador", "seguimiento", name="agenttype", create_type=False)
    campaignchannel_enum = postgresql.ENUM("telegram", "call", "whatsapp", "email", name="campaignchannel", create_type=False)
    campaignstatus_enum = postgresql.ENUM("draft", "active", "paused", "completed", name="campaignstatus", create_type=False)
    campaigntrigger_enum = postgresql.ENUM("manual", "lead_score", "stage_change", "inactivity", name="campaigntrigger", create_type=False)
    campaignstepaction_enum = postgresql.ENUM("send_message", "make_call", "schedule_meeting", "update_stage", name="campaignstepaction", create_type=False)
    campaignlogstatus_enum = postgresql.ENUM("pending", "sent", "failed", "skipped", name="campaignlogstatus", create_type=False)
    callstatus_enum = postgresql.ENUM("initiated", "ringing", "answered", "completed", "failed", "no_answer", "busy", "cancelled", name="callstatus", create_type=False)
    speakertype_enum = postgresql.ENUM("bot", "customer", name="speakertype", create_type=False)
    treatmenttype_enum = postgresql.ENUM("automated_telegram", "automated_call", "manual_follow_up", "hold", name="treatmenttype", create_type=False)

    # Create message_templates table
    op.create_table('message_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('channel', templatechannel_enum, nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('agent_type', agenttype_enum, nullable=True),
        sa.Column('variables', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('broker_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['broker_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_template_broker_channel', 'message_templates', ['broker_id', 'channel'], unique=False)
    op.create_index('idx_template_agent_type', 'message_templates', ['agent_type', 'channel'], unique=False)
    op.create_index(op.f('ix_message_templates_id'), 'message_templates', ['id'], unique=False)
    op.create_index(op.f('ix_message_templates_channel'), 'message_templates', ['channel'], unique=False)
    
    # Create campaigns table
    op.create_table('campaigns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('channel', campaignchannel_enum, nullable=False),
        sa.Column('status', campaignstatus_enum, nullable=False),
        sa.Column('triggered_by', campaigntrigger_enum, nullable=False),
        sa.Column('trigger_condition', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('max_contacts', sa.Integer(), nullable=True),
        sa.Column('broker_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['broker_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_campaign_broker_status', 'campaigns', ['broker_id', 'status'], unique=False)
    op.create_index('idx_campaign_trigger', 'campaigns', ['triggered_by', 'status'], unique=False)
    op.create_index(op.f('ix_campaigns_id'), 'campaigns', ['id'], unique=False)
    op.create_index(op.f('ix_campaigns_channel'), 'campaigns', ['channel'], unique=False)
    op.create_index(op.f('ix_campaigns_status'), 'campaigns', ['status'], unique=False)
    op.create_index(op.f('ix_campaigns_triggered_by'), 'campaigns', ['triggered_by'], unique=False)
    
    # Create campaign_steps table
    op.create_table('campaign_steps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('action', campaignstepaction_enum, nullable=False),
        sa.Column('message_template_id', sa.Integer(), nullable=True),
        sa.Column('delay_hours', sa.Integer(), nullable=False),
        sa.Column('conditions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('target_stage', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_template_id'], ['message_templates.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_campaign_step_order', 'campaign_steps', ['campaign_id', 'step_number'], unique=False)
    op.create_index(op.f('ix_campaign_steps_id'), 'campaign_steps', ['id'], unique=False)
    op.create_index(op.f('ix_campaign_steps_campaign_id'), 'campaign_steps', ['campaign_id'], unique=False)
    
    # Create campaign_logs table
    op.create_table('campaign_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('status', campaignlogstatus_enum, nullable=False),
        sa.Column('response', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_campaign_log_lead', 'campaign_logs', ['lead_id', 'status'], unique=False)
    op.create_index('idx_campaign_log_campaign_lead', 'campaign_logs', ['campaign_id', 'lead_id'], unique=False)
    op.create_index('idx_campaign_log_created', 'campaign_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_campaign_logs_id'), 'campaign_logs', ['id'], unique=False)
    op.create_index(op.f('ix_campaign_logs_campaign_id'), 'campaign_logs', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_campaign_logs_lead_id'), 'campaign_logs', ['lead_id'], unique=False)
    op.create_index(op.f('ix_campaign_logs_status'), 'campaign_logs', ['status'], unique=False)
    
    # Create voice_calls table
    op.create_table('voice_calls',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.Column('phone_number', sa.String(length=20), nullable=False),
        sa.Column('external_call_id', sa.String(length=255), nullable=True),
        sa.Column('status', callstatus_enum, nullable=False),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('recording_url', sa.String(length=500), nullable=True),
        sa.Column('transcript', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('stage_after_call', sa.String(length=50), nullable=True),
        sa.Column('score_delta', sa.Float(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('broker_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['broker_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_voice_call_lead_status', 'voice_calls', ['lead_id', 'status'], unique=False)
    op.create_index('idx_voice_call_broker', 'voice_calls', ['broker_id', 'started_at'], unique=False)
    op.create_index('idx_voice_call_external_id', 'voice_calls', ['external_call_id'], unique=True)
    op.create_index(op.f('ix_voice_calls_id'), 'voice_calls', ['id'], unique=False)
    op.create_index(op.f('ix_voice_calls_lead_id'), 'voice_calls', ['lead_id'], unique=False)
    op.create_index(op.f('ix_voice_calls_campaign_id'), 'voice_calls', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_voice_calls_status'), 'voice_calls', ['status'], unique=False)
    
    # Create call_transcripts table
    op.create_table('call_transcripts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('voice_call_id', sa.Integer(), nullable=False),
        sa.Column('speaker', speakertype_enum, nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.Float(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['voice_call_id'], ['voice_calls.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_transcript_call_timestamp', 'call_transcripts', ['voice_call_id', 'timestamp'], unique=False)
    op.create_index(op.f('ix_call_transcripts_id'), 'call_transcripts', ['id'], unique=False)
    op.create_index(op.f('ix_call_transcripts_voice_call_id'), 'call_transcripts', ['voice_call_id'], unique=False)
    
    # Update leads table - add pipeline fields
    op.add_column('leads', sa.Column('pipeline_stage', sa.String(length=50), nullable=True))
    op.add_column('leads', sa.Column('stage_entered_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('leads', sa.Column('campaign_history', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'))
    op.add_column('leads', sa.Column('assigned_to', sa.Integer(), nullable=True))
    op.add_column('leads', sa.Column('treatment_type', treatmenttype_enum, nullable=True))
    op.add_column('leads', sa.Column('next_action_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('leads', sa.Column('notes', sa.Text(), nullable=True))
    
    # Add foreign key for assigned_to
    op.create_foreign_key('fk_leads_assigned_to', 'leads', 'users', ['assigned_to'], ['id'], ondelete='SET NULL')
    
    # Create indexes for new lead columns
    op.create_index('idx_pipeline_stage', 'leads', ['pipeline_stage', 'stage_entered_at'], unique=False)
    op.create_index('idx_assigned_treatment', 'leads', ['assigned_to', 'treatment_type'], unique=False)
    op.create_index('idx_next_action', 'leads', ['next_action_at', 'treatment_type'], unique=False)
    op.create_index(op.f('ix_leads_pipeline_stage'), 'leads', ['pipeline_stage'], unique=False)
    op.create_index(op.f('ix_leads_assigned_to'), 'leads', ['assigned_to'], unique=False)
    op.create_index(op.f('ix_leads_treatment_type'), 'leads', ['treatment_type'], unique=False)
    
    # Create audit_logs table
    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('changes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_audit_user_action', 'audit_logs', ['user_id', 'action'], unique=False)
    op.create_index('idx_audit_resource', 'audit_logs', ['resource_type', 'resource_id'], unique=False)
    op.create_index('idx_audit_timestamp', 'audit_logs', ['timestamp'], unique=False)
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_resource_type'), 'audit_logs', ['resource_type'], unique=False)
    op.create_index(op.f('ix_audit_logs_resource_id'), 'audit_logs', ['resource_id'], unique=False)


def downgrade() -> None:
    # Drop audit_logs table
    op.drop_index(op.f('ix_audit_logs_resource_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_resource_type'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_user_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_id'), table_name='audit_logs')
    op.drop_index('idx_audit_timestamp', table_name='audit_logs')
    op.drop_index('idx_audit_resource', table_name='audit_logs')
    op.drop_index('idx_audit_user_action', table_name='audit_logs')
    op.drop_table('audit_logs')
    
    # Drop indexes for leads
    op.drop_index(op.f('ix_leads_treatment_type'), table_name='leads')
    op.drop_index(op.f('ix_leads_assigned_to'), table_name='leads')
    op.drop_index(op.f('ix_leads_pipeline_stage'), table_name='leads')
    op.drop_index('idx_next_action', table_name='leads')
    op.drop_index('idx_assigned_treatment', table_name='leads')
    op.drop_index('idx_pipeline_stage', table_name='leads')
    
    # Drop foreign key
    op.drop_constraint('fk_leads_assigned_to', 'leads', type_='foreignkey')
    
    # Drop columns from leads
    op.drop_column('leads', 'notes')
    op.drop_column('leads', 'next_action_at')
    op.drop_column('leads', 'treatment_type')
    op.drop_column('leads', 'assigned_to')
    op.drop_column('leads', 'campaign_history')
    op.drop_column('leads', 'stage_entered_at')
    op.drop_column('leads', 'pipeline_stage')
    
    # Drop call_transcripts table
    op.drop_index(op.f('ix_call_transcripts_voice_call_id'), table_name='call_transcripts')
    op.drop_index(op.f('ix_call_transcripts_id'), table_name='call_transcripts')
    op.drop_index('idx_transcript_call_timestamp', table_name='call_transcripts')
    op.drop_table('call_transcripts')
    
    # Drop voice_calls table
    op.drop_index(op.f('ix_voice_calls_status'), table_name='voice_calls')
    op.drop_index(op.f('ix_voice_calls_campaign_id'), table_name='voice_calls')
    op.drop_index(op.f('ix_voice_calls_lead_id'), table_name='voice_calls')
    op.drop_index(op.f('ix_voice_calls_id'), table_name='voice_calls')
    op.drop_index('idx_voice_call_external_id', table_name='voice_calls')
    op.drop_index('idx_voice_call_broker', table_name='voice_calls')
    op.drop_index('idx_voice_call_lead_status', table_name='voice_calls')
    op.drop_table('voice_calls')
    
    # Drop campaign_logs table
    op.drop_index(op.f('ix_campaign_logs_status'), table_name='campaign_logs')
    op.drop_index(op.f('ix_campaign_logs_lead_id'), table_name='campaign_logs')
    op.drop_index(op.f('ix_campaign_logs_campaign_id'), table_name='campaign_logs')
    op.drop_index(op.f('ix_campaign_logs_id'), table_name='campaign_logs')
    op.drop_index('idx_campaign_log_created', table_name='campaign_logs')
    op.drop_index('idx_campaign_log_campaign_lead', table_name='campaign_logs')
    op.drop_index('idx_campaign_log_lead', table_name='campaign_logs')
    op.drop_table('campaign_logs')
    
    # Drop campaign_steps table
    op.drop_index(op.f('ix_campaign_steps_campaign_id'), table_name='campaign_steps')
    op.drop_index(op.f('ix_campaign_steps_id'), table_name='campaign_steps')
    op.drop_index('idx_campaign_step_order', table_name='campaign_steps')
    op.drop_table('campaign_steps')
    
    # Drop campaigns table
    op.drop_index(op.f('ix_campaigns_triggered_by'), table_name='campaigns')
    op.drop_index(op.f('ix_campaigns_status'), table_name='campaigns')
    op.drop_index(op.f('ix_campaigns_channel'), table_name='campaigns')
    op.drop_index(op.f('ix_campaigns_id'), table_name='campaigns')
    op.drop_index('idx_campaign_trigger', table_name='campaigns')
    op.drop_index('idx_campaign_broker_status', table_name='campaigns')
    op.drop_table('campaigns')
    
    # Drop message_templates table
    op.drop_index(op.f('ix_message_templates_channel'), table_name='message_templates')
    op.drop_index(op.f('ix_message_templates_id'), table_name='message_templates')
    op.drop_index('idx_template_agent_type', table_name='message_templates')
    op.drop_index('idx_template_broker_channel', table_name='message_templates')
    op.drop_table('message_templates')
    
    # Drop enums
    sa.Enum(name='treatmenttype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='speakertype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='callstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='agenttype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='templatechannel').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='campaignlogstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='campaignstepaction').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='campaigntrigger').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='campaignstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='campaignchannel').drop(op.get_bind(), checkfirst=True)

