"""
AgentSupervisor — routes messages to the correct specialist agent (TASK-026).

The supervisor is the single entry point for the multi-agent system.
It:
  1. Determines which agent should handle the current message
  2. Calls the agent's ``process()`` method
  3. Applies any context updates returned by the agent
  4. Executes handoffs when the agent signals one
  5. Guards against infinite handoff loops (max 3 hops)
  6. Logs all routing decisions and handoffs to AgentEventLogger

Usage
-----
    from app.services.agents.supervisor import AgentSupervisor

    result = await AgentSupervisor.process(
        message="Hola, me interesa un depto",
        context=AgentContext(...),
        db=session,
    )
"""
from __future__ import annotations

import logging
from datetime import datetime as _dt, timezone as _tz
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.base import BaseAgent, get_agent, get_all_agents
from app.services.agents.types import (
    AgentContext,
    AgentResponse,
    AgentType,
    HandoffSignal,
)

logger = logging.getLogger(__name__)

_MAX_HANDOFFS = 3  # safety guard against routing loops

# Deterministic stage → agent mapping.
# Agents exit their own stage via handoff tool calls; the supervisor uses this
# table only for initial routing (first message) and when no current_agent is set.
_STAGE_TO_AGENT: Dict[str, AgentType] = {
    "entrada": AgentType.QUALIFIER,
    "perfilamiento": AgentType.QUALIFIER,
    "potencial": AgentType.PROPERTY,
    "calificacion_financiera": AgentType.SCHEDULER,
    "agendado": AgentType.FOLLOW_UP,
    "seguimiento": AgentType.FOLLOW_UP,
    "referidos": AgentType.FOLLOW_UP,
    "ganado": AgentType.FOLLOW_UP,
    "perdido": AgentType.FOLLOW_UP,
}


