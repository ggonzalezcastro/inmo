"""
FollowUpAgent — post-visit engagement and referral collection (TASK-026).

Responsible for pipeline stages: agendado → seguimiento → referidos/ganado
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

_OWN_STAGES = {"agendado", "seguimiento", "referidos"}
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

        return FOLLOW_UP_SYSTEM_PROMPT.format(
            agent_name=agent_name,
            broker_name=broker_name,
            lead_summary=lead_summary,
        )

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
