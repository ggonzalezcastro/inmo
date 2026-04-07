"""
QualifierAgent — collects lead data and financial qualification (TASK-026).

Responsible for pipeline stages: entrada → perfilamiento → calificacion_financiera
State machine: GREETING → INTEREST_CHECK → DATA_COLLECTION → FINANCIAL_QUAL

Hands off to SchedulerAgent when:
  - All required fields collected
  - DICOM is not "dirty" (clean or unknown)
"""
from __future__ import annotations

import asyncio
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
        # Use broker custom override if available
        template = lead_data.get("_custom_qualifier_prompt") or QUALIFIER_SYSTEM_PROMPT
        base_prompt = template.format(agent_name=agent_name, broker_name=broker_name)

        # Inject already-collected fields so the LLM never asks for them again
        _dicom_labels = {"clean": "Limpio (sin deudas)", "dirty": "Con deudas morosas", "unknown": "No especificado"}
        collected: list[str] = []
        if lead_data.get("name"):
            collected.append(f"- Nombre: {lead_data['name']}")
        if lead_data.get("phone"):
            collected.append(f"- Teléfono: {lead_data['phone']}")
        if lead_data.get("email"):
            collected.append(f"- Email: {lead_data['email']}")
        if lead_data.get("location"):
            collected.append(f"- Ubicación: {lead_data['location']}")
        if lead_data.get("salary") or lead_data.get("budget"):
            val = lead_data.get("salary") or lead_data.get("budget")
            collected.append(f"- Renta mensual: {val}")
        if lead_data.get("dicom_status"):
            label = _dicom_labels.get(lead_data["dicom_status"], lead_data["dicom_status"])
            collected.append(f"- DICOM: {label}")

        if collected:
            pending_fields = []
            if not lead_data.get("name"):
                pending_fields.append("nombre completo")
            if not lead_data.get("phone"):
                pending_fields.append("teléfono")
            if not lead_data.get("email"):
                pending_fields.append("email")
            if not lead_data.get("location"):
                pending_fields.append("ubicación (comuna/sector)")
            if not (lead_data.get("salary") or lead_data.get("budget")):
                pending_fields.append("renta mensual")
            if not lead_data.get("dicom_status"):
                pending_fields.append("estado DICOM")

            pending_str = ", ".join(pending_fields) if pending_fields else "ninguno (todos completos)"
            base_prompt += (
                "\n\n## DATOS YA RECOPILADOS — NO volver a preguntar estos campos\n"
                + "\n".join(collected)
                + f"\n\n## CAMPOS AÚN PENDIENTES: {pending_str}\n"
                + "Agrupa los campos pendientes según la ESTRATEGIA DE RECOPILACIÓN (máximo 3 por mensaje)."
            )

        return self._inject_human_release_note(self._inject_tone_hint(base_prompt, context), context)

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
            # Reuse analysis from orchestrator step 3b if available — avoids a duplicate LLM call (~4500ms)
            if context.pre_analysis is not None:
                analysis = dict(context.pre_analysis)
                # The orchestrator's lead_context uses `lead.name or "User"` as fallback.
                # Strip that placeholder so it never overwrites an unset name field.
                _PLACEHOLDER_NAMES = frozenset({"User", "Test User", "user", "test user"})
                if analysis.get("name") in _PLACEHOLDER_NAMES:
                    analysis.pop("name", None)
                self._log("Reusing pre_analysis from orchestrator", lead_id=context.lead_id)
            else:
                # Include message_history so the analysis LLM has context for
                # short answers like "no" (DICOM question) or "sí" (interest)
                analysis_context = {**context.lead_data, "message_history": context.message_history}
                analysis = await LLMServiceFacade.analyze_lead_qualification(
                    message=message,
                    lead_context=analysis_context,
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

        # Log qualification analysis for the conversation debugger
        if updates or analysis.get("score_delta"):
            try:
                from app.services.observability.event_logger import event_logger
                asyncio.ensure_future(event_logger.log_qualification(
                    lead_id=context.lead_id,
                    broker_id=context.broker_id,
                    extracted_fields=updates,
                    score_delta=float(analysis.get("score_delta") or 0),
                    agent_type=self.agent_type.value,
                ))
            except Exception:
                pass

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

        # Check handoff BEFORE generating response so we can tailor the message
        dirty_dicom = merged_data.get("dicom_status") == "dirty"
        ready_for_handoff = not dirty_dicom and temp_context.is_appointment_ready()

        if ready_for_handoff:
            # Generate a transition message — don't ask for more fields
            name = merged_data.get("name", "")
            greeting = f"¡Excelente{', ' + name if name else ''}! " if name else "¡Excelente! "
            response_text = (
                f"{greeting}Con tu renta y DICOM limpio calificás perfectamente para financiamiento. "
                "Me gustaría coordinar una reunión por Google Meet con uno de nuestros asesores. "
                "¿Qué días y horario te quedan mejor esta semana?"
            )
            function_calls = []
        else:
            # Generate normal next-step response from LLM
            system_prompt = self.get_system_prompt(temp_context)
            try:
                response_text, function_calls = (
                    await LLMServiceFacade.generate_response_with_function_calling(
                        system_prompt=system_prompt,
                        contents=_build_messages(context.message_history, message),
                        tools=[],
                        broker_id=context.broker_id,
                        lead_id=context.lead_id,
                        agent_type=self.agent_type.value,
                    )
                )
            except Exception as exc:
                self._log(f"LLM response failed: {exc}", level="error")
                response_text = "Disculpa, estoy teniendo dificultades técnicas. Por favor intenta en unos minutos."
                function_calls = []

        handoff: HandoffSignal | None = None
        if ready_for_handoff:
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
