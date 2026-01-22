"""
Template schemas for API validation
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TemplateChannelEnum(str, Enum):
    TELEGRAM = "telegram"
    CALL = "call"
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class AgentTypeEnum(str, Enum):
    PERFILADOR = "perfilador"
    CALIFICADOR_FINANCIERO = "calificador_financiero"
    AGENDADOR = "agendador"
    SEGUIMIENTO = "seguimiento"


class TemplateBase(BaseModel):
    name: str = Field(..., max_length=200)
    channel: TemplateChannelEnum
    content: str
    agent_type: Optional[AgentTypeEnum] = None
    variables: Optional[List[str]] = Field(default_factory=list)


class TemplateCreate(TemplateBase):
    pass


class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = None
    variables: Optional[List[str]] = None


class TemplateResponse(TemplateBase):
    id: int
    broker_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TemplateListResponse(BaseModel):
    data: List[TemplateResponse]



