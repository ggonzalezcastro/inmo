"""Schemas for the asset-aware unified Meta inbox."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator


class MetaInboxAsset(BaseModel):
    id: int
    type: str
    channel: Optional[str]
    name: Optional[str]
    owner_type: str
    owner_user_id: Optional[int]
    assigned_user_id: Optional[int]
    status: str
    approval_status: str
    ai_mode: str


class MetaInboxLead(BaseModel):
    id: int
    name: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    pipeline_stage: Optional[str]
    status: Optional[str]
    assigned_to: Optional[int]
    assigned_agent_name: Optional[str]


class MetaInboxConversationItem(BaseModel):
    id: int
    channel: str
    status: str
    last_message: Optional[str]
    last_message_at: Optional[datetime]
    last_message_direction: Optional[str]
    unread_count: int
    messaging_window_expires_at: Optional[datetime]
    assignment_conflict: bool
    human_mode: bool
    message_count: int
    asset: Optional[MetaInboxAsset]
    lead: MetaInboxLead


class MetaInboxConversationPage(BaseModel):
    items: list[MetaInboxConversationItem]
    next_cursor: Optional[str]
    has_more: bool


class MetaInboxMessage(BaseModel):
    id: int
    provider: str
    message_text: str
    direction: str
    status: str
    message_type: str
    generation_mode: str
    channel_message_id: Optional[str]
    reply_to_external_id: Optional[str]
    sent_by_user_id: Optional[int]
    attachments: Optional[list[dict[str, Any]]]
    remote_error_code: Optional[str]
    remote_error_subcode: Optional[str]
    created_at: datetime


class MetaInboxMessagePage(BaseModel):
    items: list[MetaInboxMessage]
    next_before_id: Optional[int]
    has_more: bool


class MetaInboxConversationDetail(BaseModel):
    conversation: MetaInboxConversationItem
    messages: MetaInboxMessagePage


class MetaInboxSendRequest(BaseModel):
    text: str = Field(default="", max_length=4096)
    media_url: Optional[HttpUrl] = None
    media_type: Optional[Literal["image", "video", "audio", "document"]] = None
    reply_to_external_id: Optional[str] = Field(default=None, max_length=255)
    template_name: Optional[str] = Field(default=None, min_length=1, max_length=512)
    template_language: str = Field(default="es_CL", min_length=2, max_length=20)
    template_components: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    generation_mode: Literal["manual", "ai_draft"] = "manual"

    @model_validator(mode="after")
    def validate_content(self):
        if bool(self.media_url) != bool(self.media_type):
            raise ValueError("media_url y media_type deben enviarse juntos")
        if self.media_url and self.template_name:
            raise ValueError("Un adjunto no puede enviarse junto a una plantilla")
        if self.media_url and self.media_url.scheme != "https":
            raise ValueError("El adjunto debe usar HTTPS")
        if not self.text.strip() and not self.template_name and not self.media_url:
            raise ValueError("El mensaje no puede estar vacío")
        return self


class MetaInboxSendResponse(BaseModel):
    ok: bool
    message: MetaInboxMessage


class MetaAssignmentConflictResponse(BaseModel):
    id: int
    broker_id: int
    lead_id: int
    asset_id: int
    current_assignee_id: Optional[int]
    asset_owner_id: Optional[int]
    status: str
    resolution: Optional[str]
    resolved_by_user_id: Optional[int]
    resolved_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class MetaAssignmentConflictResolve(BaseModel):
    resolution: Literal["keep_current", "transfer_to_asset_owner", "assign_user", "dismiss"]
    assigned_user_id: Optional[int] = None


class MetaAISummaryResponse(BaseModel):
    summary: str
    generated_by_ai: bool = True
    cached: bool
    based_on_message_id: Optional[int]


class MetaAIDraftRequest(BaseModel):
    instruction: Optional[str] = Field(default=None, max_length=1000)


class MetaAIDraftResponse(BaseModel):
    draft: str
    generated_by_ai: bool = True
    generation_mode: Literal["ai_draft"] = "ai_draft"
    based_on_message_id: Optional[int]


class MetaAITaskSuggestion(BaseModel):
    suggested: bool
    title: Optional[str] = None
    due_at: Optional[datetime] = None
    reminder_minutes_before: Optional[int] = 60
    evidence_message_id: Optional[int] = None
    evidence: Optional[str] = None
    needs_review: bool = False
    reason: Optional[str] = None
    generated_by_ai: bool = True


class MetaAITaskApprove(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    due_at: datetime
    reminder_minutes_before: Optional[int] = 60
    assigned_to: Optional[int] = None
    evidence_message_id: Optional[int] = None
