"""
Voice call models for recording and managing phone calls
"""
from enum import Enum
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, Boolean,
    ForeignKey, Enum as SQLEnum, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.models.base import Base, IdMixin, TimestampMixin


class CallStatus(str, Enum):
    """Status of a voice call"""
    INITIATED = "initiated"
    RINGING = "ringing"
    ANSWERED = "answered"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    CANCELLED = "cancelled"


class SpeakerType(str, Enum):
    """Speaker in call transcript"""
    BOT = "bot"
    CUSTOMER = "customer"
    AGENT = "agent"  # Human agent in transcriptor mode


class CallPurpose(str, Enum):
    """Purpose of the call — maps to pipeline stage context."""
    CALIFICACION_INICIAL = "calificacion_inicial"
    CALIFICACION_FINANCIERA = "calificacion_financiera"
    CONFIRMACION_REUNION = "confirmacion_reunion"
    CONFIRMACION_VISITA = "confirmacion_visita"
    SEGUIMIENTO_POST_VISITA = "seguimiento_post_visita"
    REACTIVACION = "reactivacion"


class VoiceCall(Base, IdMixin, TimestampMixin):
    """
    Voice call record for tracking phone conversations
    
    Stores call metadata, transcription, AI-generated summary,
    and results (stage changes, score changes).
    """
    
    __tablename__ = "voice_calls"
    
    # References
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Call information
    phone_number = Column(String(20), nullable=False)  # Dialed number
    external_call_id = Column(String(255), nullable=True, unique=True, index=True)  # Provider call ID (Twilio/Telnyx)
    
    # Call status
    status = Column(
        SQLEnum(CallStatus, values_callable=lambda x: [e.value for e in x]),
        default=CallStatus.INITIATED,
        nullable=False,
        index=True
    )
    
    # Call duration (seconds)
    duration = Column(Integer, nullable=True)  # Total call duration
    
    # Recording
    recording_url = Column(String(500), nullable=True)  # URL to stored recording
    
    # AI-generated content
    transcript = Column(Text, nullable=True)  # Full call transcript
    summary = Column(Text, nullable=True)  # AI-generated call summary
    
    # Results after call
    stage_after_call = Column(String(50), nullable=True)  # What stage to move lead to
    score_delta = Column(Float, nullable=True, default=0.0)  # Score change from call
    
    # Idempotency: marks end-of-call-report as fully processed
    post_processed = Column(Boolean, nullable=False, default=False, server_default="false")

    # Timestamps
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Multi-tenancy
    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)

    # CRM agent who initiated the call (NULL for campaign/outbound calls)
    agent_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Call mode: "ai_agent" | "transcriptor"
    call_mode = Column(String(20), nullable=True)

    # Purpose of the call (CallPurpose enum value)
    call_purpose = Column(String(50), nullable=True)

    # Structured output per call_purpose (JSONB)
    call_output = Column(JSONB, nullable=True)

    # Audit snapshots at call-start time
    template_snapshot = Column(JSONB, nullable=True)
    profile_snapshot = Column(JSONB, nullable=True)

    # ── Pipecat fields ────────────────────────────────────────────────────────
    # pipecat_mode: "autonomous" | "copilot" | "handoff" | "coaching"
    # (call_mode kept for VAPI backward compat; pipecat_mode for new calls)
    pipecat_mode = Column(String(20), nullable=True)
    call_direction = Column(String(10), nullable=True, default="outbound")  # "outbound" | "inbound"
    initiated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    agent_phone = Column(String(20), nullable=True)   # human agent phone for copilot/coaching/handoff
    lead_phone = Column(String(20), nullable=True)
    ai_speaking_seconds = Column(Float, nullable=True, default=0.0)
    human_speaking_seconds = Column(Float, nullable=True, default=0.0)
    lead_speaking_seconds = Column(Float, nullable=True, default=0.0)
    handoff_occurred = Column(Boolean, nullable=False, default=False, server_default="false")
    handoff_at = Column(DateTime(timezone=True), nullable=True)
    handoff_reason = Column(Text, nullable=True)
    handoff_to_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    extracted_data = Column(JSONB, nullable=True)  # sentiment, interests, objections, commitments, next_steps
    call_metrics = Column(JSONB, nullable=True)    # tts_provider, tokens, cost, latency, tools_used, emotion_tags

    # Relationships
    initiated_by = relationship("User", foreign_keys=[initiated_by_id])
    handoff_to_user = relationship("User", foreign_keys=[handoff_to_user_id])
    lead = relationship("Lead")
    campaign = relationship("Campaign", foreign_keys=[campaign_id])
    broker = relationship("Broker", foreign_keys=[broker_id])
    agent_user = relationship("User", foreign_keys=[agent_user_id])
    transcript_lines = relationship("CallTranscript", back_populates="voice_call", cascade="all, delete-orphan")
    
    # Indices
    __table_args__ = (
        Index('idx_voice_call_lead_status', 'lead_id', 'status'),
        Index('idx_voice_call_broker', 'broker_id', 'started_at'),
        Index('idx_voice_call_external_id', 'external_call_id'),
    )
    
    def __repr__(self):
        return f"<VoiceCall id={self.id} lead_id={self.lead_id} status={self.status} duration={self.duration}>"


class CallTranscript(Base, IdMixin):
    """
    Individual transcript lines for voice calls
    
    Stores detailed transcript with speaker identification,
    timestamps, and confidence scores from Speech-to-Text.
    """
    
    __tablename__ = "call_transcripts"
    
    # Reference to voice call
    voice_call_id = Column(Integer, ForeignKey("voice_calls.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Speaker identification
    speaker = Column(
        SQLEnum(SpeakerType, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    
    # Transcript line
    text = Column(Text, nullable=False)
    
    # Timestamp in call (seconds from start)
    timestamp = Column(Float, nullable=False)
    
    # STT confidence score (0.0 to 1.0)
    confidence = Column(Float, nullable=True)

    # Pipecat emotion fields
    emotion_detected = Column(String(50), nullable=True)   # detected emotion of the lead speaker
    emotion_tag_used = Column(String(100), nullable=True)  # Fish Audio emotion tag injected for AI (e.g. "[warm and enthusiastic]")
    duration_ms = Column(Integer, nullable=True)           # duration of this utterance in milliseconds

    # Relationships
    voice_call = relationship("VoiceCall", back_populates="transcript_lines")
    
    # Indices
    __table_args__ = (
        Index('idx_transcript_call_timestamp', 'voice_call_id', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<CallTranscript id={self.id} voice_call_id={self.voice_call_id} speaker={self.speaker} timestamp={self.timestamp}>"



