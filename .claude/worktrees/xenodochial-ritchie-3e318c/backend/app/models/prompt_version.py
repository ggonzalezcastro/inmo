"""
PromptVersion — versioned system-prompt snapshots per broker.

Each row represents a named version of the agent's system prompt.
Only one version can be active at a time per broker (enforced in the
service layer; is_active is flipped atomically).
"""
from sqlalchemy import (
    Column,
    Float,
    Integer,
    String,
    Text,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, IdMixin, TimestampMixin


class PromptVersion(Base, IdMixin, TimestampMixin):
    """Versioned snapshot of a broker's agent system prompt."""

    __tablename__ = "prompt_versions"

    # ── Relations ────────────────────────────────────────────────────────────
    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Version metadata ─────────────────────────────────────────────────────
    version_tag = Column(String(50), nullable=False)   # e.g. "v1.0.0"
    prompt_type = Column(String(30), nullable=True)
    # 'system', 'qualification', 'scheduling', 'property'
    prompt_hash = Column(String(64), nullable=True)    # SHA-256 for deduplication
    is_active = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=True)

    # ── Prompt content ────────────────────────────────────────────────────────
    content = Column(Text, nullable=False)             # full prompt text
    sections_json = Column(JSONB, nullable=True)       # optional structured sections

    # ── Aggregated performance metrics (updated by background task) ───────────
    total_uses = Column(Integer, nullable=False, default=0)
    avg_tokens_per_call = Column(Float, nullable=True)
    avg_latency_ms = Column(Float, nullable=True)
    avg_lead_score_delta = Column(Float, nullable=True)
    escalation_rate = Column(Float, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    broker = relationship("Broker", back_populates="prompt_versions")
    creator = relationship("User", foreign_keys=[created_by])

    # ── Constraints & indexes ─────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "broker_id", "version_tag", name="uq_prompt_version_broker_tag"
        ),
        Index("idx_prompt_versions_broker_active", "broker_id", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<PromptVersion id={self.id} broker_id={self.broker_id} "
            f"tag={self.version_tag!r} active={self.is_active}>"
        )
