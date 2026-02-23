import re
import bleach
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Optional, List, Any
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
    id: int
    status: LeadStatusEnum
    lead_score: float
    last_contacted: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    metadata: dict = Field(default_factory=dict, alias='lead_metadata')
    
    @model_validator(mode='before')
    @classmethod
    def validate_metadata(cls, data):
        """Ensure metadata is always a dict"""
        if isinstance(data, dict):
            # Handle dict input
            if 'lead_metadata' in data:
                metadata_value = data['lead_metadata']
            elif 'metadata' in data:
                metadata_value = data['metadata']
            else:
                metadata_value = {}
            
            # Ensure it's a dict
            if metadata_value is None:
                metadata_value = {}
            elif not isinstance(metadata_value, dict):
                # Try to convert to dict
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
        elif hasattr(data, 'lead_metadata'):
            # Handle SQLAlchemy model object
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
            
            # Convert object to dict for processing
            if not isinstance(data, dict):
                data = {
                    'id': data.id,
                    'phone': data.phone,
                    'name': getattr(data, 'name', None),
                    'email': getattr(data, 'email', None),
                    'tags': getattr(data, 'tags', []) or [],
                    'status': data.status,
                    'lead_score': getattr(data, 'lead_score', 0.0) or 0.0,
                    'last_contacted': getattr(data, 'last_contacted', None),
                    'created_at': data.created_at,
                    'updated_at': data.updated_at,
                    'metadata': metadata_value
                }
            else:
                data['metadata'] = metadata_value
        
        return data
    
    class Config:
        from_attributes = True
        populate_by_name = True  # Allow both 'metadata' and 'lead_metadata'


class LeadDetailResponse(LeadResponse):
    lead_score_components: dict
    recent_activities: List[dict] = []

