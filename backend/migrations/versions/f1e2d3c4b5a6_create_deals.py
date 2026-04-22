"""create deals and deal_documents tables, add ai_can_upload_deal_files to broker_lead_configs

Revision ID: f1e2d3c4b5a6
Revises: z2b3c4d5e6f7
Create Date: 2026-04-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'f1e2d3c4b5a6'
down_revision: Union[str, Sequence[str]] = 'z2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── deals ────────────────────────────────────────────────────────────────
    op.create_table(
        'deals',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        # Tenancy
        sa.Column('broker_id', sa.Integer(), sa.ForeignKey('brokers.id', ondelete='CASCADE'), nullable=False),
        # Core FKs
        sa.Column('lead_id', sa.Integer(), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('property_id', sa.Integer(), sa.ForeignKey('properties.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        # Stage & delivery
        sa.Column('stage', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('delivery_type', sa.String(20), nullable=False, server_default='desconocida'),
        # Bank review
        sa.Column('bank_review_status', sa.String(20), nullable=True),
        # Jefatura review
        sa.Column('jefatura_review_required', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('jefatura_review_status', sa.String(20), nullable=True),
        sa.Column('jefatura_review_notes', sa.Text(), nullable=True),
        # Stage timestamps
        sa.Column('reserva_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('docs_completos_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('bank_decision_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('promesa_signed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('escritura_signed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        # Cancellation
        sa.Column('cancellation_reason', sa.String(100), nullable=True),
        sa.Column('cancellation_notes', sa.Text(), nullable=True),
        # Planning
        sa.Column('escritura_planned_date', sa.Date(), nullable=True),
        # Metadata (attribute name: deal_metadata, DB column: metadata)
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        # Timestamps (from TimestampMixin)
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    # Single-column indexes
    op.create_index('ix_deals_broker_id', 'deals', ['broker_id'])
    op.create_index('ix_deals_lead_id', 'deals', ['lead_id'])
    op.create_index('ix_deals_property_id', 'deals', ['property_id'])
    # Composite indexes
    op.create_index('idx_deal_broker_lead', 'deals', ['broker_id', 'lead_id'])
    op.create_index('idx_deal_broker_property', 'deals', ['broker_id', 'property_id'])
    op.create_index('idx_deal_stage', 'deals', ['broker_id', 'stage'])
    # Partial unique index: at most one active deal per property per broker
    op.create_index(
        'uq_deal_active_property',
        'deals',
        ['broker_id', 'property_id'],
        unique=True,
        postgresql_where=sa.text("stage != 'cancelado'"),
    )

    # ── deal_documents ────────────────────────────────────────────────────────
    op.create_table(
        'deal_documents',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        # Core FK
        sa.Column('deal_id', sa.Integer(), sa.ForeignKey('deals.id', ondelete='CASCADE'), nullable=False),
        # Slot identity
        sa.Column('slot', sa.String(50), nullable=False),
        sa.Column('slot_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('co_titular_index', sa.Integer(), nullable=False, server_default='0'),
        # Status
        sa.Column('status', sa.String(20), nullable=False, server_default='pendiente'),
        # File metadata
        sa.Column('storage_key', sa.String(500), nullable=True),
        sa.Column('original_filename', sa.String(255), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('sha256', sa.String(64), nullable=True),
        # Upload tracking
        sa.Column('uploaded_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('uploaded_by_ai', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=True),
        # Review tracking
        sa.Column('reviewed_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        # Timestamps (from TimestampMixin)
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_deal_documents_deal_id', 'deal_documents', ['deal_id'])
    op.create_index('idx_dealdoc_deal_slot', 'deal_documents', ['deal_id', 'slot', 'slot_index', 'co_titular_index'])
    op.create_index('idx_dealdoc_status', 'deal_documents', ['deal_id', 'status'])

    # ── broker_lead_configs — add ai_can_upload_deal_files ────────────────────
    op.add_column(
        'broker_lead_configs',
        sa.Column('ai_can_upload_deal_files', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    # Remove column from broker_lead_configs
    op.drop_column('broker_lead_configs', 'ai_can_upload_deal_files')

    # Drop deal_documents
    op.drop_index('idx_dealdoc_status', table_name='deal_documents')
    op.drop_index('idx_dealdoc_deal_slot', table_name='deal_documents')
    op.drop_index('ix_deal_documents_deal_id', table_name='deal_documents')
    op.drop_table('deal_documents')

    # Drop deals
    op.drop_index('uq_deal_active_property', table_name='deals')
    op.drop_index('idx_deal_stage', table_name='deals')
    op.drop_index('idx_deal_broker_property', table_name='deals')
    op.drop_index('idx_deal_broker_lead', table_name='deals')
    op.drop_index('ix_deals_property_id', table_name='deals')
    op.drop_index('ix_deals_lead_id', table_name='deals')
    op.drop_index('ix_deals_broker_id', table_name='deals')
    op.drop_table('deals')
