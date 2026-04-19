"""
AgentVoiceProfile — per-agent overrides on top of AgentVoiceTemplate.
"""
from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, IdMixin, TimestampMixin


class AgentVoiceProfile(Base, IdMixin, TimestampMixin):
    """
    Per-agent voice preferences.  Each field overrides the parent template
    only if the value is in the template's allowed list.

    One profile per user (unique constraint on user_id).
    """

    __tablename__ = "agent_voice_profiles"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )
    template_id = Column(
        Integer, ForeignKey("agent_voice_templates.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # Must be in template.available_voice_ids
    selected_voice_id = Column(String(255), nullable=True)

    # Must be in template.available_tones
    selected_tone = Column(String(50), nullable=True)

    # AI persona displayed to the lead
    assistant_name = Column(String(100), nullable=True)
    opening_message = Column(Text, nullable=True)

    # Override template.default_call_mode: "ai_agent" | "transcriptor" | None
    preferred_call_mode = Column(String(20), nullable=True)

    # VAPI assistant ID managed by backend; never exposed to frontend
    vapi_assistant_id = Column(String(255), nullable=True)

    # Relationships
    user = relationship("User", back_populates="voice_profile")
    template = relationship("AgentVoiceTemplate", back_populates="profiles")

    def __repr__(self):
        return f"<AgentVoiceProfile id={self.id} user_id={self.user_id}>"
