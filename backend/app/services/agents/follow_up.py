"""
FollowUpAgent — post-qualification nurturing and appointment follow-up.

Responsible for pipeline stages: potencial, agendado
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.base import BaseAgent
from app.services.agents.prompts.follow_up_prompt import FOLLOW_UP_SYSTEM_PROMPT
from app.services.agents.types import (
    AgentContext,
    AgentResponse,
    AgentType,
)

logger = logging.getLogger(__name__)

_OWN_STAGES = {"potencial", "agendado"}
_OWN_CONV_STATES = {"COMPLETED"}


class FollowUpAgent(BaseAgent):
    """
    Specialist agent for post-visit engagement.

    Handles leads that have confirmed a property visit, guiding them
    toward final conversion or referral collection.
    """

    agent_type = AgentType.FOLLOW_UP
    name = "FollowUpAgent"

    def get_system_prompt(self, context: AgentContext) -> str:
        lead_data = context.lead_data
        broker_name = lead_data.get("broker_name", "la inmobiliaria")
        agent_name = lead_data.get("agent_name", "Sofía")

        name = lead_data.get("name", "el/la cliente")
        location = lead_data.get("location", "el proyecto")
        lead_summary = f"{name} visitó un proyecto en {location}."

        template = lead_data.get("_custom_follow_up_prompt") or FOLLOW_UP_SYSTEM_PROMPT
        base_prompt = template.format(
            agent_name=agent_name,
            broker_name=broker_name,
            lead_summary=lead_summary,
        )

        # Potencial stage: lead needs commercial follow-up to resolve doubts and schedule
        if context.pipeline_stage == "potencial":
            base_prompt += (
                "\n\n📋 INSTRUCCIÓN - ETAPA POTENCIAL: Este lead tiene potencial financiero pero "
                "aún no está completamente calificado. Tu objetivo es:\n"
                "1. Resolver dudas financieras (presupuesto, financiamiento, DICOM).\n"
                "2. Proponer una reunión con un asesor para evaluar opciones.\n"
                "3. Ser orientador/a sin presionar. Máximo un contacto cada 48h sin respuesta."
            )

        # Hot fast-track: lead was advanced to "agendado" without a real appointment
        # Sofía must proactively propose scheduling a Google Meet
        if (context.pipeline_stage == "agendado"
                and context.lead_data.get("hot_fast_track")):
            base_prompt += (
                "\n\n⚡ INSTRUCCIÓN PRIORITARIA: Este lead fue avanzado automáticamente "
                "porque mostró alto interés y está financieramente calificado. "
                "NO tiene una reunión por Google Meet agendada todavía. Tu objetivo INMEDIATO "
                "es proponer una fecha concreta para la reunión con un asesor. Sé directo/a y entusiasta."
            )

        return self._inject_human_release_note(self._inject_tone_hint(base_prompt, context), context)

    async def should_handle(self, context: AgentContext) -> bool:
        if context.pipeline_stage in _OWN_STAGES:
            return True
        if context.conversation_state in _OWN_CONV_STATES:
            return True
        if context.current_agent == AgentType.SCHEDULER:
            return context.lead_data.get("appointment_pending") is True
        return False

    async def process(
        self,
        message: str,
        context: AgentContext,
        db: AsyncSession,
    ) -> AgentResponse:
        from app.services.llm.facade import LLMServiceFacade
        from app.services.agents.qualifier import _build_messages

        self._log(
            "Processing follow-up message",
            lead_id=context.lead_id,
            stage=context.pipeline_stage,
        )

        system_prompt = self.get_system_prompt(context)

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
            response_text = "Gracias por tu mensaje. Me pondré en contacto contigo pronto."
            function_calls = []

        return AgentResponse(
            message=response_text,
            agent_type=AgentType.FOLLOW_UP,
            context_updates={},
            handoff=None,
            function_calls=function_calls or [],
        )
