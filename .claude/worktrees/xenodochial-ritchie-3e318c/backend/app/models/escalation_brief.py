"""
EscalationBrief — LLM-generated handoff summary for human agents.

When a lead escalates to human_mode, an LLM generates a structured brief
with: reason for escalation, lead profile, collected data, conversation
summary, emotional context, and a suggested action.

The brief is shown to the human agent when they open the conversation,
so they can immediately understand the context without reading the full
chat history.
"""
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql.functions import now

from app.models.base import Base, IdMixin


class EscalationBrief(Base, IdMixin):
    """LLM-generated context summary for human agents taking over a lead."""

    __tablename__ = "escalation_briefs"

    # ── Context ───────────────────────────────────────────────────────────────
    lead_id = Column(
        Integer,
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Brief content ─────────────────────────────────────────────────────────
    brief_text = Column(Text, nullable=False)
    reason = Column(String(50), nullable=True)
    # 'frustration', 'explicit_request', 'low_confidence', 'vip', 'manual'
    frustration_score = Column(Float, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    lead = relationship("Lead", foreign_keys=[lead_id])

    __table_args__ = (
        Index("idx_escalation_briefs_lead", "lead_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<EscalationBrief id={self.id} lead={self.lead_id} "
            f"reason={self.reason}>"
        )
