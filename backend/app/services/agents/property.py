"""
PropertyAgent — hybrid property search + recommendations (TASK-X).

Activated when:
  - Pipeline stage is 'potencial' or 'calificacion_financiera'
  - The lead is asking about available properties or wants to see options

Uses function calling (SEARCH_PROPERTIES_TOOL) so the LLM extracts
structured search parameters from the lead's natural language, then
this agent executes the hybrid SQL + vector search with RRF merge.

Can hand off to SchedulerAgent when the lead wants to book a visit.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.base import BaseAgent
from app.services.agents.types import (
    AgentContext,
    AgentResponse,
    AgentType,
    HandoffSignal,
)
from app.services.llm.facade import LLMServiceFacade
from app.services.properties.search_service import (
    SEARCH_PROPERTIES_TOOL,
    execute_property_search,
)

logger = logging.getLogger(__name__)

# Pipeline stages where this agent is relevant
_ACTIVE_STAGES = {"potencial", "calificacion_financiera", "agendado"}

# Single-word keywords — matched with word boundaries to avoid false positives.
# ("ver" was matching "verdad"/"conversar", "cerca" matching "acerca", etc.)
_WORD_KEYWORDS = [
    "propiedad", "propiedades", "departamento", "departamentos",
    "casa", "casas", "terreno", "terrenos",
    "opciones", "disponible", "disponibles", "mostrar", "buscar",
    "precio", "dormitorios", "piscina", "estacionamiento",
    "barrio", "comuna", "ubicacion", "ubicación",
]

# Multi-word phrases — safe as substring matches
_PHRASE_KEYWORDS = [
    "quiero ver", "qué tienen", "que tienen", "qué hay", "que hay",
    "cuánto cuesta", "cuanto cuesta", "ver en persona", "mostrar opciones",
    "cerca de", "con piscina", "con estacionamiento",
]

# Pre-compiled regex for word-boundary matching (handles accented chars via case-fold)
_WORD_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(kw) for kw in _WORD_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


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

        prompt = f"""Eres {agent_name}, asesora inmobiliaria experta de {broker_name}.

Estás ayudando a {lead_name} a encontrar la propiedad ideal.

## Contexto del cliente
{budget_ctx}
Zona de interés: {location or 'No especificada'}
Estado DICOM: {context.lead_data.get('dicom_status', 'No verificado')}

## Preferencias de propiedad registradas
{prefs_ctx}

## Tu rol
- Busca propiedades disponibles usando la herramienta `search_properties`
- Presenta los resultados de forma clara, destacando lo más relevante para el cliente
- Cuando el cliente muestre interés concreto en una propiedad, ofrece agendar una visita
- Si el cliente quiere agendar una visita a una propiedad específica, usa esa información para facilitar el handoff al agente de scheduling

## Cómo usar la herramienta de búsqueda
1. Extrae los parámetros del mensaje del cliente (dormitorios, precio, zona, preferencias)
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
- Invitación a agendar visita si muestra interés

## Tono
Entusiasta pero profesional. Ayuda al cliente a imaginar vivir en las propiedades.

