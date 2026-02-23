"""
LLMCall model — persists every call made to an LLM provider.

Provides visibility into:
  - Cost per conversation / per broker
  - Latency per provider and model
  - Error rates and failover frequency
  - Token consumption trends

Each row corresponds to one API round-trip (generate_json, generate_with_messages,
generate_with_tools). Tool execution sub-calls inside a single user turn are
recorded as separate rows with call_type="tool_call".
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Index
from sqlalchemy.sql.functions import now

from app.models.base import Base


class LLMCall(Base):
    """One row per LLM API round-trip."""

    __tablename__ = "llm_calls"

    id = Column(Integer, primary_key=True, index=True)

    # Context — who triggered the call
    broker_id = Column(Integer, ForeignKey("brokers.id", ondelete="SET NULL"), nullable=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)

    # Provider info
    provider = Column(String(20), nullable=False, index=True)   # "gemini" | "claude" | "openai"
    model = Column(String(60), nullable=False)                   # e.g. "gemini-2.5-flash"
    call_type = Column(String(30), nullable=False, index=True)  # "qualification" | "chat_response" | "json_gen"
    used_fallback = Column(Integer, default=0, nullable=False)  # 1 if failover was active

    # Token usage
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)

    # Cost (USD) — estimated from public pricing tables
    estimated_cost_usd = Column(Float, nullable=True)

    # Performance
    latency_ms = Column(Integer, nullable=True)

    # Error tracking (NULL = success)
    error = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("idx_llm_calls_broker_created", "broker_id", "created_at"),
        Index("idx_llm_calls_provider_model", "provider", "model"),
    )

    def __repr__(self) -> str:
        return (
            f"<LLMCall id={self.id} provider={self.provider} "
            f"type={self.call_type} tokens={self.input_tokens}+{self.output_tokens}>"
        )
