"""
PropertyAgent — hybrid property search + recommendations (TASK-X).

Activated when pipeline stage is 'potencial' or the lead is routed here
via a handoff from QualifierAgent.

Uses function calling (SEARCH_PROPERTIES_TOOL) so the LLM extracts
structured search parameters from the lead's natural language, then
this agent executes the hybrid SQL + vector search with RRF merge.

Can hand off to SchedulerAgent when the lead wants to book a visit,
or back to QualifierAgent for financial/DICOM questions.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.base import BaseAgent
from app.services.agents.prompts.skills import PROPERTY_SKILL
from app.services.agents.types import (
    AgentContext,
    AgentResponse,
    AgentType,
    HandoffSignal,
    make_handoff_tool,
)
from app.services.llm.facade import LLMServiceFacade
from app.services.properties.search_service import (
    SEARCH_PROPERTIES_TOOL,
    execute_property_search,
)

logger = logging.getLogger(__name__)

# google/gemini-embedding-001 pricing via OpenRouter (USD per 1M tokens)
_EMBED_COST_PER_1M = 0.025

# Handoff tools — LLM calls these when it decides a transfer is warranted.
_HANDOFF_TOOLS = [
    make_handoff_tool(
        "qualifier",
        "Llama cuando el usuario pregunte sobre financiamiento, DICOM, renta o crédito. "
        "El agente calificador maneja esas consultas.",
    ),
    make_handoff_tool(
        "scheduler",
        "Llama cuando el usuario quiere visitar o agendar cita para una propiedad concreta.",
    ),
]


class PropertyAgent(BaseAgent):
    """Specialist agent for property search and recommendations."""

    agent_type = AgentType.PROPERTY
    name = "PropertyAgent"

    def get_system_prompt(self, context: AgentContext) -> str:
        broker_name = context.lead_data.get("broker_name", "nuestra inmobiliaria")
        agent_name = context.lead_data.get("agent_name", "Sofía")
        raw_name = context.lead_data.get("name")
        name_known = bool(raw_name and raw_name.strip().lower() not in ("user", "usuario", ""))
        lead_name = raw_name if name_known else "el cliente"

        # Build budget context from what we know
        budget_ctx = ""
        max_uf = context.lead_data.get("budget")
        salary = context.lead_data.get("salary")
        if max_uf:
            budget_ctx = f"Presupuesto declarado: {max_uf} UF. "
        elif salary:
            estimated = float(salary) * 0.0001  # rough heuristic
            budget_ctx = f"Renta mensual: ${int(salary):,}. Capacidad hipotecaria estimada: ~{estimated:.0f} UF. "

        location = context.lead_data.get("location", "")

        # Build property preferences context
        prefs = context.property_preferences or {}
        pref_parts = []
        if prefs.get("property_type"):
            pref_parts.append(f"Tipo buscado: {prefs['property_type']}")
        if prefs.get("commune"):
            pref_parts.append(f"Zona preferida: {prefs['commune']}")
        if prefs.get("bedrooms"):
            pref_parts.append(f"Dormitorios deseados: {prefs['bedrooms']}")
        if prefs.get("max_uf"):
            pref_parts.append(f"Presupuesto: hasta {prefs['max_uf']} UF")
        prefs_ctx = "\n".join(pref_parts) if pref_parts else "Sin preferencias registradas aún"

        # Broker may supply a custom persona/intro via _agent_property in situation_handlers.
        # The custom prompt replaces the default header only — dynamic context is always appended.
        _custom_intro = context.lead_data.get("_custom_property_prompt")
        if _custom_intro:
            try:
                header = _custom_intro.format(
                    agent_name=agent_name, broker_name=broker_name, lead_name=lead_name
                )
            except (KeyError, ValueError):
                header = _custom_intro  # use as-is if format fails
        else:
            header = (
                f"Eres {agent_name}, asesora inmobiliaria experta de {broker_name}.\n\n"
                f"IMPORTANTE: Ya estás en una conversación activa con {lead_name}. "
                f"NO te presentes ni saludes con \"Hola [nombre]\" al inicio de tu respuesta — "
                f"eso ya ocurrió. Continúa la conversación directamente.\n\n"
                f"Estás ayudando a {lead_name} a encontrar la propiedad ideal."
            )

        prompt = f"""{header}

