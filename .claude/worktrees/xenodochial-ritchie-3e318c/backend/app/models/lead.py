from datetime import datetime
from enum import Enum
from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, JSON, Index, Text, UniqueConstraint, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin, IdMixin


class LeadStatus(str, Enum):
    COLD = "cold"
    WARM = "warm"
    HOT = "hot"
    CONVERTED = "converted"
    LOST = "lost"


class TreatmentType(str, Enum):
    """Type of treatment to give to a lead"""
    AUTOMATED_TELEGRAM = "automated_telegram"
    AUTOMATED_CALL = "automated_call"
    MANUAL_FOLLOW_UP = "manual_follow_up"
    HOLD = "hold"


class Lead(Base, IdMixin, TimestampMixin):
    """Lead model for storing prospect information"""
    
    __tablename__ = "leads"
    
    # Basic info
    phone = Column(String(20), nullable=False, index=True)  # Removed unique=True to allow duplicate phones
    name = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    
    # Scoring & Status
    status = Column(
        String(20),
        default=LeadStatus.COLD,
        nullable=False,
        index=True
    )
    lead_score = Column(Float, default=0.0, nullable=False, index=True)
    lead_score_components = Column(
        JSON,
        default={"base": 0, "behavior": 0, "engagement": 0},
        nullable=False
    )
    
    # Contact tracking
    last_contacted = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Pipeline management
    pipeline_stage = Column(
        String(50),
        nullable=True,
        index=True
    )  # "entrada", "perfilamiento", "calificacion_financiera", "potencial", "agendado", "ganado", "perdido"
    
    stage_entered_at = Column(DateTime(timezone=True), nullable=True, index=True)  # When entered current stage
    
    # Campaign tracking
    campaign_history = Column(JSON, default=[], nullable=False)  # List of campaigns applied: [{"campaign_id": 1, "applied_at": "...", "steps_completed": 2}]
    
    # Assignment and treatment
    assigned_to = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)  # Agent assigned
    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=True, index=True)  # Broker this lead belongs to
    
    treatment_type = Column(
        SQLEnum(TreatmentType),
        nullable=True,
        index=True
    )  # Type of treatment: automated_telegram, automated_call, manual_follow_up, hold
    
    next_action_at = Column(DateTime(timezone=True), nullable=True, index=True)  # Scheduled next action
    
    # Close tracking (ganado/perdido)
    close_reason = Column(String(100), nullable=True)       # e.g. "precio", "competencia", "compra_directa"
    close_reason_detail = Column(Text, nullable=True)       # Free-text notes about why closed
    closed_at = Column(DateTime(timezone=True), nullable=True)
    closed_from_stage = Column(String(50), nullable=True)   # Which stage the lead was in when closed

    # Internal notes
    notes = Column(Text, nullable=True)  # Internal notes from agents
    
    # Metadata
    tags = Column(JSON, default=[], nullable=False)  # ["inmobiliario", "activo"]
    lead_metadata = Column("metadata", JSONB, default={}, nullable=False)  # {budget: "150k", timeline: "30 dias"}

    # Human takeover state (promoted from JSONB for indexed queries and FK integrity)
    human_mode = Column(Boolean, nullable=False, default=False, server_default="false")
    human_assigned_to = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    human_taken_at = Column(DateTime(timezone=True), nullable=True)
    human_released_at = Column(DateTime(timezone=True), nullable=True)
    human_release_note = Column(Text, nullable=True)  # Context note left by human agent when returning to AI

    # Relationships
    telegram_messages = relationship(
        "TelegramMessage",
        back_populates="lead",
        cascade="all, delete-orphan"
    )
    chat_messages = relationship(
        "ChatMessage",
        back_populates="lead",
        cascade="all, delete-orphan"
    )
    activities = relationship(
        "ActivityLog",
        back_populates="lead",
        cascade="all, delete-orphan"
    )
    appointments = relationship(
        "Appointment",
        back_populates="lead",
        cascade="all, delete-orphan"
    )
    campaign_logs = relationship(
        "CampaignLog",
        back_populates="lead",
        cascade="all, delete-orphan"
    )
    voice_calls = relationship(
        "VoiceCall",
        back_populates="lead",
        cascade="all, delete-orphan"
    )
    assigned_agent = relationship("User", foreign_keys=[assigned_to])
    human_agent = relationship("User", foreign_keys=[human_assigned_to])
    broker = relationship("Broker", foreign_keys=[broker_id])
    
    # Indices
    __table_args__ = (
        Index('idx_status_score', 'status', 'lead_score'),
        Index('idx_phone', 'phone'),
        Index('idx_pipeline_stage', 'pipeline_stage', 'stage_entered_at'),
        Index('idx_assigned_treatment', 'assigned_to', 'treatment_type'),
        Index('idx_next_action', 'next_action_at', 'treatment_type'),
        # Removed UniqueConstraint on phone to allow duplicate phones
    )
    
    def __repr__(self):
        return f"<Lead id={self.id} phone={self.phone} status={self.status}>"

