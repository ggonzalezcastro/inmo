"""
Generic chat message model - provider agnostic.
Supports Telegram, WhatsApp, Instagram, Facebook, TikTok, WebChat.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, Enum as SQLEnum, Index
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


class ChatMessage(Base, IdMixin, TimestampMixin):
    """Generic chat message - provider agnostic."""

    __tablename__ = "chat_messages"

    # Relations
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)

    # Provider
    provider = Column(SQLEnum(ChatProvider), nullable=False, index=True)

    # Generic channel identifiers
    channel_user_id = Column(String(255), nullable=False, index=True)
    channel_username = Column(String(255), nullable=True)
    channel_message_id = Column(String(255), nullable=True, index=True)

    # Message data
    message_text = Column(Text, nullable=False)
    direction = Column(
        SQLEnum(MessageDirection),
        default=MessageDirection.OUTBOUND,
        nullable=False,
    )
    status = Column(
        SQLEnum(MessageStatus),
        default=MessageStatus.SENT,
        nullable=False,
    )

    # Provider-specific metadata (JSONB for flexibility)
    provider_metadata = Column(JSONB, nullable=True)

    # Attachments (media, files)
    attachments = Column(JSONB, nullable=True)

    # AI flag
    ai_response_used = Column(Boolean, default=True)

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

    __table_args__ = (
        Index("idx_chat_messages_lead_provider", "lead_id", "provider"),
        Index("idx_chat_messages_broker_provider", "broker_id", "provider"),
        Index("idx_chat_messages_channel_user", "provider", "channel_user_id"),
    )

    def __repr__(self):
        return f"<ChatMessage id={self.id} lead_id={self.lead_id} provider={self.provider} direction={self.direction}>"
