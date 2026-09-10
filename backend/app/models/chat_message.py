"""
Generic chat message model - provider agnostic.
Supports Telegram, WhatsApp, Instagram, Facebook, TikTok, WebChat.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, Enum as SQLEnum, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from enum import Enum
from app.models.base import Base, IdMixin, TimestampMixin


class MessageDirection(str, Enum):
    INBOUND = "in"
    OUTBOUND = "out"


class MessageStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class ChatProvider(str, Enum):
    """Supported chat providers"""
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    WEBCHAT = "webchat"
    VOICE = "voice"


class ChatMessage(Base, IdMixin, TimestampMixin):
    """Generic chat message - provider agnostic."""

    __tablename__ = "chat_messages"

    # Relations
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    meta_asset_id = Column(
        Integer,
        ForeignKey("meta_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sent_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Provider
    provider = Column(
        SQLEnum(ChatProvider, name="chatprovider", create_type=False,
                values_callable=lambda obj: [e.value for e in obj]),
        nullable=False, index=True,
    )

    # Generic channel identifiers
    channel_user_id = Column(String(255), nullable=False, index=True)
    channel_username = Column(String(255), nullable=True)
    channel_message_id = Column(String(255), nullable=True, index=True)
    reply_to_external_id = Column(String(255), nullable=True)
    message_type = Column(String(30), nullable=False, default="text")

    # Message data
    message_text = Column(Text, nullable=False)
    direction = Column(
        SQLEnum(MessageDirection, name="chatmessagedirection", create_type=False,
                values_callable=lambda obj: [e.value for e in obj]),
        default=MessageDirection.OUTBOUND,
        nullable=False,
    )
    status = Column(
        SQLEnum(MessageStatus, name="chatmessagestatus", create_type=False,
                values_callable=lambda obj: [e.value for e in obj]),
        default=MessageStatus.SENT,
        nullable=False,
    )

    # Provider-specific metadata (JSONB for flexibility)
    provider_metadata = Column(JSONB, nullable=True)

    # Attachments (media, files)
    attachments = Column(JSONB, nullable=True)

    # AI flag
    ai_response_used = Column(Boolean, default=True)
    generation_mode = Column(String(20), nullable=False, default="manual")
    remote_error_code = Column(String(100), nullable=True)
    remote_error_subcode = Column(String(100), nullable=True)

    # Prompt version used when generating this response (nullable — human messages)
    prompt_version_id = Column(
        Integer,
        ForeignKey("prompt_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    lead = relationship("Lead", back_populates="chat_messages")
    broker = relationship("Broker", back_populates="chat_messages")
    prompt_version = relationship("PromptVersion", foreign_keys=[prompt_version_id])
    conversation = relationship(
        "Conversation",
        back_populates="messages",
        foreign_keys="ChatMessage.conversation_id",
    )
    meta_asset = relationship("MetaAsset", foreign_keys=[meta_asset_id])
    sent_by_user = relationship("User", foreign_keys=[sent_by_user_id])

    __table_args__ = (
        Index("idx_chat_messages_lead_provider", "lead_id", "provider"),
        Index("idx_chat_messages_broker_provider", "broker_id", "provider"),
        Index("idx_chat_messages_channel_user", "provider", "channel_user_id"),
        Index("idx_chat_messages_broker_asset", "broker_id", "meta_asset_id"),
        Index(
            "uq_chat_messages_meta_external_id",
            "broker_id",
            "meta_asset_id",
            "provider",
            "channel_message_id",
            unique=True,
            postgresql_where=text(
                "channel_message_id IS NOT NULL AND meta_asset_id IS NOT NULL"
            ),
        ),
    )

    def __repr__(self):
        return f"<ChatMessage id={self.id} lead_id={self.lead_id} provider={self.provider} direction={self.direction}>"
