"""
Conversation — tracks a discrete chat session between a lead and the CRM.

One lead can have multiple conversations (one per channel, or re-opened after
closing). This separates conversation-level state from the lead profile, allowing
better context management and multi-conversation analytics.

The context_summary JSONB stores a compact snapshot of what the agent knows
so far, enabling token-efficient context passing (~200-500 tokens vs 5K-20K
from the full message history).
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql.functions import now

from app.models.base import Base, IdMixin, TimestampMixin


class Conversation(Base, IdMixin, TimestampMixin):
    """A discrete chat session for a lead on a specific channel."""

    __tablename__ = "conversations"

    # ── Tenancy ───────────────────────────────────────────────────────────────
    lead_id = Column(
        Integer,
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Channel ───────────────────────────────────────────────────────────────
    channel = Column(String(20), nullable=False)
    # 'telegram', 'whatsapp', 'instagram', 'facebook', 'webchat'
    meta_asset_id = Column(
        Integer,
        ForeignKey("meta_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    channel_identity_id = Column(
        Integer,
        ForeignKey("channel_identities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    messaging_window_expires_at = Column(DateTime(timezone=True), nullable=True)
    assignment_conflict = Column(Boolean, nullable=False, default=False)

    # ── Status ────────────────────────────────────────────────────────────────
    status = Column(String(20), nullable=False, default="active")
    # 'active', 'human_mode', 'closed', 'archived'
    close_reason = Column(String(50), nullable=True)

    # ── Agent routing state ───────────────────────────────────────────────────
    current_agent = Column(String(30), nullable=True)
    # 'qualifier', 'scheduler', 'follow_up', 'property'
    conversation_state = Column(String(30), nullable=True)
    # 'GREETING', 'INTEREST_CHECK', 'DATA_COLLECTION', 'SCHEDULING', etc.

    # ── Human handoff state ───────────────────────────────────────────────────
    human_mode = Column(Boolean, nullable=False, default=False)
    human_assigned_to = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    human_taken_at = Column(DateTime(timezone=True), nullable=True)
    human_released_at = Column(DateTime(timezone=True), nullable=True)

    # ── Message stats ─────────────────────────────────────────────────────────
    started_at = Column(
        DateTime(timezone=True),
        server_default=now(),
        nullable=False,
    )
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    message_count = Column(Integer, nullable=False, default=0)

    # ── Compact context snapshot ──────────────────────────────────────────────
    # Updated after each agent turn. Structure:
    # {
    #   "collected_fields": {"name": "Juan", "phone": "+56...", "salary": 1800000},
    #   "missing_fields": ["email", "dicom_status"],
    #   "interests": ["departamento", "Ñuñoa", "3 dormitorios"],
    #   "budget_uf": 3500,
    #   "property_preferences": {"bedrooms": 3, "commune": "Ñuñoa", "max_uf": 4000},
    #   "last_agent_note": "Lead calificó financieramente, listo para ver propiedades",
    #   "human_release_note": "Le ofrecí descuento en Vista Norte"
    # }
    context_summary = Column(JSONB, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    lead = relationship("Lead", foreign_keys=[lead_id])
    broker = relationship("Broker", foreign_keys=[broker_id])
    human_agent = relationship("User", foreign_keys=[human_assigned_to])
    meta_asset = relationship("MetaAsset", foreign_keys=[meta_asset_id])
    channel_identity = relationship("ChannelIdentity", foreign_keys=[channel_identity_id])
    messages = relationship(
        "ChatMessage",
        back_populates="conversation",
        foreign_keys="ChatMessage.conversation_id",
    )

    __table_args__ = (
        Index("idx_conv_lead", "lead_id", "started_at"),
        Index("idx_conv_broker_status", "broker_id", "status"),
        Index(
            "idx_conv_human",
            "human_mode",
            postgresql_where="human_mode = true",
        ),
        Index("idx_conv_broker_channel", "broker_id", "channel"),
        Index("idx_conv_broker_asset_status", "broker_id", "meta_asset_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Conversation id={self.id} lead={self.lead_id} "
            f"channel={self.channel} status={self.status}>"
        )


class ConversationReadState(Base, IdMixin, TimestampMixin):
    """Per-user read cursor used to compute unread messages without guesswork."""

    __tablename__ = "conversation_read_states"

    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    last_read_message_id = Column(
        Integer,
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    read_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "user_id",
            name="uq_conversation_read_state_user",
        ),
        Index("idx_conversation_read_broker_user", "broker_id", "user_id"),
    )
