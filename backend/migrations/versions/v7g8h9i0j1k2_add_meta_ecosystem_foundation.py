"""add Meta ecosystem multi-tenant foundation

Revision ID: v7g8h9i0j1k2
Revises: u6f7g8h9i0j1
Create Date: 2026-09-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "v7g8h9i0j1k2"
down_revision = "u6f7g8h9i0j1"
branch_labels = None
depends_on = None


JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column(
        "brokers",
        sa.Column(
            "meta_features",
            JSONB,
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_table(
        "meta_connections",
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("owner_type", sa.String(length=20), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("connected_by_user_id", sa.Integer(), nullable=True),
        sa.Column("auth_mode", sa.String(length=40), nullable=False),
        sa.Column("external_principal_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("scopes", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_error_detail", sa.Text(), nullable=True),
        sa.Column(
            "connection_metadata",
            JSONB,
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("owner_type IN ('broker', 'executive')", name="ck_meta_connection_owner_type"),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'degraded', 'revoked', 'disconnected', 'error')",
            name="ck_meta_connection_status",
        ),
        sa.CheckConstraint(
            "(owner_type = 'broker' AND owner_user_id IS NULL) OR "
            "(owner_type = 'executive' AND owner_user_id IS NOT NULL)",
            name="ck_meta_connection_owner_user",
        ),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["connected_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "broker_id", "auth_mode", "external_principal_id",
            name="uq_meta_connection_principal",
        ),
    )
    op.create_index("ix_meta_connections_broker_id", "meta_connections", ["broker_id"])
    op.create_index("ix_meta_connections_owner_user_id", "meta_connections", ["owner_user_id"])
    op.create_index("ix_meta_connections_connected_by_user_id", "meta_connections", ["connected_by_user_id"])
    op.create_index("ix_meta_connections_auth_mode", "meta_connections", ["auth_mode"])
    op.create_index("ix_meta_connections_status", "meta_connections", ["status"])
    op.create_index("ix_meta_connections_expires_at", "meta_connections", ["expires_at"])
    op.create_index("idx_meta_connections_broker_status", "meta_connections", ["broker_id", "status"])

    op.create_table(
        "meta_assets",
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("asset_type", sa.String(length=40), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("parent_external_id", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("owner_type", sa.String(length=20), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("assigned_user_id", sa.Integer(), nullable=True),
        sa.Column("capabilities", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("approval_status", sa.String(length=30), server_default="pending_approval", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="paused", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ai_mode", sa.String(length=30), server_default="suggestion", nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_error_detail", sa.Text(), nullable=True),
        sa.Column("asset_metadata", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("owner_type IN ('broker', 'executive')", name="ck_meta_asset_owner_type"),
        sa.CheckConstraint(
            "approval_status IN ('pending_approval', 'approved', 'rejected')",
            name="ck_meta_asset_approval_status",
        ),
        sa.CheckConstraint("status IN ('active', 'paused', 'disabled', 'error')", name="ck_meta_asset_status"),
        sa.CheckConstraint(
            "ai_mode IN ('suggestion', 'supervised_auto', 'human')",
            name="ck_meta_asset_ai_mode",
        ),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["meta_connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_type", "external_id", name="uq_meta_asset_external"),
    )
    op.create_index("ix_meta_assets_broker_id", "meta_assets", ["broker_id"])
    op.create_index("ix_meta_assets_connection_id", "meta_assets", ["connection_id"])
    op.create_index("ix_meta_assets_asset_type", "meta_assets", ["asset_type"])
    op.create_index("ix_meta_assets_channel", "meta_assets", ["channel"])
    op.create_index("ix_meta_assets_owner_user_id", "meta_assets", ["owner_user_id"])
    op.create_index("ix_meta_assets_assigned_user_id", "meta_assets", ["assigned_user_id"])
    op.create_index("ix_meta_assets_approval_status", "meta_assets", ["approval_status"])
    op.create_index("ix_meta_assets_status", "meta_assets", ["status"])
    op.create_index("idx_meta_assets_broker_channel", "meta_assets", ["broker_id", "channel"])
    op.create_index("idx_meta_assets_connection_type", "meta_assets", ["connection_id", "asset_type"])
    op.create_index(
        "uq_meta_assets_default_channel",
        "meta_assets",
        ["broker_id", "channel"],
        unique=True,
        postgresql_where=sa.text("is_default = true AND channel IS NOT NULL"),
    )

    op.create_table(
        "meta_credentials",
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=True),
        sa.Column("subject_type", sa.String(length=40), nullable=False),
        sa.Column("subject_external_id", sa.String(length=255), nullable=False),
        sa.Column("encrypted_token", sa.Text(), nullable=False),
        sa.Column("token_type", sa.String(length=40), server_default="bearer", nullable=False),
        sa.Column("scopes", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("key_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["meta_connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["meta_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "connection_id", "subject_type", "subject_external_id",
            name="uq_meta_credential_subject",
        ),
    )
    op.create_index("ix_meta_credentials_broker_id", "meta_credentials", ["broker_id"])
    op.create_index("ix_meta_credentials_connection_id", "meta_credentials", ["connection_id"])
    op.create_index("ix_meta_credentials_asset_id", "meta_credentials", ["asset_id"])
    op.create_index("ix_meta_credentials_expires_at", "meta_credentials", ["expires_at"])
    op.create_index("ix_meta_credentials_status", "meta_credentials", ["status"])
    op.create_index("idx_meta_credentials_broker_status", "meta_credentials", ["broker_id", "status"])

    op.create_table(
        "meta_message_templates",
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("waba_external_id", sa.String(length=255), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("components", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["meta_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "broker_id", "waba_external_id", "name", "language",
            name="uq_meta_message_template_name_language",
        ),
    )
    op.create_index("ix_meta_message_templates_broker_id", "meta_message_templates", ["broker_id"])
    op.create_index("ix_meta_message_templates_connection_id", "meta_message_templates", ["connection_id"])
    op.create_index("ix_meta_message_templates_waba_external_id", "meta_message_templates", ["waba_external_id"])
    op.create_index("ix_meta_message_templates_name", "meta_message_templates", ["name"])
    op.create_index("ix_meta_message_templates_status", "meta_message_templates", ["status"])
    op.create_index(
        "idx_meta_message_templates_lookup",
        "meta_message_templates",
        ["broker_id", "waba_external_id", "status"],
    )

    op.create_table(
        "channel_identities",
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=True),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("first_interaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_interaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("identity_metadata", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["meta_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "broker_id", "asset_id", "channel", "external_user_id",
            name="uq_channel_identity_external",
        ),
    )
    op.create_index("ix_channel_identities_broker_id", "channel_identities", ["broker_id"])
    op.create_index("ix_channel_identities_asset_id", "channel_identities", ["asset_id"])
    op.create_index("ix_channel_identities_lead_id", "channel_identities", ["lead_id"])
    op.create_index("ix_channel_identities_channel", "channel_identities", ["channel"])
    op.create_index("ix_channel_identities_phone", "channel_identities", ["phone"])
    op.create_index("ix_channel_identities_email", "channel_identities", ["email"])
    op.create_index("ix_channel_identities_last_interaction_at", "channel_identities", ["last_interaction_at"])
    op.create_index("idx_channel_identities_lead_channel", "channel_identities", ["lead_id", "channel"])

    op.create_table(
        "meta_webhook_events",
        sa.Column("broker_id", sa.Integer(), nullable=True),
        sa.Column("asset_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("external_event_id", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("signature_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("payload_ciphertext", sa.Text(), nullable=True),
        sa.Column("payload_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'processed', 'failed', 'ignored')",
            name="ck_meta_webhook_event_status",
        ),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["meta_assets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_meta_webhook_events_broker_id", "meta_webhook_events", ["broker_id"])
    op.create_index("ix_meta_webhook_events_asset_id", "meta_webhook_events", ["asset_id"])
    op.create_index("ix_meta_webhook_events_provider", "meta_webhook_events", ["provider"])
    op.create_index("ix_meta_webhook_events_event_type", "meta_webhook_events", ["event_type"])
    op.create_index("ix_meta_webhook_events_payload_expires_at", "meta_webhook_events", ["payload_expires_at"])
    op.create_index("ix_meta_webhook_events_status", "meta_webhook_events", ["status"])
    op.create_index("idx_meta_webhook_events_processing", "meta_webhook_events", ["status", "created_at"])
    op.create_index("idx_meta_webhook_events_broker_provider", "meta_webhook_events", ["broker_id", "provider"])

    op.create_table(
        "meta_assignment_conflicts",
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("current_assignee_id", sa.Integer(), nullable=True),
        sa.Column("asset_owner_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolution", sa.String(length=40), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('open', 'resolved', 'dismissed')", name="ck_meta_assignment_conflict_status"),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["meta_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["current_assignee_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["asset_owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meta_assignment_conflicts_broker_id", "meta_assignment_conflicts", ["broker_id"])
    op.create_index("ix_meta_assignment_conflicts_lead_id", "meta_assignment_conflicts", ["lead_id"])
    op.create_index("ix_meta_assignment_conflicts_asset_id", "meta_assignment_conflicts", ["asset_id"])
    op.create_index("ix_meta_assignment_conflicts_status", "meta_assignment_conflicts", ["status"])
    op.create_index("idx_meta_assignment_conflicts_broker_status", "meta_assignment_conflicts", ["broker_id", "status"])
    op.create_index(
        "uq_meta_assignment_conflict_open",
        "meta_assignment_conflicts",
        ["lead_id", "asset_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )

    op.add_column("conversations", sa.Column("meta_asset_id", sa.Integer(), nullable=True))
    op.add_column("conversations", sa.Column("channel_identity_id", sa.Integer(), nullable=True))
    op.add_column("conversations", sa.Column("messaging_window_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "conversations",
        sa.Column("assignment_conflict", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_foreign_key("fk_conversations_meta_asset", "conversations", "meta_assets", ["meta_asset_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_conversations_channel_identity", "conversations", "channel_identities", ["channel_identity_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_conversations_meta_asset_id", "conversations", ["meta_asset_id"])
    op.create_index("ix_conversations_channel_identity_id", "conversations", ["channel_identity_id"])
    op.create_index("idx_conv_broker_asset_status", "conversations", ["broker_id", "meta_asset_id", "status"])

    op.add_column("chat_messages", sa.Column("meta_asset_id", sa.Integer(), nullable=True))
    op.add_column("chat_messages", sa.Column("sent_by_user_id", sa.Integer(), nullable=True))
    op.add_column("chat_messages", sa.Column("reply_to_external_id", sa.String(length=255), nullable=True))
    op.add_column("chat_messages", sa.Column("message_type", sa.String(length=30), server_default="text", nullable=False))
    op.add_column("chat_messages", sa.Column("generation_mode", sa.String(length=20), server_default="manual", nullable=False))
    op.add_column("chat_messages", sa.Column("remote_error_code", sa.String(length=100), nullable=True))
    op.add_column("chat_messages", sa.Column("remote_error_subcode", sa.String(length=100), nullable=True))
    op.create_foreign_key("fk_chat_messages_meta_asset", "chat_messages", "meta_assets", ["meta_asset_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_chat_messages_sent_by_user", "chat_messages", "users", ["sent_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_chat_messages_meta_asset_id", "chat_messages", ["meta_asset_id"])
    op.create_index("ix_chat_messages_sent_by_user_id", "chat_messages", ["sent_by_user_id"])
    op.create_index("idx_chat_messages_broker_asset", "chat_messages", ["broker_id", "meta_asset_id"])
    op.create_index(
        "uq_chat_messages_meta_external_id",
        "chat_messages",
        ["broker_id", "meta_asset_id", "provider", "channel_message_id"],
        unique=True,
        postgresql_where=sa.text(
            "channel_message_id IS NOT NULL AND meta_asset_id IS NOT NULL"
        ),
    )

    op.create_table(
        "conversation_read_states",
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("last_read_message_id", sa.Integer(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["last_read_message_id"], ["chat_messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "user_id", name="uq_conversation_read_state_user"),
    )
    op.create_index("ix_conversation_read_states_broker_id", "conversation_read_states", ["broker_id"])
    op.create_index("ix_conversation_read_states_conversation_id", "conversation_read_states", ["conversation_id"])
    op.create_index("ix_conversation_read_states_user_id", "conversation_read_states", ["user_id"])
    op.create_index("idx_conversation_read_broker_user", "conversation_read_states", ["broker_id", "user_id"])


def downgrade() -> None:
    op.drop_table("conversation_read_states")
    op.drop_index("uq_chat_messages_meta_external_id", table_name="chat_messages")
    op.drop_index("idx_chat_messages_broker_asset", table_name="chat_messages")
    op.drop_index("ix_chat_messages_sent_by_user_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_meta_asset_id", table_name="chat_messages")
    op.drop_constraint("fk_chat_messages_sent_by_user", "chat_messages", type_="foreignkey")
    op.drop_constraint("fk_chat_messages_meta_asset", "chat_messages", type_="foreignkey")
    for column in (
        "remote_error_subcode", "remote_error_code", "generation_mode", "message_type",
        "reply_to_external_id", "sent_by_user_id", "meta_asset_id",
    ):
        op.drop_column("chat_messages", column)

    op.drop_index("idx_conv_broker_asset_status", table_name="conversations")
    op.drop_index("ix_conversations_channel_identity_id", table_name="conversations")
    op.drop_index("ix_conversations_meta_asset_id", table_name="conversations")
    op.drop_constraint("fk_conversations_channel_identity", "conversations", type_="foreignkey")
    op.drop_constraint("fk_conversations_meta_asset", "conversations", type_="foreignkey")
    for column in (
        "assignment_conflict", "messaging_window_expires_at", "channel_identity_id", "meta_asset_id",
    ):
        op.drop_column("conversations", column)

    op.drop_table("meta_assignment_conflicts")
    op.drop_table("meta_webhook_events")
    op.drop_table("channel_identities")
    op.drop_table("meta_message_templates")
    op.drop_table("meta_credentials")
    op.drop_table("meta_assets")
    op.drop_table("meta_connections")
    op.drop_column("brokers", "meta_features")
