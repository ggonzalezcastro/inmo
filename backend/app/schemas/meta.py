"""Public schemas for Meta connections and assets. Secrets are intentionally absent."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


MetaChannel = Literal["whatsapp", "instagram", "messenger", "business"]


class MetaAuthorizeResponse(BaseModel):
    authorization_url: str
    state: str
    channel: MetaChannel
    expires_in: int = 600


class MetaConnectionResponse(BaseModel):
    id: int
    broker_id: int
    owner_type: str
    owner_user_id: Optional[int]
    connected_by_user_id: Optional[int]
    auth_mode: str
    external_principal_id: str
    display_name: Optional[str]
    scopes: List[str]
    status: str
    expires_at: Optional[datetime]
    last_validated_at: Optional[datetime]
    revoked_at: Optional[datetime]
    disconnected_at: Optional[datetime]
    last_error_code: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MetaAssetResponse(BaseModel):
    id: int
    broker_id: int
    connection_id: int
    asset_type: str
    channel: Optional[str]
    external_id: str
    parent_external_id: Optional[str]
    display_name: Optional[str]
    owner_type: str
    owner_user_id: Optional[int]
    assigned_user_id: Optional[int]
    capabilities: List[str]
    approval_status: str
    status: str
    is_default: bool
    ai_mode: str
    last_synced_at: Optional[datetime]
    last_error_code: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MetaAssetUpdate(BaseModel):
    assigned_user_id: Optional[int] = None
    approval_status: Optional[Literal["pending_approval", "approved", "rejected"]] = None
    status: Optional[Literal["active", "paused", "disabled", "error"]] = None
    is_default: Optional[bool] = None
    ai_mode: Optional[Literal["suggestion", "supervised_auto", "human"]] = None
    capabilities: Optional[List[str]] = Field(default=None, max_length=20)


class MetaConnectionComplete(BaseModel):
    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=1, max_length=8192)
    waba_id: Optional[str] = Field(default=None, max_length=255)
    phone_number_id: Optional[str] = Field(default=None, max_length=255)
    display_name: Optional[str] = Field(default=None, max_length=255)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MetaFeatureUpdate(BaseModel):
    enabled: Optional[bool] = None
    whatsapp: Optional[bool] = None
    instagram: Optional[bool] = None
    messenger: Optional[bool] = None
    ads: Optional[bool] = None
    lead_ads: Optional[bool] = None
    conversions_api: Optional[bool] = None


class MetaMessageTemplateResponse(BaseModel):
    id: int
    waba_external_id: str
    external_id: str
    name: str
    language: str
    category: Optional[str]
    status: str
    components: List[Dict[str, Any]]
    last_synced_at: Optional[datetime]

    model_config = {"from_attributes": True}
