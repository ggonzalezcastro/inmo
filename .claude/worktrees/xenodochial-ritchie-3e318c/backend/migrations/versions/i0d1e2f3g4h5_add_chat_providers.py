"""add_chat_providers

Revision ID: i0d1e2f3g4h5
Revises: h9c0d1e2f3g4
Create Date: 2025-02-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "i0d1e2f3g4h5"
down_revision: Union[str, None] = "h9c0d1e2f3g4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enums for chat_messages (use distinct names to avoid conflict with telegram_messages enums)
    postgresql.ENUM(
        "telegram",
        "whatsapp",
        "instagram",
        "facebook",
        "tiktok",
        "webchat",
        name="chatprovider",
        create_type=True,
    ).create(op.get_bind(), checkfirst=True)
    postgresql.ENUM("in", "out", name="chatmessagedirection", create_type=True).create(
        op.get_bind(), checkfirst=True
    )
    postgresql.ENUM(
        "pending", "sent", "delivered", "read", "failed", name="chatmessagestatus", create_type=True
    ).create(op.get_bind(), checkfirst=True)

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), sa.Identity(start=1, increment=1), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column(
            "provider",
            postgresql.ENUM(
                "telegram",
                "whatsapp",
                "instagram",
                "facebook",
                "tiktok",
                "webchat",
                name="chatprovider",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("channel_user_id", sa.String(length=255), nullable=False),
        sa.Column("channel_username", sa.String(length=255), nullable=True),
        sa.Column("channel_message_id", sa.String(length=255), nullable=True),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column(
            "direction",
            postgresql.ENUM("in", "out", name="chatmessagedirection", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "sent", "delivered", "read", "failed", name="chatmessagestatus", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("provider_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("attachments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ai_response_used", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_chat_messages_lead_provider", "chat_messages", ["lead_id", "provider"], unique=False)
    op.create_index("idx_chat_messages_broker_provider", "chat_messages", ["broker_id", "provider"], unique=False)
    op.create_index("idx_chat_messages_channel_user", "chat_messages", ["provider", "channel_user_id"], unique=False)
    op.create_index(op.f("ix_chat_messages_lead_id"), "chat_messages", ["lead_id"], unique=False)
    op.create_index(op.f("ix_chat_messages_broker_id"), "chat_messages", ["broker_id"], unique=False)
    op.create_index(op.f("ix_chat_messages_provider"), "chat_messages", ["provider"], unique=False)
    op.create_index(op.f("ix_chat_messages_channel_user_id"), "chat_messages", ["channel_user_id"], unique=False)

    # Create broker_chat_configs
    op.create_table(
        "broker_chat_configs",
        sa.Column("id", sa.Integer(), sa.Identity(start=1, increment=1), nullable=False),
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("enabled_providers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column(
            "default_provider",
            postgresql.ENUM(
                "telegram",
                "whatsapp",
                "instagram",
                "facebook",
                "tiktok",
                "webchat",
                name="chatprovider",
                create_type=False,
            ),
            nullable=False,
            server_default="webchat",
        ),
        sa.Column("provider_configs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("webhook_configs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("rate_limits", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("broker_id"),
    )
    op.create_index(op.f("ix_broker_chat_configs_broker_id"), "broker_chat_configs", ["broker_id"], unique=False)

    # Migrate data from telegram_messages to chat_messages (broker_id from lead; fallback 1 if null)
    # Map telegram enums: INBOUND->in, OUTBOUND->out; SENT->sent, DELIVERED->delivered, READ->read, FAILED->failed
    op.execute("""
        INSERT INTO chat_messages (
            lead_id, broker_id, provider, channel_user_id, channel_username,
            channel_message_id, message_text, direction, status, ai_response_used,
            created_at, updated_at
        )
        SELECT
            tm.lead_id,
            COALESCE(l.broker_id, 1),
            'telegram'::chatprovider,
            tm.telegram_user_id::text,
            tm.telegram_username,
            tm.telegram_message_id,
            tm.message_text,
            CASE WHEN tm.direction::text = 'INBOUND' THEN 'in'::chatmessagedirection ELSE 'out'::chatmessagedirection END,
            LOWER(tm.status::text)::chatmessagestatus,
            tm.ai_response_used,
            tm.created_at,
            COALESCE(tm.created_at, now())
        FROM telegram_messages tm
        JOIN leads l ON l.id = tm.lead_id
    """)


def downgrade() -> None:
    op.drop_index(op.f("ix_broker_chat_configs_broker_id"), table_name="broker_chat_configs")
    op.drop_table("broker_chat_configs")

    op.drop_index(op.f("ix_chat_messages_channel_user_id"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_provider"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_broker_id"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_lead_id"), table_name="chat_messages")
    op.drop_index("idx_chat_messages_channel_user", table_name="chat_messages")
    op.drop_index("idx_chat_messages_broker_provider", table_name="chat_messages")
    op.drop_index("idx_chat_messages_lead_provider", table_name="chat_messages")
    op.drop_table("chat_messages")

    postgresql.ENUM(name="chatmessagestatus").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="chatmessagedirection").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="chatprovider").drop(op.get_bind(), checkfirst=True)
