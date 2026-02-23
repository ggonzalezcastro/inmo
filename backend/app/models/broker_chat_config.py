"""
Broker chat configuration - supports multiple providers (Telegram, WhatsApp, Instagram, etc.).
"""
from sqlalchemy import Column, Integer, String, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.models.base import Base, IdMixin, TimestampMixin
from app.models.chat_message import ChatProvider


class BrokerChatConfig(Base, IdMixin, TimestampMixin):
    """Chat configuration for broker - supports multiple providers."""

    __tablename__ = "broker_chat_configs"

    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Enabled providers (e.g. ["telegram", "whatsapp", "instagram"])
    enabled_providers = Column(JSONB, default=lambda: [], nullable=False)

    # Default provider
    default_provider = Column(
        SQLEnum(ChatProvider),
        default=ChatProvider.WEBCHAT,
        nullable=False,
    )

    # Credentials per provider (JSONB)
    # e.g. {"telegram": {"bot_token": "xxx", "webhook_secret": "yyy"},
    #       "whatsapp": {"phone_number_id": "123", "access_token": "xxx", ...}}
    provider_configs = Column(JSONB, nullable=True)

    # Webhook configs per provider
    # e.g. {"telegram": {"url": "https://...", "enabled": true}, ...}
    webhook_configs = Column(JSONB, nullable=True)

    # Features (auto_reply, typing_indicator, read_receipts, message_templates, business_hours)
    features = Column(JSONB, nullable=True)

    # Rate limits per provider
    rate_limits = Column(JSONB, nullable=True)

    broker = relationship("Broker", back_populates="chat_config")

    def __repr__(self):
        return f"<BrokerChatConfig broker_id={self.broker_id}>"
