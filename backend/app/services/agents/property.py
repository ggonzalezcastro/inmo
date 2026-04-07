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
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.base import BaseAgent
from app.services.agents.types import (
    AgentContext,
    AgentResponse,
    AgentType,
    HandoffSignal,
)
from app.services.properties.search_service import (
    SEARCH_PROPERTIES_TOOL,
    execute_property_search,
)

logger = logging.getLogger(__name__)

# Pipeline stages where this agent is relevant
_ACTIVE_STAGES = {"potencial", "calificacion_financiera", "agendado"}

# Keywords that signal the lead wants to search properties
_SEARCH_KEYWORDS = [
    "propiedad", "propiedades", "departamento", "casa", "terreno",
    "opciones", "disponible", "disponibles", "mostrar", "ver", "buscar",
    "quiero ver", "qué tienen", "qué hay", "cuánto cuesta", "precio",
    "cuántos dormitorios", "con piscina", "con estacionamiento",
    "cerca", "barrio", "comuna", "ubicación",
]


class PropertyAgent(BaseAgent):
    """Specialist agent for property search and recommendations."""

    agent_type = AgentType.PROPERTY
    name = "PropertyAgent"

    def get_system_prompt(self, context: AgentContext) -> str:
        broker_name = context.lead_data.get("broker_name", "nuestra inmobiliaria")
        agent_name = context.lead_data.get("agent_name", "Sofía")
        lead_name = context.lead_data.get("name") or "el cliente"

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

        prompt = f"""Eres {agent_name}, asesora inmobiliaria experta de {broker_name}.

Estás ayudando a {lead_name} a encontrar la propiedad ideal.

## Contexto del cliente
{budget_ctx}
Zona de interés: {location or 'No especificada'}
Estado DICOM: {context.lead_data.get('dicom_status', 'No verificado')}

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
"""
        return self._inject_human_release_note(self._inject_tone_hint(prompt, context), context)

    async def should_handle(self, context: AgentContext) -> bool:
        """
        Handle when:
        1. Lead is in an active property-search stage, OR
        2. Lead explicitly asks about properties (regardless of stage)
        """
        # Already this agent's turn
        if context.current_agent == AgentType.PROPERTY:
            return True

        # Active stage check
        if context.pipeline_stage in _ACTIVE_STAGES:
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
        from app.services.llm.facade import LLMServiceFacade
        from app.services.observability.event_logger import event_logger

        # First check if we should really handle this message
        if not _is_property_intent(message):
            # Not a property search — return to qualifier or let supervisor re-route
            return AgentResponse(
                message="",
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
                rag_chunks_used=[r["id"] for tr in tool_results for r in tr.get("results", [])[:5]],
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
    """Quick check: does the message ask about properties?"""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in _SEARCH_KEYWORDS)


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
