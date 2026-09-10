"""Request and response contracts for the isolated Meta Ads domain."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator


CampaignStatus = Literal[
    "draft", "pending_review", "rejected", "approved", "publishing",
    "published_paused", "active", "paused", "completed", "partial_error",
]


class MetaAdsPolicyResponse(BaseModel):
    currency: str
    max_daily_budget: Decimal
    max_lifetime_budget: Decimal
    require_budget_increase_confirmation: bool
    version: int

    model_config = {"from_attributes": True}


class MetaAdsPolicyUpdate(BaseModel):
    currency: Literal["CLP", "USD"] = "CLP"
    max_daily_budget: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    max_lifetime_budget: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    require_budget_increase_confirmation: bool = True
    expected_version: int = Field(ge=1)


class MetaAdSetInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    optimization_goal: str = Field(min_length=1, max_length=60)
    billing_event: str = Field(default="IMPRESSIONS", min_length=1, max_length=60)
    targeting: dict[str, Any] = Field(default_factory=dict)
    promoted_object: dict[str, Any] = Field(default_factory=dict)
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

    @model_validator(mode="after")
    def valid_dates(self):
        if self.start_at and self.start_at.tzinfo is None:
            raise ValueError("start_at debe incluir zona horaria")
        if self.end_at and self.end_at.tzinfo is None:
            raise ValueError("end_at debe incluir zona horaria")
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValueError("end_at debe ser posterior a start_at")
        return self


class MetaAdCreativeInput(BaseModel):
    page_asset_id: int
    instagram_asset_id: Optional[int] = None
    name: str = Field(min_length=1, max_length=255)
    primary_text: str = Field(min_length=1, max_length=2200)
    headline: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=500)
    call_to_action: str = Field(min_length=1, max_length=50)
    destination_url: Optional[HttpUrl] = None
    media_url: Optional[HttpUrl] = None
    media_hash: Optional[str] = Field(default=None, max_length=255)


class MetaAdCampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    ad_account_asset_id: int
    project_id: Optional[int] = None
    objective: Literal["OUTCOME_LEADS", "OUTCOME_TRAFFIC", "OUTCOME_ENGAGEMENT"]
    destination_type: Literal["lead_form", "whatsapp", "instagram", "website"]
    special_ad_category: Literal["HOUSING"] = "HOUSING"
    daily_budget: Optional[Decimal] = Field(default=None, gt=0, max_digits=16, decimal_places=2)
    lifetime_budget: Optional[Decimal] = Field(default=None, gt=0, max_digits=16, decimal_places=2)
    currency: Literal["CLP", "USD"] = "CLP"
    ad_set: MetaAdSetInput
    creative: MetaAdCreativeInput

    @model_validator(mode="after")
    def exactly_one_budget(self):
        if (self.daily_budget is None) == (self.lifetime_budget is None):
            raise ValueError("Define presupuesto diario o total, no ambos")
        if self.destination_type == "website" and self.creative.destination_url is None:
            raise ValueError("El destino web requiere una URL HTTPS")
        return self


class MetaAdCampaignUpdate(MetaAdCampaignCreate):
    expected_version: int = Field(ge=1)


class MetaAdSetResponse(MetaAdSetInput):
    id: int
    external_id: Optional[str]
    remote_status: Optional[str]
    model_config = {"from_attributes": True}


class MetaAdCreativeResponse(BaseModel):
    id: int
    page_asset_id: int
    instagram_asset_id: Optional[int]
    name: str
    primary_text: str
    headline: str
    description: Optional[str]
    call_to_action: str
    destination_url: Optional[str]
    media_url: Optional[str]
    media_hash: Optional[str]
    external_id: Optional[str]
    validation_result: dict[str, Any]
    model_config = {"from_attributes": True}


class MetaAdResponse(BaseModel):
    id: int
    name: str
    external_id: Optional[str]
    remote_status: Optional[str]
    model_config = {"from_attributes": True}


class MetaAdCampaignResponse(BaseModel):
    id: int
    broker_id: int
    ad_account_asset_id: int
    project_id: Optional[int]
    created_by_user_id: Optional[int]
    approved_by_user_id: Optional[int]
    operation_uuid: str
    name: str
    objective: str
    destination_type: str
    special_ad_category: str
    status: CampaignStatus
    daily_budget: Optional[Decimal]
    lifetime_budget: Optional[Decimal]
    currency: str
    version: int
    external_id: Optional[str]
    remote_status: Optional[str]
    submission_snapshot: Optional[dict[str, Any]]
    rejection_comment: Optional[str]
    last_error_code: Optional[str]
    last_error_detail: Optional[str]
    submitted_at: Optional[datetime]
    approved_at: Optional[datetime]
    published_at: Optional[datetime]
    activated_at: Optional[datetime]
    paused_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    ad_sets: list[MetaAdSetResponse] = Field(default_factory=list)
    creatives: list[MetaAdCreativeResponse] = Field(default_factory=list)
    ads: list[MetaAdResponse] = Field(default_factory=list)
    model_config = {"from_attributes": True}


class MetaCampaignTransition(BaseModel):
    expected_version: int = Field(ge=1)
    comment: Optional[str] = Field(default=None, max_length=2000)


class MetaCampaignActivation(BaseModel):
    expected_version: int = Field(ge=1)
    confirm_spend: bool


class MetaLeadFormUpdate(BaseModel):
    project_id: Optional[int] = None
    field_mapping: dict[str, str] = Field(default_factory=dict)


class MetaLeadFormPreviewRequest(MetaLeadFormUpdate):
    sample_values: dict[str, str] = Field(default_factory=dict)


class MetaLeadFormPreviewResponse(BaseModel):
    lead_payload: dict[str, Any]
    source_values: dict[str, str]
    warnings: list[str] = Field(default_factory=list)


class MetaLeadFormResponse(BaseModel):
    id: int
    page_asset_id: int
    project_id: Optional[int]
    external_id: str
    name: str
    status: str
    questions: list[dict[str, Any]]
    field_mapping: dict[str, str]
    last_synced_at: Optional[datetime]
    model_config = {"from_attributes": True}


class MetaAdsKPI(BaseModel):
    spend: Decimal
    impressions: int
    reach: int
    clicks: int
    conversations: int
    meta_leads: int
    crm_leads: int
    advised: int
    meetings: int
    reservations: int
    sales: int
    sales_uf: Decimal
    sales_clp: Decimal
    cost_per_conversation: Optional[Decimal]
    cost_per_lead: Optional[Decimal]
    cost_per_advised: Optional[Decimal]
    cost_per_meeting: Optional[Decimal]
    cost_per_reservation: Optional[Decimal]
    cost_per_sale: Optional[Decimal]


class MetaAdsTrendPoint(BaseModel):
    date: date
    spend: Decimal
    leads: int
    conversations: int


class MetaAdsAnalyticsResponse(BaseModel):
    kpis: MetaAdsKPI
    trend: list[MetaAdsTrendPoint]
    campaigns: list[dict[str, Any]]
    freshness_at: Optional[datetime]
    partial_sync: bool
