"""Phase 1 schema: agent_events, properties, conversations, escalation_briefs,
observability_alerts; lead columns human_released_at + human_release_note;
conversation_id on chat_messages; prompt_version metric columns.

Revision ID: p1a2b3c4d5e6
Revises: x1y2z3a4b5c6
Create Date: 2026-04-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "p1a2b3c4d5e6"
down_revision: Union[str, Sequence[str]] = "x1y2z3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. conversations ──────────────────────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("close_reason", sa.String(50), nullable=True),
        sa.Column("current_agent", sa.String(30), nullable=True),
        sa.Column("conversation_state", sa.String(30), nullable=True),
        sa.Column("human_mode", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("human_assigned_to", sa.Integer(), nullable=True),
        sa.Column("human_taken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("human_released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("context_summary", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["human_assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_conv_lead", "conversations", ["lead_id", "started_at"])
    op.create_index("idx_conv_broker_status", "conversations", ["broker_id", "status"])
    op.create_index(
        "idx_conv_human", "conversations", ["human_mode"],
        postgresql_where=sa.text("human_mode = true"),
    )
    op.create_index("idx_conv_broker_channel", "conversations", ["broker_id", "channel"])
    op.create_index("idx_conversations_lead_id", "conversations", ["lead_id"])
    op.create_index("idx_conversations_broker_id", "conversations", ["broker_id"])

    # ── 2. agent_events ───────────────────────────────────────────────────────
    op.create_table(
        "agent_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=True),
        sa.Column("broker_id", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("agent_type", sa.String(30), nullable=True),
        sa.Column("from_agent", sa.String(30), nullable=True),
        sa.Column("to_agent", sa.String(30), nullable=True),
        sa.Column("handoff_reason", sa.Text(), nullable=True),
        sa.Column("llm_provider", sa.String(20), nullable=True),
        sa.Column("llm_model", sa.String(50), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("llm_latency_ms", sa.Integer(), nullable=True),
        sa.Column("llm_cost_usd", sa.Float(), nullable=True),
        sa.Column("system_prompt_hash", sa.String(64), nullable=True),
        sa.Column("raw_response_snippet", sa.Text(), nullable=True),
        sa.Column("tool_name", sa.String(50), nullable=True),
        sa.Column("tool_input", postgresql.JSONB(), nullable=True),
        sa.Column("tool_output", postgresql.JSONB(), nullable=True),
        sa.Column("tool_latency_ms", sa.Integer(), nullable=True),
        sa.Column("tool_success", sa.Boolean(), nullable=True),
        sa.Column("pipeline_stage_before", sa.String(50), nullable=True),
        sa.Column("pipeline_stage_after", sa.String(50), nullable=True),
        sa.Column("lead_score_before", sa.Float(), nullable=True),
        sa.Column("lead_score_after", sa.Float(), nullable=True),
        sa.Column("conversation_state_before", sa.String(30), nullable=True),
        sa.Column("conversation_state_after", sa.String(30), nullable=True),
        sa.Column("extracted_fields", postgresql.JSONB(), nullable=True),
        sa.Column("score_delta", sa.Float(), nullable=True),
        sa.Column("search_strategy", sa.String(20), nullable=True),
        sa.Column("search_results_count", sa.Integer(), nullable=True),
        sa.Column("error_type", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_stack", sa.Text(), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_agent_events_lead", "agent_events", ["lead_id", "created_at"])
    op.create_index("idx_agent_events_broker", "agent_events", ["broker_id", "created_at"])
    op.create_index("idx_agent_events_type", "agent_events", ["event_type", "created_at"])
    op.create_index("idx_agent_events_agent", "agent_events", ["agent_type", "created_at"])
    op.create_index("idx_agent_events_conversation", "agent_events", ["conversation_id", "created_at"])

    # ── 3. properties ─────────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "properties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("broker_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("internal_code", sa.String(50), nullable=True),
        sa.Column("property_type", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="available"),
        sa.Column("commune", sa.String(100), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Numeric(10, 8), nullable=True),
        sa.Column("longitude", sa.Numeric(11, 8), nullable=True),
        sa.Column("price_uf", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_clp", sa.BigInteger(), nullable=True),
        sa.Column("bedrooms", sa.Integer(), nullable=True),
        sa.Column("bathrooms", sa.Integer(), nullable=True),
        sa.Column("parking_spots", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("storage_units", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("square_meters_total", sa.Numeric(10, 2), nullable=True),
        sa.Column("square_meters_useful", sa.Numeric(10, 2), nullable=True),
        sa.Column("floor_number", sa.Integer(), nullable=True),
        sa.Column("total_floors", sa.Integer(), nullable=True),
        sa.Column("orientation", sa.String(20), nullable=True),
        sa.Column("year_built", sa.Integer(), nullable=True),
        sa.Column("delivery_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("highlights", sa.Text(), nullable=True),
        sa.Column("amenities", postgresql.JSONB(), nullable=True),
        sa.Column("nearby_places", postgresql.JSONB(), nullable=True),
        sa.Column("images", postgresql.JSONB(), nullable=True),
        sa.Column("financing_options", postgresql.JSONB(), nullable=True),
        sa.Column("floor_plan_url", sa.Text(), nullable=True),
        sa.Column("virtual_tour_url", sa.Text(), nullable=True),
        sa.Column("common_expenses_clp", sa.Integer(), nullable=True),
        sa.Column("subsidio_eligible", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("embedding", sa.Text(), nullable=True),  # overridden below with vector type
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("kb_entry_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["kb_entry_id"], ["knowledge_base.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Replace placeholder column with real vector type
    op.execute("ALTER TABLE properties DROP COLUMN embedding")
    op.execute("ALTER TABLE properties ADD COLUMN embedding vector(768)")

    op.create_index("idx_prop_broker_status", "properties", ["broker_id", "status"])
    op.create_index("idx_properties_broker_id", "properties", ["broker_id"])
    op.create_index("idx_properties_commune", "properties", ["commune"])
    op.create_index("idx_properties_bedrooms", "properties", ["bedrooms"])
    op.create_index("idx_properties_price_uf", "properties", ["price_uf"])
    op.create_index(
        "idx_prop_search", "properties",
        ["broker_id", "commune", "bedrooms", "price_uf"],
        postgresql_where=sa.text("status = 'available'"),
    )
    op.create_index(
        "idx_prop_type", "properties",
        ["broker_id", "property_type"],
        postgresql_where=sa.text("status = 'available'"),
    )
    op.create_index(
        "idx_prop_geo", "properties",
        ["latitude", "longitude"],
        postgresql_where=sa.text("status = 'available'"),
    )
    # IVFFlat vector index for semantic search
    op.execute(
        "CREATE INDEX idx_prop_embedding ON properties "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50)"
    )

    # ── 4. escalation_briefs ──────────────────────────────────────────────────
    op.create_table(
        "escalation_briefs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("brief_text", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(50), nullable=True),
        sa.Column("frustration_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_escalation_briefs_lead", "escalation_briefs", ["lead_id", "created_at"])

    # ── 5. observability_alerts ───────────────────────────────────────────────
    op.create_table(
        "observability_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("related_lead_id", sa.Integer(), nullable=True),
        sa.Column("related_broker_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("alert_data", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["acknowledged_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["related_broker_id"], ["brokers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["related_lead_id"], ["leads.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_alerts_status", "observability_alerts", ["status", "created_at"])
    op.create_index("idx_alerts_severity", "observability_alerts", ["severity", "status"])
    op.create_index("idx_alerts_broker", "observability_alerts", ["related_broker_id", "status"])

    # ── 6. leads: add human_released_at, human_release_note ───────────────────
    op.add_column("leads", sa.Column("human_released_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("leads", sa.Column("human_release_note", sa.Text(), nullable=True))

    # ── 7. chat_messages: add conversation_id ─────────────────────────────────
    op.add_column(
        "chat_messages",
        sa.Column("conversation_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_chat_messages_conversation_id",
        "chat_messages", "conversations",
        ["conversation_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_chat_messages_conversation", "chat_messages", ["conversation_id"])

    # ── 8. prompt_versions: add metric columns ────────────────────────────────
    op.add_column("prompt_versions", sa.Column("prompt_type", sa.String(30), nullable=True))
    op.add_column("prompt_versions", sa.Column("prompt_hash", sa.String(64), nullable=True))
    op.add_column("prompt_versions", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("prompt_versions", sa.Column("total_uses", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("prompt_versions", sa.Column("avg_tokens_per_call", sa.Float(), nullable=True))
    op.add_column("prompt_versions", sa.Column("avg_latency_ms", sa.Float(), nullable=True))
    op.add_column("prompt_versions", sa.Column("avg_lead_score_delta", sa.Float(), nullable=True))
    op.add_column("prompt_versions", sa.Column("escalation_rate", sa.Float(), nullable=True))


def downgrade() -> None:
    # prompt_versions
    op.drop_column("prompt_versions", "escalation_rate")
    op.drop_column("prompt_versions", "avg_lead_score_delta")
    op.drop_column("prompt_versions", "avg_latency_ms")
    op.drop_column("prompt_versions", "avg_tokens_per_call")
    op.drop_column("prompt_versions", "total_uses")
    op.drop_column("prompt_versions", "notes")
    op.drop_column("prompt_versions", "prompt_hash")
    op.drop_column("prompt_versions", "prompt_type")

    # chat_messages
    op.drop_constraint("fk_chat_messages_conversation_id", "chat_messages", type_="foreignkey")
    op.drop_index("idx_chat_messages_conversation", table_name="chat_messages")
    op.drop_column("chat_messages", "conversation_id")

    # leads
    op.drop_column("leads", "human_release_note")
    op.drop_column("leads", "human_released_at")

    # observability_alerts
    op.drop_index("idx_alerts_broker", table_name="observability_alerts")
    op.drop_index("idx_alerts_severity", table_name="observability_alerts")
    op.drop_index("idx_alerts_status", table_name="observability_alerts")
    op.drop_table("observability_alerts")

    # escalation_briefs
    op.drop_index("idx_escalation_briefs_lead", table_name="escalation_briefs")
    op.drop_table("escalation_briefs")

    # properties
    op.execute("DROP INDEX IF EXISTS idx_prop_embedding")
    op.drop_index("idx_prop_geo", table_name="properties")
    op.drop_index("idx_prop_type", table_name="properties")
    op.drop_index("idx_prop_search", table_name="properties")
    op.drop_index("idx_properties_price_uf", table_name="properties")
    op.drop_index("idx_properties_bedrooms", table_name="properties")
    op.drop_index("idx_properties_commune", table_name="properties")
    op.drop_index("idx_properties_broker_id", table_name="properties")
    op.drop_index("idx_prop_broker_status", table_name="properties")
    op.drop_table("properties")

    # agent_events
    op.drop_index("idx_agent_events_conversation", table_name="agent_events")
    op.drop_index("idx_agent_events_agent", table_name="agent_events")
    op.drop_index("idx_agent_events_type", table_name="agent_events")
    op.drop_index("idx_agent_events_broker", table_name="agent_events")
    op.drop_index("idx_agent_events_lead", table_name="agent_events")
    op.drop_table("agent_events")

    # conversations
    op.drop_index("idx_conv_broker_channel", table_name="conversations")
    op.drop_index("idx_conv_human", table_name="conversations")
    op.drop_index("idx_conv_broker_status", table_name="conversations")
    op.drop_index("idx_conv_lead", table_name="conversations")
    op.drop_index("idx_conversations_broker_id", table_name="conversations")
    op.drop_index("idx_conversations_lead_id", table_name="conversations")
    op.drop_table("conversations")
