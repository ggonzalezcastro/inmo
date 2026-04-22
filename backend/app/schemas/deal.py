"""Pydantic schemas for Deal and DealDocument API."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Deal schemas
# ---------------------------------------------------------------------------

class DealCreate(BaseModel):
    lead_id: int
    property_id: int
    delivery_type: str = "desconocida"

    @field_validator("delivery_type")
    @classmethod
    def validate_delivery_type(cls, v: str) -> str:
        from app.models.deal import DELIVERY_TYPES
        if v not in DELIVERY_TYPES:
            raise ValueError(f"delivery_type must be one of {DELIVERY_TYPES}")
        return v


class DealRead(BaseModel):
    id: int
    broker_id: int
    lead_id: int
    property_id: int
    created_by_user_id: Optional[int] = None
    stage: str
    # Denormalized display fields (joined from Lead/Property/Project)
    lead_name: Optional[str] = None
    property_label: Optional[str] = None
    delivery_type: str
    bank_review_status: Optional[str] = None
    jefatura_review_required: bool
    jefatura_review_status: Optional[str] = None
    jefatura_review_notes: Optional[str] = None
    reserva_at: Optional[datetime] = None
    docs_completos_at: Optional[datetime] = None
    bank_decision_at: Optional[datetime] = None
    promesa_signed_at: Optional[datetime] = None
    escritura_signed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    cancellation_notes: Optional[str] = None
    escritura_planned_date: Optional[date] = None
    deal_metadata: dict = {}
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DealStageTransitionRequest(BaseModel):
    to_stage: str
    notes: Optional[str] = None

    @field_validator("to_stage")
    @classmethod
    def validate_stage(cls, v: str) -> str:
        from app.models.deal import DEAL_STAGES
        if v not in DEAL_STAGES:
            raise ValueError(f"to_stage must be one of {DEAL_STAGES}")
        return v


class DealCancelRequest(BaseModel):
    reason: str
    notes: Optional[str] = None


class BankReviewRequest(BaseModel):
    decision: str  # "aprobado" | "rechazado" | "en_revision"
    notes: Optional[str] = None


class JefaturaReviewRequest(BaseModel):
    decision: str  # "aprobado" | "rechazado"
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# DealDocument schemas
# ---------------------------------------------------------------------------

class DealDocumentRead(BaseModel):
    id: int
    deal_id: int
    slot: str
    slot_index: int
    co_titular_index: int
    status: str
    original_filename: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    sha256: Optional[str] = None
    uploaded_by_user_id: Optional[int] = None
    uploaded_by_ai: bool
    uploaded_at: Optional[datetime] = None
    reviewed_by_user_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: datetime
    # download_url is computed and injected by the router (not stored in model)
    download_url: Optional[str] = None

    model_config = {"from_attributes": True}


class DealDocumentApproveRequest(BaseModel):
    notes: Optional[str] = None


class DealDocumentRejectRequest(BaseModel):
    notes: str  # required for rejection


# ---------------------------------------------------------------------------
# Slot meta schemas
# ---------------------------------------------------------------------------

class SlotRequirementRead(BaseModel):
    slot_key: str
    label: str
    required_for_stage: str
    max_count: int
    supports_co_titular: bool
    optional: bool
    required: bool  # computed: required given current deal's delivery_type
    mime_whitelist: list[str]
    uploaded_count: int = 0   # how many docs exist for this slot
    approved_count: int = 0   # how many are approved


# ---------------------------------------------------------------------------
# Deal detail (with documents + required slots)
# ---------------------------------------------------------------------------

class DealDetail(DealRead):
    documents: list[DealDocumentRead] = []
    required_slots: list[SlotRequirementRead] = []