class AgentSupervisor:
    """
    Stateless supervisor that routes incoming messages to specialist agents.

    All methods are class methods so no instantiation is needed.
    """

    @classmethod
    async def process(
        cls,
        message: str,
        context: AgentContext,
        db: AsyncSession,
        message_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
    ) -> AgentResponse:
        """
        Route a lead message to the appropriate agent and return its response.

        Handles up to ``_MAX_HANDOFFS`` consecutive handoffs before returning
        the last response to avoid infinite loops.
        """
        from app.services.observability.event_logger import event_logger
        from app.services.agents.model_config import load_all_agent_configs

        current_context = context
        last_response: Optional[AgentResponse] = None
        hops = 0
        visited_agents: List[str] = []

        # Inject the current message so agents can inspect it inside should_handle()
        import dataclasses
        current_context = dataclasses.replace(current_context, current_message=message)

        # Warm up Redis cache with all agent model configs for this broker so
        # subsequent per-agent provider lookups hit the cache, not the DB.
        try:
            await load_all_agent_configs(context.broker_id, db)
        except Exception as _cache_exc:
            logger.debug("[Supervisor] Agent model config warm-up failed: %s", _cache_exc)

        logger.info(
            "[Supervisor] START lead_id=%s broker_id=%s stage=%s state=%s",
            context.lead_id, context.broker_id,
            context.pipeline_stage, context.conversation_state,
        )

        while hops < _MAX_HANDOFFS:
            agent = await cls._select_agent(current_context)
            if agent is None:
                logger.warning(
                    "No agent selected for lead %s (stage=%s, state=%s) — "
                    "falling back to QualifierAgent",
                    context.lead_id,
                    current_context.pipeline_stage,
                    current_context.conversation_state,
                )
                agent = _get_qualifier()

            # ── Loop detection ──────────────────────────────────────────────
            if agent.agent_type.value in visited_agents:
                await event_logger.log_error(
                    lead_id=context.lead_id,
                    broker_id=context.broker_id,
                    error_type="handoff_loop",
                    error_message=(
                        f"Handoff loop detected: "
                        f"{' → '.join(visited_agents)} → {agent.agent_type.value}"
                    ),
                    agent_type="supervisor",
                    message_id=message_id,
                    conversation_id=conversation_id,
                )
                logger.warning(
                    "[Supervisor] Handoff loop detected: %s → %s (stopping)",
                    " → ".join(visited_agents),
                    agent.agent_type.value,
                )
                break

            logger.info(
                "[Supervisor] Routing to %s (hop=%d, lead=%d)",
                agent.name,
                hops,
                context.lead_id,
            )

            visited_agents.append(agent.agent_type.value)

            # ── Log agent selection ─────────────────────────────────────────
            await event_logger.log_agent_selected(
                lead_id=context.lead_id,
                broker_id=context.broker_id,
                agent_type=agent.agent_type.value,
                reason=f"hop {hops + 1}, visited: {visited_agents[:-1] or 'none'}",
                message_id=message_id,
                conversation_id=conversation_id,
            )

            logger.info("[Supervisor] Calling agent.process: %s", agent.name)
            response = await agent.process(message, current_context, db)
            last_response = response
            logger.info(
                "[Supervisor] agent.process done: %s — response=%r",
                agent.name, (response.message or "")[:80],
            )

            # Apply context updates
            updated_data = {**current_context.lead_data, **response.context_updates}
            current_context = AgentContext(
                lead_id=current_context.lead_id,
                broker_id=current_context.broker_id,
                pipeline_stage=current_context.pipeline_stage,
                conversation_state=current_context.conversation_state,
                lead_data=updated_data,
                message_history=current_context.message_history,
                current_agent=agent.agent_type,
                handoff_count=hops,
                property_preferences=current_context.property_preferences,
                human_release_note=current_context.human_release_note,
                last_agent_note=response.metadata.get("agent_note") if response.metadata else current_context.last_agent_note,
                current_frustration=current_context.current_frustration,
                tone_hint=current_context.tone_hint,
            )

            # Check for handoff
            handoff: Optional[HandoffSignal] = await agent.should_handoff(response, current_context)
            if handoff is None:
                break  # No handoff — we're done

            logger.info(
                "[Supervisor] Handoff from %s → %s: %s",
                agent.name,
                handoff.target_agent.value,
                handoff.reason,
            )

            # ── Log handoff ─────────────────────────────────────────────────
            await event_logger.log_handoff(
                lead_id=context.lead_id,
                broker_id=context.broker_id,
                from_agent=agent.agent_type.value,
                to_agent=handoff.target_agent.value,
                reason=handoff.reason,
                message_id=message_id,
                conversation_id=conversation_id,
            )

            # Apply handoff context updates — persist handoff metadata for the target agent
            handoff.context_updates.setdefault("_handoff_reason", handoff.reason)
            handoff.context_updates.setdefault("_handoff_from", agent.agent_type.value)
            handoff.context_updates.setdefault("_handoff_at", _dt.now(_tz.utc).isoformat())
            handoff_data = {**updated_data, **handoff.context_updates}
            current_context = AgentContext(
                lead_id=current_context.lead_id,
                broker_id=current_context.broker_id,
                pipeline_stage=current_context.pipeline_stage,
                conversation_state=current_context.conversation_state,
                lead_data=handoff_data,
                message_history=current_context.message_history,
                current_agent=handoff.target_agent,
                handoff_count=hops + 1,
                pre_analysis=current_context.pre_analysis,  # preserve so target agent has intent/fields
                property_preferences=current_context.property_preferences,
                human_release_note=current_context.human_release_note,
                last_agent_note=current_context.last_agent_note,
                current_frustration=current_context.current_frustration,
                tone_hint=current_context.tone_hint,
            )
            hops += 1

            # Continue the loop so the target agent processes the same message
            # immediately — the user gets the real response (e.g. property listings)
            # instead of just a transition sentence.

        if last_response is None:
            # Should never happen, but be defensive
            last_response = AgentResponse(
                message="Disculpa, no pude procesar tu mensaje. Por favor intenta nuevamente.",
                agent_type=AgentType.SUPERVISOR,
            )

        return last_response

    @classmethod
    async def _select_agent(cls, context: AgentContext) -> Optional[BaseAgent]:
        """
        Select the appropriate agent for the given context.

        Sticky: if a current_agent is already set (e.g. after a handoff),
        keep it — agents exit their own stage via handoff tool calls.

        Deterministic stage lookup: map pipeline_stage → agent type via
        _STAGE_TO_AGENT.  Falls back to QualifierAgent for unknown stages.
        """
        # Sticky: if already in an agent, keep it (agent exits via handoff tool)
        if context.current_agent is not None:
            agent = get_agent(context.current_agent)
            if agent:
                return agent

        # Use intent from pre_analysis (set by orchestrator) for direct routing —
        # avoids an unnecessary hop when the lead's intent is clear.
        intent = (context.pre_analysis or {}).get("intent", "general_chat")
        logger.info(
            "[Supervisor] Intent=%s stage=%s (lead=%s)",
            intent, context.pipeline_stage, context.lead_id,
        )
        if intent == "property_search":
            prop_agent = get_agent(AgentType.PROPERTY)
            if prop_agent:
                return prop_agent
        elif intent == "schedule_visit":
            sched_agent = get_agent(AgentType.SCHEDULER)
            if sched_agent:
                return sched_agent
        elif intent == "financing_question":
            # Financing questions go directly to Qualifier regardless of stage
            return _get_qualifier()

        # Deterministic stage lookup
        target_type = _STAGE_TO_AGENT.get(context.pipeline_stage, AgentType.QUALIFIER)
        return get_agent(target_type) or _get_qualifier()


def _get_qualifier() -> BaseAgent:
    """Return the QualifierAgent instance (fallback)."""
    from app.services.agents import qualifier_agent_instance
    return qualifier_agent_instance
