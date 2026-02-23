"""Normalized types for voice provider abstraction."""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class VoiceProviderType(str, Enum):
    VAPI = "vapi"
    BLAND = "bland"
    RETELL = "retell"
    TWILIO = "twilio"
    CUSTOM_SIP = "custom_sip"


class CallEventType(str, Enum):
    CALL_STARTED = "call_started"
    CALL_RINGING = "call_ringing"
    CALL_ANSWERED = "call_answered"
    CALL_ENDED = "call_ended"
    CALL_FAILED = "call_failed"
    TRANSCRIPT_UPDATE = "transcript_update"
    STATUS_UPDATE = "status_update"
    FUNCTION_CALL = "function_call"


@dataclass
class WebhookEvent:
    event_type: CallEventType
    external_call_id: str
    status: Optional[str] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    recording_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    error_message: Optional[str] = None
    raw_data: dict = field(default_factory=dict)


@dataclass
class CallStatusResult:
    external_call_id: str
    status: str
    duration_seconds: Optional[int] = None
    transcript: Optional[str] = None
    recording_url: Optional[str] = None


@dataclass
class MakeCallRequest:
    phone_number: str
    broker_id: int
    lead_id: Optional[int] = None
    agent_type: Optional[str] = None
    system_prompt: Optional[str] = None
    first_message: Optional[str] = None
    voice_config: Optional[dict] = None
    model_config: Optional[dict] = None
    metadata: Optional[dict] = None
    webhook_url: Optional[str] = None
