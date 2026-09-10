import re
import bleach
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from typing import List, Optional
from datetime import datetime
from enum import Enum


# Allowed characters for name: letters (incl. accented), spaces, hyphens, apostrophes
NAME_SAFE_PATTERN = re.compile(r"^[\w\s\-'.áéíóúñÁÉÍÓÚÑ]+$", re.UNICODE)


def sanitize_html(value: Optional[str], max_length: int = 500) -> Optional[str]:
    """Strip all HTML/scripts and limit length. Returns None if input is None."""
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)[:max_length] if value else None
    # Strip all tags; allow no HTML
    cleaned = bleach.clean(value.strip(), tags=[], strip=True)
    return cleaned[:max_length] if cleaned else None


class LeadStatusEnum(str, Enum):
    COLD = "cold"
    WARM = "warm"
    HOT = "hot"
    CONVERTED = "converted"
    LOST = "lost"


class ContactabilityLevel(str, Enum):
    CONTACTABLE = "contactable"
    INTERMITTENT = "intermittent"
    DIFFICULT = "difficult"
    CRITICAL = "critical"
    INSUFFICIENT_DATA = "insufficient_data"
    NOT_APPLICABLE = "not_applicable"


class ContactabilityMetrics(BaseModel):
    score: Optional[int] = None
    level: ContactabilityLevel
    reasons: List[str] = Field(default_factory=list)
    suggested_action: str
    attempt_count: int = 0
    unanswered_attempts: int = 0
    no_answer_calls: int = 0
    failed_messages: int = 0
    no_shows: int = 0
    last_attempt_at: Optional[datetime] = None
    last_response_at: Optional[datetime] = None


class LeadBase(BaseModel):
    """Base schema for Lead with input validation"""
    phone: str = Field(..., min_length=1, max_length=20, description="Phone number")
    name: Optional[str] = Field(None, max_length=100, description="Lead name")
    email: Optional[EmailStr] = Field(None, description="Email address")
    tags: List[str] = Field(default_factory=list, max_length=20, description="Tags (max 20)")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")
    
    @field_validator('name')
    @classmethod
    def sanitize_name(cls, v):
        """XSS sanitization: strip all HTML/scripts; allow only safe name characters."""
        if v is None:
            return v
        clean = sanitize_html(v, max_length=100)
        if not clean:
            return None
        # Optionally enforce safe pattern (letters, spaces, hyphens, apostrophes)
        if not NAME_SAFE_PATTERN.match(clean):
            # Fallback: keep only safe chars
            clean = "".join(c for c in clean if c.isalnum() or c in " -'.")
        return clean[:100]


class LeadCreate(LeadBase):
    """Schema for creating a new lead"""

    model_config = {
        "json_schema_extra": {
            "example": {
                "phone": "+56912345678",
                "name": "Juan Pérez",
                "email": "juan.perez@gmail.com",
                "tags": ["interesado", "las-condes"],
                "metadata": {"source": "portal-inmobiliario", "utm_campaign": "verano-2026"},
            }
        }
    }


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[LeadStatusEnum] = None
    tags: Optional[List[str]] = None
    metadata: Optional[dict] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Juan Pérez",
                "status": "warm",
                "tags": ["interesado", "financiado"],
            }
        }
    }


class LeadResponse(LeadBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    phone: Optional[str] = None
    broker_id: Optional[int] = None
    assigned_to: Optional[int] = None
    assigned_agent_name: Optional[str] = None
    status: LeadStatusEnum
    lead_score: float
    pipeline_stage: Optional[str] = None
    last_contacted: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    metadata: dict = Field(default_factory=dict, alias='lead_metadata')
    email: Optional[str] = None  # Override to allow pre-existing invalid emails in DB
    response_metrics: Optional[dict] = Field(
        default=None,
        description="Bot→lead reply turnaround metrics (avg, fast_reply_count, is_fast_responder, ...).",
    )
    contactability: Optional[ContactabilityMetrics] = None
    meta_origin: Optional[dict] = Field(
        default=None,
        description="Resumen de la última atribución Meta, sin sobrescribir el primer origen histórico.",
    )
    
    @model_validator(mode='before')
    @classmethod
    def validate_metadata(cls, data):
        """Ensure metadata is always a dict and surface response_metrics."""
        # First, normalise the input into a dict we can mutate freely.
        if not isinstance(data, dict) and hasattr(data, 'lead_metadata'):
            metadata_value = data.lead_metadata
            if metadata_value is None:
                metadata_value = {}
            elif not isinstance(metadata_value, dict):
                try:
                    if hasattr(metadata_value, '__dict__'):
                        metadata_value = dict(metadata_value)
                    else:
                        metadata_value = {}
                except (TypeError, ValueError):
                    metadata_value = {}
            data = {
                'id': data.id,
                'broker_id': getattr(data, 'broker_id', None),
                'assigned_to': getattr(data, 'assigned_to', None),
                'assigned_agent_name': (
                    getattr(getattr(data, 'assigned_agent', None), 'name', None)
                    if getattr(data, 'assigned_to', None)
                    else None
                ),
                'phone': data.phone,
                'name': getattr(data, 'name', None),
                'email': getattr(data, 'email', None),
                'tags': getattr(data, 'tags', []) or [],
                'status': data.status,
                'lead_score': getattr(data, 'lead_score', 0.0) or 0.0,
                'pipeline_stage': getattr(data, 'pipeline_stage', None),
                'last_contacted': getattr(data, 'last_contacted', None),
                'created_at': data.created_at,
                'updated_at': data.updated_at,
                'metadata': metadata_value,
                'meta_origin': metadata_value.get('meta_origin'),
            }

        if isinstance(data, dict):
            if 'lead_metadata' in data:
                metadata_value = data['lead_metadata']
            elif 'metadata' in data:
                metadata_value = data['metadata']
            else:
                metadata_value = {}

            if metadata_value is None:
                metadata_value = {}
            elif not isinstance(metadata_value, dict):
                try:
                    if hasattr(metadata_value, '__dict__'):
                        metadata_value = dict(metadata_value)
                    else:
                        metadata_value = {}
                except (TypeError, ValueError):
                    metadata_value = {}

            data['metadata'] = metadata_value
            if 'lead_metadata' in data:
                data['lead_metadata'] = metadata_value

            # Promote response_metrics from metadata to top-level field.
            if data.get('response_metrics') is None:
                data['response_metrics'] = metadata_value.get('response_metrics')
            if data.get('meta_origin') is None:
                data['meta_origin'] = metadata_value.get('meta_origin')

        return data
    
class LeadDetailResponse(LeadResponse):
    lead_score_components: dict
    recent_activities: List[dict] = []
