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
from app.services.agents.prompts.skills import QUALIFIER_SKILL
from app.services.agents.types import (
    AgentContext,
    AgentResponse,
    AgentType,
    HandoffSignal,
    make_handoff_tool,
)

logger = logging.getLogger(__name__)

# Stages this agent owns
_OWN_STAGES = {"entrada", "perfilamiento"}
# Conversation states this agent owns
_OWN_CONV_STATES = {"GREETING", "INTEREST_CHECK", "DATA_COLLECTION", "FINANCIAL_QUAL"}

# Handoff tools — LLM calls these when it decides a transfer is warranted.
_HANDOFF_TOOLS = [
    make_handoff_tool(
        "scheduler",
        "Llama esta función cuando el lead está completamente calificado "
        "(nombre, teléfono, email, ubicación, renta) y DICOM está limpio. "
        "Solo cuando is_appointment_ready() sea verdadero.",
    ),
    make_handoff_tool(
        "property",
        "Llama esta función cuando el lead quiere explorar o ver propiedades "
        "ANTES de completar la calificación. Úsala si pregunta por proyectos, "
        "departamentos, casas, precios o zonas específicas.",
    ),
]


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

        # Inject already-collected fields so the LLM never asks for them again.
        # Merge pre_analysis from the current turn — the orchestrator already extracted
        # fields from the current message, so we show them as "already known".
        _dicom_labels = {"clean": "Limpio (sin deudas)", "dirty": "Con deudas morosas", "unknown": "No especificado"}
        _merged = {**lead_data}
        if context.pre_analysis:
            for field in ("name", "phone", "email", "location", "salary", "dicom_status"):
                if context.pre_analysis.get(field) and not _merged.get(field):
                    _merged[field] = context.pre_analysis[field]

        # Placeholder values set by the system for web/whatsapp leads — not real data
        _PLACEHOLDER_PHONES = {"web_chat_pending", "whatsapp_pending"}

        collected: list[str] = []
        if _merged.get("name"):
            collected.append(f"- Nombre: {_merged['name']}")
        _phone = _merged.get("phone")
        if _phone and str(_phone) not in _PLACEHOLDER_PHONES and not str(_phone).startswith(("web_chat_", "whatsapp_")):
            collected.append(f"- Teléfono: {_phone}")
        if _merged.get("email"):
            collected.append(f"- Email: {_merged['email']}")
        if _merged.get("location"):
            collected.append(f"- Ubicación: {_merged['location']}")
        if _merged.get("salary") or _merged.get("budget"):
            val = _merged.get("salary") or _merged.get("budget")
            collected.append(f"- Renta mensual: {val}")
        if _merged.get("dicom_status"):
            label = _dicom_labels.get(_merged["dicom_status"], _merged["dicom_status"])
            collected.append(f"- DICOM: {label}")

        # Build greeting instruction — will be appended at the END of the prompt
        # (recency effect: last instruction wins over earlier ones)
        # Use message_history length to detect first contact — name may already be
        # persisted in DB (orchestrator saves it before calling agents), so lead_data.name
        # alone is not a reliable "active conversation" signal.
        is_active_conversation = len(context.message_history or []) > 1
        came_from_handoff = bool(lead_data.get("_handoff_from"))
        name_persisted = lead_data.get("name") and is_active_conversation
        if name_persisted or (is_active_conversation and came_from_handoff):
            greeting_instruction = (
                "\n\n## INSTRUCCIÓN DE CONTEXTO\n"
                "Ya estás en conversación activa con este lead. "
                "NO te presentes ni uses '¡Hola!' al inicio. Continúa directamente.\n"
            )
        else:
            name_just_given = _merged.get("name", "")
            if name_just_given:
                greeting_instruction = (
                    f"\n\n## ⚠️ INSTRUCCIÓN INMEDIATA — MÁS IMPORTANTE QUE TODO LO ANTERIOR\n"
                    f"El lead acaba de presentarse por PRIMERA VEZ como '{name_just_given}'.\n"
                    f"NO conoces aún su intención. Tu respuesta DEBE ser:\n"
                    f"  '¡Hola {name_just_given.capitalize()}! Soy {agent_name} de {broker_name}, encantada 😊 ¿En qué te puedo ayudar? ¿Estás buscando alguna propiedad?'\n"
                    f"PROHIBIDO pedir teléfono, email, ni ningún dato. Primero entiende qué busca.\n"
                )
            else:
                greeting_instruction = (
                    f"\n\n## ⚠️ INSTRUCCIÓN INMEDIATA — MÁS IMPORTANTE QUE TODO LO ANTERIOR\n"
                    f"El lead acaba de escribir por PRIMERA VEZ y no ha dado su nombre.\n"
                    f"Tu respuesta DEBE comenzar con:\n"
                    f"  '¡Hola! Soy {agent_name} de {broker_name} 😊 ¿Con quién tengo el gusto?'\n"
                    f"PROHIBIDO empezar con 'Para avanzar', 'Necesito datos', o cualquier pregunta directa.\n"
                )

        # Determine if we know the lead's intent (property interest or explicit continuation)
        intent = context.pre_analysis.get("intent", "general_chat") if context.pre_analysis else "general_chat"
        interest_level = context.pre_analysis.get("interest_level", 0) if context.pre_analysis else 0
        has_property_intent = intent in ("property_search", "schedule_visit", "financing_question") or interest_level >= 3

        # Only show collected/pending data fields when we know what the lead wants.
        # If they've only given their name with no stated interest, ask about intent first.
        only_name_known = collected == [f"- Nombre: {_merged.get('name')}"] or (
            len(collected) == 1 and "Nombre:" in collected[0]
        )

        import logging as _logging
        _logging.getLogger(__name__).info(
            "[Qualifier] intent=%s interest=%s only_name=%s has_property_intent=%s collected_count=%d",
            intent, interest_level, only_name_known, has_property_intent, len(collected)
        )

        if collected:
            base_prompt += (
                "\n\n## DATOS YA RECOPILADOS — NO volver a preguntar estos campos\n"
                + "\n".join(collected)
            )

            if only_name_known and not has_property_intent:
                # Lead just gave name with no interest expressed — ask what they want
                base_prompt += (
                    "\n\n## PRÓXIMO PASO\n"
                    "El lead acaba de darte su nombre pero NO ha expresado qué busca.\n"
                    "NO pidas teléfono, email ni otros datos todavía.\n"
                    "Tu único objetivo ahora: descubrir su intención con una pregunta abierta.\n"
                    "Ejemplo: '¿En qué te puedo ayudar? ¿Estás buscando alguna propiedad?'"
                )
            else:
                pending_fields = []
                if not _merged.get("name"):
                    pending_fields.append("nombre completo")
                if not _merged.get("phone"):
                    pending_fields.append("teléfono")
                if not _merged.get("email"):
                    pending_fields.append("email")
                if not _merged.get("location"):
                    pending_fields.append("ubicación (comuna/sector)")
                if not (_merged.get("salary") or _merged.get("budget")):
                    pending_fields.append("renta mensual")
                if not _merged.get("dicom_status"):
                    pending_fields.append("estado DICOM")

                pending_str = ", ".join(pending_fields) if pending_fields else "ninguno (todos completos)"
                base_prompt += (
                    f"\n\n## CAMPOS AÚN PENDIENTES: {pending_str}\n"
                    "Agrupa los campos pendientes según la ESTRATEGIA DE RECOPILACIÓN (máximo 3 por mensaje)."
                )

        base_prompt += (
            "\n\n## HERRAMIENTAS DE TRASPASO\n"
            "- handoff_to_property: Úsala INMEDIATAMENTE si el lead pregunta por propiedades, "
            "proyectos, departamentos, precios o zonas — aunque aún no hayas recopilado todos los datos. "
            "El agente de propiedades continuará la conversación y recopilará el resto.\n"
            "- handoff_to_scheduler: Úsala solo cuando tengas nombre, teléfono, email, ubicación, renta Y "
            "DICOM limpio. Llámala DESPUÉS de tu mensaje de transición natural. "
            "reason: \"Lead calificado. Campos: [lista]. DICOM: clean.\"\n"
            "REGLA: Prioriza siempre el interés del lead. Si quiere ver propiedades, no lo bloquees con preguntas."
        )

        # Append greeting instruction LAST so recency effect ensures the model follows it
        base_prompt += greeting_instruction

        # Re-enforce financial prohibition here (end of prompt = highest recency priority)
        # This prevents the LLM from violating it even after a handoff instruction.
        base_prompt += (
            "\n\n## ⚠️ RECORDATORIO FINAL — REGLA INQUEBRANTABLE\n"
            "Si el lead pregunta por pie, financiamiento, cuotas, proceso de compra o montos: "
            "responde ÚNICAMENTE: 'Eso lo revisamos en detalle con nuestro ejecutivo en la reunión. "
            "¿Te agendamos una videollamada para orientarte?' — NADA MÁS. Sin porcentajes, sin rangos, sin estimaciones.\n"
            "NUNCA digas que el lead 'cumple el perfil', 'califica', 'está aprobado' ni ninguna variante.\n"
        )

        # When routed from PropertyAgent (no properties found), tell LLM to pivot
        # to qualification instead of trying to show properties.
        if lead_data.get("_handoff_from") == "property":
            _transition_said = lead_data.get("_property_transition_said", "")
            _no_repeat = (
                f"El agente anterior ya dijo al lead: \"{_transition_said}\" — "
                "NO repitas esa frase ni uses palabras similares. Continúa directamente con la siguiente pregunta."
                if _transition_said else ""
            )
            base_prompt += (
                "\n\n## CONTEXTO DEL TRASPASO\n"
                "Vienes del agente de propiedades — no había propiedades disponibles para los criterios del lead. "
                "Tu objetivo ahora es recopilar sus datos de calificación (nombre, teléfono, email, ubicación, renta). "
                "NO intentes buscar propiedades ni uses handoff_to_property. "
                f"{_no_repeat}\n"
                "Continúa con una pregunta natural para avanzar en la calificación.\n"
            )

        skill_ext = context.lead_data.get("_skill_qualifier_extension")
        has_custom = bool(context.lead_data.get("_custom_qualifier_prompt"))
        base_prompt = self._inject_skill(
            base_prompt, "" if has_custom else QUALIFIER_SKILL, skill_ext
        )
        base_prompt = self._inject_handoff_context(base_prompt, context)
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
                    db=db,
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

        # DICOM dirty enforcement — code-level guard BEFORE the LLM call.
        # This is a non-negotiable business rule, not LLM-decided.
        # LLM prompt returns "has_debt"; legacy data may contain "dirty".
        dirty_dicom = merged_data.get("dicom_status") in ("has_debt", "dirty")

        if dirty_dicom:
            morosidad = merged_data.get("morosidad_amount", 0) or 0
            try:
                morosidad = float(morosidad)
            except (TypeError, ValueError):
                morosidad = 0
            if morosidad > 500_000:
                return AgentResponse(
                    message=(
                        "Entendemos tu situación. Te recomendamos regularizar tus deudas primero. "
                        "Cuando lo hagas, con gusto te ayudamos a retomar el proceso."
                    ),
                    agent_type=self.agent_type,
                    context_updates={**updates, "dicom_followup_scheduled": True},
                    handoff=HandoffSignal(
                        target_agent=AgentType.FOLLOW_UP,
                        reason="DICOM dirty — deuda alta, lead derivado a seguimiento",
                        context_updates={"_handoff_reason": "Lead con DICOM activo y deuda elevada. Orientar a regularizar y retomar proceso futuro."},
                    ),
                )
            else:
                guidance_already_given = context.lead_data.get("dicom_guidance_given", False)
                if guidance_already_given:
                    return AgentResponse(
                        message=(
                            "Entendido. Cuando regularices tu situación financiera, no dudes en escribirnos "
                            "y con gusto retomamos el proceso de búsqueda."
                        ),
                        agent_type=self.agent_type,
                        context_updates={**updates},
                        handoff=HandoffSignal(
                            target_agent=AgentType.FOLLOW_UP,
                            reason="DICOM dirty — orientación ya dada, derivar a seguimiento",
                            context_updates={"_handoff_reason": "Lead con DICOM activo, orientación ya fue entregada."},
                        ),
                    )
                return AgentResponse(
                    message=(
                        "Para avanzar con tu proceso, te recomendamos regularizar esa deuda primero "
                        "(está dentro de rangos manejables). "
                        "¿Te gustaría que te orientemos sobre cómo proceder?"
                    ),
                    agent_type=self.agent_type,
                    context_updates={**updates, "dicom_guidance_given": True},
                )

        # Generate LLM response with handoff tools so the model decides when to transfer.
        system_prompt = self.get_system_prompt(temp_context)
        _handoff_intent: dict = {}

        self._log(
            "tool_mode=AUTO",
            lead_id=context.lead_id,
        )

        async def tool_executor(tool_name: str, args: dict) -> dict:
            if tool_name == "handoff_to_scheduler":
                # Code-level gate: phone is required before scheduling
                _PLACEHOLDER_PHONES = {"web_chat_pending", "whatsapp_pending"}
                phone = merged_data.get("phone", "")
                phone_missing = not phone or str(phone) in _PLACEHOLDER_PHONES or str(phone).startswith(("web_chat_", "whatsapp_"))
                if phone_missing:
                    self._log("Blocking handoff_to_scheduler — phone not collected", lead_id=context.lead_id)
                    return {
                        "status": "blocked",
                        "reason": "Falta el teléfono del lead. Debes pedirlo antes de agendar.",
                    }
                _handoff_intent["target"] = AgentType.SCHEDULER
                _handoff_intent["reason"] = args.get("reason", "Lead calificado")
                return {"status": "ok"}
            if tool_name == "handoff_to_property":
                if came_from_property:
                    self._log("Blocking handoff_to_property — loop prevention (came from property)", lead_id=context.lead_id)
                    return {"status": "blocked", "reason": "Already processed by PropertyAgent this turn. Handle the question directly."}
                _handoff_intent["target"] = AgentType.PROPERTY
                _handoff_intent["reason"] = args.get("reason", "Lead quiere ver propiedades")
                return {"status": "ok"}
            return {"error": f"Unknown tool: {tool_name}"}

        # When we just came from PropertyAgent (no properties found), exclude
        # handoff_to_property to prevent the LLM from looping back there.
        came_from_property = context.lead_data.get("_handoff_from") == "property"
        active_tools = [t for t in _HANDOFF_TOOLS if not (came_from_property and t.name == "handoff_to_property")]

        try:
            response_text, function_calls = (
                await LLMServiceFacade.generate_response_with_function_calling(
                    system_prompt=system_prompt,
                    contents=_build_messages(context.message_history, message),
                    tools=active_tools,
                    tool_executor=tool_executor,
                    tool_mode_override="AUTO",
                    broker_id=context.broker_id,
                    lead_id=context.lead_id,
                    agent_type=self.agent_type.value,
                    db=db,
                )
            )
        except Exception as exc:
            self._log(f"LLM response failed: {exc}", level="error")
            response_text = "Disculpa, estoy teniendo dificultades técnicas. Por favor intenta en unos minutos."
            function_calls = []

        handoff: HandoffSignal | None = None
        if _handoff_intent.get("target"):
            self._log(
                f"Tool-based handoff → {_handoff_intent['target'].value}",
                lead_id=context.lead_id,
            )
            # If the LLM returned empty text after calling the handoff tool,
            # use a contextual transition message instead of the generic fallback.
            if not response_text or response_text == LLMServiceFacade.FALLBACK_RESPONSE:
                target = _handoff_intent["target"]
                if target == AgentType.PROPERTY:
                    response_text = "¡Claro! Te muestro las propiedades disponibles 🏠"
                elif target == AgentType.SCHEDULER:
                    response_text = "¡Perfecto! Te paso con nuestro equipo para coordinar la visita 📅"
                else:
                    response_text = "Un momento, te conecto con el área correspondiente."
            handoff = HandoffSignal(
                target_agent=_handoff_intent["target"],
                reason=_handoff_intent["reason"],
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
