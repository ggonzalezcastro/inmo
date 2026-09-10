"""add Meta Ads, Lead Ads, attribution, and insights domain

Revision ID: w8h9i0j1k2l3
Revises: v7g8h9i0j1k2
Create Date: 2026-09-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "w8h9i0j1k2l3"
down_revision = "v7g8h9i0j1k2"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "meta_ads_policies",
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="CLP", nullable=False),
        sa.Column("max_daily_budget", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("max_lifetime_budget", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("require_budget_increase_confirmation", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("max_daily_budget >= 0", name="ck_meta_ads_policy_daily_positive"),
        sa.CheckConstraint("max_lifetime_budget >= 0", name="ck_meta_ads_policy_lifetime_positive"),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("broker_id", name="uq_meta_ads_policy_broker"),
    )

    op.create_table(
        "meta_ad_campaigns",
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("ad_account_asset_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("operation_uuid", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("objective", sa.String(50), nullable=False),
        sa.Column("destination_type", sa.String(40), nullable=False),
        sa.Column("special_ad_category", sa.String(30), server_default="HOUSING", nullable=False),
        sa.Column("status", sa.String(30), server_default="draft", nullable=False),
        sa.Column("daily_budget", sa.Numeric(16, 2), nullable=True),
        sa.Column("lifetime_budget", sa.Numeric(16, 2), nullable=True),
        sa.Column("currency", sa.String(3), server_default="CLP", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("remote_status", sa.String(40), nullable=True),
        sa.Column("submission_snapshot", JSONB, nullable=True),
        sa.Column("rejection_comment", sa.Text(), nullable=True),
        sa.Column("last_error_code", sa.String(100), nullable=True),
        sa.Column("last_error_detail", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('draft','pending_review','rejected','approved','publishing','published_paused','active','paused','completed','partial_error')", name="ck_meta_ad_campaign_status"),
        sa.CheckConstraint("daily_budget IS NULL OR daily_budget > 0", name="ck_meta_ad_campaign_daily_budget"),
        sa.CheckConstraint("lifetime_budget IS NULL OR lifetime_budget > 0", name="ck_meta_ad_campaign_lifetime_budget"),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ad_account_asset_id"], ["meta_assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("broker_id", "operation_uuid", name="uq_meta_ad_campaign_operation"),
    )
    op.create_index("idx_meta_ad_campaign_broker_status", "meta_ad_campaigns", ["broker_id", "status"])
    op.create_index("ix_meta_ad_campaigns_ad_account_asset_id", "meta_ad_campaigns", ["ad_account_asset_id"])
    op.create_index("ix_meta_ad_campaigns_project_id", "meta_ad_campaigns", ["project_id"])
    op.create_index("ix_meta_ad_campaigns_created_by_user_id", "meta_ad_campaigns", ["created_by_user_id"])
    op.create_index("ix_meta_ad_campaigns_external_id", "meta_ad_campaigns", ["external_id"])

    op.create_table(
        "meta_ad_sets",
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("optimization_goal", sa.String(60), nullable=False),
        sa.Column("billing_event", sa.String(60), server_default="IMPRESSIONS", nullable=False),
        sa.Column("targeting", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("promoted_object", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("remote_status", sa.String(40), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("end_at IS NULL OR start_at IS NULL OR end_at > start_at", name="ck_meta_ad_set_dates"),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["meta_ad_campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "external_id", name="uq_meta_ad_set_external"),
    )
    op.create_index("ix_meta_ad_sets_campaign_id", "meta_ad_sets", ["campaign_id"])

    op.create_table(
        "meta_ad_creatives",
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("page_asset_id", sa.Integer(), nullable=False),
        sa.Column("instagram_asset_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("primary_text", sa.Text(), nullable=False),
        sa.Column("headline", sa.String(255), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("call_to_action", sa.String(50), nullable=False),
        sa.Column("destination_url", sa.Text(), nullable=True),
        sa.Column("media_url", sa.Text(), nullable=True),
        sa.Column("media_hash", sa.String(255), nullable=True),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("validation_result", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["meta_ad_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_asset_id"], ["meta_assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["instagram_asset_id"], ["meta_assets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "external_id", name="uq_meta_ad_creative_external"),
    )
    op.create_index("ix_meta_ad_creatives_campaign_id", "meta_ad_creatives", ["campaign_id"])

    op.create_table(
        "meta_ads",
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("ad_set_id", sa.Integer(), nullable=False),
        sa.Column("creative_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("remote_status", sa.String(40), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["meta_ad_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ad_set_id"], ["meta_ad_sets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["creative_id"], ["meta_ad_creatives.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "external_id", name="uq_meta_ad_external"),
    )
    op.create_index("ix_meta_ads_campaign_id", "meta_ads", ["campaign_id"])

    op.create_table(
        "meta_lead_forms",
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("page_asset_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(30), server_default="active", nullable=False),
        sa.Column("questions", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("field_mapping", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("last_cursor", sa.String(500), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_asset_id"], ["meta_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("broker_id", "external_id", name="uq_meta_lead_form_external"),
    )
    op.create_index("idx_meta_lead_form_broker_status", "meta_lead_forms", ["broker_id", "status"])

    op.create_table(
        "meta_lead_attributions",
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("identity_id", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("touch_type", sa.String(20), nullable=False),
        sa.Column("source", sa.String(40), server_default="meta", nullable=False),
        sa.Column("leadgen_id", sa.String(255), nullable=True),
        sa.Column("form_external_id", sa.String(255), nullable=True),
        sa.Column("account_external_id", sa.String(255), nullable=True),
        sa.Column("campaign_external_id", sa.String(255), nullable=True),
        sa.Column("ad_set_external_id", sa.String(255), nullable=True),
        sa.Column("ad_external_id", sa.String(255), nullable=True),
        sa.Column("creative_external_id", sa.String(255), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("utm", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("attribution_metadata", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("touch_type IN ('first','last')", name="ck_meta_attribution_touch_type"),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["identity_id"], ["channel_identities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("broker_id", "lead_id", "touch_type", name="uq_meta_attribution_touch"),
        sa.UniqueConstraint("broker_id", "form_external_id", "leadgen_id", "touch_type", name="uq_meta_attribution_leadgen"),
    )
    op.create_index("ix_meta_lead_attributions_lead_id", "meta_lead_attributions", ["lead_id"])
    op.create_index("ix_meta_lead_attributions_campaign_external_id", "meta_lead_attributions", ["campaign_external_id"])

    op.create_table(
        "meta_ad_insights_daily",
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("insight_date", sa.Date(), nullable=False),
        sa.Column("account_external_id", sa.String(255), nullable=False),
        sa.Column("campaign_external_id", sa.String(255), server_default="", nullable=False),
        sa.Column("ad_set_external_id", sa.String(255), server_default="", nullable=False),
        sa.Column("ad_external_id", sa.String(255), server_default="", nullable=False),
        sa.Column("spend", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("impressions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reach", sa.Integer(), server_default="0", nullable=False),
        sa.Column("frequency", sa.Numeric(12, 4), server_default="0", nullable=False),
        sa.Column("clicks", sa.Integer(), server_default="0", nullable=False),
        sa.Column("conversations", sa.Integer(), server_default="0", nullable=False),
        sa.Column("leads", sa.Integer(), server_default="0", nullable=False),
        sa.Column("raw_actions", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("broker_id", "insight_date", "account_external_id", "campaign_external_id", "ad_set_external_id", "ad_external_id", name="uq_meta_ad_insight_grain"),
    )
    op.create_index("idx_meta_insight_broker_date", "meta_ad_insights_daily", ["broker_id", "insight_date"])

    op.create_table(
        "meta_sync_runs",
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("sync_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), server_default="running", nullable=False),
        sa.Column("checkpoint", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("result", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_meta_sync_run_broker_type_started", "meta_sync_runs", ["broker_id", "sync_type", "started_at"])

    op.create_table(
        "meta_conversion_events",
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("dataset_asset_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(255), nullable=False),
        sa.Column("event_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), server_default="pending", nullable=False),
        sa.Column("consent_basis", sa.String(100), nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=True),
        sa.Column("last_error_code", sa.String(100), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dataset_asset_id"], ["meta_assets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("broker_id", "event_id", name="uq_meta_conversion_event_id"),
    )


def downgrade() -> None:
    op.drop_table("meta_conversion_events")
    op.drop_table("meta_sync_runs")
    op.drop_table("meta_ad_insights_daily")
    op.drop_table("meta_lead_attributions")
    op.drop_table("meta_lead_forms")
    op.drop_table("meta_ads")
    op.drop_table("meta_ad_creatives")
    op.drop_table("meta_ad_sets")
    op.drop_table("meta_ad_campaigns")
    op.drop_table("meta_ads_policies")
