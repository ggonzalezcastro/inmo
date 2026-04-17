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
from app.services.agents.property import PropertyAgent
from app.services.agents.supervisor import AgentSupervisor

# ── Singleton instances ───────────────────────────────────────────────────────
qualifier_agent_instance = QualifierAgent()
scheduler_agent_instance = SchedulerAgent()
follow_up_agent_instance = FollowUpAgent()
property_agent_instance = PropertyAgent()

# Register all agents
register_agent(qualifier_agent_instance)
register_agent(scheduler_agent_instance)
register_agent(follow_up_agent_instance)
register_agent(property_agent_instance)


def get_priority_agents() -> list[BaseAgent]:
    """
    Return registered agents in routing-priority order.

    Deprecated — the supervisor now routes via the _STAGE_TO_AGENT stage table.
    Kept for reference only.
    """
    return [
        follow_up_agent_instance,
        property_agent_instance,
        scheduler_agent_instance,
        qualifier_agent_instance,
    ]



def _parse_conv_state(value) -> str:
    """Normalise conversation_state regardless of how it was stored.

    The state machine stores it as a plain string (e.g. "interest_check"),
    but older metadata entries may store it as {"state": "..."}.
    """
    if isinstance(value, str) and value:
        return value.upper()
    if isinstance(value, dict):
        return value.get("state", "GREETING")
    return "GREETING"


def build_context(
    lead,
    broker_id: int,
    broker_overrides: dict | None = None,
    message_history: list | None = None,
    broker_name: str = "",
    agent_name: str = "Sofía",
    pre_analysis: dict | None = None,
) -> AgentContext:
    """
    Convenience factory: build an AgentContext from a Lead ORM object.

    Parameters
    ----------
    lead             : Lead SQLAlchemy model instance
    broker_id        : The broker that owns this conversation
    broker_overrides: Optional dict with _custom_*_prompt keys loaded from DB
    message_history  : Conversation history from ChatMessage records (preferred
                       over what may be stale in lead_metadata)
    broker_name      : Human-readable broker name (from Broker.name)
    agent_name       : AI persona name (from BrokerPromptConfig.agent_name)
    pre_analysis     : Result of analyze_lead_qualification already run by the
                       orchestrator — passed through to avoid a duplicate LLM call
    """
    from app.core.encryption import decrypt_metadata_fields
    metadata = decrypt_metadata_fields(lead.lead_metadata or {}) or {}
    # Use lead.pipeline_stage only when it's a non-empty string (guard against MagicMock / None)
    _stage = lead.pipeline_stage if isinstance(lead.pipeline_stage, str) and lead.pipeline_stage else None
    # Prefer explicitly passed message_history (from DB records); fall back to metadata
    _history = message_history if message_history is not None else metadata.get("message_history", [])
    # Strip web/whatsapp placeholder names so agents ask for the real name
    _PLACEHOLDER_NAMES = frozenset({"User", "Test User", "user", "test user"})
    _lead_name = lead.name if lead.name and lead.name not in _PLACEHOLDER_NAMES else None
    _PLACEHOLDER_PHONES = frozenset({"web_chat_pending", "whatsapp_pending"})
    _lead_phone = (
        lead.phone
        if lead.phone and str(lead.phone) not in _PLACEHOLDER_PHONES
        and not str(lead.phone).startswith(("web_chat_", "whatsapp_"))
        else None
    )
    return AgentContext(
        lead_id=lead.id,
        broker_id=broker_id,
        pipeline_stage=_stage or metadata.get("pipeline_stage", "entrada"),
        conversation_state=_parse_conv_state(metadata.get("conversation_state")),
        lead_data={
            "name": _lead_name,
            "phone": _lead_phone,
            "email": lead.email,
            "salary": metadata.get("salary"),
            "budget": metadata.get("budget"),
            "location": metadata.get("location"),
            "dicom_status": metadata.get("dicom_status"),
            "morosidad_amount": metadata.get("morosidad_amount"),
            "broker_name": broker_name or metadata.get("broker_name", ""),
            "agent_name": agent_name or metadata.get("agent_name", "Sofía"),
            "hot_fast_track": metadata.get("hot_fast_track", False),
            # Handoff context persisted from the previous turn (Phase 1.2 / 2.3)
            "_handoff_reason": metadata.get("_handoff_reason"),
            "_handoff_from": metadata.get("_handoff_from"),
            "_handoff_at": metadata.get("_handoff_at"),
            # G8: tracks which handoff was already consumed so _inject_handoff_context
            # does not re-inject stale context in subsequent turns.
            "_last_consumed_handoff_at": metadata.get("_last_consumed_handoff_at"),
            # Broker-level custom prompt overrides (passed from orchestrator)
            "_custom_qualifier_prompt": (broker_overrides or {}).get("qualifier"),
            "_custom_scheduler_prompt": (broker_overrides or {}).get("scheduler"),
            "_custom_follow_up_prompt": (broker_overrides or {}).get("follow_up"),
            "_custom_property_prompt": (broker_overrides or {}).get("property"),
            # Broker-level skill extensions — appended after the base skill document
            "_skill_qualifier_extension": (broker_overrides or {}).get("skill_qualifier"),
            "_skill_scheduler_extension": (broker_overrides or {}).get("skill_scheduler"),
            "_skill_follow_up_extension": (broker_overrides or {}).get("skill_follow_up"),
            "_skill_property_extension": (broker_overrides or {}).get("skill_property"),
        },
        message_history=_history,
        current_agent=_parse_agent_type(metadata.get("current_agent")),
        human_release_note=getattr(lead, "human_release_note", None),
        pre_analysis=pre_analysis,
        property_preferences={
            k: v for k, v in {
                "property_type": metadata.get("property_type"),
                "commune": metadata.get("location"),
                "bedrooms": metadata.get("rooms"),
                "max_uf": metadata.get("budget"),
            }.items() if v is not None
        },
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
    "PropertyAgent",
    "build_context",
    "get_priority_agents",
    "qualifier_agent_instance",
    "scheduler_agent_instance",
    "follow_up_agent_instance",
    "property_agent_instance",
]