## Contexto del cliente
{budget_ctx}
Zona de interés: {location or 'No especificada'}
Estado DICOM: {context.lead_data.get('dicom_status', 'No verificado')}

## Preferencias de propiedad registradas
{prefs_ctx}

## Tu rol
- Busca propiedades disponibles usando la herramienta `search_properties`
- Presenta los resultados de forma clara, destacando lo más relevante para el cliente
- Si el cliente quiere refinar la búsqueda (otra zona, más m², distinto precio), hazlo con una nueva búsqueda
- NO ofrezcas agendar visitas ni coordinar citas — eso lo maneja otro agente
- NO preguntes sobre presupuesto, renta, DICOM ni datos de calificación — eso lo maneja otro agente

## Cómo usar la herramienta de búsqueda
1. Extrae los parámetros del mensaje del cliente (dormitorios, precio, zona, m², preferencias)
2. Usa strategy="hybrid" por defecto para mejores resultados
3. Si el cliente menciona solo características cualitativas ("luminoso", "tranquilo"), usa strategy="semantic"
4. Devuelve máximo 3-5 propiedades para no abrumar al cliente

## Formato de presentación de propiedades
Para cada propiedad encontrada, presenta:
- Nombre/tipo y ubicación
- Precio en UF
- Dormitorios, baños, m²
- Highlights más relevantes
- Amenidades clave

## Tono
Entusiasta pero profesional. Ayuda al cliente a imaginar vivir en las propiedades.

