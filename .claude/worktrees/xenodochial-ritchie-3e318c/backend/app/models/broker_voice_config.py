"""
Broker voice configuration for Vapi.ai assistants
"""
from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.models.base import Base, IdMixin, TimestampMixin


class BrokerVoiceConfig(Base, IdMixin, TimestampMixin):
    """Voice (Vapi) configuration for broker's AI agent"""

    __tablename__ = "broker_voice_configs"

    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    provider = Column(String(50), default="vapi", nullable=False)
    provider_credentials = Column(JSONB, nullable=True)

    phone_number_id = Column(String(255), nullable=True)
    assistant_id_default = Column(String(255), nullable=True)
    assistant_id_by_type = Column(JSONB, nullable=True)

    voice_config = Column(JSONB, nullable=True)
    model_config = Column(JSONB, nullable=True)
    transcriber_config = Column(JSONB, nullable=True)
    timing_config = Column(JSONB, nullable=True)
    end_call_config = Column(JSONB, nullable=True)

    first_message_template = Column(Text, nullable=True)
    recording_enabled = Column(Boolean, default=True, nullable=False)

    broker = relationship("Broker", back_populates="voice_config")

    def __repr__(self):
        return f"<BrokerVoiceConfig broker_id={self.broker_id}>"
