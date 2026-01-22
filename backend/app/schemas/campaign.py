"""
Campaign schemas for API validation
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class CampaignChannelEnum(str, Enum):
    TELEGRAM = "telegram"
    CALL = "call"
    WHATSAPP = "whatsapp"
    EMAIL = "email"


class CampaignStatusEnum(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class CampaignTriggerEnum(str, Enum):
    MANUAL = "manual"
    LEAD_SCORE = "lead_score"
    STAGE_CHANGE = "stage_change"
    INACTIVITY = "inactivity"


class CampaignStepActionEnum(str, Enum):
    SEND_MESSAGE = "send_message"
    MAKE_CALL = "make_call"
    SCHEDULE_MEETING = "schedule_meeting"
    UPDATE_STAGE = "update_stage"


class CampaignLogStatusEnum(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class CampaignBase(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    channel: CampaignChannelEnum
    triggered_by: Optional[CampaignTriggerEnum] = CampaignTriggerEnum.MANUAL
    trigger_condition: Optional[Dict[str, Any]] = Field(default_factory=dict)
    max_contacts: Optional[int] = Field(None, ge=1)


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    status: Optional[CampaignStatusEnum] = None
    channel: Optional[CampaignChannelEnum] = None
    triggered_by: Optional[CampaignTriggerEnum] = None
    trigger_condition: Optional[Dict[str, Any]] = None
    max_contacts: Optional[int] = Field(None, ge=1)


class CampaignResponse(CampaignBase):
    id: int
    status: CampaignStatusEnum
    broker_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CampaignStepBase(BaseModel):
    step_number: int = Field(..., ge=1)
    action: CampaignStepActionEnum
    delay_hours: int = Field(default=0, ge=0)
    message_template_id: Optional[int] = None
    conditions: Optional[Dict[str, Any]] = Field(default_factory=dict)
    target_stage: Optional[str] = None


class CampaignStepCreate(CampaignStepBase):
    pass


class CampaignStepResponse(CampaignStepBase):
    id: int
    campaign_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CampaignLogResponse(BaseModel):
    id: int
    campaign_id: int
    lead_id: int
    step_number: int
    status: CampaignLogStatusEnum
    response: Optional[Dict[str, Any]] = None
    created_at: datetime
    executed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class CampaignListResponse(BaseModel):
    data: List[CampaignResponse]
    total: int
    skip: int
    limit: int


class CampaignStatsResponse(BaseModel):
    campaign_id: int
    total_steps: int
    unique_leads: int
    pending: int
    sent: int
    failed: int
    skipped: int
    success_rate: float
    failure_rate: float



