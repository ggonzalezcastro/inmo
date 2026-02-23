"""
BaseAgent — abstract base class for all multi-agent specialists (TASK-026).
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.types import (
    AgentContext,
    AgentResponse,
    AgentType,
    HandoffSignal,
)

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Contract that every specialist agent must implement.

    Subclasses must define:
    - ``agent_type``: the ``AgentType`` enum value
    - ``name``: human-readable name for logging
    - ``get_system_prompt()``: returns the agent-specific LLM system prompt
    - ``should_handle()``: returns True if this agent is the right handler
    - ``process()``: core conversation logic

    The ``should_handoff()`` method is **optional** — override when the agent
    needs to pass control to another agent mid-conversation.
    """

    agent_type: AgentType
    name: str

    @abstractmethod
    def get_system_prompt(self, context: AgentContext) -> str:
        """
        Return the full system prompt for this agent, personalised to the lead context.

        The returned string is the *static* broker-level part suitable for
        Gemini Context Caching.  Dynamic lead-level context is injected by the
        LLM facade separately.
        """

    @abstractmethod
    async def should_handle(self, context: AgentContext) -> bool:
        """Return True if this agent is appropriate for the current context."""

    @abstractmethod
    async def process(
        self,
        message: str,
        context: AgentContext,
        db: AsyncSession,
    ) -> AgentResponse:
        """
        Process an incoming lead message and return an agent response.

        This method MUST NOT raise exceptions for normal business logic errors —
        it should return an ``AgentResponse`` with a graceful message instead.
        """

    async def should_handoff(
        self,
        response: AgentResponse,
        context: AgentContext,
    ) -> Optional[HandoffSignal]:
        """
        Called after ``process()`` to determine if a handoff is needed.

        Default implementation: returns ``response.handoff`` as-is.
        Override to add custom handoff logic.
        """
        return response.handoff

    def _log(self, msg: str, level: str = "info", **kwargs) -> None:
        """Structured logging helper."""
        extra = {"agent": self.name, "agent_type": self.agent_type.value, **kwargs}
        getattr(logger, level)(f"[{self.name}] {msg}", extra=extra)


# ── Registry ──────────────────────────────────────────────────────────────────

_AGENT_REGISTRY: Dict[AgentType, BaseAgent] = {}


def register_agent(agent: BaseAgent) -> None:
    """Register an agent instance in the global registry."""
    _AGENT_REGISTRY[agent.agent_type] = agent


def get_agent(agent_type: AgentType) -> Optional[BaseAgent]:
    """Retrieve a registered agent by type."""
    return _AGENT_REGISTRY.get(agent_type)


def get_all_agents() -> List[BaseAgent]:
    """Return all registered agent instances."""
    return list(_AGENT_REGISTRY.values())
