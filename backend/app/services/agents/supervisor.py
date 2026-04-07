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
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.base import BaseAgent, get_all_agents
from app.services.agents.types import (
    AgentContext,
    AgentResponse,
    AgentType,
    HandoffSignal,
)

logger = logging.getLogger(__name__)

_MAX_HANDOFFS = 3  # safety guard against routing loops


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

        current_context = context
        last_response: Optional[AgentResponse] = None
        hops = 0
        visited_agents: List[str] = []

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

            # Apply handoff context updates
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
                property_preferences=current_context.property_preferences,
                human_release_note=current_context.human_release_note,
                last_agent_note=current_context.last_agent_note,
                current_frustration=current_context.current_frustration,
                tone_hint=current_context.tone_hint,
            )
            hops += 1

            # After a handoff, update agent_type to the target so the orchestrator
            # persists the correct current_agent for the next message routing.
            last_response = AgentResponse(
                message=last_response.message,
                agent_type=handoff.target_agent,
                context_updates=last_response.context_updates,
                handoff=None,
                function_calls=last_response.function_calls,
            )
            # Do NOT process the same user message with the new agent —
            # the new agent starts on the next inbound message.
            break

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
        Select the most appropriate agent for the given context.

        Priority:
        1. If a current_agent is set, check if it still claims ownership
        2. Otherwise, poll all registered agents (in priority order)
        """
        from app.services.agents import get_priority_agents

        agents = get_priority_agents()

        # Current agent gets first pick (sticky routing)
        if context.current_agent:
            for agent in agents:
                if agent.agent_type == context.current_agent:
                    if await agent.should_handle(context):
                        return agent
                    break  # current agent released control — re-select

        # Poll all agents in priority order
        for agent in agents:
            if await agent.should_handle(context):
                return agent

        return None


def _get_qualifier() -> BaseAgent:
    """Return the QualifierAgent instance (fallback)."""
    from app.services.agents import qualifier_agent_instance
    return qualifier_agent_instance
