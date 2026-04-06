"""
AgentEvent — audit trail for every action taken by the multi-agent system.

Records:
  - Which agent processed each message
  - LLM calls (provider, model, tokens, cost, latency)
  - Tool calls and results
  - Agent handoffs with reasons
  - Pipeline stage changes
  - Lead score changes
  - Escalations and errors

Used by the observability dashboard and conversation debugger.
"""
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.functions import now

from app.models.base import Base


class AgentEvent(Base):
    """One row per discrete action in the multi-agent pipeline."""

    __tablename__ = "agent_events"

    id = Column(BigInteger, primary_key=True, index=True)

    # ── Context ──────────────────────────────────────────────────────────────
    lead_id = Column(
        Integer,
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    message_id = Column(
        Integer,
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Event classification ──────────────────────────────────────────────────
    # Supported types:
    #   agent_selected, agent_handoff, tool_called, tool_result,
    #   llm_call, llm_response, escalation_triggered, human_takeover,
    #   human_release, pipeline_stage_changed, lead_score_changed,
    #   sentiment_analyzed, property_search, appointment_created,
    #   qualification_analysis, error, fallback_triggered
    event_type = Column(String(50), nullable=False, index=True)

    # ── Agent routing ─────────────────────────────────────────────────────────
    agent_type = Column(String(30), nullable=True, index=True)
    # 'qualifier', 'scheduler', 'follow_up', 'property', 'supervisor'

    from_agent = Column(String(30), nullable=True)   # for handoff events
    to_agent = Column(String(30), nullable=True)      # for handoff events
    handoff_reason = Column(Text, nullable=True)

    # ── LLM call details ──────────────────────────────────────────────────────
    llm_provider = Column(String(20), nullable=True)  # 'gemini', 'claude', 'openai'
    llm_model = Column(String(50), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    llm_latency_ms = Column(Integer, nullable=True)
    llm_cost_usd = Column(Float, nullable=True)

    # Stored only when debug_mode enabled (may be large)
    system_prompt_hash = Column(String(64), nullable=True)  # SHA-256 of system prompt
    raw_response_snippet = Column(Text, nullable=True)       # first 500 chars

    # ── Tool calling ──────────────────────────────────────────────────────────
    tool_name = Column(String(50), nullable=True)
    tool_input = Column(JSONB, nullable=True)
    tool_output = Column(JSONB, nullable=True)
    tool_latency_ms = Column(Integer, nullable=True)
    tool_success = Column(Boolean, nullable=True)

    # ── State transitions ─────────────────────────────────────────────────────
    pipeline_stage_before = Column(String(50), nullable=True)
    pipeline_stage_after = Column(String(50), nullable=True)
    lead_score_before = Column(Float, nullable=True)
    lead_score_after = Column(Float, nullable=True)
    conversation_state_before = Column(String(30), nullable=True)
    conversation_state_after = Column(String(30), nullable=True)

    # ── Qualification ─────────────────────────────────────────────────────────
    extracted_fields = Column(JSONB, nullable=True)   # {"name": "Juan", "salary": 1800000}
    score_delta = Column(Float, nullable=True)

    # ── Property search ───────────────────────────────────────────────────────
    search_strategy = Column(String(20), nullable=True)  # 'hybrid', 'structured', 'semantic'
    search_results_count = Column(Integer, nullable=True)

    # ── Error tracking ────────────────────────────────────────────────────────
    error_type = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    error_stack = Column(Text, nullable=True)

    # ── Extra data ────────────────────────────────────────────────────────────
    event_metadata = Column(JSONB, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_agent_events_lead", "lead_id", "created_at"),
        Index("idx_agent_events_broker", "broker_id", "created_at"),
        Index("idx_agent_events_type", "event_type", "created_at"),
        Index("idx_agent_events_agent", "agent_type", "created_at"),
        Index("idx_agent_events_conversation", "conversation_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentEvent id={self.id} type={self.event_type} "
            f"agent={self.agent_type} lead={self.lead_id}>"
        )
