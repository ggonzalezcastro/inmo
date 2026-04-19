"""
SchedulerAgent — converts qualified leads into booked property visits (TASK-026).

Responsible for pipeline stages: calificacion_financiera → agendado
State machine: SCHEDULING

Hands off to FollowUpAgent when appointment is confirmed.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import pytz

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.base import BaseAgent
from app.services.agents.prompts.scheduler_prompt import SCHEDULER_SYSTEM_PROMPT
from app.services.agents.prompts.skills import SCHEDULER_SKILL
from app.services.agents.types import (
    AgentContext,
    AgentResponse,
    AgentType,
    HandoffSignal,
    make_handoff_tool,
)

logger = logging.getLogger(__name__)

_OWN_STAGES = {"calificacion_financiera"}
_OWN_CONV_STATES = {"SCHEDULING"}

# Simple project list for the POC (in production: read from KB or broker config)
_DEFAULT_PROJECTS = """\
- Torre Ñuñoa: Av. Irarrázaval 1234, Ñuñoa. 1D/2D/3D. Entrega Q1 2027.
- Parque Las Condes: Av. Apoquindo 5600, Las Condes. 2D/3D. Entrega Q3 2026.
"""

# Handoff tool — LLM calls this after create_appointment responds successfully.
_HANDOFF_TOOLS = [
    make_handoff_tool(
        "follow_up",
        "Llama SOLO después de que create_appointment haya respondido con éxito. "
        "Pasa el lead a seguimiento post-agendamiento. "
        "reason: 'Cita agendada exitosamente.'",
    ),
]


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
        lead_email = lead_data.get("email") or ""
        lead_summary = f"{name}, interesado en {location}{budget_str}."

        # Current datetime in broker timezone
        try:
            tz = pytz.timezone(broker_timezone)
        except Exception:
            tz = pytz.timezone("America/Santiago")
        now_local = datetime.now(tz)
        # Include the UTC offset explicitly so the LLM uses the correct one in ISO timestamps
        # (e.g. Chile is UTC-3 in summer but UTC-4 in winter — LLM must not hardcode -03:00)
        utc_offset_str = now_local.strftime("%z")  # e.g. "-0400"
        utc_offset_formatted = f"{utc_offset_str[:3]}:{utc_offset_str[3:]}"  # "-04:00"
        current_datetime_str = (
            now_local.strftime("%A %d de %B de %Y, %H:%M")
            + f" ({broker_timezone}, UTC{utc_offset_formatted})"
        )

        template = lead_data.get("_custom_scheduler_prompt") or SCHEDULER_SYSTEM_PROMPT
        base_prompt = template.format(
            agent_name=agent_name,
            broker_name=broker_name,
            lead_summary=lead_summary,
            available_projects=_DEFAULT_PROJECTS,
            current_datetime=current_datetime_str,
            lead_id=context.lead_id,
            lead_email=lead_email,
        )

        # Inject handoff context so the agent knows why it was activated
        handoff_reason = lead_data.get("_handoff_reason")
        if handoff_reason:
            base_prompt += f"\n\n[CONTEXTO DE ACTIVACIÓN]: {handoff_reason}. El lead ya completó la calificación."

        base_prompt += (
            "\n\n### Paso 4 — Traspaso\n"
            "Una vez que create_appointment responda con éxito, llama handoff_to_follow_up. "
            "NO llames handoff_to_follow_up si create_appointment devolvió error."
        )

        skill_ext = context.lead_data.get("_skill_scheduler_extension")
        has_custom = bool(context.lead_data.get("_custom_scheduler_prompt"))
        base_prompt = self._inject_skill(
            base_prompt, "" if has_custom else SCHEDULER_SKILL, skill_ext
        )
        base_prompt = self._inject_handoff_context(base_prompt, context)
        return self._inject_human_release_note(self._inject_tone_hint(base_prompt, context), context)

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
            "START",
            lead_id=context.lead_id,
            broker_id=context.broker_id,
            stage=context.pipeline_stage,
        )

        # G1: Pre-check — SchedulerAgent requires financial data before proceeding.
        # Skip when handed off from QualifierAgent: Qualifier already enforced all
        # requirements (DICOM, salary, name, phone) before calling handoff_to_scheduler.
        _came_from_qualifier = context.lead_data.get("_handoff_from") == "qualifier"
        _pre = context.pre_analysis or {}
        _has_financial_data = (
            _came_from_qualifier
            or context.lead_data.get("dicom_status") or _pre.get("dicom_status")
            or context.lead_data.get("salary") or _pre.get("salary")
            or context.lead_data.get("budget") or _pre.get("budget")
        )
        if not _has_financial_data:
            self._log("PRE-CHECK: missing financial data — handing back to QualifierAgent", lead_id=context.lead_id)
            return AgentResponse(
                message="Antes de agendar tu visita, necesito conocer un poco más sobre tu situación financiera.",
                agent_type=self.agent_type,
                handoff=HandoffSignal(
                    target_agent=AgentType.QUALIFIER,
                    reason="Faltan datos financieros para completar la calificación",
                ),
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

        _handoff_intent: dict = {}
        _last_appointment_result: dict | None = None
        _confirmation_text: list[str] = []  # [0] = formatted confirmation to override LLM inline text

        async def _handoff_only_executor(tool_name: str, arguments: dict):
            if tool_name == "handoff_to_follow_up":
                self._log(
                    "handoff requested → FollowUpAgent",
                    lead_id=context.lead_id,
                    reason=arguments.get("reason"),
                )
                _handoff_intent["target"] = AgentType.FOLLOW_UP
                _handoff_intent["reason"] = arguments.get("reason", "Cita agendada")
                return {
                    "status": "ok",
                    "instruction": "Traspaso iniciado.",
                }
            return {"error": f"Unknown tool: {tool_name}"}

        tools: list = list(_HANDOFF_TOOLS)
        tool_executor = _handoff_only_executor
        try:
            from app.services.shared import AgentToolsService
            function_declarations = AgentToolsService.get_function_declarations()

            from app.services.llm.base_provider import LLMToolDefinition
            appointment_tools = [
                LLMToolDefinition(
                    name=fd.name,
                    description=fd.description or "",
                    parameters=dict(fd.parameters) if fd.parameters else {},
                )
                for fd in function_declarations
            ]
            tools = appointment_tools + _HANDOFF_TOOLS

            async def _full_executor(tool_name: str, arguments: dict):
                nonlocal _last_appointment_result
                if tool_name == "handoff_to_follow_up":
                    # Guard: block premature handoff if no appointment has been created yet
                    if not _last_appointment_result:
                        self._log("Blocking handoff_to_follow_up — no appointment created yet", lead_id=context.lead_id)
                        return {
                            "status": "blocked",
                            "reason": "Debes llamar create_appointment primero y confirmar que fue exitoso. No puedes hacer handoff sin cita creada.",
                        }
                    self._log(
                        "handoff requested → FollowUpAgent",
                        lead_id=context.lead_id,
                        reason=arguments.get("reason"),
                    )
                    _handoff_intent["target"] = AgentType.FOLLOW_UP
                    _handoff_intent["reason"] = arguments.get("reason", "Cita agendada")
                    apt = _last_appointment_result or {}
                    lead_name = context.lead_data.get("name") or "!"
                    name_part = f" {lead_name.capitalize()}" if lead_name and lead_name != "!" else ""
                    start = apt.get("start_time", "próximamente")
                    meet = apt.get("meet_url") or ""
                    agent_name_val = apt.get("agent_name") or "tu ejecutiva"
                    lead_email = context.lead_data.get("email") or ""
                    # Build the formatted confirmation directly — don't rely on the LLM
                    # to follow format instructions (it ignores them when generating inline text)
                    lines = [f"✅ Reunión agendada{name_part}:", f"📅 {start}"]
                    if meet:
                        lines.append(f"📹 Link Meet: {meet}")
                    lines.append(f"👤 Ejecutivo/a: {agent_name_val}")
                    if lead_email:
                        lines.append(f"📩 Te llegará invitación a {lead_email}")
                    lines.append("\nRecuerda traer tu cédula de identidad y tus últimas 3 liquidaciones de sueldo. ¡Te esperamos! 🏡")
                    _confirmation_text.append("\n".join(lines))
                    return {"status": "ok"}
                try:
                    result = await AgentToolsService.execute_tool(
                        db=db,
                        tool_name=tool_name,
                        arguments=arguments,
                        lead_id=context.lead_id,
                        agent_id=None,
                    )
                    if tool_name == "create_appointment" and isinstance(result, dict) and result.get("success"):
                        _last_appointment_result = result.get("result")
                    return result
                except Exception as _te:
                    logger.error("SchedulerAgent tool %s error: %s", tool_name, _te)
                    return {"error": str(_te), "success": False}

            tool_executor = _full_executor
        except Exception as _tools_exc:
            logger.warning("SchedulerAgent: could not load AgentToolsService (%s), using handoff-only tools", _tools_exc)

        try:
            response_text, function_calls = (
                await LLMServiceFacade.generate_response_with_function_calling(
                    system_prompt=system_prompt,
                    contents=_build_messages(context.message_history, message),
                    tools=tools,
                    tool_executor=tool_executor,
                    broker_id=context.broker_id,
                    lead_id=context.lead_id,
                    agent_type=self.agent_type.value,
                    tool_mode_override="ANY",
                    db=db,
                )
            )
        except Exception as exc:
            self._log(f"LLM response failed: {exc}", level="error")
            try:
                logger.warning(
                    "[SchedulerAgent] LLM with tools failed: %s. Retrying without tools in 1s.", exc
                )
                await asyncio.sleep(1)
                response_text, function_calls = (
                    await LLMServiceFacade.generate_response_with_function_calling(
                        system_prompt=(
                            system_prompt
                            + "\n\n[NOTA: No puedes verificar disponibilidad en este momento. "
                            "Indica al lead que te contacte directamente para coordinar una visita.]"
                        ),
                        contents=_build_messages(context.message_history, message),
                        tools=[],
                        broker_id=context.broker_id,
                        lead_id=context.lead_id,
                        agent_type=self.agent_type.value,
                        db=db,
                    )
                )
            except Exception as exc2:
                self._log(f"LLM retry also failed: {exc2}", level="error")
                response_text = "Disculpa, estoy teniendo dificultades para mostrarte los horarios. Por favor contáctame directamente."
                function_calls = []

        # Override LLM inline text with the deterministic formatted confirmation
        # (LLM ignores format instructions when it generates text alongside the tool call)
        if _confirmation_text:
            response_text = _confirmation_text[0]

        updates: dict = {}
        handoff: HandoffSignal | None = None
        if _handoff_intent.get("target"):
            self._log("Tool-based handoff → follow_up", lead_id=context.lead_id)
            updates["appointment_pending"] = True
            handoff = HandoffSignal(
                target_agent=_handoff_intent["target"],
                reason=_handoff_intent["reason"],
                context_updates=updates,
            )

        self._log(
            "DONE",
            lead_id=context.lead_id,
            handoff_target=_handoff_intent.get("target"),
        )

        return AgentResponse(
            message=response_text,
            agent_type=AgentType.SCHEDULER,
            context_updates=updates,
            handoff=handoff,
            function_calls=function_calls or [],
        )


def _last_assistant_message(history: list) -> str | None:
    """Return the last assistant/bot message from the conversation history."""
    for msg in reversed(history or []):
        role = msg.get("role", "")
        if role in ("assistant", "model", "bot"):
            return msg.get("content", "")
    return None
