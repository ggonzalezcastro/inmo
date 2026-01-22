from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from enum import Enum
from app.models.base import Base, IdMixin


class MessageDirection(str, Enum):
    INBOUND = "in"
    OUTBOUND = "out"


class MessageStatus(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class TelegramMessage(Base, IdMixin):
    """Telegram message history"""
    
    __tablename__ = "telegram_messages"
    
    # Foreign key
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    
    # Telegram identifiers
    telegram_user_id = Column(Integer, nullable=False, index=True)
    telegram_username = Column(String(100), nullable=True)
    telegram_message_id = Column(String(100), nullable=True, unique=True)
    
    # Message data
    message_text = Column(Text, nullable=False)
    direction = Column(
        SQLEnum(MessageDirection),
        default=MessageDirection.OUTBOUND,
        nullable=False
    )
    status = Column(
        SQLEnum(MessageStatus),
        default=MessageStatus.SENT,
        nullable=False
    )
    
    # AI flag
    ai_response_used = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default="now()", nullable=False)
    
    # Relationship
    lead = relationship("Lead", back_populates="telegram_messages")
    
    def __repr__(self):
        return f"<TelegramMessage id={self.id} lead_id={self.lead_id} direction={self.direction}>"

