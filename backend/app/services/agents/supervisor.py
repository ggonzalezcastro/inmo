"""
AgentSupervisor — routes messages to the correct specialist agent (TASK-026).

The supervisor is the single entry point for the multi-agent system.
It:
  1. Determines which agent should handle the current message
  2. Calls the agent's ``process()`` method
  3. Applies any context updates returned by the agent
  4. Executes handoffs when the agent signals one
  5. Guards against infinite handoff loops (max 3 hops)

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
from typing import Optional

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
    ) -> AgentResponse:
        """
        Route a lead message to the appropriate agent and return its response.

        Handles up to ``_MAX_HANDOFFS`` consecutive handoffs before returning
        the last response to avoid infinite loops.
        """
        current_context = context
        last_response: Optional[AgentResponse] = None
        hops = 0

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

            logger.info(
                "[Supervisor] Routing to %s (hop=%d, lead=%d)",
                agent.name,
                hops,
                context.lead_id,
            )

            response = await agent.process(message, current_context, db)
            last_response = response

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
            )
            hops += 1

            # After a handoff we do NOT process the same user message again
            # (the new agent generates an intro / confirmation response internally)
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
