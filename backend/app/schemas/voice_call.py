"""
Voice call schemas for API validation
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class CallStatusEnum(str, Enum):
    INITIATED = "initiated"
    RINGING = "ringing"
    ANSWERED = "answered"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    CANCELLED = "cancelled"


class CallInitiateRequest(BaseModel):
    lead_id: int
    campaign_id: Optional[int] = None
    agent_type: Optional[str] = None


class VoiceCallResponse(BaseModel):
    id: int
    lead_id: int
    campaign_id: Optional[int] = None
    phone_number: str
    external_call_id: Optional[str] = None
    status: CallStatusEnum
    duration: Optional[int] = None
    recording_url: Optional[str] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    stage_after_call: Optional[str] = None
    score_delta: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class VoiceCallListResponse(BaseModel):
    data: list[VoiceCallResponse]



