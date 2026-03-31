"""
SchedulerAgent — converts qualified leads into booked property visits (TASK-026).

Responsible for pipeline stages: calificacion_financiera → agendado
State machine: SCHEDULING

Hands off to FollowUpAgent when appointment is confirmed.
"""
from __future__ import annotations

import logging
from datetime import datetime

import pytz

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.base import BaseAgent
from app.services.agents.prompts.scheduler_prompt import SCHEDULER_SYSTEM_PROMPT
from app.services.agents.types import (
    AgentContext,
    AgentResponse,
    AgentType,
    HandoffSignal,
)

logger = logging.getLogger(__name__)

_OWN_STAGES = {"calificacion_financiera"}
_OWN_CONV_STATES = {"SCHEDULING"}

# Simple project list for the POC (in production: read from KB or broker config)
_DEFAULT_PROJECTS = """\
- Torre Ñuñoa: Av. Irarrázaval 1234, Ñuñoa. 1D/2D/3D. Entrega Q1 2027.
- Parque Las Condes: Av. Apoquindo 5600, Las Condes. 2D/3D. Entrega Q3 2026.
"""


class SchedulerAgent(BaseAgent):
    """
    Specialist agent for scheduling property visits.

    Receives a pre-qualified lead from the QualifierAgent and focuses
    exclusively on proposing and confirming a visit slot.
    """

    agent_type = AgentType.SCHEDULER
    name = "SchedulerAgent"

    def get_system_prompt(self, context: AgentContext, broker_timezone: str = "America/Santiago") -> str:
        lead_data = context.lead_data
        broker_name = lead_data.get("broker_name", "la inmobiliaria")
        agent_name = lead_data.get("agent_name", "Sofía")

        # Build a one-line lead summary for the prompt
        name = lead_data.get("name", "el/la lead")
        location = lead_data.get("location", "sin preferencia de zona")
        budget = lead_data.get("budget") or lead_data.get("salary", "")
        budget_str = f", presupuesto {budget}" if budget else ""
        lead_summary = f"{name}, interesado en {location}{budget_str}."

        # Current datetime in broker timezone
        try:
            tz = pytz.timezone(broker_timezone)
        except Exception:
            tz = pytz.timezone("America/Santiago")
        now_local = datetime.now(tz)
        current_datetime_str = now_local.strftime("%A %d de %B de %Y, %H:%M") + f" ({broker_timezone})"

        template = lead_data.get("_custom_scheduler_prompt") or SCHEDULER_SYSTEM_PROMPT
        return template.format(
            agent_name=agent_name,
            broker_name=broker_name,
            lead_summary=lead_summary,
            available_projects=_DEFAULT_PROJECTS,
            current_datetime=current_datetime_str,
            lead_id=context.lead_id,
        )

    async def should_handle(self, context: AgentContext) -> bool:
        if context.pipeline_stage in _OWN_STAGES:
            return True
        if context.conversation_state in _OWN_CONV_STATES:
            return True
        # Sticky: was handed off to this agent (current_agent already set to SCHEDULER)
        if context.current_agent == AgentType.SCHEDULER:
            return True
        # Take over when qualifier signals readiness (handoff not yet persisted)
        if context.current_agent == AgentType.QUALIFIER and context.is_appointment_ready():
            return True
        return False

    async def process(
        self,
        message: str,
        context: AgentContext,
        db: AsyncSession,
    ) -> AgentResponse:
        from app.services.llm.facade import LLMServiceFacade
        from app.services.agents.qualifier import _build_messages
        from app.models.broker import BrokerPromptConfig
        from sqlalchemy.future import select

        self._log(
            "Processing scheduling message",
            lead_id=context.lead_id,
            stage=context.pipeline_stage,
        )

        # Fetch broker timezone from config
        broker_timezone = "America/Santiago"
        try:
            cfg_result = await db.execute(
                select(BrokerPromptConfig).where(BrokerPromptConfig.broker_id == context.broker_id)
            )
            broker_cfg = cfg_result.scalars().first()
            if broker_cfg and broker_cfg.meeting_config:
                broker_timezone = broker_cfg.meeting_config.get("timezone", "America/Santiago")
        except Exception:
            pass

        system_prompt = self.get_system_prompt(context, broker_timezone=broker_timezone)

        # Build tool definitions for appointment scheduling
        tools = []
        tool_executor = None
        try:
            from app.services.shared import AgentToolsService
            function_declarations = AgentToolsService.get_function_declarations()
            from google.genai import types as genai_types
            tools = [genai_types.Tool(function_declarations=function_declarations)]

            async def _tool_executor(tool_name: str, arguments: dict):
                try:
                    return await AgentToolsService.execute_tool(
                        db=db,
                        tool_name=tool_name,
                        arguments=arguments,
                        lead_id=context.lead_id,
                        agent_id=None,
                    )
                except Exception as _te:
                    logger.error("SchedulerAgent tool %s error: %s", tool_name, _te)
                    return {"error": str(_te), "success": False}

            tool_executor = _tool_executor
        except Exception as _tools_exc:
            logger.warning("SchedulerAgent: could not load tools (%s), proceeding without", _tools_exc)
            tools = []

        try:
            response_text, function_calls = (
                await LLMServiceFacade.generate_response_with_function_calling(
                    system_prompt=system_prompt,
                    contents=_build_messages(context.message_history, message),
                    tools=tools,
                    tool_executor=tool_executor,
                    broker_id=context.broker_id,
                    lead_id=context.lead_id,
                )
            )
        except Exception as exc:
            self._log(f"LLM response failed: {exc}", level="error")
            # Retry without tools on failure
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
            except Exception as exc2:
                self._log(f"LLM retry also failed: {exc2}", level="error")
                response_text = "Disculpa, estoy teniendo dificultades para mostrarte los horarios. Por favor contáctame directamente."
                function_calls = []

        # Detect appointment confirmation keywords
        appointment_confirmed = _is_appointment_confirmed(message, response_text)
        updates = {}
        if appointment_confirmed:
            updates["appointment_pending"] = True

        handoff: HandoffSignal | None = None
        if appointment_confirmed:
            self._log("Appointment confirmed — signalling handoff to FollowUp",
                      lead_id=context.lead_id)
            handoff = HandoffSignal(
                target_agent=AgentType.FOLLOW_UP,
                reason="Appointment confirmed; transitioning to post-visit follow-up.",
                context_updates=updates,
            )

        return AgentResponse(
            message=response_text,
            agent_type=AgentType.SCHEDULER,
            context_updates=updates,
            handoff=handoff,
            function_calls=function_calls or [],
        )


def _is_appointment_confirmed(user_message: str, agent_response: str) -> bool:
    """
    Heuristic: returns True when the exchange looks like a confirmed appointment.

    Checks for confirmation keywords in the user message AND confirmation
    language in the agent's response.
    """
    user_low = user_message.lower()
    agent_low = agent_response.lower()

    user_confirms = any(
        kw in user_low
        for kw in [
            "perfecto", "confirmado", "de acuerdo", "sí", "ok", "dale",
            "ese horario me queda", "me acomoda", "me viene bien",
        ]
    )

    agent_confirms = any(
        kw in agent_low
        for kw in [
            "confirmad", "te esperamos", "hasta el", "nos vemos", "cita agendada",
        ]
    )

    return user_confirms and agent_confirms
