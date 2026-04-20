"""
Agent-level LLM model configuration per broker.

Allows SUPERADMIN to assign a specific LLM provider, model, temperature
and max_tokens to each agent type for a given broker, overriding the
global env-var configuration.
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.models.base import Base, IdMixin, TimestampMixin


# Valid values — kept in sync with AgentType enum and factory provider names
VALID_AGENT_TYPES = {"qualifier", "property", "scheduler", "follow_up"}
VALID_PROVIDERS = {"gemini", "claude", "openai", "openrouter"}


class AgentModelConfig(Base, IdMixin, TimestampMixin):
    """Per-broker, per-agent LLM model configuration."""

    __tablename__ = "agent_model_configs"

    broker_id = Column(
        Integer,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Which agent this config applies to: qualifier | property | scheduler | follow_up
    agent_type = Column(String(20), nullable=False)

    # LLM provider: gemini | claude | openai
    llm_provider = Column(String(20), nullable=False)

    # Specific model identifier (e.g. "gemini-2.5-flash", "claude-sonnet-4-20250514")
    llm_model = Column(String(80), nullable=False)

    # Optional overrides — None means use provider default from env vars
    temperature = Column(Float, nullable=True)
    max_tokens = Column(Integer, nullable=True)

    # Allows disabling a config without deleting it
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("broker_id", "agent_type", name="uq_agent_model_config_broker_agent"),
        Index("ix_agent_model_configs_broker_id", "broker_id"),
    )

    # Relationship back to broker (optional — used for eager loading)
    broker = relationship("Broker", foreign_keys=[broker_id])

    def __repr__(self) -> str:
        return (
            f"<AgentModelConfig broker={self.broker_id} agent={self.agent_type} "
            f"provider={self.llm_provider} model={self.llm_model}>"
        )
