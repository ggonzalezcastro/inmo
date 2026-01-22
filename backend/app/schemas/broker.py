"""
Pydantic schemas for broker configuration
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any


class BrokerBase(BaseModel):
    name: str
    slug: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    business_hours: Optional[str] = Field(default='Lunes a Viernes 9:00-18:00')
    service_zones: Optional[Dict[str, Any]] = None
    is_active: bool = True


class BrokerCreate(BrokerBase):
    pass


class BrokerUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    business_hours: Optional[str] = None
    service_zones: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class BrokerResponse(BrokerBase):
    id: int
    
    class Config:
        from_attributes = True


class PromptConfigUpdate(BaseModel):
    agent_name: Optional[str] = None
    agent_role: Optional[str] = None
    identity_prompt: Optional[str] = None
    business_context: Optional[str] = None
    agent_objective: Optional[str] = None
    data_collection_prompt: Optional[str] = None
    behavior_rules: Optional[str] = None
    restrictions: Optional[str] = None
    situation_handlers: Optional[Dict[str, str]] = None
    output_format: Optional[str] = None
    full_custom_prompt: Optional[str] = None
    enable_appointment_booking: Optional[bool] = None
    tools_instructions: Optional[str] = None


class LeadConfigUpdate(BaseModel):
    field_weights: Optional[Dict[str, int]] = None
    cold_max_score: Optional[int] = None
    warm_max_score: Optional[int] = None
    hot_min_score: Optional[int] = None
    qualified_min_score: Optional[int] = None
    field_priority: Optional[List[str]] = None
    income_ranges: Optional[Dict[str, Any]] = None
    qualification_criteria: Optional[Dict[str, Any]] = None
    max_acceptable_debt: Optional[int] = None
    alert_on_hot_lead: Optional[bool] = None
    alert_on_qualified: Optional[bool] = None
    alert_score_threshold: Optional[int] = None
    alert_email: Optional[str] = None