## Datos del cliente pendientes de capturar
{"- IMPORTANTE: No conoces el nombre del cliente. Al presentar las propiedades, termina tu mensaje con una pregunta natural pidiendo su nombre. Ejemplo: '¿Por cierto, cómo te llamas para atenderte mejor?'" if not name_known else ""}
"""

        # When the lead is not yet qualified, guide them to provide their data
        # after showing properties — the goal is to hook them and then collect info.
        if context.pipeline_stage in ("entrada", "perfilamiento") and not context.is_qualified():
            prompt += (
                "\n\n[INSTRUCCIÓN ESPECIAL]\n"
                "El lead aún no ha sido calificado. Tu prioridad al responder:\n"
                "1. PRIMERO muestra las propiedades encontradas tal como son.\n"
                "2. Si hay resultados: al final del mensaje haz UNA pregunta natural para refinar (zona, m², etc.).\n"
                "3. NUNCA digas 'no encontramos', 'no hay', 'lamentablemente' ni nada negativo sobre disponibilidad.\n"
                "4. NUNCA pidas los datos ANTES de responder sobre las propiedades.\n"
                "5. Si el usuario dice 'no', 'no importa', 'da igual', o rechaza seguir buscando: llama handoff_to_qualifier de inmediato.\n"
            )

        prompt += (
            "\n\n## HERRAMIENTAS DE TRASPASO\n"
            "- Si el usuario pregunta sobre financiamiento, pie, DICOM, renta, cuotas, crédito o proceso de compra: llama handoff_to_qualifier INMEDIATAMENTE sin responder nada sobre el tema.\n"
            "- Si el usuario rechaza seguir buscando, dice 'no', 'no gracias', o no quiere explorar más zonas: llama handoff_to_qualifier INMEDIATAMENTE.\n"
            "- Si quiere agendar o visitar una propiedad concreta: llama handoff_to_scheduler.\n"
            "- Para todo lo demás: usa search_properties.\n\n"
            "## PROHIBIDO ABSOLUTO\n"
            "NUNCA menciones porcentajes de pie, rangos ('10% a 20%'), montos, cuotas ni ninguna orientación financiera. "
            "Ante cualquier pregunta financiera: llama handoff_to_qualifier de inmediato."
        )

        skill_ext = context.lead_data.get("_skill_property_extension")
        has_custom = bool(context.lead_data.get("_custom_property_prompt"))
        prompt = self._inject_skill(
            prompt, "" if has_custom else PROPERTY_SKILL, skill_ext
        )
        prompt = self._inject_handoff_context(prompt, context)
        return self._inject_human_release_note(self._inject_tone_hint(prompt, context), context)

    async def should_handle(self, context: AgentContext) -> bool:
        # Kept as a safe stub — supervisor now routes via stage table.
        return context.current_agent == AgentType.PROPERTY

    async def process(
        self,
        message: str,
        context: AgentContext,
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Process a property search request.

        1. Use LLM function calling to extract search parameters
        2. Execute hybrid search via search_properties tool
        3. LLM decides handoffs via handoff_to_qualifier / handoff_to_scheduler tools
        """
        from app.services.observability.event_logger import event_logger

        self._log(
            "START",
            lead_id=context.lead_id,
            broker_id=context.broker_id,
            stage=context.pipeline_stage,
        )
        system_prompt = self.get_system_prompt(context)
        messages = _build_messages(context.message_history, message)
        tool_results: List[Dict[str, Any]] = []
        _handoff_intent: dict = {}

        async def tool_executor(tool_name: str, tool_args: Dict) -> Any:
            # Handle handoff tools first
            if tool_name == "handoff_to_qualifier":
                self._log(
                    "handoff requested → QualifierAgent",
                    lead_id=context.lead_id,
                    reason=tool_args.get("reason"),
                )
                _handoff_intent["target"] = AgentType.QUALIFIER
                _handoff_intent["reason"] = tool_args.get("reason", "Pregunta financiera o de calificación")
                # Flag when triggered by 0 results so we can override the LLM's
                # inline text (which often reveals "no hay propiedades") after the call.
                if any(r["count"] == 0 for r in tool_results):
                    _handoff_intent["zero_results"] = True
                    _handoff_intent["reason"] = "Lead listo para proceso de calificación"
                _raw_name = context.lead_data.get("name", "")
                _PLACEHOLDER_PHONES = {"web_chat_pending", "whatsapp_pending"}
                _lp = context.lead_data.get("phone", "")
                _already_has_data = (
                    bool(_raw_name and _raw_name.strip().lower() not in ("user", "usuario", ""))
                    and bool(_lp and str(_lp) not in _PLACEHOLDER_PHONES and not str(_lp).startswith(("web_chat_", "whatsapp_")))
                )
                if _already_has_data:
                    instruction = "Transición natural (1-2 oraciones). Informa que buscarás las mejores opciones. Nunca menciones disponibilidad."
                else:
                    instruction = "Transición natural (1-2 oraciones). Indica que para encontrar la mejor opción necesitas conocerlo. Nunca menciones disponibilidad."
                return {"status": "ok", "instruction": instruction}
            if tool_name == "handoff_to_scheduler":
                self._log(
                    "handoff requested → SchedulerAgent",
                    lead_id=context.lead_id,
                    reason=tool_args.get("reason"),
                )
                _handoff_intent["target"] = AgentType.SCHEDULER
                _handoff_intent["reason"] = tool_args.get("reason", "Lead quiere agendar visita")
                return {"status": "ok", "instruction": "Transición natural (1-2 oraciones) confirmando interés y pasando al agente de agenda."}

            if tool_name != "search_properties":
                return {"error": f"Unknown tool: {tool_name}"}

            start = _now_ms()
            try:
                results, embed_tokens = await execute_property_search(tool_args, db, context.broker_id)
                latency = _now_ms() - start
                embed_cost = round(embed_tokens / 1_000_000 * _EMBED_COST_PER_1M, 8)
                tool_results.append({
                    "params": tool_args,
                    "count": len(results),
                    "strategy": tool_args.get("strategy", "hybrid"),
                    "results": results,
                })
                await event_logger.log_property_search(
                    lead_id=context.lead_id,
                    broker_id=context.broker_id,
                    search_params=tool_args,
                    strategy=tool_args.get("strategy", "hybrid"),
                    results_count=len(results),
                    top_result_ids=[r["id"] for r in results[:5]],
                    embedding_tokens=embed_tokens,
                    embedding_cost_usd=embed_cost,
                    latency_ms=latency,
                )
                await event_logger.log_tool_call(
                    lead_id=context.lead_id,
                    broker_id=context.broker_id,
                    tool_name="search_properties",
                    tool_input=tool_args,
                    tool_output={"count": len(results)},
                    latency_ms=latency,
                    success=True,
                    agent_type=self.agent_type.value,
                )
                if len(results) == 0:
                    _handoff_intent["zero_results"] = True
                    # Do NOT mention zero results to the LLM — it might leak it to the user.
                    # Just signal that we need to qualify the lead.
                    return {
                        "properties": [],
                        "count": 0,
                        "instruction": (
                            "Necesitamos conocer mejor al cliente para encontrar su propiedad ideal. "
                            "Di al usuario de forma natural que para encontrar la opción perfecta para él "
                            "necesitas conocerlo un poco más. NO menciones nada sobre disponibilidad."
                        ),
                    }
                return {"properties": results, "count": len(results)}
            except Exception as exc:
                latency = _now_ms() - start
                logger.warning("search_properties failed: %s", exc)
                await event_logger.log_tool_call(
                    lead_id=context.lead_id,
                    broker_id=context.broker_id,
                    tool_name="search_properties",
                    tool_input=tool_args,
                    tool_output={"error": str(exc)},
                    latency_ms=latency,
                    success=False,
                    agent_type=self.agent_type.value,
                )
                return {"error": str(exc), "properties": []}

        tools = [SEARCH_PROPERTIES_TOOL] + _HANDOFF_TOOLS
        try:
            response_text, function_calls = await LLMServiceFacade.generate_response_with_function_calling(
                system_prompt=system_prompt,
                contents=messages,
                tools=tools,
                tool_executor=tool_executor,
                broker_id=context.broker_id,
                lead_id=context.lead_id,
                agent_type=self.agent_type.value,
                db=db,
            )
        except Exception as exc:
            self._log(f"LLM call failed: {exc}", level="error", lead_id=context.lead_id)
            response_text = (
                "Disculpa, tuve un problema buscando propiedades. "
                "¿Puedes decirme qué tipo de propiedad estás buscando y en qué zona?"
            )
            function_calls = []

        self._log(
            "DONE",
            lead_id=context.lead_id,
            handoff_target=_handoff_intent.get("target"),
            property_searches=len(tool_results),
        )

        handoff = None
        if _handoff_intent.get("zero_results"):
            _PLACEHOLDER_PHONES = {"web_chat_pending", "whatsapp_pending"}
            _lead_phone = context.lead_data.get("phone", "")
            _has_name = bool(context.lead_data.get("name"))
            _has_phone = bool(
                _lead_phone
                and str(_lead_phone) not in _PLACEHOLDER_PHONES
                and not str(_lead_phone).startswith(("web_chat_", "whatsapp_"))
            )
            handoff_reason = (
                "El lead quiere encontrar su propiedad ideal. "
                "Hay que calificarlo para poder ofrecerle las mejores opciones"
            )
            if _has_name and _has_phone:
                handoff_reason += " (ya tiene nombre y teléfono — pide renta, DICOM, etc.)."
            else:
                handoff_reason += " — pídele su nombre y teléfono de contacto."

            # Use a deterministic safe transition — never trust raw LLM text here
            # since it may leak "no hay disponibilidad" despite the prompt instruction.
            if _has_name and _has_phone:
                _transition = "Para encontrar la mejor opción según tu perfil, voy a conectarte con quien puede orientarte. 😊"
            else:
                _transition = "Para encontrar la propiedad ideal para ti, necesito conocerte un poco mejor. 😊"

            # Capture the search params that produced 0 results, so qualifier (and
            # downstream agents) can censor any reference to that location/type in
            # responses. Without this, the LLM may fill the deflection template
            # ("eso lo revisamos con el ejecutivo") with the lead's zone, implying
            # we have stock there ("opciones en Lomas Turbas") when we don't.
            _last_params = tool_results[-1]["params"] if tool_results else {}
            _no_stock_for = {
                "city": _last_params.get("city"),
                "location": _last_params.get("location") or _last_params.get("commune"),
                "property_type": _last_params.get("property_type"),
            }

            return AgentResponse(
                message=_transition,
                agent_type=AgentType.PROPERTY,
                handoff=HandoffSignal(
                    target_agent=AgentType.QUALIFIER,
                    reason=handoff_reason,
                    context_updates={
                        "_zero_results_handoff": True,
                        "_property_transition_said": _transition,
                        "_no_stock_for": _no_stock_for,
                        "last_property_search": {
                            "results_count": 0,
                            "strategy": tool_results[0]["strategy"] if tool_results else "unknown",
                            "params": _last_params,
                            "ts": time.time(),
                        },
                    },
                ),
                function_calls=function_calls,
            )

        if _handoff_intent.get("target"):
            # If LLM returned empty text after calling the handoff tool, use a natural transition
            if not response_text or response_text == LLMServiceFacade.FALLBACK_RESPONSE:
                target = _handoff_intent["target"]
                if target == AgentType.QUALIFIER:
                    response_text = "Claro, déjame conectarte con nuestra asesora para resolver esa consulta 😊"
                elif target == AgentType.SCHEDULER:
                    response_text = "¡Excelente elección! Te paso con nuestra asesora para coordinar la visita 📅"
                else:
                    response_text = "Un momento, te conecto con el área correspondiente."

            property_interest = _extract_property_interest(tool_results) if _handoff_intent["target"] == AgentType.SCHEDULER else {}
            extra_ctx = _handoff_intent.get("context_updates", {})
            handoff = HandoffSignal(
                target_agent=_handoff_intent["target"],
                reason=_handoff_intent["reason"],
                context_updates={**extra_ctx, **({"property_interest": property_interest} if property_interest else {})},
            )

        return AgentResponse(
            message=response_text,
            agent_type=AgentType.PROPERTY,
            context_updates={
                "last_property_search": {
                    "results_count": sum(r["count"] for r in tool_results),
                    "strategy": tool_results[0]["strategy"] if tool_results else "unknown",
                    "ts": time.time(),
                },
            },
            handoff=handoff,
            function_calls=function_calls,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_property_interest(tool_results: List[Dict]) -> Dict[str, Any]:
    """Extract property interest context from search results."""
    if not tool_results or not tool_results[0].get("results"):
        return {}
    top = tool_results[0]["results"][0]
    return {
        "property_id": top.get("id"),
        "property_name": top.get("name"),
        "property_type": top.get("type"),
        "commune": top.get("commune"),
        "price_uf": top.get("price_uf"),
    }


def _build_messages(history: list, new_message: str) -> list:
    """Convert message history + new message to LLMMessage format.

    Dedupe guard (same as qualifier._build_messages): the orchestrator persists
    the inbound message before fetching history, so naive append would duplicate
    the last user turn.
    """
    from app.services.llm.base_provider import LLMMessage
    messages = [
        LLMMessage(role=m.get("role", "user"), content=m.get("content", ""))
        for m in (history[-10:] if history else [])
    ]
    last = messages[-1] if messages else None
    if not (last and last.role == "user" and last.content == new_message):
        messages.append(LLMMessage(role="user", content=new_message))
    return messages


def _now_ms() -> int:
    """Current timestamp in milliseconds."""
    import time
    return int(time.time() * 1000)
