"""Separate multi-tenant domain for Meta advertising and CRM attribution."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, IdMixin, TimestampMixin


META_AD_CAMPAIGN_STATUSES = (
    "draft",
    "pending_review",
    "rejected",
    "approved",
    "publishing",
    "published_paused",
    "active",
    "paused",
    "completed",
    "partial_error",
)


class MetaAdsPolicy(Base, IdMixin, TimestampMixin):
    __tablename__ = "meta_ads_policies"

    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False)
    currency = Column(String(3), nullable=False, default="CLP")
    max_daily_budget = Column(Numeric(16, 2), nullable=False, default=0)
    max_lifetime_budget = Column(Numeric(16, 2), nullable=False, default=0)
    require_budget_increase_confirmation = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("broker_id", name="uq_meta_ads_policy_broker"),
        CheckConstraint("max_daily_budget >= 0", name="ck_meta_ads_policy_daily_positive"),
        CheckConstraint("max_lifetime_budget >= 0", name="ck_meta_ads_policy_lifetime_positive"),
    )


class MetaAdCampaign(Base, IdMixin, TimestampMixin):
    __tablename__ = "meta_ad_campaigns"

    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    ad_account_asset_id = Column(Integer, ForeignKey("meta_assets.id", ondelete="RESTRICT"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    operation_uuid = Column(String(36), nullable=False)
    name = Column(String(255), nullable=False)
    objective = Column(String(50), nullable=False)
    destination_type = Column(String(40), nullable=False)
    special_ad_category = Column(String(30), nullable=False, default="HOUSING")
    status = Column(String(30), nullable=False, default="draft", index=True)
    daily_budget = Column(Numeric(16, 2), nullable=True)
    lifetime_budget = Column(Numeric(16, 2), nullable=True)
    currency = Column(String(3), nullable=False, default="CLP")
    version = Column(Integer, nullable=False, default=1)
    external_id = Column(String(255), nullable=True, index=True)
    remote_status = Column(String(40), nullable=True)
    submission_snapshot = Column(JSONB, nullable=True)
    rejection_comment = Column(Text, nullable=True)
    last_error_code = Column(String(100), nullable=True)
    last_error_detail = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    paused_at = Column(DateTime(timezone=True), nullable=True)

    ad_sets = relationship("MetaAdSet", back_populates="campaign", cascade="all, delete-orphan")
    creatives = relationship("MetaAdCreative", back_populates="campaign", cascade="all, delete-orphan")
    ads = relationship("MetaAd", back_populates="campaign", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("broker_id", "operation_uuid", name="uq_meta_ad_campaign_operation"),
        CheckConstraint(
            "status IN ('draft','pending_review','rejected','approved','publishing','published_paused','active','paused','completed','partial_error')",
            name="ck_meta_ad_campaign_status",
        ),
        CheckConstraint("daily_budget IS NULL OR daily_budget > 0", name="ck_meta_ad_campaign_daily_budget"),
        CheckConstraint("lifetime_budget IS NULL OR lifetime_budget > 0", name="ck_meta_ad_campaign_lifetime_budget"),
        Index("idx_meta_ad_campaign_broker_status", "broker_id", "status"),
    )


class MetaAdSet(Base, IdMixin, TimestampMixin):
    __tablename__ = "meta_ad_sets"

    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("meta_ad_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    optimization_goal = Column(String(60), nullable=False)
    billing_event = Column(String(60), nullable=False, default="IMPRESSIONS")
    targeting = Column(JSONB, nullable=False, default=dict)
    promoted_object = Column(JSONB, nullable=False, default=dict)
    start_at = Column(DateTime(timezone=True), nullable=True)
    end_at = Column(DateTime(timezone=True), nullable=True)
    external_id = Column(String(255), nullable=True, index=True)
    remote_status = Column(String(40), nullable=True)

    campaign = relationship("MetaAdCampaign", back_populates="ad_sets")

    __table_args__ = (
        UniqueConstraint("campaign_id", "external_id", name="uq_meta_ad_set_external"),
        CheckConstraint("end_at IS NULL OR start_at IS NULL OR end_at > start_at", name="ck_meta_ad_set_dates"),
    )


class MetaAdCreative(Base, IdMixin, TimestampMixin):
    __tablename__ = "meta_ad_creatives"

    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("meta_ad_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    page_asset_id = Column(Integer, ForeignKey("meta_assets.id", ondelete="RESTRICT"), nullable=False)
    instagram_asset_id = Column(Integer, ForeignKey("meta_assets.id", ondelete="RESTRICT"), nullable=True)
    name = Column(String(255), nullable=False)
    primary_text = Column(Text, nullable=False)
    headline = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True)
    call_to_action = Column(String(50), nullable=False)
    destination_url = Column(Text, nullable=True)
    media_url = Column(Text, nullable=True)
    media_hash = Column(String(255), nullable=True)
    external_id = Column(String(255), nullable=True, index=True)
    validation_result = Column(JSONB, nullable=False, default=dict)

    campaign = relationship("MetaAdCampaign", back_populates="creatives")

    __table_args__ = (
        UniqueConstraint("campaign_id", "external_id", name="uq_meta_ad_creative_external"),
    )


class MetaAd(Base, IdMixin, TimestampMixin):
    __tablename__ = "meta_ads"

    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("meta_ad_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    ad_set_id = Column(Integer, ForeignKey("meta_ad_sets.id", ondelete="CASCADE"), nullable=False)
    creative_id = Column(Integer, ForeignKey("meta_ad_creatives.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    external_id = Column(String(255), nullable=True, index=True)
    remote_status = Column(String(40), nullable=True)

    campaign = relationship("MetaAdCampaign", back_populates="ads")

    __table_args__ = (
        UniqueConstraint("campaign_id", "external_id", name="uq_meta_ad_external"),
    )


class MetaLeadForm(Base, IdMixin, TimestampMixin):
    __tablename__ = "meta_lead_forms"

    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    page_asset_id = Column(Integer, ForeignKey("meta_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    external_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(30), nullable=False, default="active", index=True)
    questions = Column(JSONB, nullable=False, default=list)
    field_mapping = Column(JSONB, nullable=False, default=dict)
    last_cursor = Column(String(500), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("broker_id", "external_id", name="uq_meta_lead_form_external"),
        Index("idx_meta_lead_form_broker_status", "broker_id", "status"),
    )


class MetaLeadAttribution(Base, IdMixin, TimestampMixin):
    __tablename__ = "meta_lead_attributions"

    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    identity_id = Column(Integer, ForeignKey("channel_identities.id", ondelete="SET NULL"), nullable=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    touch_type = Column(String(20), nullable=False)
    source = Column(String(40), nullable=False, default="meta")
    leadgen_id = Column(String(255), nullable=True)
    form_external_id = Column(String(255), nullable=True)
    account_external_id = Column(String(255), nullable=True)
    campaign_external_id = Column(String(255), nullable=True, index=True)
    ad_set_external_id = Column(String(255), nullable=True)
    ad_external_id = Column(String(255), nullable=True)
    creative_external_id = Column(String(255), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    utm = Column(JSONB, nullable=False, default=dict)
    attribution_metadata = Column(JSONB, nullable=False, default=dict)
    captured_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("broker_id", "lead_id", "touch_type", name="uq_meta_attribution_touch"),
        UniqueConstraint("broker_id", "form_external_id", "leadgen_id", "touch_type", name="uq_meta_attribution_leadgen"),
        CheckConstraint("touch_type IN ('first','last')", name="ck_meta_attribution_touch_type"),
    )


class MetaAdInsightDaily(Base, IdMixin, TimestampMixin):
    __tablename__ = "meta_ad_insights_daily"

    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    insight_date = Column(Date, nullable=False, index=True)
    account_external_id = Column(String(255), nullable=False)
    campaign_external_id = Column(String(255), nullable=False, default="")
    ad_set_external_id = Column(String(255), nullable=False, default="")
    ad_external_id = Column(String(255), nullable=False, default="")
    spend = Column(Numeric(18, 4), nullable=False, default=0)
    impressions = Column(Integer, nullable=False, default=0)
    reach = Column(Integer, nullable=False, default=0)
    frequency = Column(Numeric(12, 4), nullable=False, default=0)
    clicks = Column(Integer, nullable=False, default=0)
    conversations = Column(Integer, nullable=False, default=0)
    leads = Column(Integer, nullable=False, default=0)
    raw_actions = Column(JSONB, nullable=False, default=list)

    __table_args__ = (
        UniqueConstraint("broker_id", "insight_date", "account_external_id", "campaign_external_id", "ad_set_external_id", "ad_external_id", name="uq_meta_ad_insight_grain"),
        Index("idx_meta_insight_broker_date", "broker_id", "insight_date"),
    )


class MetaSyncRun(Base, IdMixin, TimestampMixin):
    __tablename__ = "meta_sync_runs"

    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    sync_type = Column(String(40), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="running", index=True)
    checkpoint = Column(JSONB, nullable=False, default=dict)
    result = Column(JSONB, nullable=False, default=dict)
    error_code = Column(String(100), nullable=True)
    error_detail = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_meta_sync_run_broker_type_started", "broker_id", "sync_type", "started_at"),
    )


class MetaConversionEvent(Base, IdMixin, TimestampMixin):
    __tablename__ = "meta_conversion_events"

    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_asset_id = Column(Integer, ForeignKey("meta_assets.id", ondelete="RESTRICT"), nullable=False)
    event_id = Column(String(255), nullable=False)
    event_name = Column(String(100), nullable=False)
    status = Column(String(30), nullable=False, default="pending", index=True)
    consent_basis = Column(String(100), nullable=False)
    provider_event_id = Column(String(255), nullable=True)
    last_error_code = Column(String(100), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("broker_id", "event_id", name="uq_meta_conversion_event_id"),
    )
