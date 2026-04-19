"""
Voice call schemas for API validation
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional
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


# ── Call start / response ─────────────────────────────────────────────────────

class CallStartRequest(BaseModel):
    lead_id: int
    call_mode: Literal["ai_agent", "transcriptor", "autonomous"]
    call_purpose: str  # CallPurpose enum value; validated in service


class CallStartResponse(BaseModel):
    voice_call_id: int
    call_mode: str
    # Web SDK modes (ai_agent / transcriptor): public key for @vapi-ai/web
    vapi_public_key: Optional[str] = None
    # When the agent has a voice profile: assistantId flow (prompt never leaves server)
    vapi_assistant_id: Optional[str] = None
    # Per-call overrides injected via vapi.start(assistantId, overrides) — only tools
    assistant_overrides: Optional[Dict[str, Any]] = None
    # Fallback inline config for bare transcriptor mode (no profile configured)
    vapi_config: Optional[Dict[str, Any]] = None
    # Autonomous mode: external call ID assigned by VAPI when it initiates the call
    external_call_id: Optional[str] = None


# ── VoiceCall response ────────────────────────────────────────────────────────

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
    call_mode: Optional[str] = None
    call_purpose: Optional[str] = None
    call_output: Optional[Dict[str, Any]] = None
    agent_user_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class VoiceCallListResponse(BaseModel):
    data: List[VoiceCallResponse]


# ── Agent voice profile ───────────────────────────────────────────────────────

class AgentVoiceProfileUpdate(BaseModel):
    selected_voice_id: Optional[str] = None
    selected_tone: Optional[str] = None
    assistant_name: Optional[str] = None
    opening_message: Optional[str] = None
    preferred_call_mode: Optional[Literal["ai_agent", "transcriptor"]] = None


class AgentVoiceProfileResponse(BaseModel):
    id: int
    user_id: int
    template_id: int
    selected_voice_id: Optional[str] = None
    selected_tone: Optional[str] = None
    assistant_name: Optional[str] = None
    opening_message: Optional[str] = None
    preferred_call_mode: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Agent voice template ──────────────────────────────────────────────────────

class AgentVoiceTemplateCreate(BaseModel):
    name: str
    business_prompt: Optional[str] = None
    qualification_criteria: Optional[Dict[str, Any]] = None
    niche_instructions: Optional[str] = None
    language: str = "es"
    transcriber_config: Optional[Dict[str, Any]] = None
    max_duration_seconds: int = 600
    max_silence_seconds: float = 30.0
    recording_policy: Literal["enabled", "optional", "disabled"] = "enabled"
    # Each entry is either a plain voiceId string (legacy) or a
    # {voiceId: str, provider: str} dict (preferred for multi-provider support).
    available_voice_ids: List[Any] = []
    available_tones: List[str] = []
    default_call_mode: Literal["ai_agent", "transcriptor"] = "transcriptor"
    is_active: bool = True


class AgentVoiceTemplateUpdate(AgentVoiceTemplateCreate):
    name: Optional[str] = None


class AgentVoiceTemplateResponse(BaseModel):
    id: int
    broker_id: int
    name: str
    business_prompt: Optional[str] = None
    qualification_criteria: Optional[Dict[str, Any]] = None
    niche_instructions: Optional[str] = None
    language: str
    transcriber_config: Optional[Dict[str, Any]] = None
    max_duration_seconds: int
    max_silence_seconds: float
    recording_policy: str
    available_voice_ids: List[Any]
    available_tones: List[str]
    default_call_mode: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Call metrics ──────────────────────────────────────────────────────────────

class CallMetricsResponse(BaseModel):
    total: int
    by_purpose: Dict[str, int]
    by_mode: Dict[str, int]
    avg_duration_seconds: Optional[float]
    this_month: int