## Datos del cliente pendientes de capturar
{"- IMPORTANTE: No conoces el nombre del cliente. Al presentar las propiedades, termina tu mensaje con una pregunta natural pidiendo su nombre. Ejemplo: '¿Por cierto, cómo te llamas para atenderte mejor?'" if not name_known else ""}
{"- No tienes el teléfono del cliente aún. Cuando el cliente muestre interés concreto, pide el teléfono y email." if not context.lead_data.get("phone") else ""}
"""
        return self._inject_human_release_note(self._inject_tone_hint(prompt, context), context)

    async def should_handle(self, context: AgentContext) -> bool:
        """
        Handle when:
        1. Already this agent's turn (sticky routing), OR
        2. Lead is in an active property-search stage, OR
        3. Lead's message contains property-search keywords (any stage)
        """
        # Already this agent's turn
        if context.current_agent == AgentType.PROPERTY:
            return True

        # Active stage check
        if context.pipeline_stage in _ACTIVE_STAGES:
            return True

        # Keyword intent check — trigger from any stage including 'entrada'
        if context.current_message and _is_property_intent(context.current_message):
            return True

        return False

    async def process(
        self,
        message: str,
        context: AgentContext,
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Process a property search request.

        1. Check if this message is actually about properties
        2. Use LLM function calling to extract search parameters
        3. Execute hybrid search
        4. Format and return results
        """
        from app.services.observability.event_logger import event_logger

        # First check if we should really handle this message
        if not _is_property_intent(message):
            # Not a property search — generate a brief conversational response
            # and hand off to Qualifier so the lead isn't left with a blank reply.
            try:
                passthrough_prompt = self.get_system_prompt(context)
                response_text, _ = await LLMServiceFacade.generate_response_with_function_calling(
                    system_prompt=passthrough_prompt,
                    contents=_build_history(context),
                    tools=[],
                    broker_id=context.broker_id,
                    lead_id=context.lead_id,
                    agent_type=self.agent_type.value,
                )
            except Exception as exc:
                logger.warning("PropertyAgent passthrough LLM failed: %s", exc)
                response_text = "Entendido. ¿Hay algo más en lo que pueda ayudarte?"
            return AgentResponse(
                message=response_text,
                agent_type=AgentType.PROPERTY,
                handoff=HandoffSignal(
                    target_agent=AgentType.QUALIFIER,
                    reason="Message not related to property search",
                ),
            )

        system_prompt = self.get_system_prompt(context)

        # Build message history for LLM
        history = _build_history(context)

        tool_results: List[Dict[str, Any]] = []

        async def tool_executor(tool_name: str, tool_args: Dict) -> Any:
            """Execute the search_properties tool and log the result."""
            if tool_name != "search_properties":
                return {"error": f"Unknown tool: {tool_name}"}

            start = _now_ms()
            try:
                results = await execute_property_search(tool_args, db, context.broker_id)
                latency = _now_ms() - start
                tool_results.append({
                    "params": tool_args,
                    "count": len(results),
                    "strategy": tool_args.get("strategy", "hybrid"),
                    "results": results,
                })
                # Log property search event
                await event_logger.log_property_search(
                    lead_id=context.lead_id,
                    broker_id=context.broker_id,
                    search_params=tool_args,
                    strategy=tool_args.get("strategy", "hybrid"),
                    results_count=len(results),
                    top_result_ids=[r["id"] for r in results[:5]],
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

        try:
            response_text, function_calls = await LLMServiceFacade.generate_response_with_function_calling(
                system_prompt=system_prompt,
                contents=history,
                tools=[SEARCH_PROPERTIES_TOOL],
                tool_executor=tool_executor,
                broker_id=context.broker_id,
                lead_id=context.lead_id,
                agent_type=self.agent_type.value,
            )
        except Exception as exc:
            logger.error("PropertyAgent LLM call failed: %s", exc)
            response_text = (
                "Disculpa, tuve un problema buscando propiedades. "
                "¿Puedes decirme qué tipo de propiedad estás buscando y en qué zona?"
            )
            function_calls = []

        # Check if lead wants to schedule a visit
        handoff = None
        if _wants_to_schedule(message, response_text):
            property_interest = _extract_property_interest(tool_results)
            handoff = HandoffSignal(
                target_agent=AgentType.SCHEDULER,
                reason="Lead wants to visit a specific property",
                context_updates={"property_interest": property_interest},
            )

        return AgentResponse(
            message=response_text,
            agent_type=AgentType.PROPERTY,
            context_updates={
                "last_property_search": {
                    "results_count": sum(r["count"] for r in tool_results),
                    "strategy": tool_results[0]["strategy"] if tool_results else "unknown",
                },
            },
            handoff=handoff,
            function_calls=function_calls,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_property_intent(message: str) -> bool:
    """Check if message relates to property search using word-boundary matching."""
    if _WORD_PATTERN.search(message):
        return True
    msg_lower = message.lower()
    return any(phrase in msg_lower for phrase in _PHRASE_KEYWORDS)


def _wants_to_schedule(message: str, response: str) -> bool:
    """Detect if lead wants to schedule a visit after seeing property results."""
    schedule_keywords = [
        "agendar", "visita", "ver en persona", "quiero ir",
        "me interesa", "cuándo puedo", "coordinar", "visitar",
    ]
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in schedule_keywords)


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


def _build_history(context: AgentContext) -> List[Dict]:
    """Build LLM message history from recent messages (max 10)."""
    return context.message_history[-10:] if context.message_history else []


def _now_ms() -> int:
    """Current timestamp in milliseconds."""
    import time
    return int(time.time() * 1000)
