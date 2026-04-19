"""
AgentVoiceTemplate — broker-owned immutable base config for agent voice calls.
"""
from sqlalchemy import (
    Boolean, Column, Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, IdMixin, TimestampMixin


class AgentVoiceTemplate(Base, IdMixin, TimestampMixin):
    """
    Broker-level voice template.  Defines the curated set of options that
    agents can pick from (voices, tones) and the immutable base config they
    cannot override (business_prompt, transcriber, limits, etc.).
    """

    __tablename__ = "agent_voice_templates"

    broker_id = Column(
        Integer, ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name = Column(String(200), nullable=False)

    # Base prompt — agents cannot edit this
    business_prompt = Column(Text, nullable=True)
    qualification_criteria = Column(JSONB, nullable=True)
    niche_instructions = Column(Text, nullable=True)

    language = Column(String(20), default="es", nullable=False)

    # Transcriber (Deepgram config dict)
    transcriber_config = Column(JSONB, nullable=True)

    # Call limits
    max_duration_seconds = Column(Integer, default=600, nullable=False)
    max_silence_seconds = Column(Float, default=30.0, nullable=False)

    # Recording policy: "enabled" | "optional" | "disabled"
    recording_policy = Column(String(20), default="enabled", nullable=False)

    # Curated lists agents can choose from
    available_voice_ids = Column(JSONB, nullable=False, default=list)
    available_tones = Column(JSONB, nullable=False, default=list)

    # Default call mode when agent has no preference: "ai_agent" | "transcriptor"
    default_call_mode = Column(String(20), default="transcriptor", nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    broker = relationship("Broker", back_populates="voice_templates")
    profiles = relationship("AgentVoiceProfile", back_populates="template")

    def __repr__(self):
        return f"<AgentVoiceTemplate id={self.id} broker_id={self.broker_id} name={self.name!r}>"
