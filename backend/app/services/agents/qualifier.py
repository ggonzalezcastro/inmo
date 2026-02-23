"""
QualifierAgent — collects lead data and financial qualification (TASK-026).

Responsible for pipeline stages: entrada → perfilamiento → calificacion_financiera
State machine: GREETING → INTEREST_CHECK → DATA_COLLECTION → FINANCIAL_QUAL

Hands off to SchedulerAgent when:
  - All required fields collected
  - DICOM is not "dirty" (clean or unknown)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.base import BaseAgent
from app.services.agents.prompts.qualifier_prompt import QUALIFIER_SYSTEM_PROMPT
from app.services.agents.types import (
    AgentContext,
    AgentResponse,
    AgentType,
    HandoffSignal,
)

logger = logging.getLogger(__name__)

# Stages this agent owns
_OWN_STAGES = {"entrada", "perfilamiento"}
# Conversation states this agent owns
_OWN_CONV_STATES = {"GREETING", "INTEREST_CHECK", "DATA_COLLECTION", "FINANCIAL_QUAL"}


class QualifierAgent(BaseAgent):
    """
    Specialist agent for lead qualification.

    Calls the LLM via LLMServiceFacade to extract data from the lead's messages
    and detects when qualification is complete, signalling a handoff to the
    SchedulerAgent.
    """

    agent_type = AgentType.QUALIFIER
    name = "QualifierAgent"

    def get_system_prompt(self, context: AgentContext) -> str:
        lead_data = context.lead_data
        broker_name = lead_data.get("broker_name", "la inmobiliaria")
        agent_name = lead_data.get("agent_name", "Sofía")
        return QUALIFIER_SYSTEM_PROMPT.format(
            agent_name=agent_name,
            broker_name=broker_name,
        )

    async def should_handle(self, context: AgentContext) -> bool:
        # Own pipeline stages
        if context.pipeline_stage in _OWN_STAGES:
            return True
        # Own conversation states (state machine hasn't reached scheduling yet)
        if context.conversation_state in _OWN_CONV_STATES:
            return True
        # No current agent assigned → default to qualifier for new leads
        if context.current_agent is None:
            return True
        return False

    async def process(
        self,
        message: str,
        context: AgentContext,
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Send the message to the LLM and extract qualification data.

        Uses `analyze_lead_qualification` to extract data fields, then checks
        if all required fields are now present.  If so, emits a HandoffSignal
        to the SchedulerAgent.
        """
        from app.services.llm.facade import LLMServiceFacade

        self._log(
            "Processing message",
            lead_id=context.lead_id,
            stage=context.pipeline_stage,
        )

        try:
            analysis = await LLMServiceFacade.analyze_lead_qualification(
                message=message,
                lead_context=context.lead_data,
                broker_id=context.broker_id,
                lead_id=context.lead_id,
            )
        except Exception as exc:
            self._log(f"LLM analysis failed: {exc}", level="warning")
            analysis = {}

        # Build updated context (merge new data into existing)
        updates: Dict[str, Any] = {}
        for field in ("name", "phone", "email", "salary", "location",
                      "budget", "dicom_status", "morosidad_amount"):
            val = analysis.get(field)
            if val and not context.lead_data.get(field):
                updates[field] = val

        # Generate response from the LLM
        merged_data = {**context.lead_data, **updates}
        temp_context = AgentContext(
            lead_id=context.lead_id,
            broker_id=context.broker_id,
            pipeline_stage=context.pipeline_stage,
            conversation_state=context.conversation_state,
            lead_data=merged_data,
            message_history=context.message_history,
            current_agent=AgentType.QUALIFIER,
        )

        system_prompt = self.get_system_prompt(temp_context)

        try:
            response_text, function_calls = (
                await LLMServiceFacade.generate_response_with_function_calling(
                    system_prompt=system_prompt,
                    contents=_build_messages(context.message_history, message),
                    tools=[],
                    broker_id=context.broker_id,
                    lead_id=context.lead_id,
                )
            )
        except Exception as exc:
            self._log(f"LLM response failed: {exc}", level="error")
            response_text = "Disculpa, estoy teniendo dificultades técnicas. Por favor intenta en unos minutos."
            function_calls = []

        # Check for DICOM violation: if lead has dirty DICOM, no handoff
        dirty_dicom = merged_data.get("dicom_status") == "dirty"

        # Decide on handoff
        handoff: HandoffSignal | None = None
        if not dirty_dicom and temp_context.is_appointment_ready():
            self._log("Qualification complete — signalling handoff to Scheduler",
                      lead_id=context.lead_id)
            handoff = HandoffSignal(
                target_agent=AgentType.SCHEDULER,
                reason="All qualification fields collected and DICOM is clean.",
                context_updates=updates,
            )

        return AgentResponse(
            message=response_text,
            agent_type=AgentType.QUALIFIER,
            context_updates=updates,
            handoff=handoff,
            function_calls=function_calls or [],
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_messages(history: list, new_message: str) -> list:
    """Convert message history + new message to LLMMessage format."""
    from app.services.llm.base_provider import LLMMessage
    messages = [
        LLMMessage(role=m.get("role", "user"), content=m.get("content", ""))
        for m in (history or [])
    ]
    messages.append(LLMMessage(role="user", content=new_message))
    return messages
