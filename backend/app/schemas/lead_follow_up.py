"""Validation and response contracts for lead notes and follow-up tasks."""

from datetime import datetime
from enum import Enum
from typing import Optional

import bleach
from pydantic import BaseModel, Field, field_validator

from app.models.lead_follow_up import ADVISORY_CHANNELS, REMINDER_OFFSETS_MINUTES


def _plain_text(value: str, *, max_length: int) -> str:
    cleaned = bleach.clean(value.strip(), tags=[], strip=True)
    if not cleaned:
        raise ValueError("El texto no puede estar vacío")
    return cleaned[:max_length]


def _timezone_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("La fecha debe incluir zona horaria")
    return value


class TaskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class AdvisoryChannel(str, Enum):
    WHATSAPP = "whatsapp"
    PHONE = "phone"
    VIDEO_CALL = "video_call"
    PROPERTY_VISIT = "property_visit"
    IN_PERSON = "in_person"
    OTHER = "other"


class LeadAdvisoryCreate(BaseModel):
    advisor_id: Optional[int] = None
    channel: AdvisoryChannel
    occurred_at: datetime
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        return _timezone_aware(value)

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, value: AdvisoryChannel) -> AdvisoryChannel:
        if value.value not in ADVISORY_CHANNELS:
            raise ValueError("Canal de asesoría no válido")
        return value

    @field_validator("notes")
    @classmethod
    def sanitize_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        return _plain_text(value, max_length=1000)


class LeadAdvisoryResponse(BaseModel):
    id: int
    lead_id: int
    advisor_id: Optional[int] = None
    advisor_name: Optional[str] = None
    recorded_by: Optional[int] = None
    recorder_name: Optional[str] = None
    channel: AdvisoryChannel
    occurred_at: datetime
    notes: Optional[str] = None
    created_at: datetime


class LeadAdvisoryListResponse(BaseModel):
    data: list[LeadAdvisoryResponse]
    total: int
    skip: int
    limit: int


class LeadNoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)

    @field_validator("body")
    @classmethod
    def sanitize_body(cls, value: str) -> str:
        return _plain_text(value, max_length=5000)


class LeadNoteResponse(BaseModel):
    id: int
    lead_id: int
    body: str
    author_id: Optional[int] = None
    author_name: Optional[str] = None
    created_at: datetime


class LeadNoteListResponse(BaseModel):
    data: list[LeadNoteResponse]
    total: int
    skip: int
    limit: int


class LeadTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    assigned_to: Optional[int] = None
    due_at: datetime
    reminder_minutes_before: Optional[int] = 60

    @field_validator("title")
    @classmethod
    def sanitize_title(cls, value: str) -> str:
        return _plain_text(value, max_length=200)

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value: datetime) -> datetime:
        return _timezone_aware(value)

    @field_validator("reminder_minutes_before")
    @classmethod
    def validate_reminder(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value not in REMINDER_OFFSETS_MINUTES:
            raise ValueError("Anticipación de recordatorio no válida")
        return value


class LeadTaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    assigned_to: Optional[int] = None
    due_at: Optional[datetime] = None
    reminder_minutes_before: Optional[int] = None

    @field_validator("title")
    @classmethod
    def sanitize_title(cls, value: Optional[str]) -> Optional[str]:
        return _plain_text(value, max_length=200) if value is not None else None

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value: Optional[datetime]) -> Optional[datetime]:
        return _timezone_aware(value) if value is not None else None

    @field_validator("reminder_minutes_before")
    @classmethod
    def validate_reminder(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value not in REMINDER_OFFSETS_MINUTES:
            raise ValueError("Anticipación de recordatorio no válida")
        return value


class LeadTaskResponse(BaseModel):
    id: int
    lead_id: int
    lead_name: Optional[str] = None
    lead_phone: Optional[str] = None
    title: str
    status: TaskStatus
    assigned_to: Optional[int] = None
    assignee_name: Optional[str] = None
    created_by: Optional[int] = None
    creator_name: Optional[str] = None
    completed_by: Optional[int] = None
    due_at: datetime
    reminder_minutes_before: Optional[int] = None
    reminder_at: Optional[datetime] = None
    reminder_sent_at: Optional[datetime] = None
    reminder_acknowledged_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class LeadTaskListResponse(BaseModel):
    data: list[LeadTaskResponse]
    total: int
    skip: int
    limit: int
