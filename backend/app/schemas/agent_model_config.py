"""
Schemas for AgentModelConfig — per-broker, per-agent LLM configuration.
All write endpoints are SUPERADMIN only.
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, field_validator, model_validator

from app.models.agent_model_config import VALID_AGENT_TYPES, VALID_PROVIDERS


class AgentModelConfigCreate(BaseModel):
    agent_type: str
    llm_provider: str
    llm_model: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    is_active: bool = True

    @field_validator("agent_type")
    @classmethod
    def validate_agent_type(cls, v: str) -> str:
        if v not in VALID_AGENT_TYPES:
            raise ValueError(f"agent_type must be one of: {sorted(VALID_AGENT_TYPES)}")
        return v

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        if v not in VALID_PROVIDERS:
            raise ValueError(f"llm_provider must be one of: {sorted(VALID_PROVIDERS)}")
        return v

    @field_validator("llm_model")
    @classmethod
    def validate_llm_model(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("llm_model cannot be empty")
        if len(v) > 80:
            raise ValueError("llm_model must be 80 characters or fewer")
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 2.0):
            raise ValueError("temperature must be between 0.0 and 2.0")
        return v

    @field_validator("max_tokens")
    @classmethod
    def validate_max_tokens(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (100 <= v <= 16384):
            raise ValueError("max_tokens must be between 100 and 16384")
        return v


class AgentModelConfigUpdate(BaseModel):
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_PROVIDERS:
            raise ValueError(f"llm_provider must be one of: {sorted(VALID_PROVIDERS)}")
        return v

    @field_validator("llm_model")
    @classmethod
    def validate_llm_model(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("llm_model cannot be empty")
            if len(v) > 80:
                raise ValueError("llm_model must be 80 characters or fewer")
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 2.0):
            raise ValueError("temperature must be between 0.0 and 2.0")
        return v

    @field_validator("max_tokens")
    @classmethod
    def validate_max_tokens(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (100 <= v <= 16384):
            raise ValueError("max_tokens must be between 100 and 16384")
        return v


class AgentModelConfigResponse(BaseModel):
    id: int
    broker_id: int
    agent_type: str
    llm_provider: str
    llm_model: str
    temperature: Optional[float]
    max_tokens: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentModelConfigList(BaseModel):
    configs: List[AgentModelConfigResponse]
    total: int


class AvailableProviderInfo(BaseModel):
    provider: str
    is_configured: bool
    default_model: str


class AvailableProvidersResponse(BaseModel):
    providers: List[AvailableProviderInfo]
