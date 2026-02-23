"""
Shared types for the multi-agent system (TASK-026).

All agents, handoffs, and context objects are defined here to avoid
circular imports between agent modules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Agent types ───────────────────────────────────────────────────────────────

class AgentType(str, Enum):
    """The specialised agents that can handle a lead conversation."""
    QUALIFIER = "qualifier"          # Collects lead data + financial qualification
    SCHEDULER = "scheduler"         # Books property visits
    FOLLOW_UP = "follow_up"         # Post-visit engagement / referrals
    SUPERVISOR = "supervisor"       # Internal: routes between agents


# ── Context ───────────────────────────────────────────────────────────────────

@dataclass
class AgentContext:
    """
    Snapshot of the current lead's state, passed into every agent call.

    Agents should treat this as read-only.  Updates are returned via
    ``AgentResponse.context_updates`` and applied by the supervisor.
    """
    lead_id: int
    broker_id: int
    pipeline_stage: str               # e.g. "entrada", "perfilamiento", "agendado"
    conversation_state: str           # e.g. "DATA_COLLECTION"
    lead_data: Dict[str, Any]         # name, phone, email, salary, budget, location, dicom_status
    message_history: List[Dict]       # [{role, content}, ...]
    current_agent: Optional[AgentType] = None
    handoff_count: int = 0            # guard against infinite handoff loops

    # ── Derived helpers ───────────────────────────────────────────────────────

    def is_qualified(self) -> bool:
        """True when the minimum data for financial qualification is present."""
        d = self.lead_data
        return bool(
            d.get("name")
            and d.get("phone")
            and (d.get("budget") or d.get("salary"))
            and d.get("dicom_status") in ("clean", "unknown")
        )

    def is_appointment_ready(self) -> bool:
        """True when the lead can be scheduled for a visit."""
        return self.is_qualified() and self.lead_data.get("location")

    def missing_fields(self) -> List[str]:
        """Return a list of required fields that have not been collected yet."""
        required = {
            "name": "nombre",
            "phone": "teléfono",
            "salary": "renta / presupuesto",
            "location": "zona de interés",
            "dicom_status": "estado DICOM",
        }
        return [label for field_key, label in required.items()
                if not self.lead_data.get(field_key)]


# ── Handoff ───────────────────────────────────────────────────────────────────

@dataclass
class HandoffSignal:
    """
    A signal emitted by an agent to trigger transfer to another agent.

    The supervisor reads this from ``AgentResponse.handoff`` and re-routes
    the next message accordingly.
    """
    target_agent: AgentType
    reason: str
    context_updates: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"HandoffSignal({self.target_agent.value}, reason={self.reason!r})"


# ── Agent response ────────────────────────────────────────────────────────────

@dataclass
class AgentResponse:
    """The output from any single agent call."""
    message: str                               # Text to send to the lead
    agent_type: AgentType                      # Which agent produced this response
    context_updates: Dict[str, Any] = field(default_factory=dict)  # Fields to merge into lead_data
    handoff: Optional[HandoffSignal] = None    # Set if this agent wants to pass control
    function_calls: List[Dict] = field(default_factory=list)
    tokens_used: int = 0
    is_final: bool = False                     # True = conversation fully completed
