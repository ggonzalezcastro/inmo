"""
Multi-agent system for AI Lead Agent Pro (TASK-026).

Agents
------
- QualifierAgent  — collects lead data + financial qualification
- SchedulerAgent  — converts qualified leads into booked visits
- FollowUpAgent   — post-visit engagement and referrals
- AgentSupervisor — routes messages to the correct specialist

Feature flag
-----------
Set ``MULTI_AGENT_ENABLED=true`` in the environment to route new conversations
through the multi-agent system instead of the monolithic orchestrator.
The flag is per-environment; broker-level override is on the roadmap.

Usage
-----
    from app.services.agents import AgentSupervisor, build_context

    context = build_context(lead, broker_id)
    result  = await AgentSupervisor.process(message, context, db)
"""
from __future__ import annotations

from app.services.agents.types import (
    AgentContext,
    AgentResponse,
    AgentType,
    HandoffSignal,
)
from app.services.agents.base import BaseAgent, register_agent, get_agent
from app.services.agents.qualifier import QualifierAgent
from app.services.agents.scheduler import SchedulerAgent
from app.services.agents.follow_up import FollowUpAgent
from app.services.agents.supervisor import AgentSupervisor

# ── Singleton instances ───────────────────────────────────────────────────────
qualifier_agent_instance = QualifierAgent()
scheduler_agent_instance = SchedulerAgent()
follow_up_agent_instance = FollowUpAgent()

# Register all agents
register_agent(qualifier_agent_instance)
register_agent(scheduler_agent_instance)
register_agent(follow_up_agent_instance)


def get_priority_agents() -> list[BaseAgent]:
    """
    Return registered agents in routing-priority order.

    FollowUp > Scheduler > Qualifier
    (More specific agents take priority over general ones.)
    """
    return [
        follow_up_agent_instance,
        scheduler_agent_instance,
        qualifier_agent_instance,
    ]


def build_context(lead, broker_id: int) -> AgentContext:
    """
    Convenience factory: build an AgentContext from a Lead ORM object.

    Parameters
    ----------
    lead    : Lead SQLAlchemy model instance
    broker_id : The broker that owns this conversation
    """
    metadata = lead.lead_metadata or {}
    return AgentContext(
        lead_id=lead.id,
        broker_id=broker_id,
        pipeline_stage=metadata.get("pipeline_stage", "entrada"),
        conversation_state=metadata.get("conversation_state", {}).get("state", "GREETING"),
        lead_data={
            "name": lead.name,
            "phone": lead.phone,
            "email": lead.email,
            "salary": metadata.get("salary"),
            "budget": metadata.get("budget"),
            "location": metadata.get("location"),
            "dicom_status": metadata.get("dicom_status"),
            "morosidad_amount": metadata.get("morosidad_amount"),
            "broker_name": metadata.get("broker_name", ""),
            "agent_name": metadata.get("agent_name", "Sofía"),
        },
        message_history=metadata.get("message_history", []),
        current_agent=_parse_agent_type(metadata.get("current_agent")),
    )


def _parse_agent_type(value: str | None) -> AgentType | None:
    if not value:
        return None
    try:
        return AgentType(value)
    except ValueError:
        return None


__all__ = [
    "AgentContext",
    "AgentResponse",
    "AgentType",
    "AgentSupervisor",
    "HandoffSignal",
    "BaseAgent",
    "QualifierAgent",
    "SchedulerAgent",
    "FollowUpAgent",
    "build_context",
    "get_priority_agents",
    "qualifier_agent_instance",
    "scheduler_agent_instance",
    "follow_up_agent_instance",
]
