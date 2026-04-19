"""
ConversationStateMachine — tracks where a lead is in Sofía's qualification flow.

States (in order):
  GREETING          → Initial contact, validating interest
  INTEREST_CHECK    → Confirmed lead is looking; collecting data
  DATA_COLLECTION   → Gathering name / phone / email / location
  FINANCIAL_QUAL    → Asking for renta líquida and DICOM status
  SCHEDULING        → Offering/confirming appointment slot
  COMPLETED         → Appointment confirmed ✅
  LOST              → Lead declined or disqualified 🚫

Transitions are persisted into lead_metadata["conversation_state"].
The machine is intentionally lenient — only known triggers advance state;
unknown triggers are ignored (so a misfire never crashes the pipeline).

Usage:
    from app.services.chat.state_machine import ConversationStateMachine

    machine = ConversationStateMachine.from_lead_metadata(metadata)
    machine.confirm_interest()          # advance
    current = machine.state             # "interest_check"
    metadata = machine.to_metadata(metadata)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from transitions import Machine

logger = logging.getLogger(__name__)


# ── State & trigger constants ─────────────────────────────────────────────────

class States:
    GREETING = "greeting"
    INTEREST_CHECK = "interest_check"
    DATA_COLLECTION = "data_collection"
    FINANCIAL_QUAL = "financial_qualification"
    SCHEDULING = "scheduling"
    COMPLETED = "completed"
    LOST = "lost"

    @classmethod
    def all(cls):
        return [
            cls.GREETING,
            cls.INTEREST_CHECK,
            cls.DATA_COLLECTION,
            cls.FINANCIAL_QUAL,
            cls.SCHEDULING,
            cls.COMPLETED,
            cls.LOST,
        ]


_TRANSITIONS = [
    # Normal progression
    {
        "trigger": "confirm_interest",
        "source": States.GREETING,
        "dest": States.INTEREST_CHECK,
    },
    {
        "trigger": "start_data_collection",
        "source": States.INTEREST_CHECK,
        "dest": States.DATA_COLLECTION,
    },
    {
        "trigger": "start_financial_qualification",
        "source": States.DATA_COLLECTION,
        "dest": States.FINANCIAL_QUAL,
    },
    {
        "trigger": "offer_appointment",
        "source": States.FINANCIAL_QUAL,
        "dest": States.SCHEDULING,
    },
    {
        "trigger": "complete",
        "source": States.SCHEDULING,
        "dest": States.COMPLETED,
    },
    # Fast-path: qualified lead can go directly from financial_qualification to completed
    {
        "trigger": "complete",
        "source": States.FINANCIAL_QUAL,
        "dest": States.COMPLETED,
    },
    # Disqualification can happen from any active state
    {
        "trigger": "disqualify",
        "source": [
            States.GREETING,
            States.INTEREST_CHECK,
            States.DATA_COLLECTION,
            States.FINANCIAL_QUAL,
            States.SCHEDULING,
        ],
        "dest": States.LOST,
    },
    # Allow re-opening a LOST conversation (e.g., lead comes back later)
    {
        "trigger": "reopen",
        "source": States.LOST,
        "dest": States.INTEREST_CHECK,
    },
]


# ── Machine class ─────────────────────────────────────────────────────────────

class ConversationStateMachine:
    """Thin wrapper around `transitions.Machine` for lead qualification flow."""

    METADATA_KEY = "conversation_state"

    def __init__(self, initial_state: str = States.GREETING) -> None:
        if initial_state not in States.all():
            logger.warning(
                "Unknown initial state %r — defaulting to greeting", initial_state
            )
            initial_state = States.GREETING

        self.machine = Machine(
            model=self,
            states=States.all(),
            transitions=_TRANSITIONS,
            initial=initial_state,
            ignore_invalid_triggers=True,   # unknown triggers are silently ignored
            queued=False,
        )

    # ── Serialisation ─────────────────────────────────────────────────────────

    @classmethod
    def from_lead_metadata(
        cls, metadata: Optional[Dict[str, Any]]
    ) -> "ConversationStateMachine":
        """Reconstruct machine from lead_metadata dict (or start fresh)."""
        if not isinstance(metadata, dict):
            return cls()
        saved_state = metadata.get(cls.METADATA_KEY, States.GREETING)
        return cls(initial_state=saved_state)

    def to_metadata(self, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Return a copy of metadata with the current state persisted."""
        result = dict(metadata) if isinstance(metadata, dict) else {}
        result[self.METADATA_KEY] = self.state
        return result

    # ── Convenience helpers ───────────────────────────────────────────────────

    @property
    def is_terminal(self) -> bool:
        return self.state in (States.COMPLETED, States.LOST)

    @property
    def is_qualified(self) -> bool:
        return self.state == States.COMPLETED

    @property
    def current_state(self) -> str:
        return self.state

    def advance_from_llm_output(self, llm_metadata: Dict[str, Any]) -> None:
        """
        Inspect LLM qualification output and advance the state machine
        automatically when clear signals are present.

        llm_metadata keys inspected:
          - "lead_status"     : "CALIFICADO" | "NO_CALIFICADO" | "POTENCIAL"
          - "appointment_id"  : truthy value → scheduling or completed
          - "data_complete"   : True → move past data_collection
          - "financial_asked" : True → move into financial_qualification
        """
        lead_status: str = (llm_metadata.get("lead_status") or "").upper()
        appointment_id = llm_metadata.get("appointment_id")
        data_complete: bool = bool(llm_metadata.get("data_complete"))
        financial_asked: bool = bool(llm_metadata.get("financial_asked"))

        if lead_status == "NO_CALIFICADO":
            self.disqualify()
            return

        if appointment_id:
            # Appointment confirmed → mark complete
            if self.state not in (States.COMPLETED, States.LOST):
                self.complete()
            return

        if lead_status == "CALIFICADO":
            if self.state == States.FINANCIAL_QUAL:
                self.offer_appointment()
            return

        # Softer progression
        if self.state == States.GREETING:
            self.confirm_interest()
        elif self.state == States.INTEREST_CHECK and data_complete:
            self.start_data_collection()
        elif self.state == States.DATA_COLLECTION and (data_complete or financial_asked):
            self.start_financial_qualification()
