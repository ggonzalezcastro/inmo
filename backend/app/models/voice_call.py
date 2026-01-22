"""
Voice call models for recording and managing phone calls
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, 
    ForeignKey, JSON, Enum as SQLEnum, Index
)
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
        SQLEnum(CallStatus),
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
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Multi-tenancy
    broker_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Relationships
    lead = relationship("Lead")
    campaign = relationship("Campaign", foreign_keys=[campaign_id])
    broker = relationship("User", foreign_keys=[broker_id])
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
        SQLEnum(SpeakerType),
        nullable=False
    )
    
    # Transcript line
    text = Column(Text, nullable=False)
    
    # Timestamp in call (seconds from start)
    timestamp = Column(Float, nullable=False)
    
    # STT confidence score (0.0 to 1.0)
    confidence = Column(Float, nullable=True)
    
    # Relationships
    voice_call = relationship("VoiceCall", back_populates="transcript_lines")
    
    # Indices
    __table_args__ = (
        Index('idx_transcript_call_timestamp', 'voice_call_id', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<CallTranscript id={self.id} voice_call_id={self.voice_call_id} speaker={self.speaker} timestamp={self.timestamp}>"



