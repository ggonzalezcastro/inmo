from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date, time
from enum import Enum


class AppointmentStatusEnum(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class AppointmentTypeEnum(str, Enum):
    PROPERTY_VISIT = "property_visit"
    VIRTUAL_MEETING = "virtual_meeting"
    PHONE_CALL = "phone_call"
    OFFICE_MEETING = "office_meeting"
    OTHER = "other"


class AppointmentBase(BaseModel):
    appointment_type: AppointmentTypeEnum = AppointmentTypeEnum.VIRTUAL_MEETING  # Default to virtual
    start_time: datetime
    duration_minutes: int = Field(default=60, ge=15, le=480)  # 15 min to 8 hours
    agent_id: Optional[int] = None  # Required for multi-agent support
    location: Optional[str] = None
    property_address: Optional[str] = None
    notes: Optional[str] = None
    lead_notes: Optional[str] = None


class AppointmentCreate(AppointmentBase):
    lead_id: int


class AppointmentUpdate(BaseModel):
    appointment_type: Optional[AppointmentTypeEnum] = None
    start_time: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=15, le=480)
    agent_id: Optional[int] = None
    location: Optional[str] = None
    property_address: Optional[str] = None
    notes: Optional[str] = None
    lead_notes: Optional[str] = None
    status: Optional[AppointmentStatusEnum] = None


class AppointmentResponse(AppointmentBase):
    id: int
    lead_id: int
    status: AppointmentStatusEnum
    end_time: datetime
    meet_url: Optional[str] = None  # Google Meet URL
    reminder_sent_24h: bool
    reminder_sent_1h: bool
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AppointmentDetailResponse(AppointmentResponse):
    lead_name: Optional[str] = None
    lead_phone: Optional[str] = None
    agent_name: Optional[str] = None


class AvailabilitySlotBase(BaseModel):
    day_of_week: int = Field(ge=0, le=6)  # 0=Monday, 6=Sunday
    start_time: time
    end_time: time
    valid_from: date
    valid_until: Optional[date] = None
    appointment_type: Optional[AppointmentTypeEnum] = None
    slot_duration_minutes: int = Field(default=60, ge=15, le=480)
    max_appointments_per_slot: int = Field(default=1, ge=1)
    is_active: bool = True
    notes: Optional[str] = None


class AvailabilitySlotCreate(AvailabilitySlotBase):
    agent_id: Optional[int] = None


class AvailabilitySlotUpdate(BaseModel):
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    appointment_type: Optional[AppointmentTypeEnum] = None
    slot_duration_minutes: Optional[int] = Field(None, ge=15, le=480)
    max_appointments_per_slot: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class AvailabilitySlotResponse(AvailabilitySlotBase):
    id: int
    agent_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AppointmentBlockBase(BaseModel):
    start_time: datetime
    end_time: datetime
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None
    recurrence_end_date: Optional[date] = None
    reason: str
    notes: Optional[str] = None


class AppointmentBlockCreate(AppointmentBlockBase):
    agent_id: Optional[int] = None


class AppointmentBlockUpdate(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_recurring: Optional[bool] = None
    recurrence_pattern: Optional[str] = None
    recurrence_end_date: Optional[date] = None
    reason: Optional[str] = None
    notes: Optional[str] = None


class AppointmentBlockResponse(AppointmentBlockBase):
    id: int
    agent_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AvailableSlotResponse(BaseModel):
    """Response for available time slots"""
    start_time: str  # ISO format
    end_time: str  # ISO format
    duration_minutes: int
    date: str  # ISO date
    time: str  # HH:MM format


class AppointmentListResponse(BaseModel):
    """Response for listing appointments"""
    data: List[AppointmentResponse]
    total: int
    skip: int
    limit: int
